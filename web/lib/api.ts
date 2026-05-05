// Typed fetch wrappers for the FastAPI backend. Reads NEXT_PUBLIC_API_BASE_URL
// (defaults to http://localhost:8000 in dev). Exposes getCity / getRestaurant.

import type { CityResponse, RestaurantDetail, Weights } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // body wasn't JSON; keep statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export interface GetCityOptions {
  weights?: Partial<Weights>;
  cache?: RequestCache;
}

export async function getCity(
  citySlug: string,
  options: GetCityOptions = {},
): Promise<CityResponse> {
  const params = new URLSearchParams();
  const { weights, cache } = options;
  if (weights?.quality !== undefined)
    params.set("quality_weight", weights.quality.toString());
  if (weights?.service !== undefined)
    params.set("service_weight", weights.service.toString());
  if (weights?.ambiance !== undefined)
    params.set("ambiance_weight", weights.ambiance.toString());
  const qs = params.toString();
  return request<CityResponse>(
    `/api/cities/${encodeURIComponent(citySlug)}${qs ? `?${qs}` : ""}`,
    cache ? { cache } : undefined,
  );
}

export async function getRestaurant(
  slug: string,
  cache?: RequestCache,
): Promise<RestaurantDetail> {
  return request<RestaurantDetail>(
    `/api/restaurants/${encodeURIComponent(slug)}`,
    cache ? { cache } : undefined,
  );
}
