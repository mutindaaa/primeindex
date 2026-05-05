from datetime import datetime, date

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    google_place_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    google_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    google_review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    scores: Mapped[list["Score"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_reviews_source_source_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String, nullable=False)            # 'google' | 'reddit'
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)          # nullable so Google rows can be purged after 30d
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)     # Google 1-5
    reddit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    restaurant: Mapped["Restaurant"] = relationship(back_populates="reviews")
    sentences: Mapped[list["Sentence"]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    pillar: Mapped[str] = mapped_column(String, nullable=False, index=True)   # quality|service|ambiance|other
    sentiment: Mapped[float] = mapped_column(Float, nullable=False)           # -1.0 .. 1.0
    classifier_version: Mapped[str] = mapped_column(String, nullable=False)
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review: Mapped["Review"] = relationship(back_populates="sentences")


class Score(Base):
    """Append-only. One row per restaurant per scoring run."""

    __tablename__ = "scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    service_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    ambiance_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prime_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Raw, pre-shrinkage, pre-penalty scores. Retained for debugging and v1.1 tuning.
    raw_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_service_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_ambiance_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Per-pillar sentence counts. Surfaced in the API so the UI can show
    # "based on N sentences" subscripts on thin pillar scores.
    quality_n_sentences: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_n_sentences: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ambiance_n_sentences: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Snapshot of restaurants.google_review_count at scoring time, so the API can
    # surface "based on N total Google ratings" without re-querying restaurants.
    google_review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Volume-aware shrinkage debug fields. effective_k is the K actually used in
    # this restaurant's pillar shrinkage; confidence_factor in [0, 1] is the
    # log-volume signal driving K_HIGH -> K_LOW interpolation.
    effective_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    google_review_count_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reddit_mention_count_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    date_range_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_range_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Cached Claude summarization (regenerated every 7 days). JSON arrays of strings.
    house_take: Mapped[str | None] = mapped_column(Text, nullable=True)
    quality_themes_pos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    quality_themes_neg: Mapped[list | None] = mapped_column(JSON, nullable=True)
    service_themes_pos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    service_themes_neg: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ambiance_themes_pos: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ambiance_themes_neg: Mapped[list | None] = mapped_column(JSON, nullable=True)
    summary_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    restaurant: Mapped["Restaurant"] = relationship(back_populates="scores")
