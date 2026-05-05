import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft, ExternalLink } from "lucide-react";

import { ApiError, getRestaurant } from "@/lib/api";
import {
  formatIsoDate,
  formatPriceTier,
  formatReviewCount,
  formatScore,
  getMapsUrl,
  pillarBarColor,
  pillarLabel,
  truncateForMeta,
} from "@/lib/format";
import type { PillarDetail, PillarKey, RestaurantDetail } from "@/lib/types";

export const dynamic = "force-dynamic";

const PILLARS: PillarKey[] = ["quality", "service", "ambiance"];

const AMBIANCE_UNRANKED_EXPLANATION =
  "We didn't see enough ambiance content in this restaurant's reviews to score this pillar confidently. As more reviews come in, this will be filled in.";

async function fetchOr404(slug: string): Promise<RestaurantDetail> {
  try {
    return await getRestaurant(slug, "no-store");
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) notFound();
    throw e;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  try {
    const data = await getRestaurant(slug, "no-store");
    return {
      title: `${data.name} — Prime Index`,
      description: truncateForMeta(data.house_take) || `${data.name} on Prime Index.`,
    };
  } catch {
    return { title: "Not found — Prime Index" };
  }
}

export default async function RestaurantPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const data = await fetchOr404(slug);
  const tier = formatPriceTier(data.price_tier);
  const mapsUrl = getMapsUrl(data.lat, data.lng, data.address);

  return (
    <article className="mx-auto max-w-4xl px-6 py-10 sm:py-14">
      <p className="mb-8">
        <Link
          href="/chicago"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ChevronLeft size={16} aria-hidden />
          Back to all Chicago steakhouses
        </Link>
      </p>

      <header className="mb-12">
        <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">
          {data.name}
        </h1>

        <p className="text-muted-foreground mt-3 text-sm sm:text-base">
          {data.neighborhood ?? "Chicago"}
          {" · "}
          {tier.missing ? (
            <span className="italic">{tier.symbol}</span>
          ) : (
            <span className="tracking-wide">{tier.symbol}</span>
          )}
        </p>

        {data.address ? (
          <p className="mt-2 text-sm">
            {mapsUrl ? (
              <a
                href={mapsUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 underline-offset-4 hover:underline"
              >
                {data.address}
                <ExternalLink size={12} aria-hidden />
              </a>
            ) : (
              <span className="text-muted-foreground">{data.address}</span>
            )}
          </p>
        ) : null}

        <div className="mt-6 flex flex-wrap gap-2 text-xs">
          <Chip>
            {data.prime_score !== null
              ? `Prime Score ${formatScore(data.prime_score)}`
              : "Score not available"}
          </Chip>
          <Chip>
            {`Q ${formatScore(data.quality_score, 0)} · S ${formatScore(
              data.service_score,
              0,
            )} · A ${formatScore(data.ambiance_score, 0)}`}
          </Chip>
          <Chip>
            {`from ${formatReviewCount(data.google_review_count)} reviews`}
          </Chip>
        </div>

        {data.house_take ? (
          <p className="text-foreground/90 font-serif mt-8 max-w-2xl text-lg leading-relaxed italic">
            &ldquo;{data.house_take}&rdquo;
          </p>
        ) : null}
      </header>

      <section
        aria-labelledby="pillar-cards-heading"
        className="mt-12 grid gap-5 md:grid-cols-3"
      >
        <h2 id="pillar-cards-heading" className="sr-only">
          Pillar breakdown
        </h2>
        {PILLARS.map((p) => (
          <PillarCard key={p} pillarKey={p} pillar={data.pillars[p]} />
        ))}
      </section>

      <section className="mt-16 border-t border-border/60 pt-10">
        <h2 className="text-foreground text-sm font-medium tracking-widest uppercase">
          Methodology
        </h2>
        <p className="text-muted-foreground mt-4 max-w-3xl text-sm leading-relaxed">
          Scores computed from {data.sources.google_reviews} Google review
          {data.sources.google_reviews === 1 ? "" : "s"}
          {data.sources.date_range
            ? ` posted between ${formatIsoDate(
                data.sources.date_range.start,
              )} and ${formatIsoDate(data.sources.date_range.end)}`
            : ""}
          , classified by an AI model into pillars and weighted with time-decay
          (recent reviews count more). Reddit local sentiment is planned for a
          future version.{" "}
          <Link
            href="/methodology"
            className="text-foreground underline-offset-4 hover:underline"
          >
            Read the methodology →
          </Link>
        </p>
      </section>

      <p className="mt-12">
        <Link
          href="/chicago"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ChevronLeft size={16} aria-hidden />
          All Chicago steakhouses
        </Link>
      </p>
    </article>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="border-border/60 text-foreground inline-flex items-center rounded-full border px-3 py-1 font-mono tabular-nums">
      {children}
    </span>
  );
}

