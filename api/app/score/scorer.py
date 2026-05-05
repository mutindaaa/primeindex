"""Pillar + Prime Score computation, with Bayesian shrinkage and Claude-generated
house_take + per-pillar themes. Per-restaurant scoring is one append row in `scores`.

Pipeline per restaurant (per spec §7 + project decisions):
  1. Load all classified sentences (joined with reviews to get posted_at + source).
  2. Skip the restaurant entirely if Google reviews used < MIN_REVIEWS_PER_RESTAURANT.
  3. For each pillar (quality/service/ambiance):
       - Compute the time-decay-weighted mean sentiment, mapped from [-1,1] to [0,100].
         This is the RAW pillar score, stored as raw_*_score regardless of n.
       - If n_sentences < MIN_SENTENCES_PER_PILLAR -> final pillar score = None (UI shows '—').
       - Else apply Bayesian shrinkage toward the corpus pillar mean with prior
         weight K = SHRINKAGE_PRIOR_K. This pulls extreme small-N scores toward
         the corpus average, addressing the "5 enthusiastic Google reviews
         outranking a 3,945-review establishment" problem.
  4. Apply price-tier penalty to the SHRUNK quality score (so the penalty
     isn't double-amplified by an extreme raw value).
  5. Composite Prime Score = 0.4*Q + 0.3*S + 0.3*A. Strict: any pillar None -> Prime None.
  6. Resolve house_take + per-pillar themes:
       - If the prior score row's summary is < SUMMARY_CACHE_DAYS old, copy it.
       - Else call Claude once and store fresh.
  7. Snapshot google_review_count (total ratings, from restaurants table).
  8. Append a new `scores` row.

When Reddit ingest ships in v1.1, flip these two threshold constants back to
spec §7 values:
    MIN_REVIEWS_PER_RESTAURANT: 5 -> 20
    MIN_SENTENCES_PER_PILLAR:   2 -> 5
That's the entire scoring change required. Shrinkage and summarization remain.

CLI:
    python -m app.score.scorer --slug bavettes-bar-boeuf
    python -m app.score.scorer --all
"""

from __future__ import annotations

import argparse
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from anthropic import Anthropic
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.classify.claude_client import _client
from app.config import settings
from app.db import SessionLocal
from app.logging_setup import get_logger
from app.models import Restaurant, Review, Score, Sentence

log = get_logger(__name__)

PILLARS = ("quality", "service", "ambiance")
RECENCY_DECAY_DAYS = 365

# When Reddit ingest ships in v1.1, flip these two constants back to spec §7 values:
#   MIN_REVIEWS_PER_RESTAURANT: 5 -> 20
#   MIN_SENTENCES_PER_PILLAR:   2 -> 5
# That's the entire scoring change required.
MIN_REVIEWS_PER_RESTAURANT = 5  # MVP relaxed (spec §7: 20). Forced by Google's 5-reviews-per-call cap.
MIN_SENTENCES_PER_PILLAR = 2    # MVP relaxed (spec §7: 5). Forced by lower sentence volume w/o Reddit.

# Volume-aware Bayesian shrinkage. The shrinkage K (prior weight) varies per
# restaurant based on its total Google review count, since Google's API caps us
# at 5 reviews per restaurant — both a 76-rating place and a 6,747-rating place
# yield ~5 reviews → similar n_sentences. We need a separate confidence signal.
#
#   confidence_factor = log10(google_review_count + 10) / log10(corpus_max + 10)
#                       in [0, 1] — saturates at the most-reviewed restaurant
#   effective_K       = K_HIGH * (1 - cf) + K_LOW * cf
#                       low-volume -> K_HIGH (heavy shrinkage toward corpus mean)
#                       high-volume -> K_LOW (light shrinkage; trust the local signal)
#
# K=10 (the previous flat value) sat between these. Splitting them lets a place
# with 76 ratings get pulled hard toward the mean while Bavette's (3,945) barely
# moves from its raw signal.
SHRINKAGE_K_HIGH = 12   # applied at minimum volume (confidence_factor -> 0)
SHRINKAGE_K_LOW = 2     # applied at corpus max volume (confidence_factor -> 1)

