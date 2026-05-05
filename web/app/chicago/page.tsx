import type { Metadata } from "next";

import { getCity } from "@/lib/api";
import { formatDate } from "@/lib/format";

import { RankedList } from "./RankedList";

export const metadata: Metadata = {
  title: "Chicago Steakhouses — Prime Index",
  description:
    "Chicago steakhouses ranked by quality, service, and ambiance. Drag the sliders to weight what matters to you.",
};

// Always fetch fresh — no caching at the page level.
export const dynamic = "force-dynamic";

export default async function ChicagoPage() {
  const data = await getCity("chicago", { cache: "no-store" });
  const totalReviewsUsed = data.restaurants.reduce(
    (acc, r) => acc + (r.google_review_count_used ?? 0),
    0,
  );

  return (
    <div className="mx-auto max-w-4xl px-6 py-12 sm:py-16">
      <header className="mb-12">
        <h1 className="font-serif text-4xl tracking-tight sm:text-5xl">
          Chicago Steakhouses
        </h1>
        <p className="text-muted-foreground mt-3 text-sm sm:text-base">
          Ranked by what actually matters. {data.restaurants.length} restaurants,
          scored from {totalReviewsUsed.toLocaleString("en-US")} reviews. Last
          updated {formatDate(data.computed_at)}.
        </p>
      </header>

      <RankedList data={data} />
    </div>
  );
}
