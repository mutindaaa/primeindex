"use client";

import Link from "next/link";
import { ChevronRight } from "lucide-react";
import { useCallback, useMemo, useState } from "react";

import { Slider } from "@/components/ui/slider";
import {
  computeWeightedPrime,
  formatPriceTier,
  formatReviewCount,
  formatScore,
  pillarBarColor,
  unrankedReason,
} from "@/lib/format";
import type { CityResponse, CityRestaurantSummary } from "@/lib/types";

const DEFAULT_WEIGHTS = { quality: 40, service: 30, ambiance: 30 } as const;

type WeightKey = "quality" | "service" | "ambiance";
type Weights = Record<WeightKey, number>;

const PILLAR_LABELS: Record<WeightKey, string> = {
  quality: "Quality & Value",
  service: "Service",
  ambiance: "Ambiance",
};

/** Distribute the change in `key` across the other two weights so the sum stays 100. */
function rebalance(prev: Weights, key: WeightKey, newVal: number): Weights {
  const clamped = Math.max(0, Math.min(100, Math.round(newVal)));
  const others = (Object.keys(prev) as WeightKey[]).filter((k) => k !== key);
  const remaining = 100 - clamped;
  const otherSum = prev[others[0]] + prev[others[1]];

  if (otherSum === 0) {
    const half = Math.floor(remaining / 2);
    return {
      ...prev,
      [key]: clamped,
      [others[0]]: half,
      [others[1]]: remaining - half,
    } as Weights;
  }

  const newA = Math.round((prev[others[0]] / otherSum) * remaining);
  const newB = remaining - newA;
  return {
    ...prev,
    [key]: clamped,
    [others[0]]: newA,
    [others[1]]: newB,
  } as Weights;
}

export function RankedList({ data }: { data: CityResponse }) {
  const [weights, setWeights] = useState<Weights>({ ...DEFAULT_WEIGHTS });

  const handleSlider = useCallback(
    (key: WeightKey, vals: number[]) =>
      setWeights((prev) => rebalance(prev, key, vals[0])),
    [],
  );

  const handleReset = useCallback(
    () => setWeights({ ...DEFAULT_WEIGHTS }),
    [],
  );

  const ordered = useMemo(() => {
    const recomputed = data.restaurants.map((r) => ({
      r,
      weightedPrime: computeWeightedPrime(
        r.quality_score,
        r.service_score,
        r.ambiance_score,
        weights.quality,
        weights.service,
        weights.ambiance,
      ),
    }));
    recomputed.sort((a, b) => {
      if (a.weightedPrime === null && b.weightedPrime === null)
        return a.r.name.localeCompare(b.r.name);
      if (a.weightedPrime === null) return 1;
      if (b.weightedPrime === null) return -1;
      return b.weightedPrime - a.weightedPrime;
    });
    return recomputed;
  }, [data.restaurants, weights]);

  const ranked = ordered.filter((x) => x.weightedPrime !== null);
  const unranked = ordered.filter((x) => x.weightedPrime === null);

  const isDefault =
    weights.quality === DEFAULT_WEIGHTS.quality &&
    weights.service === DEFAULT_WEIGHTS.service &&
    weights.ambiance === DEFAULT_WEIGHTS.ambiance;

  return (
    <>
      <section
        aria-labelledby="weights-heading"
        className="border-border/60 mb-10 rounded-lg border p-5 sm:p-6"
      >
        <div className="mb-4 flex items-baseline justify-between">
          <h2
            id="weights-heading"
            className="text-foreground text-sm font-medium tracking-wide uppercase"
          >
            Weighting
          </h2>
          <button
            type="button"
            onClick={handleReset}
            disabled={isDefault}
            className="text-muted-foreground hover:text-foreground text-xs underline-offset-4 hover:underline disabled:opacity-40 disabled:no-underline"
          >
            Reset to default
          </button>
        </div>
        <div className="grid gap-5 sm:grid-cols-3 sm:gap-8">
          {(Object.keys(PILLAR_LABELS) as WeightKey[]).map((key) => (
            <div key={key} className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between text-sm">
                <label htmlFor={`slider-${key}`} className="font-medium">
                  {PILLAR_LABELS[key]}
                </label>
                <span className="text-muted-foreground tabular-nums font-mono text-xs">
                  {weights[key]}
                </span>
              </div>
              <Slider
                id={`slider-${key}`}
                value={[weights[key]]}
                min={0}
                max={100}
                step={1}
                onValueChange={(vals) => handleSlider(key, vals)}
              />
            </div>
          ))}
        </div>
      </section>

      <ol className="divide-border/60 divide-y">
        {ranked.map((item, idx) => (
          <RestaurantRow
            key={item.r.slug}
            r={item.r}
            rank={idx + 1}
            weightedPrime={item.weightedPrime}
          />
        ))}
      </ol>

      {unranked.length > 0 && (
        <section className="mt-12">
          <h2 className="text-muted-foreground mb-4 text-xs font-medium tracking-widest uppercase">
            Not enough data to score
          </h2>
          <ol className="divide-border/60 divide-y">
            {unranked.map((item) => (
              <RestaurantRow
                key={item.r.slug}
                r={item.r}
                rank={null}
                weightedPrime={null}
                reason={unrankedReason(item.r)}
              />
            ))}
          </ol>
        </section>
      )}
    </>
  );
}