# Price-tier penalty applied to the (shrunk) quality score. Original spec §7
# values {3: -2, 4: -5} proved too punitive against the 5-review-per-place sample
# Google gives us — a single critical review on a $$$$ place could push it
# multiple ranks down on the basis of one sentence. Per spec §7's invitation
# to iterate after launch ("conservative ... we can iterate after launch"),
# this MVP softens the penalty by ~50%. Revisit when Reddit volume widens
# the per-pillar sentence count.
PRICE_PENALTY = {1: 0, 2: 0, 3: -1, 4: -3}

# House_take + themes: regenerate at most every SUMMARY_CACHE_DAYS days per restaurant.
SUMMARY_CACHE_DAYS = 7
SUMMARIZE_TOP_N_PER_DIRECTION = 5   # 5 most positive + 5 most negative per pillar -> Claude


@dataclass
class _SentenceRow:
    pillar: str
    sentiment: float
    text: str
    posted_at: datetime
    review_id: int
    source: str


@dataclass
class _PillarOutcome:
    raw_score: float | None     # 0-100, before shrinkage and penalty
    final_score: float | None   # 0-100, after shrinkage + (for quality) price penalty
    n_sentences: int


@dataclass
class _ShrinkageParams:
    effective_k: float
    confidence_factor: float


@dataclass
class _Summary:
    house_take: str | None = None
    themes: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    generated_at: datetime | None = None


@dataclass
class ScoreResult:
    name: str
    skipped: bool = False
    skip_reason: str | None = None
    quality: float | None = None
    service: float | None = None
    ambiance: float | None = None
    prime: float | None = None
    raw_quality: float | None = None
    raw_service: float | None = None
    raw_ambiance: float | None = None
    n_by_pillar: dict[str, int] = field(default_factory=dict)
    google_reviews_used: int = 0
    google_review_count: int | None = None
    effective_k: float | None = None
    confidence_factor: float | None = None
    date_range: tuple[date, date] | None = None
    summary_cached: bool = False


# ---------------------------------------------------------------------------
# Pillar scoring core
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _load_sentence_rows(
    session: Session, restaurant_id: int, classifier_version: str
) -> list[_SentenceRow]:
    rows = session.execute(
        select(
            Sentence.pillar,
            Sentence.sentiment,
            Sentence.text,
            Review.posted_at,
            Review.id,
            Review.source,
        )
        .join(Review, Review.id == Sentence.review_id)
        .where(
            Review.restaurant_id == restaurant_id,
            Sentence.classifier_version == classifier_version,
            Review.posted_at.is_not(None),
        )
    ).all()
    return [_SentenceRow(*r) for r in rows]


def _compute_corpus_pillar_means(session: Session, classifier_version: str) -> dict[str, float]:
    """Per-pillar mean sentiment across the entire corpus, mapped to [0, 100]."""
    out: dict[str, float] = {}
    for pillar in PILLARS:
        avg = session.scalar(
            select(func.avg(Sentence.sentiment)).where(
                Sentence.pillar == pillar,
                Sentence.classifier_version == classifier_version,
            )
        )
        out[pillar] = round((float(avg) + 1.0) * 50.0, 2) if avg is not None else 50.0
    return out


def _raw_pillar_score(rows: list[_SentenceRow], *, now: datetime) -> float | None:
    """Time-decay-weighted mean sentiment in [-1, 1] mapped to [0, 100]. None if empty."""
    if not rows:
        return None
    weighted_sum = 0.0
    weight_sum = 0.0
    for r in rows:
        posted = r.posted_at if r.posted_at.tzinfo else r.posted_at.replace(tzinfo=timezone.utc)
        age_days = max((now - posted).days, 0)
        w = math.exp(-age_days / RECENCY_DECAY_DAYS)
        weighted_sum += w * r.sentiment
        weight_sum += w
    if weight_sum == 0.0:
        return None
    weighted_mean = weighted_sum / weight_sum
    return round((weighted_mean + 1.0) * 50.0, 1)


