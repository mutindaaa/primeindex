"""Seed the restaurants table from data/chicago_seed.csv.

Idempotent: skips rows whose google_place_id is already present.
Does NOT call Google Places — Place IDs come from the CSV. The Places API
refresh happens in step 5 (app/ingest/google_places.py).

Run from repo root with the api venv active:
    python -m app.ingest.seed_chicago
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.db import SessionLocal
from app.ingest.slugs import slugify, unique_slug
from app.logging_setup import get_logger
from app.models import Restaurant

log = get_logger(__name__)

SEED_CSV_PATH = REPO_ROOT / "data" / "chicago_seed.csv"
CITY = "chicago"
REQUIRED_COLUMNS = {"name", "google_place_id", "neighborhood"}


def _read_seed_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"seed CSV not found: {path}")
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise ValueError(
                f"seed CSV must have columns {sorted(REQUIRED_COLUMNS)}, got {reader.fieldnames}"
            )
        rows: list[dict[str, str]] = []
        for i, row in enumerate(reader, start=2):  # start=2 because of header
            name = (row.get("name") or "").strip()
            place_id = (row.get("google_place_id") or "").strip()
            neighborhood = (row.get("neighborhood") or "").strip() or None
            if not name or not place_id:
                log.warning("skipping CSV row %d: missing name or google_place_id", i)
                continue
            rows.append({"name": name, "google_place_id": place_id, "neighborhood": neighborhood})
        return rows


def seed_chicago(session: Session, csv_path: Path = SEED_CSV_PATH) -> tuple[int, int]:
    """Insert restaurants from the CSV. Returns (inserted, skipped)."""
    rows = _read_seed_rows(csv_path)
    if not rows:
        log.warning("seed CSV %s is empty — nothing to seed", csv_path)
        return (0, 0)

    existing_place_ids = set(session.scalars(select(Restaurant.google_place_id)).all())
    existing_slugs = set(session.scalars(select(Restaurant.slug)).all())

    inserted = 0
    skipped = 0

    for row in rows:
        if row["google_place_id"] in existing_place_ids:
            log.info(
                "skip existing: name=%r place_id=%s", row["name"], row["google_place_id"]
            )
            skipped += 1
            continue

        base_slug = slugify(row["name"])
        slug = unique_slug(base_slug, existing_slugs)
        existing_slugs.add(slug)

        restaurant = Restaurant(
            slug=slug,
            google_place_id=row["google_place_id"],
            name=row["name"],
            city=CITY,
            neighborhood=row["neighborhood"],
            active=True,
        )
        session.add(restaurant)
        existing_place_ids.add(row["google_place_id"])
        inserted += 1
        log.info("insert: name=%r slug=%s place_id=%s", row["name"], slug, row["google_place_id"])

    session.commit()
    return (inserted, skipped)


def main() -> None:
    log.info("seed_chicago: reading %s", SEED_CSV_PATH)
    with SessionLocal() as session:
        inserted, skipped = seed_chicago(session)
    log.info("Seeded %d new restaurants, skipped %d existing.", inserted, skipped)
    print(f"Seeded {inserted} new restaurants, skipped {skipped} existing.")


if __name__ == "__main__":
    main()
