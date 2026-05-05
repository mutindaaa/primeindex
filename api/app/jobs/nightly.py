"""Nightly orchestrator for Prime Index.

Sequential pipeline (per spec §11, with project-level Reddit deferral baked in):

  1. Google Places refresh — pulls latest 5 reviews per active restaurant, updates
     metadata (address, lat/lng, price_tier, rating, review_count, website, phone).
  2. Reddit ingest — DEFERRED to v1.1; explicit no-op log line so cron output makes
     the deferral visible.
  3. Classifier — sentence-classify any new reviews via Claude. Idempotent at
     (review_id, classifier_version): already-classified reviews skip cleanly.
  4. Scorer — recompute pillar scores + Prime Score with volume-aware shrinkage
     and softened price-tier penalty. Always appends a fresh `scores` row.
     House_take + per-pillar themes are regenerated unless the prior summary is
     less than SUMMARY_CACHE_DAYS old (currently 7).
  5. Google 30-day body purge — clear `reviews.body` for source='google' rows
     older than 30 days, per Google Places ToS.
  6. Print a summary table to stdout (per project requirement A): one row per
     restaurant with reviews_ingested / sentences_classified / scores_written /
     prime, plus totals.

Idempotency: every step is safe to re-run. Failures in one step are logged but
do NOT abort the orchestrator — subsequent steps still run with whatever state
the prior step managed to commit. This keeps the cron job resilient against
transient API errors (Anthropic/Google 5xxs, Reddit later, etc.).

Run from api/ with venv active:
    python -m app.jobs.nightly
"""

from __future__ import annotations

from dataclasses import dataclass

from app.classify.classifier import RestaurantClassifyResult, classify_all
from app.db import SessionLocal
from app.ingest.google_places import IngestResult, purge_stale_google_bodies, refresh_all
from app.logging_setup import configure_logging, get_logger
from app.score.scorer import ScoreResult, score_all

log = get_logger(__name__)


@dataclass
class _PerRestaurantRow:
    name: str
    reviews_ingested: int = 0
    sentences_classified: int = 0
    scores_written: int = 0
    prime: float | None = None
    skipped: bool = False
    skip_reason: str | None = None


def _aggregate(
    google_results: list[IngestResult],
    classify_results: list[RestaurantClassifyResult],
    score_results: list[ScoreResult],
) -> dict[str, _PerRestaurantRow]:
    rows: dict[str, _PerRestaurantRow] = {}

    def _row(name: str) -> _PerRestaurantRow:
        return rows.setdefault(name, _PerRestaurantRow(name=name))

    for g in google_results:
        _row(g.name).reviews_ingested = g.reviews_inserted

    for c in classify_results:
        _row(c.name).sentences_classified = c.sentences_inserted

    for s in score_results:
        r = _row(s.name)
        if s.skipped:
            r.scores_written = 0
            r.skipped = True
            r.skip_reason = s.skip_reason
        else:
            r.scores_written = 1
            r.prime = s.prime

    return rows


def _print_summary_table(
    rows: dict[str, _PerRestaurantRow],
    purged_bodies: int,
    errors: list[str],
) -> None:
    headers = ("restaurant", "reviews_ingested", "sentences_classified", "scores_written", "prime")
    name_w = max(len(headers[0]), max((len(r.name) for r in rows.values()), default=0))
    name_w = min(name_w, 42)

    def _truncate(s: str, w: int) -> str:
        return s if len(s) <= w else s[: w - 1] + "…"

    sep_line = (
        f"+-{'-' * name_w}-+-{'-' * 16}-+-{'-' * 20}-+-{'-' * 14}-+-{'-' * 7}-+"
    )
    header_line = (
        f"| {headers[0]:<{name_w}} | {headers[1]:>16} | {headers[2]:>20} | "
        f"{headers[3]:>14} | {headers[4]:>7} |"
    )

    print()
    print("=" * len(sep_line))
    print("Prime Index — nightly summary")
    print("=" * len(sep_line))
    print(sep_line)
    print(header_line)
    print(sep_line)

    total_ri = total_sc = total_sw = 0
    for name in sorted(rows.keys()):
        r = rows[name]
        prime_cell = f"{r.prime:>7.1f}" if r.prime is not None else ("skipped" if r.skipped else "    --")
        print(
            f"| {_truncate(r.name, name_w):<{name_w}} "
            f"| {r.reviews_ingested:>16d} "
            f"| {r.sentences_classified:>20d} "
            f"| {r.scores_written:>14d} "
            f"| {prime_cell:>7} |"
        )
        total_ri += r.reviews_ingested
        total_sc += r.sentences_classified
        total_sw += r.scores_written

    print(sep_line)
    print(
        f"| {'TOTAL':<{name_w}} | {total_ri:>16d} | {total_sc:>20d} "
        f"| {total_sw:>14d} | {'--':>7} |"
    )
    print(sep_line)
    print()
    print(f"Google 30-day body purge: cleared {purged_bodies} review body rows")
    if errors:
        print()
        print(f"WARNING: {len(errors)} step(s) errored — see logs above:")
        for e in errors:
            print(f"  - {e}")
    print()


def run_nightly() -> dict[str, _PerRestaurantRow]:
    """Run the full nightly pipeline. Returns the per-restaurant aggregate."""
    configure_logging()
    log.info("=" * 60)
    log.info("Prime Index nightly job — start")
    log.info("=" * 60)

    errors: list[str] = []

    # Step 1: Google Places refresh
    google_results: list[IngestResult] = []
    log.info("[step 1/5] google_places.refresh_all")
    try:
        google_results = refresh_all()
    except Exception as e:  # noqa: BLE001 — orchestrator: log and continue
        log.exception("google_places.refresh_all failed")
        errors.append(f"google_places: {e}")

    # Step 2: Reddit (deferred)
    log.info("[step 2/5] reddit ingest — DEFERRED to v1.1, skipping")

    # Step 3: Classifier
    classify_results: list[RestaurantClassifyResult] = []
    log.info("[step 3/5] classifier.classify_all")
    try:
        classify_results = classify_all()
    except Exception as e:  # noqa: BLE001
        log.exception("classifier.classify_all failed")
        errors.append(f"classifier: {e}")

    # Step 4: Scorer (with summarization, 7-day cache for house_take)
    score_results: list[ScoreResult] = []
    log.info("[step 4/5] scorer.score_all")
    try:
        score_results = score_all()
    except Exception as e:  # noqa: BLE001
        log.exception("scorer.score_all failed")
        errors.append(f"scorer: {e}")

    # Step 5: Google 30-day body purge
    purged_bodies = 0
    log.info("[step 5/5] purge_stale_google_bodies")
    try:
        with SessionLocal() as session:
            purged_bodies = purge_stale_google_bodies(session)
    except Exception as e:  # noqa: BLE001
        log.exception("purge_stale_google_bodies failed")
        errors.append(f"purge: {e}")

    log.info("=" * 60)
    log.info("Prime Index nightly job — done")
    log.info("=" * 60)

    rows = _aggregate(google_results, classify_results, score_results)
    _print_summary_table(rows, purged_bodies=purged_bodies, errors=errors)
    return rows


def main() -> None:
    run_nightly()


if __name__ == "__main__":
    main()
