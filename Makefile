# Every Python target goes through `uv run`, which resolves .venv from the repo
# root (even in the `cd`-ing targets) and creates it from uv.lock if missing.
# No `source .venv/bin/activate` needed anywhere.
.PHONY: db-up db-down ingest ingest-parks test test-backend mvp dbt-deps dbt-seed \
        dbt-snapshot dbt-build refresh

db-up:
	docker compose up -d db

db-down:
	docker compose down

ingest:
	uv run python -m ingestion

ingest-parks:
	uv run python -m ingestion.nyc_parks

test:
	uv run python -m pytest ingestion/tests

test-backend:
	cd backend && uv run python -m pytest tests

mvp:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dbt-deps:
	cd dbt && uv run dbt deps --profiles-dir .

dbt-seed:
	cd dbt && uv run dbt seed --profiles-dir .

dbt-snapshot:
	cd dbt && uv run dbt snapshot --profiles-dir .

dbt-build:
	cd dbt && uv run dbt build --profiles-dir .

# One pass of the live pipeline, in the only order that preserves history:
# ingest overwrites raw with the feed's current state, so the snapshot must
# read it *before* the next ingest destroys the previous version. `dbt build`
# runs the snapshot too, but only as a DAG node -- running it explicitly first
# keeps the ordering guarantee obvious rather than incidental.
refresh: ingest-parks dbt-snapshot dbt-build
