"""Tests that re-running ingestion upserts rather than duplicates rows.

Runs against an in-memory SQLite database (schema=None) as a fast,
Docker-free stand-in for Postgres. upsert_rows() picks its SQL dialect
from the engine, so this exercises the same code path used against
Postgres in production (schema="raw", via docker-compose).
"""

from sqlalchemy import create_engine, select

from ingestion.db import build_metadata, upsert_rows

SAMPLE_ROW = {
    "source_id": "s1",
    "name": "A",
    "category": "sports",
    "channel_type": "website",
    "url": "https://a.example",
    "update_cadence": None,
    "last_checked": None,
    "notes": None,
}


def _make_engine_and_table():
    engine = create_engine("sqlite:///:memory:")
    metadata, sources_table, _ = build_metadata(schema=None)
    metadata.create_all(engine)
    return engine, sources_table


def test_upsert_inserts_new_rows() -> None:
    engine, table = _make_engine_and_table()
    inserted, updated = upsert_rows(engine, table, [dict(SAMPLE_ROW)], "source_id")
    assert (inserted, updated) == (1, 0)
    with engine.connect() as conn:
        rows = conn.execute(select(table)).fetchall()
    assert len(rows) == 1


def test_upsert_is_idempotent_on_rerun() -> None:
    engine, table = _make_engine_and_table()
    upsert_rows(engine, table, [dict(SAMPLE_ROW)], "source_id")
    inserted, updated = upsert_rows(engine, table, [dict(SAMPLE_ROW)], "source_id")
    assert (inserted, updated) == (0, 1)
    with engine.connect() as conn:
        rows = conn.execute(select(table)).fetchall()
    assert len(rows) == 1  # no duplicate row created


def test_upsert_updates_changed_fields() -> None:
    engine, table = _make_engine_and_table()
    upsert_rows(engine, table, [dict(SAMPLE_ROW)], "source_id")
    changed_row = dict(SAMPLE_ROW, name="A Updated")
    upsert_rows(engine, table, [changed_row], "source_id")
    with engine.connect() as conn:
        row = conn.execute(select(table)).first()
    assert row.name == "A Updated"
