# Architecture & Data Flow

## Components

- **Source directory (offline, human-maintained)** — `backend/data/sources.yaml`
- **Curated sample data** — `data/sample/*.csv` (events + sources; read directly by the
  MVP, and separately loaded into Postgres by `ingestion/`)
- **Ingestion + raw database** — `ingestion/` loads CSVs (plus live NYC Parks events)
  into Postgres's `raw` schema; `backend/app/db.py` reuses those same table definitions
  for the favorites/organizations endpoints (see below)
- **Analytics mart** — `dbt/` builds `analytics.mart_activity_candidates` on top of
  `raw.*`, enforcing every business rule in one place (not yet consumed by the API)
- **API** — FastAPI (`backend/app/`)
- **Frontend** — React + Vite + TS Discover page (`frontend/src/`), built and served
  from `backend/app/static/`

## End-to-end flow (recommendations)

```
data/sample/sources.csv, events.csv (curated, human-verified)
      │
      ▼
filter_engine.py   — hard constraints only (feasibility before attractiveness)
      │  small candidate set
      ▼
scoring_engine.py  — transparent, inspectable ranking (proximity, vibe, source confidence)
      │
      ▼
explain_engine.py  — "why this fits" + explicit uncertainty
      │
      ▼
presentation.py    — display-only derived fields (badges, tags, category label, transit estimate)
      │
      ▼
GET /recommendations  (app/api/recommendations.py)
      │  if device_id supplied: one lazy lookup against raw.app_favorites for is_favorited
      ▼
React Discover page (frontend/src/App.tsx) — HeroSearch + CategoryFilterRow request params
      │
      ▼
ActivityCard (+ FavoriteButton) — renders each recommendation + explanation + uncertainty
```

`GET /recommendations` reads `data/sample/*.csv` directly — it does not read from
Postgres, even though `ingestion/` populates the same data there. This is deliberate,
not an oversight (see STATUS.md's "smallest next deliverable"): the CSV path is the
fastest way to demo the product loop without requiring Docker.

## End-to-end flow (favorites, organizations)

```
device_id (client-generated UUID, localStorage)
      │
      ▼
POST /favorites {device_id, event_id}  ──┐
GET  /favorites?device_id=              ├──►  raw.app_favorites  (backend/app/db.py)
DELETE /favorites/{device_id}/{event_id}─┘         ▲
                                                     │ reuses table defs from
GET /organizations  ─────────────────────►  raw.activity_sources / raw.activity_events
                                              (backend/app/db.py + ingestion/db.py)
```

Unlike `/recommendations`, `/favorites` and `/organizations` query Postgres's `raw`
schema directly via SQLAlchemy Core, reusing the same table definitions
`ingestion/db.py` uses to populate it. This is a **named, accepted architectural
inconsistency**, not resolved this pass: the API now has two coexisting data paths
(CSV for recommendations, Postgres for favorites/organizations). See STATUS.md for the
reasoning and the direction that would eventually unify them (pointing
`filter_engine.py` at Postgres, likely at `analytics.mart_activity_candidates` rather
than the raw tables).

## Why data enters this way

Nothing is scraped or generated live. The only way an activity reaches a user is:
someone manually finds a source → manually verifies an activity from it → it gets
written into `data/sample/events.csv` (or, longer-term, `sources.yaml` +
`seed_activities.json`) with a `source_url` and `last_checked` date. This is
intentional (principles #2, #5, #6): prove the recommendation logic is useful on a
small, trustworthy dataset before ever considering scraping or automated ingestion.
The same principle applies to the frontend's presentation-layer additions — badges,
tags, images, weather, and transit time are either derived from fields already backed
by real data, or (images, weather) explicitly absent/labeled-illustrative rather than
fabricated. See STATUS.md's "Unnecessary complexity to avoid" section for the specifics
of what's deliberately still an estimate or a placeholder.

## Why filtering happens before explaining

`filter_engine.py` only asks "does this fit?" (time, budget, distance, solo-friendly,
hours free, after-time). It does not rank by how appealing an activity sounds.
`scoring_engine.py` and `explain_engine.py` run only on the activities that already
passed the feasibility filter; `presentation.py`'s badges/tags/labels run after that,
purely for display. Keeping these as separate stages makes principle #1 ("feasibility
before attractiveness") a structural guarantee rather than a hope.
