# Prime Index

  A steakhouse aggregator that ranks restaurants on three pillars instead of one blended star rating: **Quality & Value**, **Service**, and **Ambiance**.

  ## Status

  In active development. MVP launches with 25 Chicago steakhouses, scored from Google Places reviews + (pending) Reddit local sentiment.

  ## Why three pillars?

  A 4.5-star rating doesn't tell you *why* a restaurant is good. Prime Index decomposes the score so users can see whether a place earned its rating from the food, the service, or the ambiance — and adjust the weighting to match what they personally care about.

  ## Methodology

  Each review is sentence-classified by an LLM into one of four pillars (`quality`, `service`, `ambiance`, `other`) with a sentiment score in [-1, 1]. Pillar scores are computed with time-decay weighting (recent reviews count more). The composite Prime Score defaults to 40/30/30 weighting but is user-adjustable in the UI.

  ## Tech

  Python (FastAPI), SQLAlchemy, Anthropic Claude (classifier), Next.js + Tailwind frontend.

  ---

  Built by [@mutindaaa](https://github.com/mutindaaa). UIUC '29.
