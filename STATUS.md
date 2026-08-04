# Status

## Currently working

> **Latest change: the pipeline is now joined up end to end on live data.**
> `/recommendations` reads the dbt mart instead of flat CSVs, and the mart is fed by
> the live NYC Parks Open Data feed — currently **184 real, upcoming events**. The
> long-standing "two disconnected data paths" issue below is resolved, and the sample
> CSVs have been demoted to test fixtures. Details in
> [Live data end to end](#live-data-end-to-end).

**A runnable end-to-end MVP with transparent ranking.** `make mvp` starts a FastAPI app
that serves:
- `GET /recommendations` — a two-stage pipeline over `analytics.mart_activity_candidates`:
  (1) `filter_engine.py` excludes hard-constraint-
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
backend test suite (`make test-backend`, grown from 18 to 49 tests) covering per-mode
hard filtering, scoring components, ranking order, surprise-mode reproducibility,
presentation-layer badges/tags/transit estimates, the favorites/organizations
endpoints, and how genuinely-unknown values are handled.

### Live data end to end

`GET /recommendations` reads `analytics.mart_activity_candidates` — the dbt mart —
rather than `data/sample/*.csv`. The CSV path had quietly become misleading: every
curated sample event has since expired, so it served an empty result set while a live
NYC Parks feed sat ingested and unused in Postgres. The feed is now wired through
staging → intermediate → mart → API, and `make mvp` shows real events happening this
week.

This also collapses the duplicated business logic. Expiry, inactive sources, abandoned
freshness, missing URLs and cancelled events are excluded once, in the mart, each with
a matching singular test; `filter_engine.py` no longer re-implements any of them and
only applies the constraints belonging to a specific user request.

**Wiring the real feed in surfaced four data-quality problems that the curated sample
data had never exercised**, each handled explicitly in `stg_nyc_parks_events.sql`:

1. **`starttime`/`endtime` carry a meaningless date component** — the API returns them
   as full timestamps whose date is the feed's publication date, not the event's. Only
   the time-of-day is trustworthy, so `start_at` is rebuilt from `startdate` plus that
   time.
2. **`categories` is a pipe-delimited multi-value string** with 28 distinct values,
   ~60% of rows carrying a fitness variant. Mapping it onto the 7-value taxonomy needs
   a *priority* order rather than first-match, or a volunteer gardening event tagged
   `Fitness | Volunteer | Gardening` lands in `active`. 5 of 393 rows match nothing and
   stay `NULL`, which excludes them via the existing structural rule instead of
   guessing a bucket.
3. **Cancelled events keep being served**, marked only by a `CANCELED:` title prefix —
   they are otherwise indistinguishable from healthy rows, hence the new business rule.
4. **`coordinates` and `description` were being discarded at ingestion** despite being
   present on every row. Extracting them (`ingestion/nyc_parks.py`) is what makes
   proximity ranking work for API events at all, since the feed publishes no ZIP.

**A real timezone bug, found by profiling that live data.** Postgres runs in UTC while
the product is entirely NYC-local, so `current_date`/`current_timestamp` in the models
meant *UTC today*. Between 8pm and midnight EDT, UTC has already rolled over, and the
mart was therefore excluding that evening's remaining events as "expired" — 15 of them
at the moment it was caught. Fixed with `macros/nyc_time.sql`, so the model and the
test that guards it now agree on what "now" means.

**What the feed does not publish is left unknown, not defaulted.** It has no price, no
`solo_friendly` flag and no vibe tags. Those stay `NULL` end to end: an unknown price
never satisfies a budget filter, unknown solo-friendliness never satisfies a
solo-friendly request, and the four audience-fit scores are `NULL` rather than computed
(every such event would otherwise score exactly 60 for "couple" purely from the
constant baseline — a confident-looking number derived from nothing). `/recommendations`
returns `null` for these fields rather than `0`/`false`. The cost is a visible coverage
gap; the alternative was a fabricated reassurance.

Fixing that also exposed a ranking flaw worth naming: dropping the proximity component
for an event with no coordinates renormalised the remaining weights and pushed it
*above* an event confirmed to be 0.3 miles away — missing data outranking good data.
Events we cannot locate now take a neutral half-score instead (`scoring_engine.py`).

Both `make ingest` and `make ingest-parks` have now been verified end to end against a
**real local Postgres** (via `docker compose up -d db`), not just the SQLite substitute
used during initial development. Ran each twice: first run inserted (5 sources, 8
events, 200 parks events), second run reported `0 inserted, N updated` for all three
tables with no row-count growth — confirming the upsert logic is genuinely idempotent
against Postgres, not just SQLite. Row counts and sample rows verified via `psql`.

The dbt analytics layer (`dbt/`) builds two marts on top of `raw.*` — staging views (one
per feed, plus a synthetic source row for the API) → an intermediate model that unions
the feeds and computes freshness/audience-fit/discovery/actionability scores →
`mart_activity_candidates`, which enforces every business rule in one place, and
`mart_organizations`, one row per active source with a count of the events it currently
has *in the candidates mart*. That second mart matters for correctness rather than
convenience: counting the raw event table instead — which is what `/organizations` used
to do — applies none of the business rules, so it would advertise an organization on
the strength of cancelled or expired events, and could not represent a machine-ingested
feed as a source at all.

`make dbt-build` runs clean: 1 seed, 5 views, 2 tables, 53 tests (grown from 26), all
against real Postgres. Every model/column has a `description` (see
`dbt/models/**/_*.yml` and the shared doc blocks in `dbt/models/docs.md`), and a
pre-generated static lineage/docs site is committed at `dbt/docs_site/index.html` — see
the README's "Documentation & lineage" section.

### Recording history the source doesn't keep

The NYC Parks API serves a rolling 14-day window and has no history endpoint; raw
ingestion upserts on the publisher's `guid`, so it too holds only current state. Ask
either one what the feed said yesterday and there is no answer. That made a whole class
of question permanently unanswerable — how often this publisher cancels, how much
notice attendees get, how far ahead events are posted.

Three pieces now record it:

- `snapshots/snap_nyc_parks_events.sql` — SCD2 via the `check` strategy over content
  columns. `ingested_at` is deliberately excluded from `check_cols`: it is rewritten on
  every upsert regardless of whether anything changed, so including it would create a
  version per run and turn a change log into a write log. `invalidate_hard_deletes` is
  off for a similar reason — a record leaving the feed is usually the 14-day window
  sliding, not a cancellation.
- `models/marts/fct_event_observations.sql` — append-only incremental fact, one row per
  (event, date confirmed present in the feed), `delete+insert` on the composite key so
  a same-day re-run replaces rather than duplicates. Verified idempotent across three
  consecutive runs (393 rows, 393 distinct keys, unchanged).
- `models/marts/mart_source_reliability.sql` — the payoff: cancellation rate, median
  notice period, reschedule rate per source.

**The correctness detail worth keeping.** 13 events were already carrying a `CANCELED:`
prefix at first capture. Their notice period is *unknowable* — subtracting first-capture
from the event date yields a number describing when this pipeline started collecting,
not anything about the publisher. So `cancellation_lead_hours` is populated only where
the live→cancelled transition was actually witnessed between two snapshot versions;
everything else is NULL and flagged via `cancellation_observed`, and the reliability
mart uses `events_with_observed_lifecycle` as its denominator rather than the total. It
also reports `observation_window_days` next to every rate, so a percentage computed over
a few days can't be misread as a settled property of the publisher.

Verified end to end: snapshot is idempotent on re-run (393 → 393, no spurious versions,
confirming the `ingested_at` exclusion works); a controlled mutation test confirmed the
live→cancelled transition is captured with correct `dbt_valid_from`/`dbt_valid_to`, after
which the snapshot was dropped and rebuilt so no synthetic cancellation persists in the
history.

`.github/workflows/daily-refresh.yml` runs ingest → snapshot → build daily, in that
order — ingest overwrites raw with current state, so the snapshot must read it before
the next ingest destroys the previous version. Without the schedule the snapshot would
hold exactly one version per event forever, and the capability would be structural
rather than real.

### Business rules → tests

Every business rule the mart enforces maps to a specific test, not a vague "data looks
right" check. The six most important ones are singular tests (custom SQL, fail if any
row returns) because each is really "the mart's WHERE clause is correct," which a
generic schema test can't express:

| Business rule | Enforced in (`mart_activity_candidates.sql` unless noted) | Test |
|---|---|---|
| Expired events excluded | `coalesce(end_at, start_at) >= {{ nyc_now() }}` — NYC local time, not the warehouse's UTC | `dbt/tests/assert_no_expired_events_in_mart.sql` |
| Inactive sources excluded | `is_active` filter | `dbt/tests/assert_no_inactive_source_events_in_mart.sql` |
| Unknown price stays `NULL`, never coalesced to 0/free | `stg_activity_events.sql` / `stg_nyc_parks_events.sql` (no coalesce, anywhere downstream) | `dbt/tests/assert_unknown_price_stays_null.sql` |
| Abandoned-freshness sources excluded (not just penalized — `stale` is kept, `abandoned` is not) | `freshness_status != 'abandoned'` filter | `dbt/tests/assert_no_abandoned_freshness_in_mart.sql` |
| Missing source URL excluded (nothing to verify/register with) | `source_url is not null and != ''` filter | `dbt/tests/assert_no_missing_url_in_mart.sql` |
| Cancelled events excluded | `not is_cancelled` filter; the flag is derived in `stg_nyc_parks_events.sql` from the feed's `CANCELED:` title prefix, its only cancellation signal | `dbt/tests/assert_no_cancelled_events_in_mart.sql` |