function RestaurantRow({
  r,
  rank,
  weightedPrime,
  reason,
}: {
  r: CityRestaurantSummary;
  rank: number | null;
  weightedPrime: number | null;
  reason?: string;
}) {
  const tier = formatPriceTier(r.price_tier);
  return (
    <li>
      <Link
        href={`/restaurant/${r.slug}`}
        className="group hover:bg-muted/40 -mx-3 flex gap-4 rounded-md px-3 py-6 transition-colors sm:gap-6"
      >
        <div className="font-serif text-muted-foreground group-hover:text-foreground w-10 shrink-0 text-2xl tabular-nums sm:w-14 sm:text-3xl">
          {rank !== null ? `#${rank}` : "—"}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-base font-medium sm:text-lg">
                {r.name}
              </h3>
              <p className="text-muted-foreground mt-0.5 text-xs sm:text-sm">
                {r.neighborhood ?? ""}
              </p>
            </div>
            <div className="text-right">
              <div className="font-serif text-3xl leading-none tabular-nums sm:text-4xl">
                {weightedPrime !== null ? weightedPrime.toFixed(1) : "—"}
              </div>
              <p
                className={`text-muted-foreground mt-1 text-xs ${
                  tier.missing ? "italic" : ""
                }`}
              >
                {tier.symbol}
              </p>
              <p className="text-muted-foreground text-xs">
                from {formatReviewCount(r.google_review_count)} reviews
              </p>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-3 sm:gap-5">
            <PillarBar label="Q" score={r.quality_score} />
            <PillarBar label="S" score={r.service_score} />
            <PillarBar label="A" score={r.ambiance_score} />
          </div>

          {reason ? (
            <p className="text-muted-foreground mt-3 text-xs italic">
              {reason}
            </p>
          ) : r.house_take ? (
            <p className="text-muted-foreground font-serif mt-3 line-clamp-1 text-sm italic">
              &ldquo;{r.house_take}&rdquo;
            </p>
          ) : null}
        </div>

        <ChevronRight
          className="text-muted-foreground/0 group-hover:text-muted-foreground/60 mt-1 hidden self-start transition-colors sm:block"
          size={18}
          aria-hidden
        />
      </Link>
    </li>
  );
}

function PillarBar({
  label,
  score,
}: {
  label: "Q" | "S" | "A";
  score: number | null;
}) {
  const pct = score === null ? 0 : Math.max(0, Math.min(100, score));
  const fill = pillarBarColor(score);
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground font-mono w-3 shrink-0">
        {label}
      </span>
      <div
        className="bg-muted/70 relative h-1.5 flex-1 overflow-hidden rounded-full"
        role="progressbar"
        aria-label={`${label} score`}
        aria-valuenow={score ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tabular-nums w-9 shrink-0 text-right">
        {formatScore(score)}
      </span>
    </div>
  );
}