def _apply_shrinkage(raw: float | None, n: int, corpus_mean: float, k: float) -> float | None:
    if raw is None:
        return None
    return round((n * raw + k * corpus_mean) / (n + k), 1)


def _compute_corpus_max_review_count(session: Session) -> int:
    """Largest google_review_count among active restaurants. Floor at 1 to avoid log(0)."""
    val = session.scalar(
        select(func.max(Restaurant.google_review_count)).where(Restaurant.active.is_(True))
    )
    return max(int(val or 0), 1)


def _compute_shrinkage_params(
    google_review_count: int | None, corpus_max_review_count: int
) -> _ShrinkageParams:
    """Volume-aware K: low-volume places get heavy K_HIGH; high-volume get light K_LOW."""
    grc = max(int(google_review_count or 0), 0)
    log_local = math.log10(grc + 10)
    log_max = math.log10(corpus_max_review_count + 10)
    cf = log_local / log_max if log_max > 0 else 0.0
    cf = max(0.0, min(1.0, cf))
    eff_k = SHRINKAGE_K_HIGH * (1.0 - cf) + SHRINKAGE_K_LOW * cf
    return _ShrinkageParams(effective_k=round(eff_k, 3), confidence_factor=round(cf, 4))


def _apply_price_penalty(score: float | None, price_tier: int | None) -> float | None:
    if score is None:
        return None
    penalty = PRICE_PENALTY.get(price_tier or 0, 0)
    return max(0.0, min(100.0, round(score + penalty, 1)))


def _composite_prime_score(q: float | None, s: float | None, a: float | None) -> float | None:
    if q is None or s is None or a is None:
        return None
    return round(0.4 * q + 0.3 * s + 0.3 * a, 1)


# ---------------------------------------------------------------------------
# House_take + themes (Claude summarization, cached 7 days)
# ---------------------------------------------------------------------------

SUMMARY_SYSTEM_PROMPT = """You are summarizing a steakhouse based on its computed pillar scores and classified review sentences. You'll receive:
- The restaurant name
- Three pillar scores in [0, 100]: Quality, Service, Ambiance (any may be null/missing)
- The most positive and most negative classified sentences for each pillar

Your "house_take" MUST be consistent with the scores:
- If a pillar score is below 65, do NOT describe that pillar positively. Name the weakness.
- If a pillar score is above 85, you may emphasize that pillar as a strength.
- If a pillar score is in [65, 85], be neutral or note both strengths and weaknesses for that pillar.
- If a pillar score is null, do not make claims about it.

Produce a single JSON object with these fields exactly:
- "house_take": one sentence, maximum 25 words. Specific, concrete, score-consistent. No clichés. The phrase "a cut above" is banned.
- "quality_themes_pos": list of 2-3 short phrases (1-4 words each) that recur in the positive quality sentences. Examples: ["dry-aged ribeye", "wedge salad"].
- "quality_themes_neg": list of 0-2 short phrases. Empty list if nothing notable.
- "service_themes_pos": same shape, 2-3 phrases.
- "service_themes_neg": same shape, 0-2 phrases.
- "ambiance_themes_pos": same shape, 2-3 phrases.
- "ambiance_themes_neg": same shape, 0-2 phrases.

Return ONLY the JSON object. No prose, no markdown fencing."""

SUMMARY_MAX_TOKENS = 800
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _select_summary_inputs(
    sentences_by_pillar: dict[str, list[_SentenceRow]],
    n_per_direction: int = SUMMARIZE_TOP_N_PER_DIRECTION,
) -> dict[str, dict[str, list[str]]]:
    """For each pillar return {'pos': [...], 'neg': [...]} of top N sentence texts."""
    out: dict[str, dict[str, list[str]]] = {}
    for pillar in PILLARS:
        rows = sentences_by_pillar.get(pillar, [])
        sorted_by_sent = sorted(rows, key=lambda r: r.sentiment)
        neg = [r.text for r in sorted_by_sent[:n_per_direction]]
        pos = [r.text for r in sorted_by_sent[-n_per_direction:][::-1]]
        out[pillar] = {"pos": pos, "neg": neg}
    return out


