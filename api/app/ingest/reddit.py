"""Reddit ingest — DEFERRED to v1.1.

Status: Reddit API access request submitted; approval window is 1–4 weeks.
The MVP ships with Google reviews only. This module exists as a skeleton so
that the v1.1 plug-in is a localized change: implement the function bodies,
add the call into app.jobs.nightly, and re-run.

When unblocked:
  - Use PRAW (already listed in `optional-dependencies.ingest` in pyproject.toml).
  - Auth via REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET / REDDIT_USER_AGENT (in .env;
    intentionally left empty for the MVP).
  - Subreddits to search: chicago, AskChicago, ChicagoFood, FoodChicago, steak, FoodPorn.
  - Filter window: rolling 24 months (matches the Google reviews window).
  - Per spec §8: drop posts/comments under 30 chars or with reddit_score < 1.
  - Idempotent: insert reviews with source='reddit' and source_id=<post or comment id>;
    the (source, source_id) unique constraint catches duplicates on re-run.
  - Per spec §8: time.sleep(1.1) between requests so we don't trip Reddit's bursty-client
    penalty even though we're nowhere near the 100 req/min limit.

The MVP scorer, "Sources" UI section, and methodology page all currently report
Google-only stats. The fields/behaviors that need to flip when Reddit ships:
  - score.reddit_mention_count_used: currently always 0
  - /api/restaurants/{slug}.sources.reddit_mentions: currently always 0
  - docs/methodology.md: mentions Reddit as a planned v1.1 enhancement; promote to
    a first-class source when this module is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.logging_setup import get_logger
from app.models import Restaurant

log = get_logger(__name__)

SUBREDDITS = ["chicago", "AskChicago", "ChicagoFood", "FoodChicago", "steak", "FoodPorn"]
LOOKBACK_DAYS = 365 * 2
MIN_BODY_CHARS = 30
MIN_REDDIT_SCORE = 1
INTER_REQUEST_SLEEP_SECONDS = 1.1


@dataclass
class RedditIngestResult:
    name: str
    posts_inserted: int
    comments_inserted: int
    skipped_duplicate: int
    skipped_too_old: int
    skipped_too_short: int
    skipped_low_score: int


def search_for_restaurant(
    session: Session,
    restaurant: Restaurant,
) -> RedditIngestResult:
    """[v1.1] Search SUBREDDITS for `restaurant.name` and ingest matching posts + top-level comments.

    Not implemented in MVP. Calling this raises NotImplementedError so callers
    can't accidentally include Reddit data in scoring before the API key lands.
    """
    raise NotImplementedError(
        "Reddit ingest is deferred to v1.1 pending API access approval. "
        "Do not call this from the nightly orchestrator until then."
    )


def ingest_all() -> list[RedditIngestResult]:
    """[v1.1] Run search_for_restaurant against every active restaurant. Not implemented in MVP."""
    raise NotImplementedError(
        "Reddit ingest is deferred to v1.1 pending API access approval."
    )
