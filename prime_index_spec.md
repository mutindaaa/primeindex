# Prime Index — Technical Spec (MVP, Chicago)

This is the build doc you hand to Claude Code (or future-you in a terminal). It is opinionated. Where two ways exist, I've picked one. Don't deviate without a reason. By the end of this doc, a Claude Code session can scaffold and ship the MVP without further architectural input.

---

## 0. Domain & branding

**Status of the name "Prime Index":**
- `primeindex.com` is **taken** (parked for resale — someone's holding it. Avoid.)
- `primeindex.io` — **available**
- `primeindex.app` — **available**
- `primeindex.co` — **available**
- `getprimeindex.com` — **available**

**Recommendation: register `primeindex.io`.**

Reasoning: `.io` is the strongest tech-product TLD after `.com`. It signals "real product, not a parked toy." `.app` forces HTTPS (good) but reads as "mobile app" which we're not. `.co` is fine but reads as a company name, not a tool. `getprimeindex.com` is ugly. `.io` is the right move.

Cost: ~$35–55/year on Namecheap or Cloudflare Registrar. Buy with WHOIS privacy on. **Do not pay for hosting bundles or "premium" upsells** — you don't need them.

> **Verify before buying.** DNS-based availability checking is a strong signal but not 100%. Search `primeindex.io` on Namecheap or Cloudflare Registrar before paying.

---

## 1. Product surface (what the user actually sees)

Three pages. That's the entire MVP.

### Page 1: `/` (homepage)
Single hero: **"The best steakhouses in Chicago, ranked by what actually matters."**
Below the hero: a static "Methodology" link, a single CTA button → `/chicago`.
Footer: small attribution to data sources (required by Google's ToS).

### Page 2: `/chicago` (the ranked list)
- Top of page: three weight sliders for **Quality & Value / Service / Ambiance**, defaulting to 40/30/30. Sliders sum to 100. Changing them re-sorts the list client-side instantly.
- Below: ranked list of ~25 Chicago steakhouses. Each row shows:
  - Rank, name, neighborhood
  - Prime Score (big, bold, 0–100)
  - Three small pillar bars (Q/S/A)
  - Price tier ($–$$$$)
  - One-sentence "house take" (we generate this from reviews, more on this in §6)
- Click a row → `/restaurant/[slug]`

### Page 3: `/restaurant/[slug]` (the breakdown)
- Header: name, neighborhood, price tier, Prime Score, link to Google Maps + their website
- Three pillar cards. Each card contains:
  - The pillar score (0–100)
  - 2–3 representative quoted snippets from reviews (Google or Reddit, attributed)
  - Top recurring positive themes and top recurring negative themes (1-line each)
- "Sources" section: counts of how many Google reviews and Reddit mentions were analyzed, with a date range
- "Last updated" timestamp

**Out of scope for MVP** (do not build, no matter how tempted):
- User accounts, favorites, login of any kind
- Map view
- Photos
- Booking/reservation links
- Multiple cities
- Search bar (25 restaurants don't need search)
- Mobile app
- Dark mode toggle (just pick one and ship)

---

## 2. Tech stack — final decisions

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js 15 (App Router) + TypeScript + Tailwind** | Vercel-native, fast, the standard. App Router is the current default. |
| Backend | **FastAPI (Python 3.12)** | You already use Python. Pydantic models = automatic API contracts. Same Python you used in Stone AI. |
| Database | **SQLite** in dev, **Postgres** in prod (via Supabase free tier) | SQLite for fast iteration locally. Supabase Postgres in prod gives you a real DB plus free hosting plus easy backups. |
| ORM | **SQLAlchemy 2.0 + Alembic for migrations** | Standard. Don't use raw SQL in app code. |
| LLM classifier | **Anthropic API, claude-haiku-4-5-20251001** | Cheapest fast Claude. Genuinely good at structured output. ~$1/M input tokens. |
| Reddit | **PRAW** (Python Reddit API Wrapper) | Standard library. Free tier covers you. |
| Google Places | **`googlemaps` Python client** | Official. Stable. |
| Background jobs | **GitHub Actions cron** | Free for public repos. Runs nightly. No infra to manage. |
| Frontend hosting | **Vercel** | Free tier, push-to-deploy. |
| Backend hosting | **Render** (free Web Service) or **Fly.io** | Render is simpler for first deploy; Fly is cheaper if you outgrow free. Start with Render. |
| Domain registrar | **Cloudflare Registrar** | At-cost pricing, no upsells, free WHOIS privacy. |
| Secret management | **`.env` files locally, platform secrets in prod** | Don't commit keys. |
| Monitoring | **Sentry free tier** | Catches errors. Set it up day one. |

**Languages and versions to pin in `pyproject.toml` and `package.json`:** Python 3.12, Node 20 LTS, Next.js 15.x.

---

## 3. Repository layout

Single monorepo. Two top-level packages.

```
primeindex/
├── README.md
├── .gitignore
├── .env.example
├── api/                         # FastAPI backend
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── config.py            # env vars, Pydantic Settings
│   │   ├── db.py                # SQLAlchemy session
│   │   ├── models.py            # SQLAlchemy models
│   │   ├── schemas.py           # Pydantic response models
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── cities.py        # GET /cities/{slug}
│   │   │   └── restaurants.py   # GET /restaurants/{slug}
│   │   ├── ingest/
│   │   │   ├── __init__.py
│   │   │   ├── google_places.py # Google Places client + ingest
│   │   │   ├── reddit.py        # PRAW client + ingest
│   │   │   └── seed_chicago.py  # One-shot script: seed the 25 places
│   │   ├── classify/
│   │   │   ├── __init__.py
│   │   │   ├── claude_client.py # Anthropic client wrapper
│   │   │   └── classifier.py    # Sentence → {pillar, sentiment} pipeline
│   │   ├── score/
│   │   │   ├── __init__.py
│   │   │   └── scorer.py        # Pillar aggregation + Prime Score
│   │   └── jobs/
│   │       ├── __init__.py
│   │       └── nightly.py       # The cron entrypoint
│   └── tests/
├── web/                         # Next.js frontend
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── app/
│       ├── layout.tsx
│       ├── page.tsx             # Homepage
│       ├── globals.css
│       ├── chicago/
│       │   └── page.tsx         # Ranked list
│       └── restaurant/
│           └── [slug]/
│               └── page.tsx     # Breakdown
├── .github/
│   └── workflows/
│       ├── nightly.yml          # Cron: run ingest + classify + score
│       └── ci.yml               # PR tests
└── docs/
    └── methodology.md           # Public-facing methodology writeup
```

---

## 4. Database schema

Plain English first, then SQL.

**`restaurants`** — the canonical list. One row per place. Sourced from Google Places.

**`reviews`** — raw reviews from any source. One row per review (Google review, Reddit comment/post mentioning the place).

**`sentences`** — every review broken into sentences, classified by Claude. The unit of analysis.

**`scores`** — computed nightly. One row per restaurant per scoring run, so we keep history and can show trend over time later.

```sql
-- restaurants
CREATE TABLE restaurants (
  id              SERIAL PRIMARY KEY,
  slug            TEXT UNIQUE NOT NULL,         -- "bavettes-chicago"
  google_place_id TEXT UNIQUE NOT NULL,         -- from Google Places API
  name            TEXT NOT NULL,
  city            TEXT NOT NULL,                -- "chicago" for MVP
  neighborhood    TEXT,
  address         TEXT,
  lat             DOUBLE PRECISION,
  lng             DOUBLE PRECISION,
  price_tier      INT,                          -- 1-4 ($-$$$$)
  google_rating   DOUBLE PRECISION,
  google_review_count INT,
  website         TEXT,
  phone           TEXT,
  active          BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMPTZ DEFAULT NOW(),
  updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- reviews (raw)
CREATE TABLE reviews (
  id              SERIAL PRIMARY KEY,
  restaurant_id   INT REFERENCES restaurants(id) ON DELETE CASCADE,
  source          TEXT NOT NULL,                -- 'google' | 'reddit'
  source_id       TEXT NOT NULL,                -- Google review id, Reddit comment/post id
  source_url      TEXT,
  author          TEXT,
  body            TEXT NOT NULL,
  rating          DOUBLE PRECISION,             -- Google 1-5; null for Reddit
  reddit_score    INT,                          -- upvotes; null for Google
  posted_at       TIMESTAMPTZ,
  ingested_at     TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (source, source_id)
);
CREATE INDEX idx_reviews_restaurant ON reviews(restaurant_id);

-- sentences (post-classification)
CREATE TABLE sentences (
  id              SERIAL PRIMARY KEY,
  review_id       INT REFERENCES reviews(id) ON DELETE CASCADE,
  text            TEXT NOT NULL,
  pillar          TEXT NOT NULL,                -- 'quality' | 'service' | 'ambiance' | 'other'
  sentiment       DOUBLE PRECISION NOT NULL,    -- -1.0 to 1.0
  classifier_version TEXT NOT NULL,             -- "haiku-4-5-v1"
  classified_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_sentences_review ON sentences(review_id);
CREATE INDEX idx_sentences_pillar ON sentences(pillar);

-- scores (computed nightly, append-only)
CREATE TABLE scores (
  id              SERIAL PRIMARY KEY,
  restaurant_id   INT REFERENCES restaurants(id) ON DELETE CASCADE,
  quality_score   DOUBLE PRECISION,             -- 0-100
  service_score   DOUBLE PRECISION,
  ambiance_score  DOUBLE PRECISION,
  prime_score     DOUBLE PRECISION,             -- composite at default 40/30/30 weights
  google_review_count_used INT,
  reddit_mention_count_used INT,
  date_range_start DATE,
  date_range_end   DATE,
  computed_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_scores_restaurant_computed ON scores(restaurant_id, computed_at DESC);
```

The frontend reads only the most recent `scores` row per restaurant. The user-adjustable weights happen client-side: we send the three pillar scores down, and JS recomputes the composite.

---

## 5. The seed list — Chicago steakhouses (you supply these)

For the MVP, we don't auto-discover restaurants. We hand-pick 25 and feed Google Place IDs into the seed script. This is the one piece **you** do (not Claude Code), because (a) you know Chicago and (b) auto-discovery introduces noise we don't want for a 25-restaurant launch.

The seed list should include the obvious ones (Bavette's, RPM, Gibson's, Mastro's, Maple & Ash, Joe's, Swift & Sons, Prime & Provisions, Boeufhaus, Rosebud Steakhouse, etc.) plus a few less-obvious that you personally want benchmarked. Do this part on a Sunday afternoon — search each on Google Maps, copy the place ID from the URL, drop into a CSV.

Format: `data/chicago_seed.csv` with columns `name, google_place_id, neighborhood`. The seed script reads this and populates the `restaurants` table.

---

## 6. The classifier (the heart of the product)

One Claude call per review. Batch sentences within a review into a single prompt. Use **claude-haiku-4-5-20251001** for cost; it handles this task fine.

### Prompt

System prompt (set once, reuse):

```
You are a review analyst. You will receive a single restaurant review. Break it into sentences. For each sentence, return:
- "text": the sentence verbatim
- "pillar": exactly one of "quality", "service", "ambiance", or "other"
- "sentiment": a float from -1.0 (very negative) to 1.0 (very positive); 0.0 means neutral or factual

Pillar definitions:
- "quality" = the food itself, including taste, preparation, portions, ingredients, and whether the price is justified by the food
- "service" = waitstaff, hosts, sommelier, kitchen pacing, attentiveness, knowledge, friendliness
- "ambiance" = decor, noise level, lighting, cleanliness (including bathrooms), crowd, vibe
- "other" = anything that doesn't fit the three above (parking, location, reservations, etc.)

Return ONLY a JSON object of the form: {"sentences": [{"text": "...", "pillar": "...", "sentiment": 0.0}, ...]}
No prose, no markdown fencing.
```

User message: the review body.

### Why Haiku and not a fine-tuned model
- Cost: ~$1/M input tokens, ~$5/M output. A typical review is ~150 tokens in, ~300 tokens out. 25 restaurants × ~80 reviews each × $0.000001 × ~450 tokens ≈ under $1 for the entire MVP corpus. Negligible.
- Accuracy: structured tagging at the sentence level is something modern Claude does very reliably. You don't need a fine-tune.
- Iteration speed: prompt changes ship instantly. Fine-tune iteration is days.

### Claude API in this product
The MVP uses the Anthropic API server-side from the FastAPI backend. The model identifier is `claude-haiku-4-5-20251001`. Set max_tokens to 2000 (well above worst-case output), use the standard messages endpoint, pass the API key via `ANTHROPIC_API_KEY` env var. Validate the JSON response and on parse failure, retry once with temperature lowered to 0.

### Caching
Hash each review body. If we've classified that exact text before with the current `classifier_version`, skip. This matters when Google returns the same 5 reviews on every refresh.

---

## 7. The scorer

Runs nightly after ingest + classify. For each restaurant:

```python
def score_pillar(sentences, pillar: str, recency_decay_days: int = 365) -> float:
    """Return a 0-100 pillar score."""
    pillar_sentences = [s for s in sentences if s.pillar == pillar]
    if not pillar_sentences:
        return None  # not enough data; UI shows "—"

    # Time-decay: a sentence from a review posted today gets weight 1.0;
    # one from a year ago gets ~0.37 (e^-1).
    weights = []
    sentiments = []
    now = datetime.utcnow()
    for s in pillar_sentences:
        age_days = (now - s.review.posted_at).days
        w = math.exp(-age_days / recency_decay_days)
        weights.append(w)
        sentiments.append(s.sentiment)

    weighted_mean = sum(w*v for w,v in zip(weights, sentiments)) / sum(weights)
    # weighted_mean is in [-1, 1]; map to [0, 100]
    return round((weighted_mean + 1) * 50, 1)
```

### Quality & Value adjustment
For the `quality` pillar specifically, after computing the base score, adjust by price tier. The intuition: a $$$$ restaurant is held to a higher bar.

```python
PRICE_PENALTY = {1: 0, 2: 0, 3: -2, 4: -5}
quality_score += PRICE_PENALTY[restaurant.price_tier]
quality_score = max(0, min(100, quality_score))
```

This is conservative. The first version should not over-engineer this. We can iterate after launch.

### Composite Prime Score
```python
prime_score = 0.4 * quality + 0.3 * service + 0.3 * ambiance
```

Stored in the DB at the default weights. The frontend lets users adjust, but we always store the canonical 40/30/30.

### Minimum sample sizes
- Skip pillar scoring entirely if fewer than 5 classified sentences for that pillar
- Skip the restaurant entirely if fewer than 20 total reviews ingested

The UI handles `null` pillar scores by showing a dash, not a zero.

---

## 8. Reddit ingestion — the differentiator

The whole "what locals actually say" story rides on this. Build it carefully.

### What to search

PRAW lets you search subreddits with keywords. For each restaurant in the seed list:

```
For each restaurant `r`:
  For each subreddit in [chicago, AskChicago, ChicagoFood, FoodChicago, steak, FoodPorn]:
    search the subreddit for r.name (last 2 years)
    for each matching post: ingest the post body + all top-level comments
```

Filter for relevance: drop any post/comment under 30 characters or with a Reddit score below 1.

### Auth setup
Register a "script" type app at https://www.reddit.com/prefs/apps. You get a client ID and secret. Use OAuth, not unauthenticated. Set a clear `user_agent` like `prime-index/0.1 by u/yourusername`.

### Rate limits
100 req/min on the free tier is plenty for 25 restaurants × 6 subreddits × monthly refresh. Add `time.sleep(1.1)` between requests anyway — Reddit penalizes bursty clients.

### What to store
Each post = 1 row in `reviews` with source='reddit'. Each top-level comment = 1 row. Don't go deeper than top-level comments — replies-of-replies are usually noise.

### Important: don't be a bot
Reddit's API ToS specifically forbids automated content extraction beyond the limits and requires non-commercial use unless you have a contract. For a portfolio project shown to friends and family this is fine. Do not commercialize without a contract.

---

## 9. Google Places ingestion

Use the **Places API (New)** — `places.googleapis.com/v1/places/...`. Don't use the legacy Places API; Google is sunsetting it.

### Cost management
- Place Details (with reviews field): ~$17/1000 calls, but Google gives 5,000 free Pro events per month
- 25 restaurants × refreshed weekly = 100 calls/month. Free tier covers it 50× over.
- **Set a budget cap of $5/month in Google Cloud Console.** This is a hard guardrail against bugs.

### Field masking
Always send a `FieldMask` header listing exactly the fields you want. This both saves money (you're billed at the highest tier of any field requested) and reduces payload. For our needs:

```
X-Goog-FieldMask: id,displayName,formattedAddress,location,priceLevel,
                  rating,userRatingCount,websiteUri,internationalPhoneNumber,
                  reviews
```

`reviews` is a Pro tier field. Everything else is Essentials/Pro. We're paying Pro rates for the Place Details call; the FieldMask just keeps us off Enterprise.

### Attribution
Google ToS requires "Powered by Google" attribution somewhere on any page that displays Google data, plus you can't permanently store reviews more than 30 days. The DB schema accommodates this — we store reviews, score them, and rotate them out on the next refresh. (Sentences derived from those reviews are derived works and keepable; the verbatim review text is what has the 30-day cap.)

We can quote *short excerpts* of reviews in the UI under fair use, but should not reproduce full reviews. Keep displayed quotes under ~100 characters and always link to the source.

---

## 10. API design (FastAPI routes)

Three endpoints. That's it.

### `GET /api/cities/{city_slug}`
Returns the ranked list for a city. Query params: `quality_weight`, `service_weight`, `ambiance_weight` (all optional, default 0.4/0.3/0.3, must sum to 1).

```json
{
  "city": "chicago",
  "weights": {"quality": 0.4, "service": 0.3, "ambiance": 0.3},
  "computed_at": "2026-05-04T03:00:00Z",
  "restaurants": [
    {
      "slug": "bavettes-chicago",
      "name": "Bavette's Bar & Boeuf",
      "neighborhood": "River North",
      "price_tier": 4,
      "prime_score": 88.4,
      "quality_score": 91.2,
      "service_score": 85.0,
      "ambiance_score": 87.1,
      "house_take": "Old-school steakhouse atmosphere, consistently great execution, expect to wait."
    }
  ]
}
```

### `GET /api/restaurants/{slug}`
Returns the breakdown for one place.

```json
{
  "slug": "bavettes-chicago",
  "name": "Bavette's Bar & Boeuf",
  "address": "...", "lat": 41.89, "lng": -87.63,
  "price_tier": 4,
  "google_rating": 4.6,
  "prime_score": 88.4,
  "computed_at": "2026-05-04T03:00:00Z",
  "pillars": {
    "quality":  {"score": 91.2, "themes_pos": ["wagyu", "wedge salad"], "themes_neg": ["bread overpriced"], "quotes": [{"text": "...", "source": "google", "url": "..."}]},
    "service":  { ... },
    "ambiance": { ... }
  },
  "sources": {"google_reviews": 5, "reddit_mentions": 47, "date_range": ["2024-05-04", "2026-05-04"]}
}
```

The "house_take" and theme arrays are generated by Claude as a separate, low-frequency call — once per scoring run, given the top sentences for each pillar. Don't do this on every request.

### `GET /api/health`
Returns `{"ok": true, "version": "0.1.0"}`. For uptime monitoring.

CORS: lock to your Vercel domain in production, allow localhost in dev.

---

## 11. The nightly job

Single GitHub Actions workflow. Runs at 03:00 UTC daily.

```yaml
# .github/workflows/nightly.yml
name: Nightly refresh
on:
  schedule:
    - cron: "0 3 * * *"
  workflow_dispatch:        # also lets you trigger manually
jobs:
  refresh:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ./api
      - run: python -m app.jobs.nightly
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GOOGLE_PLACES_API_KEY: ${{ secrets.GOOGLE_PLACES_API_KEY }}
          REDDIT_CLIENT_ID: ${{ secrets.REDDIT_CLIENT_ID }}
          REDDIT_CLIENT_SECRET: ${{ secrets.REDDIT_CLIENT_SECRET }}
          REDDIT_USER_AGENT: "prime-index/0.1 by u/yourusername"
```

The `nightly.py` script does, in order:
1. For each restaurant in the seed: refresh Google Places data
2. For each restaurant: search Reddit for new mentions
3. For each new review: classify with Claude (skip if already classified)
4. For each restaurant: recompute pillar scores + Prime Score, write a new `scores` row
5. For each restaurant: regenerate "house_take" and themes via Claude (cached for 7 days)
6. Print a summary to stdout (GitHub Actions logs)

Each step is idempotent. You can re-run safely.

---

## 12. Frontend specifics

Use shadcn/ui components on top of Tailwind. Don't hand-roll buttons and sliders — install shadcn and use their `Slider`, `Card`, `Badge`. The methodology page is plain prose markdown rendered through `next-mdx-remote`.

### Visual direction
You said you like the field-notebook aesthetic for your personal site. Resist that here. Prime Index should feel **editorial-magazine** — think NYT Cooking or Eater's "Eater 38" pages — clean serif headlines, sans-serif body, restrained use of color, lots of white space, the pillar bars in three muted tones. Avoid emoji, avoid steak puns ("a cut above" is banned).

### Loading states
The list and detail pages are server-rendered. You should not see any client-side loading spinners on first paint. The slider re-sort is instant and client-side because we ship all three pillar scores in the initial payload.

---

## 13. Build order — exact sequence

This is what to feed into Claude Code. Each step is a clean PR-sized chunk.

1. **Repo scaffold** — create the directory structure above, init git, add `.gitignore`, write a README stub
2. **Backend boot** — FastAPI hello world at `/api/health`, FastAPI + SQLAlchemy + Alembic wired up, env loading via Pydantic Settings
3. **DB schema** — write models, generate first Alembic migration, run it against local SQLite
4. **Seed script** — read `data/chicago_seed.csv`, fetch each restaurant via Google Places, populate `restaurants` table
5. **Google Places ingest** — function that takes a `restaurant_id` and refreshes its reviews
6. **Reddit ingest** — function that searches subreddits for a restaurant and ingests posts/comments
7. **Claude classifier** — function that takes a `review_id`, sends to Claude, parses JSON, writes `sentences` rows
8. **Scorer** — pillar scoring + Prime Score, write `scores` rows
9. **Nightly orchestrator** — `app.jobs.nightly` ties 5–8 together
10. **API routes** — `/api/cities/chicago` and `/api/restaurants/{slug}`
11. **Frontend scaffold** — Next.js app, shadcn install, Tailwind, basic layout
12. **Homepage** — hero, methodology link, CTA
13. **Chicago page** — fetch list from API, render rows, sliders, client-side re-sort
14. **Restaurant page** — fetch detail, render pillar cards, quote snippets, sources
15. **Methodology page** — markdown with the scoring writeup
16. **Deploy** — Vercel for frontend, Render for API, Supabase for Postgres, GitHub Actions for cron
17. **Polish + ship** — Sentry, OG image, basic SEO meta, share on X/Reddit

Stop and demo to friends after step 16. Do not add features before getting feedback from real users.

---

## 14. Things you'll be tempted to do — don't

- **Don't add a city beyond Chicago in the MVP.** You don't know if the methodology works yet. Adding cities multiplies your validation surface and your data costs.
- **Don't add user accounts.** No login = no friction = more people will try it.
- **Don't add scraping of Eater/Infatuation in v1.** They're more legally fraught and Reddit + Google is enough signal to validate.
- **Don't ship without a methodology page.** When someone disagrees with a ranking on Reddit (and they will), the methodology page is the answer.
- **Don't use OpenAI for the classifier.** You're already in the Anthropic ecosystem; one less API key and one less vendor relationship.
- **Don't perfectionism the design.** The product is the scoring methodology. The site is a showcase for that methodology.

---

## 15. Environment variables

`.env.example` (commit this; never commit `.env`):

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/primeindex     # prod (Supabase)
# DATABASE_URL=sqlite:///./primeindex.db                      # local

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Google
GOOGLE_PLACES_API_KEY=AIza...

# Reddit (script-type app)
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=prime-index/0.1 by u/yourusername

# App
ENVIRONMENT=development         # development | production
ALLOWED_ORIGINS=http://localhost:3000,https://primeindex.io
SENTRY_DSN=
```

---

## 16. Definition of "done" for the MVP

A non-technical friend can:
1. Open `https://primeindex.io` on their phone
2. Click through to the Chicago list
3. See 25 ranked steakhouses with Prime Scores
4. Tap one and see why it scored that way, with quoted reviews
5. Drag the sliders and watch the list re-sort
6. Read the methodology page and understand it

When all six of those are true, post on X and on r/chicago. Then collect feedback. Then decide what's next.

---

## 17. Handoff note for Claude Code

When you start the Claude Code session, paste this whole spec in as initial context. Then ask Claude Code to start at step 1 of §13 and proceed sequentially, pausing for your review after each numbered step. Do not let it skip ahead. The spec is opinionated for a reason — every decision in here was made to maximize the chance you actually ship.

A specific instruction worth repeating: **before writing any code, Claude Code should re-read this spec end-to-end, then re-read §3 (repo layout), §4 (DB schema), and §13 (build order)**. Those three sections are the contract. Everything else supports them.

Good luck. Ship it.
