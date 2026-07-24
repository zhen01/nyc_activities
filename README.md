# NYC Activity Discovery Engine

[![CI](https://github.com/zhen01/nyc_activities/actions/workflows/ci.yml/badge.svg)](https://github.com/zhen01/nyc_activities/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

A personalized activity discovery tool for NYC: give it a free-time window, budget, and
a few constraints, and get back 1-5 real, feasible, source-backed activities — including
ones from small organizations (social sports leagues, free kayaking programs, volunteer
marketplaces, language exchanges) that don't show up on mainstream event platforms.

Built as an end-to-end personal data project: a FastAPI recommendation service with
transparent, inspectable scoring, backed by a Postgres ingestion pipeline and a dbt
analytics layer, all exercised by an automated test suite and CI on every PR.

## Table of Contents

- [Problem](#problem)
- [Product Principles](#product-principles)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Quick Start](#quick-start-the-mvp)
- [Repo Structure](#repo-structure)
- [Local Data Ingestion (Postgres)](#local-data-ingestion-postgres)
- [External Source: NYC Parks Public Events](#external-source-nyc-parks-public-events)
- [Analytics Layer: dbt](#analytics-layer-dbt-mart_activity_candidates)
- [Continuous Integration](#continuous-integration)
- [Status & Roadmap](#status--roadmap)
- [License](#license)

## Problem

NYC activity discovery is fragmented. Big marketplaces surface commercial/popular events;
smaller recurring communities publish only on their own sites, Instagram, or newsletters.
Someone with three free hours often spends more time searching than participating. This
project reduces that information gap by turning scattered local knowledge into a
trustworthy, constraint-aware recommendation — not by aggregating everything, but by
being deliberately small and feasibility-first.

## Product Principles

1. **Feasibility before attractiveness** — reject anything that doesn't fit the user's
   time, budget, or participation constraints.
2. **Discovery without hallucination** — recommend from verified sources only, never
   invented events.
3. **Small result set** — a few strong choices, not a catalog.
4. **Explain the recommendation** — show why it fits and what remains uncertain.
5. **Progressive engineering** — prove usefulness with curated data before adding
   infrastructure.
6. **Human-maintainable sources** — a manual source directory is acceptable when
   automation is unreliable or inappropriate.

## Features

- **Two-stage recommendation pipeline** — hard feasibility filtering, then transparent,
  component-based scoring (no black-box model).
- **Three request modes** — `specific` (hard category filter), `mood` (rank by vibe-tag
  match), `surprise` (weighted-random sample from the top-scored pool, reproducible via a
  fixed seed).
- **Explainable results** — every recommendation ships a `score`, a `confidence_label`
  derived from source-channel type and check recency, and a rule-based "why this fits"
  string.
- **Live external data source** — NYC Parks public events pulled from the NYC Open Data
  Socrata API, upserted idempotently alongside curated CSV data.
- **Idempotent ingestion** — CSV and API ingestion both upsert on a natural key; rerunning
  produces `0 inserted, N updated`, never duplicate rows.
- **dbt analytics mart** — a single `mart_activity_candidates` model that enforces every
  business rule (expired events, inactive sources, unknown-price-is-not-free, stale
  sources) in one place, with a singular SQL test per rule.
- **React Discover page** — hero search (free time, date, after-time, "looking to"
  intent), a category filter row, a photo-card grid, a "Discover hidden gems"
  organizations row, and a sidebar (plan-at-a-glance, an explicitly-illustrative weather
  card, a favorites summary).
- **Server-persisted favorites** — heart-toggle any activity; persisted via
  `GET/POST/DELETE /favorites`, scoped to an anonymous `device_id` (no login/auth).
- **CI on every PR** — lint (`ruff`, `sqlfluff`), two pytest suites, a `frontend/`
  build compile-check, ingestion, and `dbt build` all run against a real Postgres
  service container.

## Tech Stack

| Layer | Tools |
|---|---|
| API | FastAPI, Pydantic, Uvicorn |
| Frontend | React + Vite + TypeScript (`frontend/`) — no router/state library, one screen |
| Ingestion | Python, SQLAlchemy, psycopg, requests, pandas |
| Database | PostgreSQL 16 (Docker Compose locally) |
| Analytics | dbt (staging → intermediate → mart), sqlfluff |
| Testing | pytest (backend + ingestion suites, 18+ tests) |
| CI/CD | GitHub Actions, Postgres service container |
| External data | NYC Open Data Socrata API (NYC Parks public events) |

## Architecture

```
sources.yaml (curator finds & lists orgs/channels manually)
      │
      ▼  curator manually verifies an activity is real & current
seed_activities.json / data/sample/*.csv (curated, human-verified)
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
GET /recommendations  →  React Discover page (frontend/)
```

Separately, `ingestion/` loads the same curated data (plus live NYC Parks events) into
Postgres, and `dbt/` builds an analytics mart on top of that raw data — see
[ARCHITECTURE.md](ARCHITECTURE.md) for the full data-flow diagram and rationale, and
[STATUS.md](STATUS.md) for exactly which pieces are wired together today versus still
independent tracks.

## Quick Start (the MVP)

The fastest way to see the product loop end to end (no Docker required — this reads
`data/sample/*.csv` directly rather than Postgres):

```bash
python3 -m venv .venv && source .venv/bin/activate   # skip if already created
pip install -r backend/requirements.txt
make mvp
# equivalent: cd backend && uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000 in a browser to use the built React Discover page directly
from FastAPI's static mount. Or query the API directly:

```bash
curl "http://localhost:8000/recommendations?category=active&max_cost=15&solo_friendly=true"
```

### Frontend dev server (optional, for editing the UI)

For live-reloading frontend development, run Vite and FastAPI side by side instead of
using the built static bundle:

```bash
# terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 — `vite.config.ts` proxies `/recommendations`,
`/organizations`, and `/favorites` to the FastAPI backend on port 8000, so the frontend
code never hardcodes a base URL.

To rebuild the static bundle FastAPI serves at `/` (what `make mvp` uses):

```bash
cd frontend && npm run build
cp -r dist/* ../backend/app/static/
```

### Favorites (`GET/POST/DELETE /favorites`)

Heart-toggling an activity persists it server-side in Postgres (`raw.app_favorites`),
keyed by an anonymous `device_id` UUID the frontend generates and stores in
`localStorage` — there's no login/auth system. This is the first API surface that
requires Postgres to be running (`make db-up`); plain `/recommendations` calls (no
`device_id`) still never touch it, preserving the CSV-only, Docker-free MVP demo path.

### Organizations (`GET /organizations`)

Powers the Discover page's "Discover hidden gems" row: active sources plus a count of
their upcoming events, queried directly against `raw.activity_sources` /
`raw.activity_events`. Like `/favorites`, this reads from Postgres directly rather than
the CSV path `/recommendations` still uses — see [STATUS.md](STATUS.md) for why these
two data paths currently coexist unresolved.

### Inputs and ranking behavior

Beyond category/budget/solo/date, the form supports:

- **Starting ZIP code** — used to compute straight-line distance to each event (via a
  small curated `data/sample/zip_centroids.csv` lookup, not a geocoding API). Distance
  is a *scoring* factor, not a hard filter — an unmapped or omitted ZIP just drops
  proximity from the ranking rather than erroring or zeroing out results.
- **Mode**: `specific` (category is a hard filter, today's original behavior),
  `mood` (category is not required; results are ranked by how well an event's
  `vibe_tags` match the requested vibe), `surprise` (hard constraints still apply, but
  the top-scored pool is weighted-sampled rather than a strict top-N, for variety).

Every request runs through two stages:

1. **Feasibility filter** (`filter_engine.py`) — hard pass/fail. Excludes expired events
   (`start_time` in the past) and anything violating a hard constraint (category in
   `specific` mode, budget, solo-friendly, date).
2. **Transparent scoring** (`scoring_engine.py`) — ranks what's left using simple,
   inspectable components (proximity, vibe match, source confidence), each normalized
   0–1 and blended into a 0–100 score. Any component whose input wasn't provided (no
   ZIP, no mood) is dropped from the blend, not fabricated.

The API returns up to the **top 5** results, each including `score`, `confidence_label`
(`High`/`Medium`/`Low`, based on the source's channel type and how recently it was
checked relative to its own update cadence), `source_name`, `source_verified_date`,
`distance_miles` (nullable), and a rule-based `explanation` string.

## Repo Structure

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI entrypoint (routers + CORS + static mount) |
| `backend/app/api/` | HTTP routes: `recommendations.py`, `favorites.py`, `organizations.py` |
| `backend/app/models/schema.py` | Request/response models (`UserConstraints`, `Recommendation`) |
| `backend/app/services/filter_engine.py` | Feasibility filtering (excludes expired/incompatible events) — principle #1 |
| `backend/app/services/scoring_engine.py` | Transparent ranking (proximity, vibe match, source confidence) |
| `backend/app/services/geo.py` | ZIP centroid lookup + straight-line distance |
| `backend/app/services/presentation.py` | Display-only derived fields for the Discover page: badges, tags, category labels, transit-time estimate |
| `backend/app/services/explain_engine.py` | "Why this fits" explanation generation — principle #4 |
| `data/sample/zip_centroids.csv` | Small curated NYC ZIP → lat/lon lookup table (no geocoding API) |
| `backend/app/db.py` | Postgres access for `favorites`/`organizations` (reuses `ingestion/db.py`'s table definitions) — see STATUS.md's noted CSV-vs-Postgres split |
| `backend/data/sources.yaml` | Manually maintained directory of orgs/channels — principle #6 |
| `backend/data/seed_activities.json` | Curated, human-verified activities actually served to users |
| `backend/scripts/load_seed_data.py` | Loads seed data into the database |
| `backend/tests/` | Unit + API tests: filter/scoring engines, presentation, favorites, organizations |
| `backend/app/static/` | Built React app (from `frontend/dist/`); prior plain HTML/JS page archived at `static/legacy/` |
| `frontend/src/` | React + Vite + TS Discover page: `App.tsx`, `api/client.ts`, `components/` (`HeroSearch`, `CategoryFilterRow`, `ActivityCard`, `FavoriteButton`, `OrganizationRow`, `Sidebar`, ...) |
| `docs/source_directory_guide.md` | How to add/maintain a source and promote it to a seed activity |
| `ARCHITECTURE.md` | How data flows end to end |
| `STATUS.md` | What currently works, the highest-risk issue, and the next deliverable |
| `docker-compose.yml` | Local Postgres for the ingestion vertical slice |
| `data/sample/*.csv` | Curated sample data loaded by the ingestion module |
| `ingestion/db.py` | Engine, `raw` schema table definitions, upsert helper |
| `ingestion/validate.py` | Required-column/value and date validation |
| `ingestion/ingest.py` | Reads CSVs, validates, upserts into Postgres, logs counts |
| `ingestion/nyc_parks.py` | Fetches/parses/loads the NYC Parks API into `raw.nyc_parks_events`, isolated from the CSV path |
| `ingestion/tests/` | Validation, dedup, and NYC Parks ingestion tests |
| `dbt/models/staging/` | Renaming-only views over `raw.*` (`stg_activity_sources`, `stg_activity_events`) |
| `dbt/models/intermediate/int_activity_enriched.sql` | Joins staging + `zip_centroids` seed; computes freshness, audience-fit scores, discovery/actionability scores |
| `dbt/models/marts/mart_activity_candidates.sql` | The recommendable-events mart — applies every business-rule exclusion in one place |
| `dbt/tests/` | Singular SQL tests mapping 1:1 to each business rule (expired, inactive source, unknown price, stale freshness, missing URL) |
| `.github/workflows/ci.yml` | Runs on every PR: `ruff`, `sqlfluff`, both pytest suites, ingestion, `dbt build` |
| `Makefile` | `db-up`, `db-down`, `ingest`, `test`, `test-backend`, `dbt-deps`, `dbt-seed`, `dbt-build` |

## Local Data Ingestion (Postgres)

This is the first runnable piece of the project: loading curated sample CSV data into a
local Postgres database. It does not include the API, UI, or recommendation logic yet.

Note: `data/sample/*.csv` (raw ingestion sample data) is separate from
`backend/data/sources.yaml` (the curated org directory for the future recommendation
engine) — same word "sources," different purpose and consumer. Don't conflate them.

### Prerequisites

- Docker Desktop (for `docker compose`)
- Python 3.11+ recommended (a virtualenv is strongly recommended)

### Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install ingestion dependencies
pip install -r ingestion/requirements.txt

# 3. Configure environment variables
cp .env.example .env
# edit .env if you want non-default credentials

# 4. Start Postgres
make db-up
# equivalent: docker compose up -d db

# 5. Load the environment variables and run ingestion
export $(grep -v '^#' .env | xargs)
make ingest
# equivalent: python -m ingestion
```

You should see log output like:

```
sources.csv: 5 inserted, 0 updated
events.csv: 8 inserted, 0 updated
```

Running `make ingest` again will report `0 inserted, N updated` — no duplicate rows are
created, since each row is upserted on its natural key (`source_id` / `event_id`).

### Verifying row counts

```bash
docker compose exec db psql -U nyc_activities -d nyc_activities \
  -c "select count(*) from raw.activity_sources;" \
  -c "select count(*) from raw.activity_events;"
```

### Running tests

```bash
pytest ingestion/tests
# or: make test
```

Tests validate column/value/date checks and the upsert (dedup) logic directly; the
dedup tests run against an in-memory SQLite database (no Docker required) since the
upsert helper is dialect-aware and exercises the same code path against Postgres in
production.

The MVP's filter/scoring engine has its own test suite:

```bash
cd backend && python -m pytest tests
# or: make test-backend
```

Covers: expired-event exclusion, hard-constraint filtering per mode, proximity/vibe/
confidence scoring components, top-5 ranking order, and surprise-mode sampling
(including reproducibility with a fixed random seed).

### Stopping Postgres

```bash
make db-down
# equivalent: docker compose down
```

## External Source: NYC Parks Public Events

The second source in the raw layer: upcoming NYC Parks public events, fetched live
from the NYC Open Data Socrata API ("NYC Parks Public Events - Upcoming 14 Days",
dataset `w3wp-dpdi`). This is isolated from the curated-CSV path above --
`ingestion/nyc_parks.py` owns its own fetch/parse/table logic and writes to its own
table, only reusing the generic engine/upsert helpers from `ingestion/db.py`.

### Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Same connection string used by the CSV ingestion (see above) |
| `NYC_OPEN_DATA_APP_TOKEN` | no | Optional Socrata app token; raises the default public rate limit. Not required for normal use |
| `NYC_PARKS_RECORD_LIMIT` | no | Max records to fetch per run (default 200), paginated in batches of 50 |

### Running the API ingestion

```bash
make db-up      # if not already running
export $(grep -v '^#' .env | xargs)
make ingest-parks
# equivalent: python -m ingestion.nyc_parks
```

Output looks like:

```
nyc_parks: fetched 20 raw record(s) from the API
nyc_parks_events: 20 inserted, 0 updated, 0 failed
```

Re-running upserts by the API's `guid` (stored as `source_record_id`) -- no
duplicates, existing rows are never deleted, and rows are updated in place with a
fresh `ingested_at`.

### Expected raw table

`raw.nyc_parks_events`: `source_record_id` (PK, the API's `guid`), a handful of
directly-copied fields (`title`, `startdate`, `enddate`, `starttime`, `endtime`,
`location`, `parknames`, `categories`, `link_url`, `registration_url`), a
`raw_payload` JSON column holding the full original API record, and `ingested_at`.
No business normalization happens here (categories aren't mapped, costs aren't
inferred, etc.) -- that's deferred to a later curated/staging step.

### Verifying row counts

```bash
docker compose exec db psql -U nyc_activities -d nyc_activities \
  -c "select count(*) from raw.nyc_parks_events;" \
  -c "select source_record_id, title, startdate, location from raw.nyc_parks_events limit 5;"
```

## Analytics Layer: dbt (`mart_activity_candidates`)

A dbt project under `dbt/` turns `raw.activity_sources` / `raw.activity_events` into a
single mart of records that could plausibly be recommended, with every business rule
enforced in one place instead of scattered across application code.

**Business rules** (each one has a matching singular test in `dbt/tests/`):

- Expired events cannot appear (`coalesce(end_at, start_at) >= now()`).
- Inactive sources cannot appear (`is_active = true`).
- An unknown price must never be treated as free — `NULL` stays `NULL` all the way
  through staging into the mart, it's never coalesced to `0`.
- Events whose source hasn't been checked recently enough (`freshness_status =
  'abandoned'`, see below) are excluded, not just penalized.

**Layering**: `stg_activity_sources` / `stg_activity_events` (rename-only views over
`raw.*`) → `int_activity_enriched` (joins in the `zip_centroids` seed for `borough`,
computes `freshness_status` and the audience-fit/discovery/actionability scores) →
`mart_activity_candidates` (applies every exclusion rule, selects the final field list).

**Freshness**: `freshness_status` is `fresh` / `stale` / `abandoned`, based on days
since the *source's* `last_checked` relative to its `update_cadence` (`daily`/`weekly`/
`seasonal` → 1/7/90 days), using the same `CADENCE_DAYS` mapping as
`backend/app/services/scoring_engine.py` so "freshness" means the same thing in the API
and in this mart. Only `abandoned` is excluded from the mart; `stale` rows are kept but
flagged.

**Audience-fit scores** (`solo_private_score`, `solo_social_score`, `couple_score`,
`small_group_score`, each 0-100): simple, documented point sums from `solo_friendly` +
`vibe_tags` — rule-based, not a model, so every point is traceable to a specific input
(consistent with the "no black-box scoring" principle already established for the API).
`group_suitability` is just the label of whichever of the four scores is highest.

### Running it

```bash
pip install -r ingestion/requirements.txt   # now includes dbt-core, dbt-postgres, ruff, sqlfluff
make db-up
export $(grep -v '^#' .env | xargs)
make ingest          # populates raw.* that dbt reads from
make dbt-deps        # installs dbt_utils
make dbt-seed        # loads dbt/seeds/zip_centroids.csv
make dbt-build       # runs all models + all tests
```

`profiles.yml` lives in `dbt/` (not `~/.dbt/`) and reuses the same `POSTGRES_*` env vars
as `ingestion/` and `docker-compose.yml` — one connection config for the whole project.

Verify the mart directly:

```bash
docker compose exec db psql -U nyc_activities -d nyc_activities \
  -c "select event_id, event_name, freshness_status, group_suitability from analytics.mart_activity_candidates;"
```

## Continuous Integration

`.github/workflows/ci.yml` runs on every pull request against a real Postgres service
container: `ruff check`, `sqlfluff lint` (dbt models), `docker compose config`, both
pytest suites, `python -m ingestion` (to populate `raw.*`), then `dbt deps` / `dbt seed`
/ `dbt build`. The point isn't a complex pipeline — it's that a broken data model or a
failing test is caught automatically before merge, not discovered later in Postgres.

## Status & Roadmap

This repo has a runnable MVP, a working ingestion pipeline, and a dbt analytics mart —
but they're not all wired together yet. See [STATUS.md](STATUS.md) for exactly what's
implemented, the current highest-risk issue, and the next planned deliverable
(pointing `filter_engine.py` at Postgres instead of flat CSVs).

## License

[MIT](LICENSE) © Zhen Fang
