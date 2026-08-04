"""Tests for GET /organizations against an in-memory SQLite database
standing in for the warehouse.

The endpoint reads `analytics.mart_organizations`, so the fixture attaches
a second in-memory database under the name `analytics` -- SQLite has no
schemas, but an attached database is addressed with exactly the same
`schema.table` syntax, which keeps the query under test identical to the
one that runs against Postgres.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from app.db import get_engine
from app.main import app

ROWS = [
    # (source_id, name, category, channel_type, url, image_url, count)
    ("nyc-parks-open-data", "NYC Parks Open Data", "outdoors", "api",
     "https://data.cityofnewyork.us/x.json", None, 184),
    ("volunteer-shift-market", "NYC Volunteer Shift Marketplace", "volunteer", "website",
     "https://volunteershifts.example.org", None, 3),
    ("open-mic-collective", "NYC Open Mic Collective", "culture", "instagram",
     "https://instagram.com/example_openmic", None, 0),
]


def _make_test_engine():
    # StaticPool + check_same_thread=False: TestClient runs the endpoint in a
    # worker thread, and SQLite's default pool would hand that thread a
    # different (empty) in-memory database -- including a different set of
    # attached ones.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("attach database ':memory:' as analytics"))
        conn.execute(
            text(
                """
                create table analytics.mart_organizations (
                    source_id text,
                    source_name text,
                    source_category text,
                    channel_type text,
                    source_url text,
                    source_image_url text,
                    upcoming_event_count integer
                )
                """
            )
        )
        for row in ROWS:
            conn.execute(
                text(
                    "insert into analytics.mart_organizations values "
                    "(:sid, :name, :cat, :chan, :url, :img, :cnt)"
                ),
                dict(sid=row[0], name=row[1], cat=row[2], chan=row[3],
                     url=row[4], img=row[5], cnt=row[6]),
            )
    return engine


def _client():
    engine = _make_test_engine()
    app.dependency_overrides[get_engine] = lambda: engine
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _get():
    gen = _client()
    client = next(gen)
    try:
        resp = client.get("/organizations")
        assert resp.status_code == 200, resp.text
        return resp.json()
    finally:
        gen.close()


def test_all_active_sources_are_returned():
    assert {o["source_id"] for o in _get()} == {r[0] for r in ROWS}


def test_results_are_ordered_by_upcoming_count_descending():
    counts = [o["upcoming_event_count"] for o in _get()]
    assert counts == sorted(counts, reverse=True)


def test_a_machine_ingested_api_feed_appears_as_a_source():
    # It has no row in the hand-curated source directory, so it can only
    # surface here via the analytics layer.
    by_id = {o["source_id"]: o for o in _get()}
    assert by_id["nyc-parks-open-data"]["channel_type"] == "api"
    assert by_id["nyc-parks-open-data"]["upcoming_event_count"] == 184


def test_a_source_with_no_recommendable_events_is_still_listed_with_zero():
    # Zero is a meaningful answer ("this org has nothing on right now"),
    # not a reason to hide the organization.
    by_id = {o["source_id"]: o for o in _get()}
    assert by_id["open-mic-collective"]["upcoming_event_count"] == 0


def test_null_image_url_is_returned_as_none():
    assert all(o["image_url"] is None for o in _get())
