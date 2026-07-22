"""Standalone data-ingestion vertical slice: loads curated CSV data into
the `raw` Postgres schema. Independent of the (not-yet-built) FastAPI app
in backend/ -- see ARCHITECTURE.md for how this fits the larger project.
"""
