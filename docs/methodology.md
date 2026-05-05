# How Prime Index works

Most restaurant scores collapse food, service, decor, value, and the bathroom into a single number. Prime Index decomposes that into three separate pillars, scores each independently, and lets you weight them yourself. Here is how.

## The three pillars

- **Quality & Value** — the food itself: taste, preparation, portions, ingredients, and whether the price is justified.
- **Service** — waitstaff, hosts, sommelier, kitchen pacing, attentiveness, knowledge, friendliness.
- **Ambiance** — decor, noise level, lighting, cleanliness (including bathrooms), crowd, vibe.

Anything that does not fit those three — parking, reservations, location — is dropped from scoring.

## Where the data comes from

For the MVP, every restaurant is scored on its public Google reviews (rolling 24-month window). We use Google's Places API to refresh the data nightly. Per Google's terms, verbatim review text is purged from our database after 30 days; the derived pillar classifications and scores remain.

**Reddit local sentiment** — posts and top-level comments mentioning the restaurant across r/chicago, r/ChicagoFood, r/AskChicago, r/FoodChicago, r/steak, and r/FoodPorn — is planned for v1.1. It is the larger half of the methodology and substantially increases sample size. Reddit API access takes 1–4 weeks to approve, so we shipped the MVP first on Google data alone.

## How a review becomes a score

Every review is broken into individual sentences. Each sentence is sent to an AI model (Claude Haiku 4.5) which returns:

- which pillar the sentence is about (quality, service, ambiance, or "other")
- how positive or negative the sentence is, on a scale from -1.0 to +1.0

Sentences tagged "other" are kept for context but dropped from scoring.

For each pillar, we take a time-decay-weighted mean of the sentences. A sentence from a review posted today carries full weight; one from a year ago carries about 37% (e<sup>-1</sup>); older still less. The score reflects what people are saying *now*, not what they said three years ago. We then map that weighted mean from [-1, +1] onto a 0–100 scale.

## The volume-aware adjustment

A restaurant with 76 Google ratings does not carry the same statistical confidence as one with 6,747. To keep small-sample places from dominating the leaderboard on five enthusiastic reviews, we apply Bayesian shrinkage: each pillar score is pulled toward the corpus average. The strength of the pull is set per-restaurant by total Google review count — high-volume restaurants barely move from their raw signal; low-volume restaurants are pulled meaningfully toward the mean.

As Reddit ships in v1.1, this adjustment naturally weakens because per-restaurant sentence counts climb.

## Price-tier adjustment

The Quality & Value pillar gets a small penalty for higher price tiers — a $$$$ steakhouse is held to a slightly higher bar than a $$$ one. The current penalty is conservative: -1 for $$$, -3 for $$$$. We expect to revisit it with feedback after launch.

## The composite Prime Score

> **Prime Score = 0.4 × Quality + 0.3 × Service + 0.3 × Ambiance**

Those default weights are our editorial opinion. The sliders on the Chicago page let you reweight however you want — drag Quality to 100% if you only care about the food, balance equally, whatever matches how you eat.

If a restaurant does not have enough sentences in a given pillar, we leave that pillar score blank rather than guess. The composite Prime Score is also blank when any pillar is missing — you will still see whichever pillars have enough data.

## What this MVP does *not* claim to do

- We score 25 hand-picked Chicago steakhouses. We are not a comprehensive directory.
- We do not detect fake reviews, paid reviews, or reviewer bias. We treat the public corpus as-is.
- We are not a Michelin guide. We do not visit. We measure what the public is saying.

**The honest part — sample size.** For each restaurant, we're scoring from the 5 most recent reviews Google returns through their API. That's a small sample. One unusually critical or unusually glowing review gets meaningful weight in the score. We deliberately surface this rather than hide it: when you see Bavette's score lower than your gut tells you, look at the quoted reviews — that's exactly the data behind the number.

Reddit local sentiment in v1.1 increases this sample by 10–20x. Until then, treat Prime Index as a starting point for a conversation, not a verdict.

## Coming in v1.1

- Reddit local sentiment integration
- More cities — likely New York and San Francisco first
- Per-pillar quote browsing on the restaurant page
- "Compare these two" overlay
- A queue for suggesting restaurants we should add

This is a personal project by a UIUC student. Found a bug, disagree with a ranking, or want to suggest a restaurant? GitHub issues open: [github.com/mutindaaa/primeindex/issues](https://github.com/mutindaaa/primeindex/issues).

The source code lives at [github.com/mutindaaa/primeindex](https://github.com/mutindaaa/primeindex).
