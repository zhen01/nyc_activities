# Architecture & Data Flow

## Components

- **Source directory (offline, human-maintained)** — `backend/data/sources.yaml`
- **Curated sample data** — `data/sample/*.csv`, ingested into `raw.*`; also reused as
  the deterministic pytest fixture in `backend/tests/conftest.py`
- **Live external feed** — NYC Parks events from the NYC Open Data Socrata API, a
  rolling 14-day window, ingested by `ingestion/nyc_parks.py`
- **Ingestion + raw database** — `ingestion/` loads both feeds into Postgres's `raw`
  schema, upserting on each feed's natural key
- **Analytics marts** — `dbt/` builds `mart_activity_candidates` (business rules
  enforced once) and `mart_organizations` (sources + recommendable-event counts)
- **API** — FastAPI (`backend/app/`), reading the marts
- **Frontend** — React + Vite + TS Discover page (`frontend/src/`), built and served
  from `backend/app/static/`

## End-to-end flow (recommendations)

```
data/sample/*.csv          NYC Open Data Socrata API (live, 14-day window)
      │                              │
      │ ingestion/ingest.py          │ ingestion/nyc_parks.py
      ▼                              ▼
raw.activity_sources/_events   raw.nyc_parks_events
      │                              │
      ▼ stg_activity_*               ▼ stg_nyc_parks_*   (reshape + data-quality fixes)
      └───────────────┬──────────────┘  union
                      ▼
        int_activity_enriched  — freshness, discovery/actionability, audience fit
                      ▼
        mart_activity_candidates  — every business rule enforced once
                      ▼
filter_engine.py   — the user's own constraints only
                      ▼
scoring_engine.py  — transparent ranking (proximity, vibe, source confidence)
                      ▼
explain_engine.py  — "why this fits" + explicit uncertainty
                      ▼
presentation.py    — display-only fields (badges, tags, transit estimate)
                      ▼
GET /recommendations  (app/api/recommendations.py)
      │  if device_id supplied: one lazy lookup against raw.app_favorites
      ▼
React Discover page (frontend/src/App.tsx)
```

## Why the API reads the mart, not the raw tables

Every business rule — expired, inactive source, abandoned freshness, missing URL,
unknown-price-is-not-free, cancelled — is enforced once in
`mart_activity_candidates`, with a singular dbt test per rule. `filter_engine.py`
therefore applies only the constraints belonging to a specific request (category,
budget, solo, date, hours free). Before this, the same rules existed in both SQL and
Python and could drift apart silently.

`GET /organizations` reads `mart_organizations` for the same reason: counting
`raw.activity_events` directly applies none of those rules, so it would advertise an
organization on the strength of cancelled or expired events.

```
device_id (client-generated UUID, localStorage)
      │
      ▼
POST /favorites {device_id, event_id}  ──┐
GET  /favorites?device_id=               ├──►  raw.app_favorites  (backend/app/db.py)
DELETE /favorites/{device_id}/{event_id}─┘
```

Favorites remain in `raw` rather than the analytics layer deliberately: they are
application state written by user actions, not modeled analytics derived from a source
feed. dbt owns the read models; the app owns its own writes.

## Two feeds, one contract

The curated CSV directory and the NYC Parks API are unioned in
`int_activity_enriched` rather than modeled separately, because every enrichment
applies identically to both. What differs is how much each feed publishes, and that is
expressed as `NULL`s rather than as branching logic — the API feed carries no price, no
`solo_friendly` flag and no vibe tags.

Two consequences are load-bearing:

- **`NULL` means unknown, never a default.** An unknown price never satisfies a budget
  filter; unknown solo-friendliness never satisfies a solo-friendly request; and the
  audience-fit scores are `NULL` rather than computed, because scoring them from absent
  inputs would produce a confident-looking number derived from nothing.
- **The API is modeled as a source.** It has no row in the hand-curated source
  directory, so `stg_nyc_parks_source` synthesizes one, with `source_last_checked`
  derived from `max(ingested_at)`. All the existing freshness/confidence/discovery
  logic then applies unchanged — and a pipeline that silently stops running decays in
  freshness instead of staying permanently "fresh".

## Time is evaluated in NYC, not UTC

`macros/nyc_time.sql` provides `nyc_now()`/`nyc_today()`, used by every model and test
that reasons about "now". The warehouse runs in UTC; the product is entirely
NYC-local. Using bare `current_timestamp` meant that between 8pm and midnight EDT, UTC
had already rolled over and that evening's remaining events were excluded as
"expired" — a real bug, caught with 15 events affected.

## Why data enters this way

Nothing is scraped or invented. An activity reaches a user by exactly one of two
routes: a curator manually finds and verifies it and writes it into
`data/sample/events.csv` with a `source_url` and `last_checked` date, or it comes from
a publisher's own official API. Both are attributable to a named, checkable source
(principles #2, #5, #6) — which is what makes "discovery without hallucination"
enforceable rather than aspirational. Scraping is still explicitly out of scope.
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