function PillarCard({
  pillarKey,
  pillar,
}: {
  pillarKey: PillarKey;
  pillar: PillarDetail;
}) {
  const isAmbianceUnranked =
    pillarKey === "ambiance" && pillar.score === null;
  const themesPos = uniqStrings(pillar.themes_pos);
  const themesNeg = uniqStrings(pillar.themes_neg);
  const quotes = dedupQuotes(pillar.quotes);
  const pct =
    pillar.score === null ? 0 : Math.max(0, Math.min(100, pillar.score));

  return (
    <div className="border-border/60 rounded-lg border p-6">
      <h3 className="font-serif text-xl tracking-tight">
        {pillarLabel(pillarKey)}
      </h3>

      <p className="font-serif mt-2 text-3xl tabular-nums sm:text-4xl">
        {pillar.score !== null ? formatScore(pillar.score) : "—"}
      </p>

      <div
        className="bg-muted/70 relative mt-3 h-1.5 overflow-hidden rounded-full"
        role="progressbar"
        aria-label={`${pillarLabel(pillarKey)} score`}
        aria-valuenow={pillar.score ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`absolute inset-y-0 left-0 rounded-full ${pillarBarColor(pillar.score)}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {isAmbianceUnranked ? (
        <p className="text-muted-foreground mt-6 text-sm leading-relaxed">
          {AMBIANCE_UNRANKED_EXPLANATION}
        </p>
      ) : (
        <>
          {themesPos.length > 0 ? (
            <div className="mt-6">
              <h4 className="text-muted-foreground text-xs font-medium tracking-widest uppercase">
                What people praise
              </h4>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {themesPos.map((t) => (
                  <ThemePill key={`pos-${t}`}>{t}</ThemePill>
                ))}
              </div>
            </div>
          ) : null}

          {themesNeg.length > 0 ? (
            <div className="mt-5">
              <h4 className="text-muted-foreground text-xs font-medium tracking-widest uppercase">
                What people criticize
              </h4>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {themesNeg.map((t) => (
                  <ThemePill key={`neg-${t}`}>{t}</ThemePill>
                ))}
              </div>
            </div>
          ) : null}

          {quotes.length > 0 ? (
            <div className="mt-6">
              <h4 className="text-muted-foreground text-xs font-medium tracking-widest uppercase">
                From reviews
              </h4>
              <div className="mt-3 flex flex-col gap-4">
                {quotes.slice(0, 3).map((q, i) => (
                  <blockquote
                    key={`${q.url ?? "noref"}-${i}`}
                    className="border-muted/60 border-l-2 pl-3"
                  >
                    <p className="font-serif text-sm leading-relaxed italic">
                      &ldquo;{q.text}&rdquo;
                    </p>
                    {q.url ? (
                      <a
                        href={q.url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-muted-foreground hover:text-foreground mt-1 inline-flex items-center gap-1 text-xs underline-offset-4 hover:underline"
                      >
                        → source
                        <ExternalLink size={10} aria-hidden />
                      </a>
                    ) : null}
                  </blockquote>
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}

      <p className="text-muted-foreground mt-6 text-xs">
        {isAmbianceUnranked
          ? `Based on ${pillar.n_sentences} sentence${pillar.n_sentences === 1 ? "" : "s"}`
          : `Based on ${pillar.n_sentences} sentence${pillar.n_sentences === 1 ? "" : "s"}`}
      </p>
    </div>
  );
}

function ThemePill({ children }: { children: React.ReactNode }) {
  return (
    <span className="border-border/60 text-muted-foreground inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs">
      {children}
    </span>
  );
}

function uniqStrings(items: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const s of items) {
    const key = s.trim().toLowerCase();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    out.push(s.trim());
  }
  return out;
}

function dedupQuotes<T extends { text: string }>(quotes: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const q of quotes) {
    const key = q.text.trim().toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(q);
  }
  return out;
}
