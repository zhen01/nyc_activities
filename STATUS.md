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
- `GET /` — a static HTML/JS page (`backend/app/static/index.html`) with ZIP, mode
  (specific/mood/surprise), vibe, category, budget, solo, and date inputs, rendering
  results as cards with score/confidence/source badges.

Verified with curl across all three modes (specific, mood+ZIP, surprise) and via the
18-test backend suite (`make test-backend`) covering expiry exclusion, per-mode hard
filtering, scoring components, ranking order, and surprise-mode reproducibility.

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
ingestion, and `dbt build` on every PR against a Postgres service container. Verified by
running every step locally in the same order before committing the workflow.

While building the dbt mart, found and fixed a real bug in `ingestion/ingest.py`: a
blank/unknown numeric cell (e.g. `cost`) was round-tripping through pandas as `NaN`
instead of a true SQL `NULL`, because assigning `None` into a `float64`-typed column is
silently coerced back to `NaN` by pandas. Fixed with `.astype(object)` before the
NaN→None conversion. This directly mattered for the "unknown price must not be treated
as free" business rule — a `NaN` in a Postgres `numeric` column sorts/compares like a
huge number, not like an absence of data, which would have quietly broken any downstream
"price is legal" check.

Not working: `backend/app/db/*` (ORM models) and `backend/scripts/load_seed_data.py`
are still TODO stubs — they were designed for a different, not-yet-needed SQLite/JSON
path and are now superseded by `ingestion/` + `filter_engine.py`. The `frontend/`
React scaffold (Vite/TSX) is also still unimplemented; the MVP's plain HTML/JS page in
`backend/app/static/` replaces it for now.

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
- **No React/Vite build.** The plain HTML/JS page in `backend/app/static/` is enough to
  demonstrate the product loop; revisit `frontend/` only if a richer UI is needed.
- **No user accounts or auth.** Not needed for a single-session recommendation tool.
- **No scraping/automation pipeline.** Principles #5 and #6 explicitly say start manual.
- **No state management library or routing on the frontend.** One screen, one form, one
  result list.
- **No geocoding API for ZIP proximity.** A small, human-maintainable centroid table
  (`data/sample/zip_centroids.csv`) is enough to rank "nearby vs. far" — routing-accurate
  distance isn't the point.
- **No learned/ML scoring model.** `scoring_engine.py` is a fixed set of simple,
  inspectable weighted components on purpose — transparency (principle #4) would be
  lost the moment ranking becomes a black box.