def _build_summary_user_message(
    restaurant_name: str,
    inputs: dict[str, dict[str, list[str]]],
    pillar_scores: dict[str, float | None],
) -> str:
    def _fmt(v: float | None) -> str:
        return f"{v:.1f}" if v is not None else "null"

    lines = [
        f"Restaurant: {restaurant_name}",
        "",
        "Computed pillar scores (0-100):",
        f"- Quality:  {_fmt(pillar_scores.get('quality'))}",
        f"- Service:  {_fmt(pillar_scores.get('service'))}",
        f"- Ambiance: {_fmt(pillar_scores.get('ambiance'))}",
        "",
        "Top sentences per pillar (most-positive first, most-negative second):",
        "",
    ]
    for pillar in PILLARS:
        block = inputs.get(pillar, {"pos": [], "neg": []})
        lines.append(f"=== {pillar.upper()} ===")
        lines.append("Most positive sentences:")
        if block["pos"]:
            lines.extend(f"- {t}" for t in block["pos"])
        else:
            lines.append("- (none)")
        lines.append("Most negative sentences:")
        if block["neg"]:
            lines.extend(f"- {t}" for t in block["neg"])
        else:
            lines.append("- (none)")
        lines.append("")
    return "\n".join(lines)


def _parse_summary_response(raw: str) -> _Summary:
    cleaned = _FENCE_RE.sub("", raw).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError(f"summary response is not a JSON object: {cleaned[:200]!r}")

    house_take = payload.get("house_take")
    if not isinstance(house_take, str) or not house_take.strip():
        raise ValueError("summary missing 'house_take'")

    themes: dict[str, dict[str, list[str]]] = {}
    for pillar in PILLARS:
        pos = payload.get(f"{pillar}_themes_pos", [])
        neg = payload.get(f"{pillar}_themes_neg", [])
        if not isinstance(pos, list) or not isinstance(neg, list):
            raise ValueError(f"summary {pillar} themes are not lists")
        themes[pillar] = {
            "pos": [str(p).strip() for p in pos if isinstance(p, str) and p.strip()],
            "neg": [str(n).strip() for n in neg if isinstance(n, str) and n.strip()],
        }

    return _Summary(house_take=house_take.strip(), themes=themes, generated_at=_utcnow())


def _generate_summary(
    restaurant: Restaurant,
    sentences_by_pillar: dict[str, list[_SentenceRow]],
    pillar_scores: dict[str, float | None],
    client: Anthropic,
) -> _Summary:
    inputs = _select_summary_inputs(sentences_by_pillar)
    user_msg = _build_summary_user_message(restaurant.name, inputs, pillar_scores)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=SUMMARY_MAX_TOKENS,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw_text = response.content[0].text if response.content else ""
    try:
        return _parse_summary_response(raw_text)
    except (ValueError, json.JSONDecodeError) as e:
        log.warning("summary parse failed for %s (%s); retrying at temp=0", restaurant.slug, e)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.0,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw_text = response.content[0].text if response.content else ""
        return _parse_summary_response(raw_text)


def _summary_from_score(score: Score) -> _Summary:
    themes = {
        "quality": {"pos": score.quality_themes_pos or [], "neg": score.quality_themes_neg or []},
        "service": {"pos": score.service_themes_pos or [], "neg": score.service_themes_neg or []},
        "ambiance": {"pos": score.ambiance_themes_pos or [], "neg": score.ambiance_themes_neg or []},
    }
    return _Summary(house_take=score.house_take, themes=themes, generated_at=score.summary_generated_at)


def _resolve_summary(
    session: Session,
    restaurant: Restaurant,
    sentences_by_pillar: dict[str, list[_SentenceRow]],
    pillar_scores: dict[str, float | None],
    client: Anthropic,
    now: datetime,
    force: bool = False,
) -> tuple[_Summary, bool]:
    """Return (summary, was_cached). force=True bypasses the cache entirely."""
    if not force:
        last = session.scalar(
            select(Score)
            .where(Score.restaurant_id == restaurant.id)
            .order_by(Score.computed_at.desc())
            .limit(1)
        )
        if last and last.summary_generated_at and last.house_take:
            prior = last.summary_generated_at
            if prior.tzinfo is None:
                prior = prior.replace(tzinfo=timezone.utc)
            if now - prior < timedelta(days=SUMMARY_CACHE_DAYS):
                return _summary_from_score(last), True

    summary = _generate_summary(restaurant, sentences_by_pillar, pillar_scores, client=client)
    return summary, False


