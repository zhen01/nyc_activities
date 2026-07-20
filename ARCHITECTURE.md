# Architecture & Data Flow

## Components

- **Source directory (offline, human-maintained)** — `backend/data/sources.yaml`
- **Curated dataset (offline, human-verified)** — `backend/data/seed_activities.json`
- **Database** — SQLite locally / Postgres-ready (`backend/app/db/`)
- **API** — FastAPI (`backend/app/`)
- **Frontend** — minimal React app (`frontend/src/`)

## End-to-end flow

```
sources.yaml (curator finds & lists orgs/channels manually)
      │
      ▼  curator manually verifies an activity is real & current
seed_activities.json (curated, human-verified)
      │
      │  scripts/load_seed_data.py
      ▼
Database  (Activity, Organization, Source tables)
      ▲
      │  query
ConstraintForm (frontend)
      │  time window, budget, location, solo?, skill level
      ▼
POST /recommendations  (app/api/recommendations.py)
      │
      ▼
filter_engine.py   — hard constraints only (feasibility before attractiveness)
      │  small candidate set (1-3 items)
      ▼
explain_engine.py  — "why this fits" + explicit uncertainty, grounded in DB fields only
      │
      ▼
API response (Recommendation[])
      │
      ▼
ActivityCard (frontend) — renders each recommendation + explanation + uncertainty
```

## Why data enters this way

Nothing is scraped or generated live. The only way an activity reaches a user is:
someone manually finds a source → manually verifies an activity from it → it gets
written into `seed_activities.json` with a `source_url` and `last_checked` date →
`load_seed_data.py` puts it in the database. This is intentional (principles #2, #5, #6):
prove the recommendation logic is useful on a small, trustworthy dataset before ever
considering scraping or automated ingestion.

## Why filtering happens before explaining

`filter_engine.py` only asks "does this fit?" (time, budget, distance, solo-friendly).
It does not rank by how appealing an activity sounds. `explain_engine.py` runs only on
the activities that already passed the feasibility filter, and its job is limited to
describing fit and uncertainty — not to influence which activities were selected.
Keeping these as separate stages makes principle #1 ("feasibility before
attractiveness") a structural guarantee rather than a hope.
