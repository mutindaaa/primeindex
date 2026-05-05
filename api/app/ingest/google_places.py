"""Google Places API (New) v1 ingest.

For a given restaurant:
  1. Refresh metadata fields (address, lat/lng, price_tier, google_rating, etc.)
  2. Fetch reviews returned by Places (typically 5 most relevant), filter to the
     rolling 24-month window, and insert new ones into `reviews`.

Idempotent: re-running on the same restaurant updates metadata in place and
skips reviews already stored under the same (source, source_id) unique key.

Run from api/ with venv active:
    python -m app.ingest.google_places --slug bavettes-bar-boeuf
    python -m app.ingest.google_places --all
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.logging_setup import get_logger
from app.models import Restaurant, Review

log = get_logger(__name__)

# Per Google Places ToS (spec §9): verbatim review body text cannot be retained
# more than 30 days. We hard-clear `reviews.body` for source='google' rows past
# this age while keeping the row (so derived `sentences` keep their FK).
GOOGLE_BODY_RETENTION_DAYS = 30

PLACES_API_URL = "https://places.googleapis.com/v1/places/{place_id}"
FIELD_MASK = (
    "id,displayName,formattedAddress,location,priceLevel,"
    "rating,userRatingCount,websiteUri,internationalPhoneNumber,reviews"
)
REVIEW_LOOKBACK_DAYS = 365 * 2  # 24-month window per project decision

# Places API (New) returns priceLevel as an enum string. Map to 1-4 tier.
PRICE_LEVEL_MAP = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}


@dataclass
class IngestResult:
    name: str
    fields_updated: int
    reviews_inserted: int
    reviews_skipped_duplicate: int
    reviews_skipped_too_old: int


class GooglePlacesError(RuntimeError):
    pass


def _fetch_place(place_id: str, api_key: str, client: httpx.Client) -> dict:
    url = PLACES_API_URL.format(place_id=place_id)
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    log.debug("GET %s", url)
    resp = client.get(url, headers=headers, timeout=20.0)
    if resp.status_code != 200:
        raise GooglePlacesError(
            f"Places API {resp.status_code} for {place_id}: {resp.text[:300]}"
        )
    return resp.json()


def _parse_publish_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    # Places returns RFC3339 like "2025-04-01T12:34:56.789Z"
    s = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        log.warning("could not parse publishTime=%r", raw)
        return None


def _apply_metadata(restaurant: Restaurant, payload: dict) -> int:
    """Update restaurant fields in place. Return count of changed fields."""
    updates: dict[str, object] = {}

    display_name = (payload.get("displayName") or {}).get("text")
    if display_name and display_name != restaurant.name:
        updates["name"] = display_name

    formatted_address = payload.get("formattedAddress")
    if formatted_address and formatted_address != restaurant.address:
        updates["address"] = formatted_address

    location = payload.get("location") or {}
    lat = location.get("latitude")
    lng = location.get("longitude")
    if lat is not None and lat != restaurant.lat:
        updates["lat"] = lat
    if lng is not None and lng != restaurant.lng:
        updates["lng"] = lng

    price_level_enum = payload.get("priceLevel")
    if price_level_enum:
        tier = PRICE_LEVEL_MAP.get(price_level_enum)
        if tier is not None and tier != restaurant.price_tier:
            updates["price_tier"] = tier

    rating = payload.get("rating")
    if rating is not None and rating != restaurant.google_rating:
        updates["google_rating"] = rating

    review_count = payload.get("userRatingCount")
    if review_count is not None and review_count != restaurant.google_review_count:
        updates["google_review_count"] = review_count

    website = payload.get("websiteUri")
    if website and website != restaurant.website:
        updates["website"] = website

    phone = payload.get("internationalPhoneNumber")
    if phone and phone != restaurant.phone:
        updates["phone"] = phone

    for field, value in updates.items():
        setattr(restaurant, field, value)

    if updates:
        log.debug("metadata changed for %s: %s", restaurant.slug, sorted(updates.keys()))
    return len(updates)


def _ingest_reviews(
    session: Session,
    restaurant: Restaurant,
    payload: dict,
    cutoff: datetime,
) -> tuple[int, int, int]:
    """Insert new Google reviews. Returns (inserted, skipped_duplicate, skipped_too_old)."""
    raw_reviews = payload.get("reviews") or []
    if not raw_reviews:
        return (0, 0, 0)

    existing_source_ids = set(
        session.scalars(
            select(Review.source_id).where(
                Review.restaurant_id == restaurant.id,
                Review.source == "google",
            )
        ).all()
    )

    inserted = 0
    skipped_duplicate = 0
    skipped_too_old = 0

    for r in raw_reviews:
        source_id = r.get("name")  # "places/{place_id}/reviews/{review_id}" — globally unique
        if not source_id:
            log.warning("review missing 'name' field for %s — skipping", restaurant.slug)
            continue

        if source_id in existing_source_ids:
            skipped_duplicate += 1
            continue

        posted_at = _parse_publish_time(r.get("publishTime"))
        if posted_at and posted_at < cutoff:
            skipped_too_old += 1
            continue

        text_block = r.get("text") or r.get("originalText") or {}
        body = text_block.get("text") or ""
        if not body.strip():
            log.debug("review %s has no body text — skipping", source_id)
            continue

        author = (r.get("authorAttribution") or {}).get("displayName")
        rating = r.get("rating")
        source_url = r.get("googleMapsUri")

        review = Review(
            restaurant_id=restaurant.id,
            source="google",
            source_id=source_id,
            source_url=source_url,
            author=author,
            body=body,
            rating=rating,
            posted_at=posted_at,
        )
        session.add(review)
        existing_source_ids.add(source_id)
        inserted += 1

    return (inserted, skipped_duplicate, skipped_too_old)


def refresh_restaurant(
    session: Session,
    restaurant: Restaurant,
    client: httpx.Client | None = None,
    api_key: str | None = None,
) -> IngestResult:
    """Refresh one restaurant's metadata + reviews against Places API (New)."""
    key = api_key or settings.google_places_api_key
    if not key:
        raise GooglePlacesError("GOOGLE_PLACES_API_KEY is not set in environment")

    cutoff = datetime.now(timezone.utc) - timedelta(days=REVIEW_LOOKBACK_DAYS)

    owns_client = client is None
    if owns_client:
        client = httpx.Client()

    try:
        payload = _fetch_place(restaurant.google_place_id, key, client)
    finally:
        if owns_client:
            client.close()

    fields_updated = _apply_metadata(restaurant, payload)
    inserted, skipped_dup, skipped_old = _ingest_reviews(session, restaurant, payload, cutoff)
    session.commit()

    log.info(
        "google_places: name=%r fields_updated=%d reviews_inserted=%d "
        "reviews_skipped_duplicate=%d reviews_skipped_too_old=%d",
        restaurant.name,
        fields_updated,
        inserted,
        skipped_dup,
        skipped_old,
    )

    return IngestResult(
        name=restaurant.name,
        fields_updated=fields_updated,
        reviews_inserted=inserted,
        reviews_skipped_duplicate=skipped_dup,
        reviews_skipped_too_old=skipped_old,
    )