# ---------------------------------------------------------------------------
# Per-restaurant orchestration
# ---------------------------------------------------------------------------


def _score_one_pillar(
    pillar: str,
    rows: list[_SentenceRow],
    corpus_mean: float,
    effective_k: float,
    *,
    now: datetime,
) -> _PillarOutcome:
    n = len(rows)
    raw = _raw_pillar_score(rows, now=now)
    if n < MIN_SENTENCES_PER_PILLAR:
        return _PillarOutcome(raw_score=raw, final_score=None, n_sentences=n)
    shrunk = _apply_shrinkage(raw, n, corpus_mean, k=effective_k)
    return _PillarOutcome(raw_score=raw, final_score=shrunk, n_sentences=n)


def score_restaurant(
    session: Session,
    restaurant: Restaurant,
    corpus_means: dict[str, float] | None = None,
    corpus_max_review_count: int | None = None,
    client: Anthropic | None = None,
    classifier_version: str | None = None,
    now: datetime | None = None,
    force_summaries: bool = False,
) -> ScoreResult:
    cv = classifier_version or settings.classifier_version
    now = now or _utcnow()
    if corpus_means is None:
        corpus_means = _compute_corpus_pillar_means(session, cv)
    if corpus_max_review_count is None:
        corpus_max_review_count = _compute_corpus_max_review_count(session)
    if client is None:
        client = _client()

    rows = _load_sentence_rows(session, restaurant.id, cv)
    google_review_ids = {r.review_id for r in rows if r.source == "google"}
    google_reviews_used = len(google_review_ids)

    if google_reviews_used < MIN_REVIEWS_PER_RESTAURANT:
        reason = f"only {google_reviews_used} Google reviews (< {MIN_REVIEWS_PER_RESTAURANT})"
        log.info("score: name=%r SKIPPED — %s", restaurant.name, reason)
        return ScoreResult(name=restaurant.name, skipped=True, skip_reason=reason)

    by_pillar: dict[str, list[_SentenceRow]] = {p: [] for p in PILLARS}
    for r in rows:
        if r.pillar in by_pillar:
            by_pillar[r.pillar].append(r)

    shrink = _compute_shrinkage_params(restaurant.google_review_count, corpus_max_review_count)

    outcomes = {
        p: _score_one_pillar(p, by_pillar[p], corpus_means[p], shrink.effective_k, now=now)
        for p in PILLARS
    }

    # Apply price-tier penalty to the SHRUNK quality score (per project decision).
    quality_final = _apply_price_penalty(outcomes["quality"].final_score, restaurant.price_tier)
    service_final = outcomes["service"].final_score
    ambiance_final = outcomes["ambiance"].final_score
    prime = _composite_prime_score(quality_final, service_final, ambiance_final)

    # Date range from reviews actually represented in the sentences used.
    review_ids_used = {r.review_id for r in rows}
    posted_dates = sorted({r.posted_at.date() for r in rows if r.review_id in review_ids_used})
    date_range = (posted_dates[0], posted_dates[-1]) if posted_dates else None

    pillar_scores_for_summary = {
        "quality": quality_final,
        "service": service_final,
        "ambiance": ambiance_final,
    }
    summary, was_cached = _resolve_summary(
        session, restaurant, by_pillar, pillar_scores_for_summary,
        client=client, now=now, force=force_summaries,
    )

    score_row = Score(
        restaurant_id=restaurant.id,
        quality_score=quality_final,
        service_score=service_final,
        ambiance_score=ambiance_final,
        prime_score=prime,
        raw_quality_score=outcomes["quality"].raw_score,
        raw_service_score=outcomes["service"].raw_score,
        raw_ambiance_score=outcomes["ambiance"].raw_score,
        quality_n_sentences=outcomes["quality"].n_sentences,
        service_n_sentences=outcomes["service"].n_sentences,
        ambiance_n_sentences=outcomes["ambiance"].n_sentences,
        google_review_count=restaurant.google_review_count,
        google_review_count_used=google_reviews_used,
        reddit_mention_count_used=0,            # Reddit deferred to v1.1
        effective_k=shrink.effective_k,
        confidence_factor=shrink.confidence_factor,
        date_range_start=date_range[0] if date_range else None,
        date_range_end=date_range[1] if date_range else None,
        house_take=summary.house_take,
        quality_themes_pos=summary.themes.get("quality", {}).get("pos", []),
        quality_themes_neg=summary.themes.get("quality", {}).get("neg", []),
        service_themes_pos=summary.themes.get("service", {}).get("pos", []),
        service_themes_neg=summary.themes.get("service", {}).get("neg", []),
        ambiance_themes_pos=summary.themes.get("ambiance", {}).get("pos", []),
        ambiance_themes_neg=summary.themes.get("ambiance", {}).get("neg", []),
        summary_generated_at=summary.generated_at,
    )
    session.add(score_row)
    session.commit()

    log.info(
        "score: name=%r prime=%s Q=%s S=%s A=%s n=Q%d/S%d/A%d "
        "K=%.2f cf=%.3f gTotal=%s summary=%s",
        restaurant.name,
        prime,
        quality_final,
        service_final,
        ambiance_final,
        outcomes["quality"].n_sentences,
        outcomes["service"].n_sentences,
        outcomes["ambiance"].n_sentences,
        shrink.effective_k,
        shrink.confidence_factor,
        restaurant.google_review_count,
        "cached" if was_cached else "fresh",
    )

    return ScoreResult(
        name=restaurant.name,
        quality=quality_final,
        service=service_final,
        ambiance=ambiance_final,
        prime=prime,
        raw_quality=outcomes["quality"].raw_score,
        raw_service=outcomes["service"].raw_score,
        raw_ambiance=outcomes["ambiance"].raw_score,
        n_by_pillar={p: outcomes[p].n_sentences for p in PILLARS},
        google_reviews_used=google_reviews_used,
        google_review_count=restaurant.google_review_count,
        effective_k=shrink.effective_k,
        confidence_factor=shrink.confidence_factor,
        date_range=date_range,
        summary_cached=was_cached,
    )


