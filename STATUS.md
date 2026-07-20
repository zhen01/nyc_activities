# Status

## Currently working

Nothing is functional yet. This repo is a structural scaffold: every backend/frontend
file contains a docstring/comment describing its intended responsibility plus a `TODO`,
so the intended architecture is documented before any logic is written. No database is
created, no endpoint responds, and no frontend renders yet.

## Highest-risk issue

**Data trust and freshness of the manually curated source directory.** The entire
product's credibility depends on `sources.yaml` / `seed_activities.json` staying
accurate and current, and that's a manual, likely single-maintainer process. If
`last_checked` dates go stale, the engine will recommend events that are outdated,
cancelled, or wrong — directly violating principle #2 ("discovery without
hallucination"). There is currently no mechanism, in the repo or otherwise, to detect
or surface staleness. This is a bigger risk right now than any technical/infra choice.

## Smallest next deliverable

Skip the frontend and the explain engine entirely for v0. Ship just:

1. 10-15 real, manually curated NYC activities in `seed_activities.json` (not
   placeholders).
2. `load_seed_data.py` implemented to load them into SQLite.
3. `filter_engine.py` implemented for the 4 hard constraints: time window, budget,
   location/travel radius, solo-friendly.
4. One working endpoint you can `curl` with constraints and get back 1-3 real matches
   as JSON.

That alone proves principle #1 end-to-end without needing UI or explanation-generation
work.

## Unnecessary complexity to avoid (for now)

- **No LLM calls yet.** Rule-based templates in `explain_engine.py` are enough to prove
  the "why it fits" concept. Adding an LLM before the filter logic works is solving the
  wrong problem first.
- **No Postgres/Docker/deployment.** SQLite + local `uvicorn`/`vite` is enough to
  demonstrate the architecture; add infra only once the MVP loop works end to end.
- **No user accounts or auth.** Not needed for a single-session recommendation tool.
- **No scraping/automation pipeline.** Principles #5 and #6 explicitly say start manual
  — don't build a scraper before the manual version has proven useful.
- **No state management library or routing on the frontend.** One screen, one form, one
  result list.
