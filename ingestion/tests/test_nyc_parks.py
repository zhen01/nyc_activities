"""Tests for the NYC Parks ingestion module: API parsing, empty/malformed
responses, timeout/HTTP failures, duplicate handling, and date edge cases.

HTTP calls are mocked (unittest.mock) -- no real network access in tests.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests
from sqlalchemy import create_engine, select

from ingestion.nyc_parks import (
    NycParksFetchError,
    NycParksRecordError,
    build_table,
    fetch_events,
    parse_event_date,
    parse_record,
    parse_records,
)
from ingestion.db import upsert_rows

SAMPLE_RECORD = {
    "title": "Summer on the Hudson: Tai Chi",
    "guid": "2146730",
    "link": {"url": "http://www.nycgovparks.org/events/2026/07/19/tai-chi"},
    "description": "Join us for Tai Chi.",
    "parkids": "M072",
    "parknames": "Riverside Park",
    "startdate": "2026-07-19T00:00:00.000",
    "enddate": "2026-07-19T00:00:00.000",
    "starttime": "2026-07-19 08:00:00",
    "endtime": "2026-07-19 09:30:00",
    "location": "Soldiers' and Sailors' Monument (in Riverside Park)",
    "categories": "Fitness | Outdoor Fitness",
    "registration_url": {"url": "https://example.org/register"},
    "pubdate": "2026-07-19 00:00:05",
}


def _mock_response(json_data, status_ok=True):
    resp = MagicMock()
    resp.json.return_value = json_data
    if status_ok:
        resp.raise_for_status.return_value = None
    else:
        resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 error")
    return resp


# --- successful API response parsing ---------------------------------------


def test_fetch_events_returns_records_from_a_full_page():
    with patch("ingestion.nyc_parks.requests.get") as mock_get:
        mock_get.return_value = _mock_response([SAMPLE_RECORD, SAMPLE_RECORD])
        records = fetch_events(limit=2, page_size=2)
    assert len(records) == 2
    assert mock_get.call_count == 1


def test_parse_record_extracts_expected_fields():
    row = parse_record(SAMPLE_RECORD)
    assert row["source_record_id"] == "2146730"
    assert row["title"] == "Summer on the Hudson: Tai Chi"
    assert row["startdate"] == date(2026, 7, 19)
    assert row["link_url"] == "http://www.nycgovparks.org/events/2026/07/19/tai-chi"
    assert row["registration_url"] == "https://example.org/register"
    assert row["raw_payload"] == SAMPLE_RECORD
    assert row["ingested_at"] is not None


# --- empty API response ------------------------------------------------------


def test_fetch_events_returns_empty_list_on_empty_response():
    with patch("ingestion.nyc_parks.requests.get") as mock_get:
        mock_get.return_value = _mock_response([])
        records = fetch_events(limit=50)
    assert records == []
    assert mock_get.call_count == 1


# --- malformed records --------------------------------------------------------


def test_parse_record_raises_when_guid_missing():
    bad_record = dict(SAMPLE_RECORD)
    del bad_record["guid"]
    with pytest.raises(NycParksRecordError, match="guid"):
        parse_record(bad_record)


def test_parse_records_skips_malformed_and_counts_failures():
    good = dict(SAMPLE_RECORD)
    missing_guid = dict(SAMPLE_RECORD)
    del missing_guid["guid"]
    bad_date = dict(SAMPLE_RECORD, guid="999", startdate="not-a-date")

    rows, failed = parse_records([good, missing_guid, bad_date])

    assert len(rows) == 1
    assert failed == 2


# --- timeout / failed request --------------------------------------------------


def test_fetch_events_raises_on_timeout():
    with patch("ingestion.nyc_parks.requests.get") as mock_get:
        mock_get.side_effect = requests.exceptions.Timeout()
        with pytest.raises(NycParksFetchError, match="timed out"):
            fetch_events(limit=10)


def test_fetch_events_raises_on_http_error():
    with patch("ingestion.nyc_parks.requests.get") as mock_get:
        mock_get.return_value = _mock_response(None, status_ok=False)
        with pytest.raises(NycParksFetchError, match="HTTP error"):
            fetch_events(limit=10)


# --- duplicate source records --------------------------------------------------


def test_upsert_of_nyc_parks_events_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    metadata, table = build_table(schema=None)
    metadata.create_all(engine)

    row = parse_record(SAMPLE_RECORD)
    inserted, updated = upsert_rows(engine, table, [row], "source_record_id")
    assert (inserted, updated) == (1, 0)

    inserted, updated = upsert_rows(engine, table, [row], "source_record_id")
    assert (inserted, updated) == (0, 1)

    with engine.connect() as conn:
        rows = conn.execute(select(table)).fetchall()
    assert len(rows) == 1  # no duplicate


# --- date parsing edge cases --------------------------------------------------


def test_parse_event_date_parses_valid_iso_date():
    assert parse_event_date("2026-07-19T00:00:00.000", "startdate") == date(2026, 7, 19)


def test_parse_event_date_returns_none_for_missing_value():
    assert parse_event_date(None, "startdate") is None
    assert parse_event_date("", "startdate") is None
    assert parse_event_date("   ", "startdate") is None


def test_parse_event_date_raises_for_malformed_value():
    with pytest.raises(NycParksRecordError, match="startdate"):
        parse_event_date("not-a-date", "startdate")
