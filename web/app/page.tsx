import type { Metadata } from "next";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "Prime Index — Chicago Steakhouses, Ranked",
  description:
    "Steakhouses scored on quality, service, and ambiance separately. Built for people who want to know what they're paying for.",
};

export default function HomePage() {
  return (
    <section className="mx-auto flex max-w-3xl flex-col items-center px-6 py-24 text-center sm:py-32 md:py-40">
      <h1 className="font-serif text-4xl leading-[1.05] tracking-tight text-balance sm:text-5xl md:text-6xl">
        The best steakhouses in Chicago, ranked by what actually matters.
      </h1>

      <p className="text-muted-foreground mt-8 max-w-xl text-base leading-relaxed sm:text-lg">
        Quality. Service. Ambiance. Scored separately, so you can see what
        you&rsquo;re actually paying for.
      </p>

      <div className="mt-12">
        <Button asChild size="lg" className="px-8 text-base">
          <Link href="/chicago">See the Chicago ranking</Link>
        </Button>
      </div>

      <p className="mt-6 text-sm">
        <Link
          href="/methodology"
          className="text-muted-foreground hover:text-foreground underline-offset-4 hover:underline"
        >
          How we score
        </Link>
      </p>
    </section>
  );
}