The remaining rules are structural/referential-integrity guarantees, better expressed as
generic schema tests (declared in the `_*.yml` files next to each model):

| Guarantee | Where declared | Test type |
|---|---|---|
| `event_id`/`source_id` are unique, non-null natural keys at every layer | `_staging.yml`, `_intermediate.yml`, `_marts.yml` | `unique` / `not_null` |
| Every event references a real, existing source | `_staging.yml` (on `raw.activity_events.source_id`) | `relationships` |
| `event_name`, `start_at`, `source_url` are always present in the mart (every field a recommendation needs to render) | `_marts.yml` | `not_null` |
| Derived category-like fields (`activity_family`, `freshness_status`, `group_suitability`, `social_structure`) only ever take a known value | `_intermediate.yml`, `_marts.yml` | `accepted_values` |
| ZIP codes in the proximity lookup are unique | `_seeds.yml` (on `zip_centroids.zip_code`) | `unique` |

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
via `psql`), and the organizations row all round-tripped correctly. The backend test
suite has grown from 18 to 49 tests across that redesign and the later live-data
rewire (`test_presentation.py`, `test_favorites_api.py`, `test_organizations_api.py`,
`test_unknown_values.py`), all green.

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

**The two-data-path split is resolved.** Every endpoint now reads Postgres:
`/recommendations` and `/organizations` from the `analytics` marts, `/favorites` from
`raw.app_favorites`. The sample CSVs are no longer a serving path at all — they survive
as a pytest fixture (`backend/tests/conftest.py`), which is the right role for them:
asserting "`evt-001` ranks above `evt-004`" against a live feed whose contents change
daily would be neither deterministic nor meaningful.

**Trade-off this made explicit:** Postgres is now required to serve recommendations
(`make db-up` first). The previous "runs with no Docker" property is gone, deliberately
— it was only ever true because the app was reading flat files that had gone stale.

## Highest-risk issue

**Content coverage now rests almost entirely on one source.** All 184 recommendable
events come from the NYC Parks feed; the five curated organizations contribute zero,
because their sample events have all expired and nobody has re-curated them. The
product is therefore only as good, and only as diverse, as one public API — and that
API skews hard toward fitness classes (~69% of the mart). "Discover things you wouldn't
otherwise find" is undercut when the single supplier is itself the most discoverable
publisher in the city, which is exactly what `discovery_score` scores it as.

This is visible rather than hidden — `mart_organizations` shows the zeros plainly —
and it replaces the old top risk (the two disconnected data paths), which is now fixed.
The underlying curation problem below is unchanged, and this is its consequence made
concrete: the curated directory went stale, and nothing surfaced that until the events
simply stopped appearing.

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

~~Point `filter_engine.py` at Postgres instead of the CSVs.~~ **Done** — see
[Live data end to end](#live-data-end-to-end).

~~A dbt snapshot over feed history (SCD Type 2).~~ **Done** — see
[Recording history the source doesn't keep](#recording-history-the-source-doesnt-keep).

Next: **a small dashboard over the reliability and coverage marts.** Deliberately
sequenced after the snapshot, because the interesting views (cancellation trend, notice
period distribution, how coverage changes day to day) are views onto accumulated
history. Built first, it would have charted a single static snapshot.

Also worth doing, smaller: **alerting on the scheduled job.** The daily workflow keeps
history accumulating, but nothing announces a silent failure — the only signal today is
source freshness decaying until content drops out of the mart, which is passive and
after the fact.

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
