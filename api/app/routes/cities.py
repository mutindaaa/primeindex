"""GET /api/cities/{city_slug} — ranked restaurant list for a city.

Always reads the latest scores row per restaurant (by computed_at). The pillar
scores returned are the canonical, stored values (computed at scoring time
under the default 0.4/0.3/0.3 weights). The `prime_score` field is recomputed
live using the user-supplied weights so the client can render new orderings
without re-querying the DB.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Restaurant, Score
from app.schemas import CityResponse, CityRestaurantSummary, Weights

router = APIRouter(prefix="/api/cities", tags=["cities"])

WEIGHTS_TOLERANCE = 0.001


def _validate_weights(q: float, s: float, a: float) -> None:
    total = q + s + a
    if abs(total - 1.0) > WEIGHTS_TOLERANCE:
        raise HTTPException(
            status_code=400,
            detail=f"weights must sum to 1.0 (got {total:.3f})",
        )


def _weighted_prime(
    q: float | None, s: float | None, a: float | None,
    qw: float, sw: float, aw: float,
) -> float | None:
    """Strict: any pillar None -> None (matches scorer.py behavior)."""
    if q is None or s is None or a is None:
        return None
    return round(qw * q + sw * s + aw * a, 1)


@router.get("/{city_slug}", response_model=CityResponse)
def get_city(
    city_slug: str,
    quality_weight: float = Query(0.4, ge=0.0, le=1.0),
    service_weight: float = Query(0.3, ge=0.0, le=1.0),
    ambiance_weight: float = Query(0.3, ge=0.0, le=1.0),
    session: Session = Depends(get_session),
) -> CityResponse:
    _validate_weights(quality_weight, service_weight, ambiance_weight)

    latest_score_subq = (
        select(Score.restaurant_id, func.max(Score.computed_at).label("max_ts"))
        .group_by(Score.restaurant_id)
        .subquery()
    )

    rows = session.execute(
        select(Restaurant, Score)
        .join(Score, Score.restaurant_id == Restaurant.id)
        .join(
            latest_score_subq,
            (latest_score_subq.c.restaurant_id == Score.restaurant_id)
            & (latest_score_subq.c.max_ts == Score.computed_at),
        )
        .where(
            Restaurant.city == city_slug.lower(),
            Restaurant.active.is_(True),
        )
    ).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"city not found: {city_slug!r}")

    summaries: list[CityRestaurantSummary] = []
    latest_computed_at = None

    for restaurant, score in rows:
        prime = _weighted_prime(
            score.quality_score, score.service_score, score.ambiance_score,
            quality_weight, service_weight, ambiance_weight,
        )
        summaries.append(
            CityRestaurantSummary(
                slug=restaurant.slug,
                name=restaurant.name,
                neighborhood=restaurant.neighborhood,
                price_tier=restaurant.price_tier,
                prime_score=prime,
                quality_score=score.quality_score,
                service_score=score.service_score,
                ambiance_score=score.ambiance_score,
                quality_n_sentences=score.quality_n_sentences,
                service_n_sentences=score.service_n_sentences,
                ambiance_n_sentences=score.ambiance_n_sentences,
                google_review_count=score.google_review_count,
                google_review_count_used=score.google_review_count_used,
                house_take=score.house_take,
                confidence_factor=score.confidence_factor,
            )
        )
        if latest_computed_at is None or score.computed_at > latest_computed_at:
            latest_computed_at = score.computed_at

    # Ranked first (prime not None) DESC by prime; unranked at the bottom alphabetically.
    summaries.sort(key=lambda r: (r.prime_score is None, -(r.prime_score or 0.0), r.name))

    return CityResponse(
        city=city_slug.lower(),
        weights=Weights(
            quality=quality_weight, service=service_weight, ambiance=ambiance_weight
        ),
        computed_at=latest_computed_at,
        restaurants=summaries,
    )
