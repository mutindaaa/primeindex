// Display helpers shared across pages. Keep pure — no React, no fetch.

import type { CityRestaurantSummary } from "./types";

export function formatScore(score: number | null, decimals = 1): string {
  if (score === null) return "—";
  return score.toFixed(decimals);
}

export interface PriceTierDisplay {
  symbol: string;
  missing: boolean;
}

export function formatPriceTier(tier: number | null): PriceTierDisplay {
  if (tier === null || tier < 1 || tier > 4) {
    return { symbol: "Price unavailable", missing: true };
  }
  return { symbol: "$".repeat(tier), missing: false };
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  // Backend returns naive UTC ISO (no tz suffix in SQLite-rendered values).
  // Append Z so the browser interprets as UTC, then format in the user's locale.
  const normalized = iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`;
  const d = new Date(normalized);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function formatReviewCount(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return n.toLocaleString("en-US");
}

/** Tailwind class for the pillar bar fill — warmer = higher score, cooler = lower. */
export function pillarBarColor(score: number | null): string {
  if (score === null) return "bg-muted";
  if (score >= 85) return "bg-amber-500";
  if (score >= 75) return "bg-amber-400/80";
  if (score >= 65) return "bg-stone-400";
  if (score >= 55) return "bg-slate-500";
  return "bg-slate-600";
}

/** Recompute the composite Prime Score using user-supplied integer weights (sum = 100). Strict: any pillar null -> null. */
export function computeWeightedPrime(
  q: number | null,
  s: number | null,
  a: number | null,
  qw: number,
  sw: number,
  aw: number,
): number | null {
  if (q === null || s === null || a === null) return null;
  const weighted = (qw * q + sw * s + aw * a) / 100;
  return Math.round(weighted * 10) / 10;
}

/** Google Maps deep-link to a lat/lng. Falls back to address-search if coords missing. */
export function getMapsUrl(
  lat: number | null,
  lng: number | null,
  address: string | null,
): string | null {
  if (lat !== null && lng !== null) {
    return `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
  }
  if (address) {
    return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address)}`;
  }
  return null;
}

/** Truncate a string for use in meta description tags (≤160 chars, ellipsized cleanly). */
export function truncateForMeta(s: string | null | undefined, max = 160): string {
  if (!s) return "";
  if (s.length <= max) return s;
  const slice = s.slice(0, max - 1);
  const lastSpace = slice.lastIndexOf(" ");
  return (lastSpace > max - 30 ? slice.slice(0, lastSpace) : slice) + "…";
}

/** ISO date "YYYY-MM-DD" -> "May 5, 2026". */
export function formatIsoDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

const PILLAR_LABELS_FULL: Record<string, string> = {
  quality: "Quality & Value",
  service: "Service",
  ambiance: "Ambiance",
};
export function pillarLabel(key: string): string {
  return PILLAR_LABELS_FULL[key] ?? key;
}

/** One-line explanation of why a restaurant is unranked. */
export function unrankedReason(r: CityRestaurantSummary): string {
  const missing: string[] = [];
  if (r.quality_score === null) missing.push("quality");
  if (r.service_score === null) missing.push("service");
  if (r.ambiance_score === null) missing.push("ambiance");
  if (missing.length === 0) return "Not enough data to score";
  if (missing.length === 1) {
    return `Not enough ${missing[0]} reviews for a confident score`;
  }
  return `Not enough ${missing.join(" or ")} reviews for a confident score`;
}
