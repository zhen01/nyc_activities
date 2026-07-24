"""Postgres access for endpoints that read/write the raw schema directly
(favorites, organizations) rather than the CSV-backed MVP pipeline in
filter_engine.py. Deliberately not resolved into one consistent data path
this pass -- see STATUS.md's "architectural inconsistency accepted"
note.

Reuses ingestion.db's engine/table-definition helpers so both the
ingestion CLI and this API share one source of truth for connecting to
and defining the raw schema.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import Column, DateTime, MetaData, String, Table, text  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

from ingestion.db import RAW_SCHEMA, ensure_schema, make_engine  # noqa: E402


def schema_for(engine: Engine) -> Optional[str]:
    """Postgres uses the "raw" schema; SQLite (used in tests) has no
    concept of schemas, so table definitions there must use schema=None.
    """
    return RAW_SCHEMA if engine.dialect.name == "postgresql" else None


def build_favorites_metadata(schema: Optional[str] = RAW_SCHEMA) -> Tuple[MetaData, Table]:
    """Defines app_favorites: one row per (device_id, event_id) a device
    has favorited. No login/auth -- device_id is a client-generated UUID
    persisted in localStorage (see frontend/src/api/client.ts).
    """
    metadata = MetaData(schema=schema)
    app_favorites = Table(
        "app_favorites",
        metadata,
        Column("device_id", String, primary_key=True),
        Column("event_id", String, primary_key=True),
        Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
    )
    return metadata, app_favorites


def ensure_favorites_table(engine: Engine) -> None:
    # ensure_schema() is already a no-op on SQLite, so no branching needed.
    ensure_schema(engine, RAW_SCHEMA)
    metadata, _ = build_favorites_metadata(schema_for(engine))
    metadata.create_all(engine)


@lru_cache
def get_engine() -> Engine:
    """Process-wide engine for the raw-schema endpoints (favorites,
    organizations). Cached since engines are meant to be reused/pooled,
    not recreated per request. Overridden in tests via
    app.dependency_overrides[get_engine].
    """
    engine = make_engine()
    ensure_favorites_table(engine)
    return engine
