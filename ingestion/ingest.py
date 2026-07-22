"""Reads data/sample/sources.csv and data/sample/events.csv, validates
them, and loads them into the raw Postgres schema (raw.activity_sources,
raw.activity_events).

Safe to rerun: rows are upserted by their natural key (source_id /
event_id), so re-running does not create duplicate records.

Run with: python -m ingestion  (or `make ingest`)
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

from ingestion.db import (
    RAW_SCHEMA,
    build_metadata,
    ensure_schema,
    make_engine,
    run_pending_migrations,
    upsert_rows,
)
from ingestion.validate import (
    IngestionValidationError,
    parse_date_columns,
    validate_required_columns,
    validate_required_values,
)

logger = logging.getLogger("ingestion")

DEFAULT_SOURCES_CSV = Path("data/sample/sources.csv")
DEFAULT_EVENTS_CSV = Path("data/sample/events.csv")

REQUIRED_SOURCE_COLUMNS = ["source_id", "name", "category", "channel_type", "url"]
REQUIRED_EVENT_COLUMNS = ["event_id", "source_id", "title", "category", "start_time", "location"]


def load_sources(path: Path) -> pd.DataFrame:
    """Read, validate, and type-parse the sources CSV."""
    df = pd.read_csv(path)
    validate_required_columns(df, REQUIRED_SOURCE_COLUMNS, "sources.csv")
    validate_required_values(df, REQUIRED_SOURCE_COLUMNS, "source_id", "sources.csv")
    df = parse_date_columns(df, ["last_checked"], "source_id", "sources.csv")
    # astype(object) first: assigning None into a float64 column is silently
    # coerced back to NaN by pandas (it can't hold None in a float array), so
    # a blank/unknown numeric cell would round-trip through here as NaN
    # instead of a real SQL NULL -- the opposite of what "unknown must not be
    # treated as X" requires downstream.
    return df.astype(object).where(pd.notna(df), None)


def load_events(path: Path) -> pd.DataFrame:
    """Read, validate, and type-parse the events CSV."""
    df = pd.read_csv(path)
    validate_required_columns(df, REQUIRED_EVENT_COLUMNS, "events.csv")
    validate_required_values(df, REQUIRED_EVENT_COLUMNS, "event_id", "events.csv")
    df = parse_date_columns(df, ["start_time", "end_time", "last_checked"], "event_id", "events.csv")
    # See load_sources() above: astype(object) first so blank cells (e.g. an
    # unknown cost) become a real SQL NULL instead of round-tripping back to
    # NaN through pandas' float-column coercion.
    return df.astype(object).where(pd.notna(df), None)


def run(
    sources_csv: Path = DEFAULT_SOURCES_CSV,
    events_csv: Path = DEFAULT_EVENTS_CSV,
    schema: str = RAW_SCHEMA,
) -> None:
    """Load both CSVs into the database. Sources are loaded before events
    since events reference source_id.
    """
    engine = make_engine()
    ensure_schema(engine, schema)
    metadata, activity_sources, activity_events = build_metadata(schema=schema)
    metadata.create_all(engine)
    run_pending_migrations(engine, schema)

    sources_df = load_sources(sources_csv)
    inserted, updated = upsert_rows(
        engine, activity_sources, sources_df.to_dict("records"), "source_id"
    )
    logger.info("sources.csv: %d inserted, %d updated", inserted, updated)

    events_df = load_events(events_csv)
    inserted, updated = upsert_rows(
        engine, activity_events, events_df.to_dict("records"), "event_id"
    )
    logger.info("events.csv: %d inserted, %d updated", inserted, updated)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        run()
    except IngestionValidationError as exc:
        logger.error("Ingestion failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
