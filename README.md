# Prime Index

The best steakhouses in Chicago, ranked by what actually matters.

This is the MVP. See `prime_index_spec.md` for the full technical spec and `docs/methodology.md` for the public-facing scoring methodology.

## Layout

- `api/` — FastAPI backend (Python 3.12)
- `web/` — Next.js 15 frontend (added at build step 11)
- `data/` — Seed CSVs (e.g. `chicago_seed.csv`)
- `docs/` — Methodology and other prose
- `.github/workflows/` — CI + nightly cron (added at build step 9/17)

## Local development

```bash
cd api
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
cp ../.env.example ../.env       # then edit
alembic upgrade head             # create local SQLite DB
uvicorn app.main:app --reload    # serves on http://localhost:8000
```

## Status

Built sequentially per `prime_index_spec.md` §13. See git history for current step.
