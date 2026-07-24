"""Tests for GET /organizations against an in-memory SQLite database
(schema=None), overriding app.db.get_engine. Exercises the upcoming-event
count join and the is_active filter with the same table definitions
ingestion/db.py uses in production.
"""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import get_engine
from app.main import app
from ingestion.db import build_metadata

NOW = datetime.utcnow()


def _make_test_engine():
    # StaticPool + check_same_thread=False: see test_favorites_api.py's
    # _make_test_engine() for why this is required for :memory: SQLite here.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata, sources, events = build_metadata(schema=None)
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            sources.insert(),
            [
                dict(
                    source_id="src-active-upcoming",
                    name="Active With Upcoming Events",
                    category="active",
                    channel_type="website",
                    url="https://a.example",
                    is_active=True,
                ),
                dict(
                    source_id="src-active-none",
                    name="Active Without Events",
                    category="social",
                    channel_type="newsletter",
                    url="https://b.example",
                    is_active=True,
                ),
                dict(
                    source_id="src-inactive",
                    name="Inactive Source",
                    category="culture",
                    channel_type="website",
                    url="https://c.example",
                    is_active=False,
                ),
            ],
        )
        conn.execute(
            events.insert(),
            [
                dict(
                    event_id="evt-upcoming-1",
                    source_id="src-active-upcoming",
                    title="Upcoming Event 1",
                    category="active",
                    start_time=NOW + timedelta(days=1),
                    location="NYC",
                ),
                dict(
                    event_id="evt-upcoming-2",
                    source_id="src-active-upcoming",
                    title="Upcoming Event 2",
                    category="active",
                    start_time=NOW + timedelta(days=2),
                    location="NYC",
                ),
                dict(
                    event_id="evt-past",
                    source_id="src-active-upcoming",
                    title="Past Event",
                    category="active",
                    start_time=NOW - timedelta(days=1),
                    location="NYC",
                ),
                dict(
                    event_id="evt-inactive-upcoming",
                    source_id="src-inactive",
                    title="Upcoming Event For Inactive Source",
                    category="culture",
                    start_time=NOW + timedelta(days=1),
                    location="NYC",
                ),
            ],
        )
    return engine


def _client():
    engine = _make_test_engine()
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app)


def test_only_active_sources_are_returned():
    client = _client()
    resp = client.get("/organizations")
    assert resp.status_code == 200
    source_ids = {org["source_id"] for org in resp.json()}
    assert source_ids == {"src-active-upcoming", "src-active-none"}


def test_upcoming_event_count_excludes_past_events():
    client = _client()
    resp = client.get("/organizations")
    by_id = {org["source_id"]: org for org in resp.json()}
    assert by_id["src-active-upcoming"]["upcoming_event_count"] == 2


def test_source_with_no_events_has_zero_count():
    client = _client()
    resp = client.get("/organizations")
    by_id = {org["source_id"]: org for org in resp.json()}
    assert by_id["src-active-none"]["upcoming_event_count"] == 0


def test_results_are_ordered_by_upcoming_count_descending():
    client = _client()
    resp = client.get("/organizations")
    counts = [org["upcoming_event_count"] for org in resp.json()]
    assert counts == sorted(counts, reverse=True)
