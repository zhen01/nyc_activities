"""Ingests upcoming NYC Parks public events from the NYC Open Data Socrata
API into a dedicated raw table (raw.nyc_parks_events).

Isolated from the curated-CSV ingestion path (ingest.py / validate.py):
this module owns its own fetch/parse/table-definition logic end to end,
and only reuses generic DB plumbing (engine, schema creation, upsert)
from ingestion.db.

Source: "NYC Parks Public Events - Upcoming 14 Days"
API docs: https://dev.socrata.com/foundry/data.cityofnewyork.us/w3wp-dpdi
No auth is required for this public dataset; NYC_OPEN_DATA_APP_TOKEN is
optional and, if set, is sent to raise Socrata's default rate limit.

Run with: python -m ingestion.nyc_parks
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests
from sqlalchemy import JSON, Column, Date, DateTime, MetaData, String, Table

from ingestion.db import RAW_SCHEMA, ensure_schema, make_engine, upsert_rows

logger = logging.getLogger("ingestion.nyc_parks")

API_URL = "https://data.cityofnewyork.us/resource/w3wp-dpdi.json"
REQUEST_TIMEOUT_SECONDS = 10
PAGE_SIZE = 50
DEFAULT_RECORD_LIMIT = 200  # overridable via NYC_PARKS_RECORD_LIMIT


class NycParksFetchError(Exception):
    """Raised when the NYC Parks API request fails: timeout, HTTP error,
    or a response that isn't valid/expected JSON."""


class NycParksRecordError(Exception):
    """Raised for a single malformed record: missing id or an unparseable
    date. Callers should catch this per-record and keep going."""


def build_table(schema: Optional[str] = RAW_SCHEMA) -> tuple[MetaData, Table]:
    """Define the nyc_parks_events raw table.

    `schema=None` is used by tests running against SQLite, which has no
    concept of schemas; production runs against Postgres with schema="raw".
    Columns mirror the source fields as closely as possible (no derived/
    computed fields) plus a raw_payload JSON backup of the full record and
    an ingested_at timestamp -- this is a raw/bronze layer, not curated.
    """
    metadata = MetaData(schema=schema)
    table = Table(
        "nyc_parks_events",
        metadata,
        Column("source_record_id", String, primary_key=True),
        Column("title", String),
        Column("startdate", Date),
        Column("enddate", Date),
        Column("starttime", String),
        Column("endtime", String),
        Column("location", String),
        Column("parknames", String),
        Column("categories", String),
        Column("link_url", String),
        Column("registration_url", String),
        Column("raw_payload", JSON, nullable=False),
        Column("ingested_at", DateTime, nullable=False),
    )
    return metadata, table


def fetch_events(limit: int = DEFAULT_RECORD_LIMIT, page_size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    """Fetch up to `limit` events from the NYC Parks API, paging through
    results in batches of `page_size` ($limit/$offset/$order=guid).

    Raises NycParksFetchError on timeout, HTTP error, a network failure,
    or a response body that isn't a JSON list.
    """
    app_token = os.environ.get("NYC_OPEN_DATA_APP_TOKEN")
    headers = {"X-App-Token": app_token} if app_token else {}

    records: list[dict[str, Any]] = []
    offset = 0
    while len(records) < limit:
        batch_limit = min(page_size, limit - len(records))
        params = {"$limit": batch_limit, "$offset": offset, "$order": "guid"}
        try:
            response = requests.get(
                API_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            batch = response.json()
        except requests.exceptions.Timeout as exc:
            raise NycParksFetchError(
                f"NYC Parks API request timed out after {REQUEST_TIMEOUT_SECONDS}s"
            ) from exc
        except requests.exceptions.HTTPError as exc:
            raise NycParksFetchError(f"NYC Parks API returned an HTTP error: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise NycParksFetchError(f"NYC Parks API request failed: {exc}") from exc
        except ValueError as exc:  # response.json() decode failure
            raise NycParksFetchError(f"NYC Parks API returned invalid JSON: {exc}") from exc

        if not isinstance(batch, list):
            raise NycParksFetchError(
                "NYC Parks API returned an unexpected response shape (expected a JSON list)"
            )

        if not batch:
            break  # no more pages

        records.extend(batch)
        offset += len(batch)
        if len(batch) < batch_limit:
            break  # short page means we've reached the end

    return records[:limit]


def _extract_url(value: Any) -> Optional[str]:
    """Socrata `url`-type columns (link, registration_url, image) come
    back as {"url": "..."} objects rather than plain strings."""
    if isinstance(value, dict):
        return value.get("url")
    if isinstance(value, str):
        return value
    return None


def parse_event_date(value: Any, field_name: str) -> Optional[date]:
    """Validate/parse a Socrata calendar_date string for safe storage in a
    SQL Date column. Returns None for missing/empty values. Raises
    NycParksRecordError for a non-empty value that isn't a parseable date
    -- this is type-safety for storage, not business normalization.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError as exc:
        raise NycParksRecordError(f"unparseable {field_name}: {value!r}") from exc


def parse_record(record: dict[str, Any]) -> dict[str, Any]:
    """Convert one raw API record into a row dict for nyc_parks_events.

    Raises NycParksRecordError if the record has no usable id (guid) or
    an unparseable date -- these are the two ways a record is "malformed"
    for our purposes.
    """
    source_record_id = record.get("guid")
    if not source_record_id:
        raise NycParksRecordError("record is missing required field 'guid'")

    return {
        "source_record_id": str(source_record_id),
        "title": record.get("title"),
        "startdate": parse_event_date(record.get("startdate"), "startdate"),
        "enddate": parse_event_date(record.get("enddate"), "enddate"),
        "starttime": record.get("starttime"),
        "endtime": record.get("endtime"),
        "location": record.get("location"),
        "parknames": record.get("parknames"),
        "categories": record.get("categories"),
        "link_url": _extract_url(record.get("link")),
        "registration_url": _extract_url(record.get("registration_url")),
        "raw_payload": record,
        "ingested_at": datetime.now(timezone.utc),
    }


def parse_records(raw_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Parse a batch of raw API records, skipping (and counting) any that
    are malformed instead of failing the whole batch. Returns (rows, failed_count).
    """
    rows: list[dict[str, Any]] = []
    failed = 0
    for record in raw_records:
        try:
            rows.append(parse_record(record))
        except NycParksRecordError as exc:
            failed += 1
            logger.warning("nyc_parks: skipping malformed record: %s", exc)
    return rows, failed


def ingest(limit: int = DEFAULT_RECORD_LIMIT, schema: str = RAW_SCHEMA) -> None:
    """Fetch, parse, and upsert NYC Parks events into raw.nyc_parks_events.

    Safe to rerun: rows are upserted by source_record_id (the API's guid),
    so re-running does not create duplicate records. Existing rows are
    never deleted.
    """
    engine = make_engine()
    ensure_schema(engine, schema)
    metadata, table = build_table(schema=schema)
    metadata.create_all(engine)

    raw_records = fetch_events(limit=limit)
    logger.info("nyc_parks: fetched %d raw record(s) from the API", len(raw_records))

    rows, failed = parse_records(raw_records)
    inserted, updated = upsert_rows(engine, table, rows, "source_record_id")
    logger.info(
        "nyc_parks_events: %d inserted, %d updated, %d failed", inserted, updated, failed
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    limit = int(os.environ.get("NYC_PARKS_RECORD_LIMIT", DEFAULT_RECORD_LIMIT))
    try:
        ingest(limit=limit)
    except NycParksFetchError as exc:
        logger.error("nyc_parks ingestion failed: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
