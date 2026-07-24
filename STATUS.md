# Status

## Currently working

**A runnable end-to-end MVP with transparent ranking.** `make mvp` starts a FastAPI app
that serves:
- `GET /recommendations` — a two-stage pipeline over `data/sample/events.csv` (joined
  with `sources.csv`): (1) `filter_engine.py` excludes expired and hard-constraint-
  incompatible events (category in `specific` mode, budget, solo-friendly, date), then
  (2) `scoring_engine.py` ranks the survivors by transparent, inspectable components
  (ZIP proximity via `geo.py` + a curated ZIP centroid table, vibe-tag match for `mood`
  mode, and a source confidence rubric based on channel type + check recency). Returns
  the top 5 (or, in `surprise` mode, a weighted-random sample of 5 from the top-scored
  pool). Each result includes `score`, `confidence_label`, `source_name`,
  `source_verified_date`, `distance_miles`, and a rule-based explanation string
  (principles #1, #3, #4).
- `GET /` — now the built React Discover page (`frontend/`, see below) served from
  `backend/app/static/`; the original static HTML/JS page is preserved at
  `backend/app/static/legacy/index.html` for reference, not deleted.
- `GET/POST/DELETE /favorites`, `GET /organizations` — new this pass, see below.

Verified with curl across all three modes (specific, mood+ZIP, surprise) and via the
backend test suite (`make test-backend`, grown from 18 to 40 tests) covering expiry
exclusion, per-mode hard filtering, scoring components, ranking order, surprise-mode
reproducibility, presentation-layer badges/tags/transit estimates, and the new
favorites/organizations endpoints.

Also working, separately: the ingestion vertical slice (`ingestion/`) loads the same
sample CSVs into a local Postgres `raw` schema via `make ingest`, and is idempotent on
rerun. **The MVP above does not use Postgres yet** — it reads the CSVs directly, since
Docker isn't installed on this dev machine. This is a deliberate simplification, not an
oversight (see "smallest next deliverable" below).

Also working, separately: `ingestion/nyc_parks.py` fetches upcoming NYC Parks events
live from the NYC Open Data Socrata API and loads them into a dedicated
`raw.nyc_parks_events` table via `make ingest-parks`. Verified against the live API:
fetch, parse, idempotent upsert, and real sample rows confirmed. Like the CSV
ingestion, this is not yet wired into the MVP's filter engine — it's a second,
independent raw source for now.

Both `make ingest` and `make ingest-parks` have now been verified end to end against a
**real local Postgres** (via `docker compose up -d db`), not just the SQLite substitute
used during initial development. Ran each twice: first run inserted (5 sources, 8
events, 200 parks events), second run reported `0 inserted, N updated` for all three
tables with no row-count growth — confirming the upsert logic is genuinely idempotent
against Postgres, not just SQLite. Row counts and sample rows verified via `psql`.

Also working, separately: a dbt analytics layer (`dbt/`) builds
`analytics.mart_activity_candidates` on top of `raw.*` — staging views → an intermediate
model computing freshness/audience-fit/discovery/actionability scores → a mart that
enforces every business rule (expired, inactive source, unknown-price-is-not-free,
stale/abandoned freshness, missing URL) in one place. `make dbt-build` runs clean: 1
seed, 3 views, 1 table, 26 tests, all passing against real Postgres. Not yet consumed by
the MVP or the API — it's a standalone analytics artifact for now, same relationship to
the MVP as the raw ingestion tables below.

Also new: `.github/workflows/ci.yml` runs `ruff`, `sqlfluff`, both pytest suites,
ingestion, `dbt build`, and (as of the frontend redesign below) a `frontend/` build
compile-check on every PR against a Postgres service container. Verified by running
every step locally in the same order before committing the workflow.

**The Discover page has been redesigned as a React/Vite/TS app** (`frontend/`),
replacing the plain HTML/JS page as the default UI — see the reversed "No React/Vite
build" bullet below. It's a single screen (no router): a hero search bar (free time,
date, after-time, intent — new `UserConstraints` fields), a category filter row over
the 7-category taxonomy, a photo-card grid of `/recommendations` results (image or a
CSS category-colored placeholder, badges/tags computed by the new
`backend/app/services/presentation.py`), a "Discover hidden gems" organizations row
(`GET /organizations`), and a sidebar (plan-at-a-glance, an explicitly-illustrative
weather card, a favorites-count summary). Favorites are heart-toggled per card and
persisted server-side via `GET/POST/DELETE /favorites`, scoped by an anonymous
`device_id` UUID generated client-side and stored in `localStorage` — no login/auth.
Verified end to end: `npm run build` compiles clean; `npm run dev` (5173, proxied to
FastAPI on 8000 via `vite.config.ts`) and the standalone FastAPI static mount (after
`npm run build` + copying `frontend/dist/*` into `backend/app/static/`, with the prior
plain-HTML page archived to `backend/app/static/legacy/`) were both exercised manually
— search filters, category filter, favorite add/remove/persist-across-reload (checked
via `psql`), and the organizations row all round-tripped correctly. Backend test suite
grew from 18 to 40 tests (`backend/tests/test_presentation.py`,
`test_favorites_api.py`, `test_organizations_api.py` added), all green.

While building the dbt mart, found and fixed a real bug in `ingestion/ingest.py`: a
blank/unknown numeric cell (e.g. `cost`) was round-tripping through pandas as `NaN`
instead of a true SQL `NULL`, because assigning `None` into a `float64`-typed column is
silently coerced back to `NaN` by pandas. Fixed with `.astype(object)` before the
NaN→None conversion. This directly mattered for the "unknown price must not be treated
as free" business rule — a `NaN` in a Postgres `numeric` column sorts/compares like a
huge number, not like an absence of data, which would have quietly broken any downstream
"price is legal" check.