def refresh_by_slug(slug: str) -> IngestResult:
    with SessionLocal() as session:
        restaurant = session.scalar(select(Restaurant).where(Restaurant.slug == slug))
        if restaurant is None:
            raise ValueError(f"no restaurant with slug={slug!r}")
        return refresh_restaurant(session, restaurant)


def refresh_all() -> list[IngestResult]:
    results: list[IngestResult] = []
    with SessionLocal() as session, httpx.Client() as client:
        restaurants = session.scalars(
            select(Restaurant).where(Restaurant.active.is_(True)).order_by(Restaurant.id)
        ).all()
        for r in restaurants:
            try:
                results.append(refresh_restaurant(session, r, client=client))
            except GooglePlacesError as e:
                log.error("google_places: failed for slug=%s: %s", r.slug, e)
    return results


def purge_stale_google_bodies(
    session: Session, retention_days: int = GOOGLE_BODY_RETENTION_DAYS
) -> int:
    """Clear reviews.body for Google rows older than retention_days. Returns rowcount."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    result = session.execute(
        update(Review)
        .where(
            Review.source == "google",
            Review.ingested_at < cutoff,
            Review.body.is_not(None),
        )
        .values(body=None)
    )
    session.commit()
    n = result.rowcount or 0
    log.info(
        "purge_stale_google_bodies: cleared %d Google review bodies older than %d days",
        n,
        retention_days,
    )
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh Google Places data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Refresh a single restaurant by slug")
    group.add_argument("--all", action="store_true", help="Refresh every active restaurant")
    args = parser.parse_args()

    if args.slug:
        refresh_by_slug(args.slug)
    else:
        refresh_all()


if __name__ == "__main__":
    main()
