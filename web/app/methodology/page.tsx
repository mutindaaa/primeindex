import type { Metadata } from "next";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { promises as fs } from "node:fs";
import path from "node:path";
import { compileMDX } from "next-mdx-remote/rsc";
import type { ComponentPropsWithoutRef } from "react";

export const metadata: Metadata = {
  title: "How Prime Index works — Methodology",
  description:
    "How Prime Index scores Chicago steakhouses across quality, service, and ambiance using AI-classified review sentences.",
};

// Static at request time. Re-rendered on each request in dev; cached in prod by
// default since the markdown rarely changes. Force-dynamic isn't required.
export const dynamic = "force-static";

const METHODOLOGY_FILENAME = path.join("docs", "methodology.md");

/** Try several locations so the file resolves whether the deploy root is the
 *  monorepo root or `web/` itself. */
async function readMethodologyMarkdown(): Promise<string> {
  const cwd = process.cwd();
  const candidates = [
    path.resolve(cwd, METHODOLOGY_FILENAME),                  // deploy root = repo root
    path.resolve(cwd, "..", METHODOLOGY_FILENAME),            // deploy root = web/
    path.resolve(cwd, "..", "..", METHODOLOGY_FILENAME),      // monorepo nesting
  ];
  for (const p of candidates) {
    try {
      return await fs.readFile(p, "utf8");
    } catch {
      // try next
    }
  }
  throw new Error(
    `docs/methodology.md not found. Tried: ${candidates.join(", ")}`,
  );
}

// MDX components — match the editorial palette established by the homepage and
// /chicago, since the prose plugin would impose its own opinionated typography.
const mdxComponents = {
  h1: (props: ComponentPropsWithoutRef<"h1">) => (
    <h1
      className="font-serif text-4xl tracking-tight sm:text-5xl"
      {...props}
    />
  ),
  h2: (props: ComponentPropsWithoutRef<"h2">) => (
    <h2
      className="font-serif text-foreground mt-12 mb-4 text-2xl tracking-tight sm:text-3xl"
      {...props}
    />
  ),
  h3: (props: ComponentPropsWithoutRef<"h3">) => (
    <h3
      className="font-serif text-foreground mt-8 mb-3 text-xl tracking-tight"
      {...props}
    />
  ),
  p: (props: ComponentPropsWithoutRef<"p">) => (
    <p
      className="text-foreground/90 mt-4 text-base leading-relaxed"
      {...props}
    />
  ),
  ul: (props: ComponentPropsWithoutRef<"ul">) => (
    <ul
      className="text-foreground/90 mt-4 ml-5 list-disc space-y-2 text-base leading-relaxed"
      {...props}
    />
  ),
  ol: (props: ComponentPropsWithoutRef<"ol">) => (
    <ol
      className="text-foreground/90 mt-4 ml-5 list-decimal space-y-2 text-base leading-relaxed"
      {...props}
    />
  ),
  li: (props: ComponentPropsWithoutRef<"li">) => (
    <li className="pl-1 leading-relaxed" {...props} />
  ),
  strong: (props: ComponentPropsWithoutRef<"strong">) => (
    <strong className="text-foreground font-medium" {...props} />
  ),
  em: (props: ComponentPropsWithoutRef<"em">) => (
    <em className="italic" {...props} />
  ),
  blockquote: (props: ComponentPropsWithoutRef<"blockquote">) => (
    <blockquote
      className="border-border my-6 border-l-2 py-1 pl-4 font-serif text-lg italic"
      {...props}
    />
  ),
  a: (props: ComponentPropsWithoutRef<"a">) => {
    const isExternal =
      typeof props.href === "string" && /^https?:\/\//.test(props.href);
    return (
      <a
        className="text-foreground underline-offset-4 hover:underline"
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noreferrer noopener" : undefined}
        {...props}
      />
    );
  },
  code: (props: ComponentPropsWithoutRef<"code">) => (
    <code
      className="bg-muted text-foreground rounded px-1 py-0.5 font-mono text-sm"
      {...props}
    />
  ),
  hr: (props: ComponentPropsWithoutRef<"hr">) => (
    <hr className="border-border/60 my-12" {...props} />
  ),
};

export default async function MethodologyPage() {
  const source = await readMethodologyMarkdown();
  const { content } = await compileMDX({
    source,
    components: mdxComponents,
    options: { parseFrontmatter: false },
  });

  return (
    <article className="mx-auto max-w-3xl px-6 py-10 sm:py-14">
      <p className="mb-8">
        <Link
          href="/chicago"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ChevronLeft size={16} aria-hidden />
          Back to Chicago ranking
        </Link>
      </p>
      {content}
      <p className="mt-16">
        <Link
          href="/chicago"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm"
        >
          <ChevronLeft size={16} aria-hidden />
          Back to Chicago ranking
        </Link>
      </p>
    </article>
  );
}
