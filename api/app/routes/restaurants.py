"""GET /api/restaurants/{slug} — full breakdown for one restaurant.

Reads the latest scores row. Pillars include cached themes and 2-3 short
representative quotes pulled from sentences with high absolute sentiment;
quotes are dropped if their source review's body has been purged under the
Google 30-day retention rule.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import Restaurant, Review, Score, Sentence
from app.schemas import (
    DateRange,
    PillarDetail,
    Quote,
    RestaurantDetail,
    Sources,
)

router = APIRouter(prefix="/api/restaurants", tags=["restaurants"])

PILLARS = ("quality", "service", "ambiance")
QUOTE_MAX_CHARS = 100
QUOTES_PER_PILLAR = 3


def _load_pillar_quotes(
    session: Session, restaurant_id: int, pillar: str, classifier_version: str
) -> list[Quote]:
    rows = session.execute(
        select(Sentence.text, Sentence.sentiment, Review.source, Review.source_url)
        .join(Review, Review.id == Sentence.review_id)
        .where(
            Review.restaurant_id == restaurant_id,
            Review.body.is_not(None),  # drop quotes where source body was purged
            Sentence.pillar == pillar,
            Sentence.classifier_version == classifier_version,
            func.length(Sentence.text) <= QUOTE_MAX_CHARS,
        )
        .order_by(func.abs(Sentence.sentiment).desc())
        .limit(QUOTES_PER_PILLAR)
    ).all()
    return [Quote(text=text, source=source, url=source_url) for text, _, source, source_url in rows]


@router.get("/{slug}", response_model=RestaurantDetail)
def get_restaurant(
    slug: str, session: Session = Depends(get_session)
) -> RestaurantDetail:
    restaurant = session.scalar(
        select(Restaurant).where(
            Restaurant.slug == slug, Restaurant.active.is_(True)
        )
    )
    if restaurant is None:
        raise HTTPException(status_code=404, detail=f"restaurant not found: {slug!r}")

    score = session.scalar(
        select(Score)
        .where(Score.restaurant_id == restaurant.id)
        .order_by(Score.computed_at.desc())
        .limit(1)
    )
    if score is None:
        raise HTTPException(
            status_code=404, detail=f"no scores yet for restaurant {slug!r}"
        )

    pillars: dict[str, PillarDetail] = {}
    for pillar in PILLARS:
        quotes = _load_pillar_quotes(
            session, restaurant.id, pillar, settings.classifier_version
        )
        pillars[pillar] = PillarDetail(
            score=getattr(score, f"{pillar}_score"),
            n_sentences=getattr(score, f"{pillar}_n_sentences") or 0,
            themes_pos=getattr(score, f"{pillar}_themes_pos") or [],
            themes_neg=getattr(score, f"{pillar}_themes_neg") or [],
            quotes=quotes,
        )

    date_range: DateRange | None = None
    if score.date_range_start and score.date_range_end:
        date_range = DateRange(start=score.date_range_start, end=score.date_range_end)

    sources = Sources(
        google_reviews=score.google_review_count_used or 0,
        reddit_mentions=score.reddit_mention_count_used or 0,
        date_range=date_range,
    )

    return RestaurantDetail(
        slug=restaurant.slug,
        name=restaurant.name,
        neighborhood=restaurant.neighborhood,
        address=restaurant.address,
        lat=restaurant.lat,
        lng=restaurant.lng,
        price_tier=restaurant.price_tier,
        google_rating=restaurant.google_rating,
        google_review_count=restaurant.google_review_count,
        website=restaurant.website,
        prime_score=score.prime_score,
        quality_score=score.quality_score,
        service_score=score.service_score,
        ambiance_score=score.ambiance_score,
        house_take=score.house_take,
        confidence_factor=score.confidence_factor,
        computed_at=score.computed_at,
        pillars=pillars,
        sources=sources,
    )
