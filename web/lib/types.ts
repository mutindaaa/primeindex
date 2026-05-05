// TypeScript mirror of api/app/schemas.py (Pydantic models).
// Hand-maintained for MVP — no codegen. Keep in sync when schemas.py changes.

export interface Weights {
  quality: number;
  service: number;
  ambiance: number;
}

export interface CityRestaurantSummary {
  slug: string;
  name: string;
  neighborhood: string | null;
  price_tier: number | null;
  prime_score: number | null;
  quality_score: number | null;
  service_score: number | null;
  ambiance_score: number | null;
  quality_n_sentences: number | null;
  service_n_sentences: number | null;
  ambiance_n_sentences: number | null;
  google_review_count: number | null;
  google_review_count_used: number | null;
  house_take: string | null;
  confidence_factor: number | null;
}

export interface CityResponse {
  city: string;
  weights: Weights;
  computed_at: string | null; // ISO 8601
  restaurants: CityRestaurantSummary[];
}

export interface Quote {
  text: string;
  source: string;
  url: string | null;
}

export interface PillarDetail {
  score: number | null;
  n_sentences: number;
  themes_pos: string[];
  themes_neg: string[];
  quotes: Quote[];
}

export interface DateRange {
  start: string; // ISO date "YYYY-MM-DD"
  end: string;
}

export interface Sources {
  google_reviews: number;
  reddit_mentions: number;
  date_range: DateRange | null;
}

export interface RestaurantDetail {
  slug: string;
  name: string;
  neighborhood: string | null;
  address: string | null;
  lat: number | null;
  lng: number | null;
  price_tier: number | null;
  google_rating: number | null;
  google_review_count: number | null;
  website: string | null;
  prime_score: number | null;
  quality_score: number | null;
  service_score: number | null;
  ambiance_score: number | null;
  house_take: string | null;
  confidence_factor: number | null;
  computed_at: string | null;
  pillars: { quality: PillarDetail; service: PillarDetail; ambiance: PillarDetail };
  sources: Sources;
}

export type PillarKey = "quality" | "service" | "ambiance";
