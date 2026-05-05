import type { Metadata } from "next";
import Link from "next/link";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const playfair = Playfair_Display({
  variable: "--font-serif",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  // URL/canonical fields are filled in at deploy time (step 16).
  title: "Prime Index",
  description: "The best steakhouses in Chicago, ranked by what actually matters.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      // Force dark theme site-wide via shadcn's class-based variant. Without this,
      // some browsers (notably Chrome's "auto dark theme for web content") decide
      // case-by-case whether to invert the page, producing visual inconsistency
      // across routes. Picking the dark palette explicitly removes that ambiguity.
      className={`dark ${inter.variable} ${playfair.variable} h-full antialiased`}
    >
      <body className="bg-background text-foreground flex min-h-full flex-col font-sans">
        <header className="border-border/60 border-b">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
            <Link
              href="/"
              className="font-serif text-2xl tracking-tight hover:opacity-70"
            >
              Prime Index
            </Link>
            <nav className="text-muted-foreground text-sm">
              <Link href="/methodology" className="hover:text-foreground">
                Methodology
              </Link>
            </nav>
          </div>
        </header>
        <main className="flex-1">{children}</main>
        <footer className="border-border/60 text-muted-foreground border-t text-xs">
          <div className="mx-auto max-w-5xl px-6 py-6">
            Powered by Google. Restaurant data refreshed nightly.
          </div>
        </footer>
      </body>
    </html>
  );
}
