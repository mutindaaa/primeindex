"""Pydantic response models. Returned by API routes — never return raw SQLAlchemy models.

These shapes are the public contract the frontend consumes. Match spec §10.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class Weights(BaseModel):
    quality: float
    service: float
    ambiance: float


class CityRestaurantSummary(BaseModel):
    slug: str
    name: str
    neighborhood: str | None = None
    price_tier: int | None = None
    prime_score: float | None = None
    quality_score: float | None = None
    service_score: float | None = None
    ambiance_score: float | None = None
    quality_n_sentences: int | None = None
    service_n_sentences: int | None = None
    ambiance_n_sentences: int | None = None
    google_review_count: int | None = None
    google_review_count_used: int | None = None
    house_take: str | None = None
    confidence_factor: float | None = None


class CityResponse(BaseModel):
    city: str
    weights: Weights
    computed_at: datetime | None = None
    restaurants: list[CityRestaurantSummary]


class Quote(BaseModel):
    text: str
    source: str
    url: str | None = None


class PillarDetail(BaseModel):
    score: float | None = None
    n_sentences: int = 0
    themes_pos: list[str] = []
    themes_neg: list[str] = []
    quotes: list[Quote] = []


class DateRange(BaseModel):
    start: date
    end: date


class Sources(BaseModel):
    google_reviews: int
    reddit_mentions: int = 0
    date_range: DateRange | None = None


class RestaurantDetail(BaseModel):
    slug: str
    name: str
    neighborhood: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    price_tier: int | None = None
    google_rating: float | None = None
    google_review_count: int | None = None
    website: str | None = None
    prime_score: float | None = None
    quality_score: float | None = None
    service_score: float | None = None
    ambiance_score: float | None = None
    house_take: str | None = None
    confidence_factor: float | None = None
    computed_at: datetime | None = None
    pillars: dict[str, PillarDetail]
    sources: Sources
