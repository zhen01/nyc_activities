# NYC Activity Discovery Engine

A personalized activity discovery tool for NYC: give it a free-time window, budget, and
a few constraints, and get back 1-3 real, feasible, source-backed activities — including
ones from small organizations (social sports leagues, free kayaking programs, volunteer
marketplaces, language exchanges) that don't show up on mainstream event platforms.

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

## Repo Structure

| Path | Purpose |
|---|---|
| `backend/app/main.py` | FastAPI entrypoint |
| `backend/app/api/` | HTTP routes (`POST /recommendations`) |
| `backend/app/models/schema.py` | Request/response models (`UserConstraints`, `Recommendation`) |
| `backend/app/services/filter_engine.py` | Feasibility filtering — principle #1 |
| `backend/app/services/explain_engine.py` | "Why this fits" explanation generation — principle #4 |
| `backend/app/db/` | DB connection + ORM models (`Organization`, `Activity`, `Source`) |
| `backend/data/sources.yaml` | Manually maintained directory of orgs/channels — principle #6 |
| `backend/data/seed_activities.json` | Curated, human-verified activities actually served to users |
| `backend/scripts/load_seed_data.py` | Loads seed data into the database |
| `backend/tests/` | Unit tests, starting with the filter engine |
| `frontend/src/` | Minimal React UI: one constraint form, one results list |
| `docs/source_directory_guide.md` | How to add/maintain a source and promote it to a seed activity |
| `ARCHITECTURE.md` | How data flows end to end |
| `STATUS.md` | What currently works, the highest-risk issue, and the next deliverable |

## Status

This repo is currently a structural scaffold — see [STATUS.md](STATUS.md) for what's
implemented, what isn't, and what to build next.
