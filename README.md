# NYC Activity Discovery — an analytics engineering project

[![CI](https://github.com/zhen01/nyc-open-data-pipeline/actions/workflows/ci.yml/badge.svg)](https://github.com/zhen01/nyc-open-data-pipeline/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

An end-to-end pipeline that turns two very different sources — a hand-curated
organization directory and a live NYC Open Data API — into a single modeled,
tested, documented analytics layer, and then actually consumes it from a product.

**dbt** (staging → intermediate → marts, plus an SCD2 snapshot and an incremental
fact table; 75 tests, one singular test per business rule) on **Postgres**, fed by
idempotent **Python ingestion**, served through a **FastAPI** app, with **CI**
running the whole thing against a real database on every PR and a scheduled job
accumulating feed history daily.

The part worth reading is not the plumbing — it's what happened when a real feed
replaced sample data. A public API that republishes cancelled events, stamps the
wrong date on its own time fields, packs 28 categories into one delimited string,
and publishes no price at all forces you to decide what a pipeline should do when
the truth is *unknown*. Those decisions, and a genuine timezone bug they exposed,
are documented in [What the live feed threw at us](#what-the-live-feed-threw-at-us).

<details>
<summary><strong>Product context</strong> — why the business rules are what they are</summary>

NYC activity discovery is fragmented: big marketplaces surface commercial events,
while smaller recurring communities publish only on their own sites, Instagram or
newsletters. The product takes a free-time window, a budget and a few constraints,
and returns a handful of real, feasible, source-backed activities.

Two commitments drive every modeling decision in this repo:

1. **Never recommend something that isn't real and current.** An outdated, cancelled
   or unverifiable listing is worse than no result — it costs someone a trip across
   the city. This is why exclusions are enforced in the mart with a test each,
   rather than being left to the application.
2. **Never state something the data doesn't support.** Unknown price, unknown
   solo-friendliness and unknown location stay unknown rather than becoming
   free/false/nearby.

Result-set size is deliberately small, and every result explains itself.

</details>

---

## Contents

- [What this project demonstrates](#what-this-project-demonstrates)
- [The pipeline](#the-pipeline)
- [What the live feed threw at us](#what-the-live-feed-threw-at-us)
- [Creating data the source doesn't have](#creating-data-the-source-doesnt-have)
- [Modeling decisions worth defending](#modeling-decisions-worth-defending)
- [Business rules → tests](#business-rules--tests)
- [Quick start](#quick-start)
- [Repo structure](#repo-structure)
- [Ingestion layer](#ingestion-layer)
- [Analytics layer (dbt)](#analytics-layer-dbt)
- [Documentation & lineage](#documentation--lineage)
- [Continuous integration](#continuous-integration)
- [The application layer](#the-application-layer)
- [Known limitations & what's next](#known-limitations--whats-next)
- [License](#license)

## What this project demonstrates

| Capability | Where to look |
|---|---|
| Layered dimensional modeling (staging → intermediate → marts), consistent grain | [`dbt/models/`](dbt/models) |
| SCD Type 2 history over a source that publishes no history at all | [`snap_nyc_parks_events.sql`](dbt/snapshots/snap_nyc_parks_events.sql) |
| Append-only incremental fact table, idempotent across same-day re-runs | [`fct_event_observations.sql`](dbt/models/marts/fct_event_observations.sql) |
| Refusing to compute left-censored metrics rather than reporting an artefact | [`int_parks_event_lifecycle.sql`](dbt/models/intermediate/int_parks_event_lifecycle.sql) |
| Scheduled pipeline so history actually accumulates | [`daily-refresh.yml`](.github/workflows/daily-refresh.yml) |
| Business logic centralized in one place, not duplicated in application code | [`mart_activity_candidates.sql`](dbt/models/marts/mart_activity_candidates.sql) |
| Handling genuinely messy source data without fabricating values | [`stg_nyc_parks_events.sql`](dbt/models/staging/stg_nyc_parks_events.sql) |
| Data quality testing: 75 dbt tests, incl. 6 singular tests mapped 1:1 to business rules | [`dbt/tests/`](dbt/tests) + `_*.yml` |
| Modeling a source system that has no row in your source directory | [`stg_nyc_parks_source.sql`](dbt/models/staging/stg_nyc_parks_source.sql) |
| Correctness of "now" across timezones, enforced in models *and* their tests | [`dbt/macros/nyc_time.sql`](dbt/macros/nyc_time.sql) |
| Idempotent upsert-based ingestion from both CSV and a paginated REST API | [`ingestion/`](ingestion) |
| Self-documenting models: doc blocks, column descriptions, committed lineage site | [`dbt/docs_site/index.html`](dbt/docs_site/index.html) |
| CI that rebuilds and retests the warehouse on every PR | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| Deterministic tests over a non-deterministic live feed | [`backend/tests/conftest.py`](backend/tests/conftest.py) |

Scale: 1 seed, 10 models, 1 snapshot, 75 dbt tests, 81 Python tests. Roughly 200
recommendable events at any moment from a rolling 14-day window, with change
history accumulating daily.

## The pipeline

```
data/sample/*.csv                    NYC Open Data Socrata API
(curated, human-verified)            (live NYC Parks events, rolling 14-day window)
      │                                        │
      │  ingestion/ingest.py                   │  ingestion/nyc_parks.py
      ▼                                        ▼
raw.activity_sources/_events         raw.nyc_parks_events
      │                                        │
      ▼  stg_* (rename-only)                   ▼  stg_* (reshape + data-quality fixes)
stg_activity_events/_sources         stg_nyc_parks_events/_source
      │                                        │
      └──────────────┬─────────────────────────┘  union
                     ▼
        int_activity_enriched   — freshness, discovery/actionability,
                     │            audience fit (NULL when unknowable)
                     ▼
        mart_activity_candidates  — every business rule, enforced once
        mart_organizations        — sources + recommendable-event counts
                     ▼
        FastAPI (filter → score → explain)  →  React Discover page


  history track (daily schedule)
  ──────────────────────────────
raw.nyc_parks_events
      │
      ▼  snapshot, check strategy on content cols
snap_nyc_parks_events        — SCD2: the only record of what the feed used to say
      │
      ├─────────────────────────────┐
      ▼                             ▼
int_parks_event_lifecycle    fct_event_observations  — append-only, incremental
  per-event: cancelled?        one row per (event, date seen)
  rescheduled? notice given?
      │                             │
      └──────────────┬──────────────┘
                     ▼
        mart_source_reliability   — cancellation rate, notice period,
                                    reschedule rate per publisher
```

Both feeds land in `raw`, dbt models them into two marts, and the API reads those
marts. A business rule is written once, tested once, and enforced everywhere.

## What the live feed threw at us

The project originally ran on curated sample CSVs. Every one of those events
eventually expired, which meant the app was serving an empty result set while a
live feed sat ingested and unused — so the serving layer was repointed at the
warehouse and the real feed wired through. That surfaced five problems the clean
sample data had never exercised.

### 1. The time fields carry the wrong date

`starttime` and `endtime` come back as full timestamps, but their date component
is the feed's *publication* date — every row read `2026-07-20` regardless of when
the event actually happens. The real date is in `startdate`. Only the time-of-day
is trustworthy, so `start_at` is rebuilt from `startdate` plus that time, behind a
regex guard so one malformed value can't fail the model.

### 2. One string, 28 categories, no hierarchy

`categories` is pipe-delimited free text (`Fitness | Volunteer | Gardening`), with
28 distinct values and roughly 60% of rows carrying some fitness variant. Mapping
it onto the project's 7-value taxonomy therefore needs a **priority order**, not a
first match — otherwise a volunteer gardening event lands in `active` because
"Fitness" appeared first. `active` is deliberately *last*: it's the broad catch-all,
not a precise label.

It also mixes genuine activity types with audience modifiers (`Best for Kids`,
`Seniors`) and delivery format (`Virtual/Online Events`). Those describe *who* and
*how*, not *what*, so they're surfaced as separate flags rather than overwriting the
category. 5 of ~390 rows match nothing at all and stay `NULL`, which excludes them
via an existing structural rule instead of guessing a bucket for them.

### 3. Cancelled events keep being published

The feed serves cancelled events indefinitely, recording the cancellation only as a
`CANCELED:` prefix on the title. There is no status field. Those rows are otherwise
completely healthy — upcoming, active source, fresh, valid URL — so without an
explicit rule they'd be recommended. Hence a new business rule and
[a test](dbt/tests/assert_no_cancelled_events_in_mart.sql) enforcing it.

### 4. Coordinates were being thrown away at ingestion

`coordinates` and `description` are present on every row of the payload but were
never extracted into columns. Extracting them is what makes proximity ranking work
for API events at all, since the feed publishes no ZIP code. Coordinates outside
plausible NYC bounds are rejected rather than stored — a wrong coordinate that
silently ranks an event as "nearby" is worse than no coordinate.

### 5. The warehouse's "today" was not New York's today

Postgres runs in UTC; the product is entirely NYC-local. Bare `current_timestamp`
in the models therefore meant *UTC today*. Between 8pm and midnight EDT, UTC has
already rolled over — so the mart was excluding that evening's remaining events as
"expired" while they were still hours away. **15 events were affected at the moment
it was caught.**

Fixed with [`nyc_now()` / `nyc_today()`](dbt/macros/nyc_time.sql), used by the
models *and* by the singular tests that guard them, so the two can't drift apart.

## Creating data the source doesn't have

The API publishes a rolling 14-day window of current state and no history
endpoint. Ask it what it said yesterday and there is no answer — not behind a
paywall, not in an archive. Raw ingestion upserts on the publisher's `guid`, so
it too keeps only the latest version.

That means a whole class of question is unanswerable from the source: *how often
does this publisher cancel? how much notice do attendees get? how far ahead are
events posted?* Those facts only come into existence if something records the
feed over time.

Three pieces do that:

- **[`snap_nyc_parks_events`](dbt/snapshots/snap_nyc_parks_events.sql)** — SCD2
  history via the `check` strategy over content columns. `ingested_at` is
  deliberately *excluded* from `check_cols`: it is rewritten on every upsert
  whether or not anything changed, so including it would manufacture a version
  per run and turn a change log into a write log.
- **[`fct_event_observations`](dbt/models/marts/fct_event_observations.sql)** —
  append-only incremental fact, one row per (event, date confirmed present in
  the feed). `delete+insert` on the composite key so a same-day re-run replaces
  rather than duplicates. A row asserts presence only; a gap is never read as
  absence, since it is equally consistent with the pipeline not having run.
- **[`mart_source_reliability`](dbt/models/marts/mart_source_reliability.sql)** —
  the payoff: cancellation rate, notice period, reschedule rate per source.

### The correctness detail that matters most here

13 events were already carrying a `CANCELED:` prefix the first time the pipeline
ever saw them. Their cancellation happened before the observation window opened,
so **the notice period is unknowable** — subtracting first-capture from the event
date would produce a number describing when *I* started collecting, not anything
about the publisher.

So `cancellation_lead_hours` is populated only where the live→cancelled
transition was actually witnessed between two snapshot versions. Everything else
is `NULL` and flagged via `cancellation_observed`, and the reliability mart uses
`events_with_observed_lifecycle` as its denominator rather than the total. It
also reports `observation_window_days` alongside every rate, so a cancellation
percentage computed over a few days cannot be misread as a stable property of
the publisher.

A daily [scheduled workflow](.github/workflows/daily-refresh.yml) runs
ingest → snapshot → build in that order, because ingest overwrites raw with the
feed's current state and the snapshot must read it before the next ingest
destroys the previous version.

## Modeling decisions worth defending

### Unknown is not a default

The API publishes no price, no solo-friendliness flag, and no vibe tags. Those stay
`NULL` end to end:

- an unknown price never satisfies a budget filter (the inverse of the
  already-enforced "unknown price is not free" rule);
- unknown solo-friendliness never satisfies a solo-friendly request;
- the four audience-fit scores are `NULL` rather than computed — scoring them from
  absent inputs would have given every such event exactly 60 for "couple", purely
  from a constant baseline. A confident-looking number derived from nothing is worse
  than an honest gap.

The cost is real: some filters legitimately return very little. That gap is visible
in `mart_organizations` rather than papered over.

Fixing this also exposed a ranking flaw worth naming. Dropping the proximity
component for an event with no coordinates renormalized the remaining weights and
pushed it *above* an event confirmed to be 0.3 miles away — **missing data
outranking good data**. Unlocatable events now take a neutral half-score instead.

### The API is modeled as a source

NYC Parks has no row in the hand-curated source directory, but conceptually it *is*
a source, and all the downstream freshness/confidence/discovery logic is written in
terms of a source's `channel_type` / `update_cadence` / `last_checked`. Rather than
branching that logic on "CSV or API?", [`stg_nyc_parks_source.sql`](dbt/models/staging/stg_nyc_parks_source.sql)
synthesizes the one source row the API deserves.

Its `source_last_checked` is derived from `max(ingested_at)` rather than hardcoded,
so **a pipeline that silently stops running decays in freshness instead of staying
permanently "fresh"** — the failure mode shows up in the data itself.

### Business rules live in the mart, not the application

Expiry, inactive sources, abandoned freshness, missing URLs, unknown prices and
cancellations are enforced once in `mart_activity_candidates`, each with a matching
singular test. The API's `filter_engine.py` applies only the constraints belonging
to a specific user request. Previously the same rules existed in both SQL and Python
and could drift apart silently.

`GET /organizations` reads `mart_organizations` for the same reason: counting the
raw event table applies none of those rules, so it would advertise an organization
on the strength of cancelled or expired events.

## Business rules → tests

Each rule is a singular test — custom SQL that fails if any row comes back — because
each is really "the mart's `WHERE` clause is correct", which a generic schema test
can't express.

| Business rule | Test |
|---|---|
| Expired events excluded (in **NYC** local time) | [`assert_no_expired_events_in_mart.sql`](dbt/tests/assert_no_expired_events_in_mart.sql) |
| Inactive sources excluded | [`assert_no_inactive_source_events_in_mart.sql`](dbt/tests/assert_no_inactive_source_events_in_mart.sql) |
| Unknown price stays `NULL`, never coalesced to 0/free | [`assert_unknown_price_stays_null.sql`](dbt/tests/assert_unknown_price_stays_null.sql) |
| Abandoned-freshness sources excluded (`stale` is kept, `abandoned` is not) | [`assert_no_abandoned_freshness_in_mart.sql`](dbt/tests/assert_no_abandoned_freshness_in_mart.sql) |
| Missing source URL excluded — nothing to verify or register with | [`assert_no_missing_url_in_mart.sql`](dbt/tests/assert_no_missing_url_in_mart.sql) |
| Cancelled events excluded | [`assert_no_cancelled_events_in_mart.sql`](dbt/tests/assert_no_cancelled_events_in_mart.sql) |

The remaining 69 are generic schema tests (`unique`, `not_null`, `accepted_values`,
`relationships`) declared beside each model. Full mapping, including the structural
guarantees, in [STATUS.md](STATUS.md#business-rules--tests).

## Quick start

Needs Docker and [uv](https://docs.astral.sh/uv/). From a clean checkout:

```bash
uv sync                          # creates .venv on the pinned Python, from uv.lock
cp .env.example .env && export $(grep -v '^#' .env | xargs)
make db-up                       # Postgres via docker compose
make ingest && make ingest-parks # curated CSVs + the live NYC Parks feed
make dbt-deps && make dbt-seed && make dbt-build
```

Inspect the warehouse directly:

```bash
docker compose exec db psql -U nyc_activities -d nyc_activities \
  -c "select activity_category, count(*) from analytics.mart_activity_candidates group by 1 order by 2 desc;" \
  -c "select source_name, channel_type, upcoming_event_count from analytics.mart_organizations order by 3 desc;"
```

Or run the app on top of it:

```bash
make mvp   # http://localhost:8000
curl "http://localhost:8000/recommendations?category=active&zip_code=10001"
```

`make ingest-parks` pulls a rolling 14-day window — re-run it, then `make dbt-build`,
to refresh the catalogue.

## Repo structure

| Path | Purpose |
|---|---|
| **Analytics layer** | |
| `dbt/models/staging/stg_activity_*.sql` | Rename-only views over the curated `raw.*` tables |
| `dbt/models/staging/stg_nyc_parks_events.sql` | Reshapes the live feed: rebuilds timestamps, maps 28 categories by priority, flags cancelled/virtual |
| `dbt/models/staging/stg_nyc_parks_source.sql` | Synthesizes the API as a source row so downstream logic applies unchanged |
| `dbt/models/intermediate/int_activity_enriched.sql` | Unions both feeds; computes freshness, audience-fit, discovery/actionability |
| `dbt/models/marts/mart_activity_candidates.sql` | The recommendable-events mart — every business-rule exclusion, in one place |
| `dbt/models/marts/mart_organizations.sql` | One row per active source + how many recommendable events it currently has |
| `dbt/macros/nyc_time.sql` | `nyc_now()` / `nyc_today()` — "now" in NYC local time, not the warehouse's UTC |
| `dbt/models/docs.md` | Shared doc blocks for derived fields, referenced via `{{ doc(...) }}` |
| `dbt/snapshots/snap_nyc_parks_events.sql` | SCD2 change history — the only place the feed's past state exists |
| `dbt/models/marts/fct_event_observations.sql` | Append-only incremental fact: event present in feed on date |
| `dbt/models/intermediate/int_parks_event_lifecycle.sql` | Per-event lifecycle; refuses to compute left-censored notice periods |
| `dbt/models/marts/mart_source_reliability.sql` | Cancellation rate, notice period, reschedule rate per source |
| `dbt/tests/` | One singular SQL test per business rule |
| `dbt/seeds/zip_centroids.csv` | Small curated ZIP → lat/lon/borough table (deliberately not a geocoding API) |
| **Ingestion** | |
| `ingestion/db.py` | Engine, `raw` table definitions, dialect-aware upsert helper, additive migrations |
| `ingestion/ingest.py` | Reads curated CSVs, validates, upserts, logs counts |
| `ingestion/nyc_parks.py` | Fetches/parses/loads the paginated Socrata API into `raw.nyc_parks_events` |
| `ingestion/validate.py` | Required-column/value and date validation |
| `ingestion/tests/` | Validation, dedup/idempotency, API parsing, coordinate-bounds tests |
| **Application** | |
| `backend/app/services/filter_engine.py` | Reads the mart; applies the user's own constraints only |
| `backend/app/services/scoring_engine.py` | Transparent ranking (proximity, vibe, source confidence) — no learned weights |
| `backend/app/services/explain_engine.py` | Rule-based "why this fits" + explicit uncertainty |
| `backend/app/services/presentation.py` | Display-only derived fields (badges, tags, transit estimate) |
| `backend/app/api/` | `recommendations.py`, `favorites.py`, `organizations.py` |
| `backend/tests/conftest.py` | Deterministic fixture so tests don't assert against a live feed |
| `frontend/src/` | React + Vite + TS Discover page |
| **Docs & ops** | |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How data flows end to end, and why each layer exists |
| [`STATUS.md`](STATUS.md) | What works today, the highest-risk issue, the next deliverable |
| `.github/workflows/ci.yml` | Lint, both pytest suites, frontend build, ingestion, `dbt build` |
| `.github/workflows/daily-refresh.yml` | Scheduled ingest → snapshot → build, so history accumulates |
| `Makefile` | `db-up`, `ingest`, `ingest-parks`, `dbt-*`, `refresh`, `test`, `test-backend`, `mvp` |

## Ingestion layer

Two independent paths that share only generic plumbing (engine, upsert helper,
schema creation) from `ingestion/db.py`.

**Curated CSVs** (`make ingest`) load `data/sample/*.csv` into
`raw.activity_sources` / `raw.activity_events`. **The NYC Parks API**
(`make ingest-parks`) pages through the Socrata dataset `w3wp-dpdi` in batches of
50 and loads `raw.nyc_parks_events`, keeping the full original record in a
`raw_payload` JSON column so no field is lost to the column projection.

Both upsert on a natural key (`source_id` / `event_id` / the API's `guid`), so
re-running reports `0 inserted, N updated` and never duplicates rows. Neither does
any business normalization — categories aren't mapped and costs aren't inferred at
this layer. That's staging's job.

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string, shared by ingestion, dbt and the API |
| `NYC_OPEN_DATA_APP_TOKEN` | no | Socrata app token; raises the default public rate limit |
| `NYC_PARKS_RECORD_LIMIT` | no | Max records per run (default 200) |

A latent bug found while building the mart is worth recording: a blank numeric cell
was round-tripping through pandas as `NaN` instead of a true SQL `NULL`, because
assigning `None` into a `float64` column is silently coerced back. In a Postgres
`numeric` column `NaN` sorts and compares like a *huge* number rather than an
absence — which would have quietly broken the "unknown price is not free" rule
downstream. Fixed with `.astype(object)` before the conversion.

## Analytics layer (dbt)

**Layering.** Staging is one model per source table, rename-only for the curated
feed and reshaping for the API feed. `int_activity_enriched` unions them and does
all the derivation. The marts apply exclusions and select the final field list.
Grain is one row per event throughout — the intermediate model adds columns, never
rows.

**Freshness.** `freshness_status` is `fresh` / `stale` / `abandoned`, from days
since the *source's* `last_checked` relative to its own `update_cadence`
(`daily`/`weekly`/`seasonal` → 1/7/90 days). Only `abandoned` is excluded; `stale`
rows are kept and flagged. The same cadence mapping exists in
`scoring_engine.py` so "freshness" means one thing in both the warehouse and the API.

**Audience-fit scores** (`solo_private_score`, `solo_social_score`, `couple_score`,
`small_group_score`) are documented point sums over `solo_friendly` and vibe tags —
rule-based, so every point traces to a specific input, and `NULL` when the inputs
are unknown. `group_suitability` is the label of whichever score is highest.

`profiles.yml` lives in `dbt/` rather than `~/.dbt/` and reuses the same `POSTGRES_*`
env vars as `ingestion/` and `docker-compose.yml` — one connection config for the
whole project.

## Documentation & lineage

Every model and mart column has a `description`. Shared explanations for derived
fields (`freshness_status`, `discovery_score`, the audience scores) live once in
`dbt/models/docs.md` as doc blocks and are referenced via `{{ doc(...) }}` rather
than copy-pasted.

A self-contained static docs site — lineage graph, every description, every test —
is committed at [`dbt/docs_site/index.html`](dbt/docs_site/index.html). Open it
directly in a browser; no server needed.

```bash
cd dbt && dbt docs generate --profiles-dir . --static
cp target/static_index.html docs_site/index.html
```

## Continuous integration

`.github/workflows/ci.yml` runs on every PR against a real Postgres service
container: `ruff`, `sqlfluff` (with the dbt templater), both pytest suites, a
frontend build check, then `python -m ingestion` and `dbt deps` / `seed` / `build`.

The point isn't a complex pipeline — it's that **a broken data model is caught
before merge rather than discovered in the warehouse later**. The dbt step runs
the full test suite against freshly loaded data, so a modeling change that violates
a business rule fails the PR.

## The application layer

Secondary to the pipeline, but it exists so the marts have a real consumer rather
than being a warehouse nobody queries.

`GET /recommendations` runs a two-stage pipeline over the mart: hard feasibility
filtering, then transparent component-based scoring (ZIP proximity, vibe-tag match,
source confidence), each normalized 0–1 and blended into a 0–100 score. Any
component whose input the user didn't provide is dropped and the remaining weights
renormalized. Every result carries a `score`, `confidence_label`,
`source_verified_date` and a rule-based explanation — no black-box ranking.

Three modes: `specific` (category as a hard filter), `mood` (ranked by vibe match),
`surprise` (weighted-random sample from the top pool, reproducible with a fixed
seed). `GET /organizations` powers a "hidden gems" row from `mart_organizations`.
`GET/POST/DELETE /favorites` persists per-device favorites in `raw.app_favorites`,
keyed by an anonymous client-generated UUID — no login.

The frontend is a single-screen React + Vite + TS Discover page, built into
`backend/app/static/` and served from the same origin. For UI work, run Vite and
FastAPI side by side:

```bash
cd backend && uvicorn app.main:app --reload --port 8000   # terminal 1
cd frontend && npm install && npm run dev                 # terminal 2 → :5173
```

`vite.config.ts` proxies the API routes to port 8000, so no base URL is hardcoded.

## Known limitations & what's next

Stated plainly, because they're the honest boundary of what this demonstrates:

- **History starts when recording started, not before.** The snapshot and the
  observation fact table can only know what they have witnessed. Metrics that
  depend on seeing a transition — cancellation rate, notice period — are `NULL`
  until one is actually observed, and events already cancelled at first capture
  are excluded from those denominators rather than guessed at. The numbers get
  meaningful as the window widens; they are not meaningful on day one, and the
  models say so via `observation_window_days`.
- **Scheduled, but not monitored.** A daily workflow keeps history accumulating,
  but there is no alerting if it silently stops — the only signal is source
  freshness decaying until content drops out of the mart, which is passive and
  after the fact.
- **Content rests almost entirely on one source.** All ~200 recommendable events
  come from NYC Parks; the five curated organizations contribute zero, because
  their sample events expired and nobody re-curated them. The feed also skews
  heavily toward fitness (~69%). This is visible in `mart_organizations` rather
  than hidden.
- **No geocoding or routing API.** ZIP proximity uses a small curated centroid
  table, and transit time is a documented fixed-speed estimate from straight-line
  distance, labeled as approximate in the UI.
- **Rule-based scoring by choice.** Transparency is the point; a learned ranking
  model would lose the per-result "why this fits" explanation.

See [STATUS.md](STATUS.md) for the full current state, the highest-risk issue, and
the sequenced next deliverables.

## License

[MIT](LICENSE) © Zhen Fang
