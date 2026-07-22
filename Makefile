.PHONY: db-up db-down ingest ingest-parks test test-backend mvp dbt-deps dbt-seed dbt-build

db-up:
	docker compose up -d db

db-down:
	docker compose down

ingest:
	python -m ingestion

ingest-parks:
	python -m ingestion.nyc_parks

test:
	python -m pytest ingestion/tests

test-backend:
	cd backend && python -m pytest tests

mvp:
	cd backend && uvicorn app.main:app --reload --port 8000

dbt-deps:
	cd dbt && dbt deps --profiles-dir .

dbt-seed:
	cd dbt && dbt seed --profiles-dir .

dbt-build:
	cd dbt && dbt build --profiles-dir .
