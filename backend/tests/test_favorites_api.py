"""Tests for GET/POST/DELETE /favorites against an in-memory SQLite
database (schema=None), overriding app.db.get_engine the same way
ingestion/tests/test_ingest_dedup.py stands in for Postgres. Exercises the
same upsert/idempotency code paths used against Postgres in production.
"""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.db import build_favorites_metadata, ensure_favorites_table, get_engine
from app.main import app


def _make_test_engine():
    # StaticPool + check_same_thread=False: TestClient runs the sync FastAPI
    # endpoint in a worker thread, but SQLite's default SingletonThreadPool
    # keys :memory: connections by thread id, which would silently hand that
    # worker thread a *different*, empty in-memory database than the one
    # this fixture just created the table in.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    ensure_favorites_table(engine)
    return engine


def _client_with_fresh_engine():
    engine = _make_test_engine()
    app.dependency_overrides[get_engine] = lambda: engine
    return TestClient(app), engine


def test_list_favorites_is_empty_for_unknown_device():
    client, _ = _client_with_fresh_engine()
    resp = client.get("/favorites", params={"device_id": "device-1"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_add_favorite_then_list_returns_it():
    client, _ = _client_with_fresh_engine()
    resp = client.post("/favorites", json={"device_id": "device-1", "event_id": "evt-001"})
    assert resp.status_code == 204

    resp = client.get("/favorites", params={"device_id": "device-1"})
    assert resp.json() == ["evt-001"]


def test_add_favorite_is_idempotent_on_conflict():
    client, engine = _client_with_fresh_engine()
    for _ in range(2):
        resp = client.post("/favorites", json={"device_id": "device-1", "event_id": "evt-001"})
        assert resp.status_code == 204

    _, app_favorites = build_favorites_metadata(schema=None)
    with engine.connect() as conn:
        rows = conn.execute(app_favorites.select()).fetchall()
    assert len(rows) == 1


def test_remove_favorite_deletes_it():
    client, _ = _client_with_fresh_engine()
    client.post("/favorites", json={"device_id": "device-1", "event_id": "evt-001"})

    resp = client.delete("/favorites/device-1/evt-001")
    assert resp.status_code == 204

    resp = client.get("/favorites", params={"device_id": "device-1"})
    assert resp.json() == []


def test_remove_favorite_is_idempotent_when_missing():
    client, _ = _client_with_fresh_engine()
    resp = client.delete("/favorites/device-1/evt-does-not-exist")
    assert resp.status_code == 204


def test_favorites_are_scoped_per_device():
    client, _ = _client_with_fresh_engine()
    client.post("/favorites", json={"device_id": "device-1", "event_id": "evt-001"})
    client.post("/favorites", json={"device_id": "device-2", "event_id": "evt-002"})

    resp = client.get("/favorites", params={"device_id": "device-1"})
    assert resp.json() == ["evt-001"]