Not working: `backend/scripts/load_seed_data.py` is still a TODO stub — it was designed
for a different, not-yet-needed SQLite/JSON path and is now superseded by `ingestion/`
+ `filter_engine.py`. The old `backend/app/db/` ORM-model stub package has been removed
outright (it was empty/unused and collided on import with the new `backend/app/db.py`,
which now backs the favorites/organizations endpoints — see below).

**New architectural inconsistency, accepted for now, not resolved this pass:**
`GET/POST/DELETE /favorites` and `GET /organizations` (`backend/app/db.py`,
`backend/app/api/favorites.py`, `backend/app/api/organizations.py`) are the *first*
endpoints to query Postgres (`raw.*`) directly, using the same table definitions
`ingestion/db.py` populates. `GET /recommendations` still reads `data/sample/*.csv`
directly and does not touch Postgres unless a `device_id` is supplied (in which case it
does one extra lazy lookup against `raw.app_favorites` to populate `is_favorited` —
deliberately not a FastAPI `Depends`, so that plain `/recommendations` calls still never
require Docker/Postgres, preserving the CSV-only MVP demo path). So the API now
straddles two data paths on purpose: recommendations from CSVs, favorites/organizations
from Postgres. Unifying this (per "smallest next deliverable" below) would also resolve
this split.

## Highest-risk issue

**Data trust and freshness of the manually curated source directory** is still the
top product risk long-term (see reasoning below, unchanged from before). Short-term,
the more immediate risk is that the MVP's filter engine reads flat CSVs directly and
has still never been run against the Postgres `raw` schema that `ingestion/` populates
(now confirmed working against real Postgres) — those two data paths remain
disconnected, since the MVP isn't wired to read from Postgres yet.

<details>
<summary>Original reasoning (still valid)</summary>

The entire product's credibility depends on `sources.yaml` / curated activity data
staying accurate and current, and that's a manual, likely single-maintainer process.
If `last_checked` dates go stale, the engine will recommend events that are outdated,
cancelled, or wrong — directly violating principle #2 ("discovery without
hallucination"). There is currently no mechanism, in the repo or otherwise, to detect
or surface staleness.
</details>

## Smallest next deliverable

Point `filter_engine.py` at Postgres instead of the CSVs directly — i.e. make the MVP
read from `raw.activity_events` and `raw.nyc_parks_events` (both now populated and
verified against real Postgres) instead of two disconnected raw sources sitting
unused behind it. Docker is now confirmed installed and working on this dev machine,
so this is unblocked. Until this is done, the CSV-based MVP remains the fastest way to
demo the product loop. Note: `raw.nyc_parks_events` doesn't yet have `lat`/`lon`/
`vibe_tags`/`zip_code` columns the way `data/sample/events.csv` now does — that mapping
will need to be designed as part of this wiring work, not assumed away.

Once the MVP does read from Postgres, `analytics.mart_activity_candidates` (see the dbt
section above) is the more likely long-term source for `filter_engine.py` than raw
tables directly — the business-rule filtering and audience-fit scores it already
computes would let `filter_engine.py`/`scoring_engine.py` shrink rather than duplicate
that logic. Not done yet; flagging the direction, not committing to it.

## Unnecessary complexity to avoid (for now)

- **No LLM calls yet.** Rule-based templates in `explain_engine.py` are enough to prove
  the "why it fits" concept.
- ~~No React/Vite build.~~ **Reversed.** The Discover page's mockup (branded nav, hero
  search, category filters, photo-card grid, organizations row, sidebar widgets) needed
  real component/state complexity that a plain HTML/JS page couldn't reasonably carry.
  `frontend/` (React + Vite + TS, no router/state library — still one screen) now
  replaces the old static page as the default UI; the old page is preserved, not
  deleted, at `backend/app/static/legacy/index.html`.
- **No user accounts or auth.** Favorites use a client-generated anonymous `device_id`
  (localStorage), not a login system — see above.
- **No scraping/automation pipeline.** Principles #5 and #6 explicitly say start manual.
- **No state management library or routing on the frontend.** Still one screen —
  Organizations/Favorites nav links are inert labels, not routed pages, this pass.
- **No geocoding or routing API for ZIP proximity or transit time.** A small,
  human-maintainable centroid table (`data/sample/zip_centroids.csv`) is enough to rank
  "nearby vs. far" — routing-accurate distance isn't the point. The new
  `estimated_transit_minutes` field (`presentation.py`) is likewise a documented,
  fixed-assumed-speed (12 mph) estimate from that same haversine distance, labeled
  `"~N min"` in the UI — not a real Google-Directions-style routing call, no API key
  added.
- **No external image hosting/generation.** `image_url` is a nullable passthrough
  column (CSV → Postgres → API); no rows currently populate it, and the frontend falls
  back to a CSS category-colored placeholder block when it's absent. Populating real
  photo URLs is a manual curation task, not something this pass fabricates.
- **No live weather API.** The sidebar's weather card is a static, explicitly-labeled
  "Illustrative only, not a live forecast" card (`is_live: false` in the underlying
  data) — no external key needed this pass.
- **No learned/ML scoring model.** `scoring_engine.py` is a fixed set of simple,
  inspectable weighted components on purpose — transparency (principle #4) would be
  lost the moment ranking becomes a black box.