def score_by_slug(slug: str, force_summaries: bool = False) -> ScoreResult:
    with SessionLocal() as session:
        restaurant = session.scalar(select(Restaurant).where(Restaurant.slug == slug))
        if restaurant is None:
            raise ValueError(f"no restaurant with slug={slug!r}")
        return score_restaurant(session, restaurant, force_summaries=force_summaries)


def score_all(force_summaries: bool = False) -> list[ScoreResult]:
    results: list[ScoreResult] = []
    with SessionLocal() as session:
        client = _client()
        cv = settings.classifier_version
        corpus_means = _compute_corpus_pillar_means(session, cv)
        corpus_max_review_count = _compute_corpus_max_review_count(session)
        log.info(
            "corpus pillar means (0-100): %s | corpus_max_review_count=%d (denom for confidence_factor)",
            corpus_means,
            corpus_max_review_count,
        )
        restaurants = session.scalars(
            select(Restaurant).where(Restaurant.active.is_(True)).order_by(Restaurant.id)
        ).all()
        for r in restaurants:
            results.append(
                score_restaurant(
                    session,
                    r,
                    corpus_means=corpus_means,
                    corpus_max_review_count=corpus_max_review_count,
                    client=client,
                    force_summaries=force_summaries,
                )
            )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute pillar + Prime scores")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Score one restaurant by slug")
    group.add_argument("--all", action="store_true", help="Score every active restaurant")
    parser.add_argument(
        "--force-summaries",
        action="store_true",
        help="Bypass the SUMMARY_CACHE_DAYS cache and regenerate house_take + themes",
    )
    args = parser.parse_args()

    if args.slug:
        score_by_slug(args.slug, force_summaries=args.force_summaries)
    else:
        score_all(force_summaries=args.force_summaries)


if __name__ == "__main__":
    main()
