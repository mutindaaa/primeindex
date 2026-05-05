"""Classifier orchestrator: review_id -> sentences in DB.

Idempotent at the (review_id, classifier_version) level: a review that already
has sentences at the current `settings.classifier_version` is skipped on re-run.
This is the body-hash check from spec §6 reframed: review bodies are immutable
per review_id (the (source, source_id) unique constraint blocks duplicate
inserts), so checking review_id existence is equivalent.

CLI:
    python -m app.classify.classifier --slug bavettes-bar-boeuf
    python -m app.classify.classifier --all
    python -m app.classify.classifier --review-id 42
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classify.claude_client import (
    ClassifierError,
    SentenceClass,
    _client,
    classify_review,
)
from app.config import settings
from app.db import SessionLocal
from app.logging_setup import get_logger
from app.models import Restaurant, Review, Sentence

log = get_logger(__name__)


@dataclass
class ReviewClassifyResult:
    review_id: int
    skipped_already_classified: bool
    sentences_inserted: int
    error: str | None = None


@dataclass
class RestaurantClassifyResult:
    name: str
    reviews_processed: int
    reviews_skipped: int
    sentences_inserted: int
    errors: int


def _already_classified(session: Session, review_id: int, classifier_version: str) -> bool:
    return (
        session.scalar(
            select(Sentence.id)
            .where(
                Sentence.review_id == review_id,
                Sentence.classifier_version == classifier_version,
            )
            .limit(1)
        )
        is not None
    )


def classify_one_review(
    session: Session,
    review: Review,
    client: Anthropic,
    classifier_version: str,
) -> ReviewClassifyResult:
    if _already_classified(session, review.id, classifier_version):
        return ReviewClassifyResult(
            review_id=review.id, skipped_already_classified=True, sentences_inserted=0
        )

    if not review.body or not review.body.strip():
        log.debug("review_id=%d has empty body — skipping", review.id)
        return ReviewClassifyResult(
            review_id=review.id, skipped_already_classified=False, sentences_inserted=0
        )

    try:
        sentences: list[SentenceClass] = classify_review(review.body, client=client)
    except ClassifierError as e:
        log.error("classify review_id=%d failed: %s", review.id, e)
        return ReviewClassifyResult(
            review_id=review.id,
            skipped_already_classified=False,
            sentences_inserted=0,
            error=str(e),
        )

    for s in sentences:
        session.add(
            Sentence(
                review_id=review.id,
                text=s.text,
                pillar=s.pillar,
                sentiment=s.sentiment,
                classifier_version=classifier_version,
            )
        )
    session.flush()
    return ReviewClassifyResult(
        review_id=review.id,
        skipped_already_classified=False,
        sentences_inserted=len(sentences),
    )


def classify_restaurant(
    session: Session,
    restaurant: Restaurant,
    client: Anthropic | None = None,
    classifier_version: str | None = None,
) -> RestaurantClassifyResult:
    cv = classifier_version or settings.classifier_version
    c = client or _client()

    reviews = session.scalars(
        select(Review).where(Review.restaurant_id == restaurant.id).order_by(Review.id)
    ).all()

    processed = 0
    skipped = 0
    sentences_inserted = 0
    errors = 0

    for review in reviews:
        result = classify_one_review(session, review, c, cv)
        if result.error:
            errors += 1
        elif result.skipped_already_classified:
            skipped += 1
        else:
            processed += 1
            sentences_inserted += result.sentences_inserted

    session.commit()

    log.info(
        "classify: name=%r reviews_processed=%d reviews_skipped=%d "
        "sentences_inserted=%d errors=%d classifier_version=%s",
        restaurant.name,
        processed,
        skipped,
        sentences_inserted,
        errors,
        cv,
    )
    return RestaurantClassifyResult(
        name=restaurant.name,
        reviews_processed=processed,
        reviews_skipped=skipped,
        sentences_inserted=sentences_inserted,
        errors=errors,
    )


def classify_by_slug(slug: str) -> RestaurantClassifyResult:
    with SessionLocal() as session:
        restaurant = session.scalar(select(Restaurant).where(Restaurant.slug == slug))
        if restaurant is None:
            raise ValueError(f"no restaurant with slug={slug!r}")
        return classify_restaurant(session, restaurant)


def classify_review_id(review_id: int) -> ReviewClassifyResult:
    with SessionLocal() as session:
        review = session.get(Review, review_id)
        if review is None:
            raise ValueError(f"no review with id={review_id}")
        client = _client()
        result = classify_one_review(session, review, client, settings.classifier_version)
        session.commit()
        log.info("classify review_id=%d -> %s", review_id, result)
        return result


def classify_all() -> list[RestaurantClassifyResult]:
    results: list[RestaurantClassifyResult] = []
    with SessionLocal() as session:
        client = _client()
        restaurants = session.scalars(
            select(Restaurant).where(Restaurant.active.is_(True)).order_by(Restaurant.id)
        ).all()
        for r in restaurants:
            results.append(classify_restaurant(session, r, client=client))
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify reviews via Claude")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Classify all reviews for one restaurant")
    group.add_argument("--all", action="store_true", help="Classify reviews for every active restaurant")
    group.add_argument("--review-id", type=int, help="Classify a single review by id")
    args = parser.parse_args()

    if args.slug:
        classify_by_slug(args.slug)
    elif args.review_id is not None:
        classify_review_id(args.review_id)
    else:
        classify_all()


if __name__ == "__main__":
    main()
