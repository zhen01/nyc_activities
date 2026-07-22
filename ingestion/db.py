"""Database engine, table definitions, and upsert helper for the raw
ingestion schema.

Table definitions take a `schema` argument (default "raw") so the same
definitions can be reused against Postgres in production and against an
unqualified in-memory SQLite database in tests (SQLite has no concept of
schemas).
"""

from __future__ import annotations

import os

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    MetaData,
    Numeric,
    String,
    Table,
    text,
)
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine
from sqlalchemy import create_engine

RAW_SCHEMA = "raw"


def get_database_url() -> str:
    """Read DATABASE_URL from the environment.

    Raises RuntimeError with a clear message if it isn't set, since a
    missing connection string is a configuration error we want to fail
    on loudly rather than guess a default.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env, fill it in, "
            "and export it (or load it with python-dotenv) before running ingestion."
        )
    return url


def make_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine from an explicit URL or DATABASE_URL."""
    return create_engine(database_url or get_database_url())


def build_metadata(schema: str | None = RAW_SCHEMA) -> tuple[MetaData, Table, Table]:
    """Define the activity_sources and activity_events tables.

    Returns (metadata, activity_sources, activity_events).
    """
    metadata = MetaData(schema=schema)

    activity_sources = Table(
        "activity_sources",
        metadata,
        Column("source_id", String, primary_key=True),
        Column("name", String, nullable=False),
        Column("category", String, nullable=False),
        Column("channel_type", String, nullable=False),
        Column("url", String, nullable=False),
        Column("update_cadence", String),
        Column("last_checked", Date),
        Column("notes", String),
        # Defaults to true so existing rows/tests that don't set it explicitly
        # still behave as "active" -- an inactive source has to be an
        # explicit, deliberate flag, not an accidental side effect.
        Column("is_active", Boolean, nullable=False, server_default=text("true")),
        Column("image_url", String),
    )

    activity_events = Table(
        "activity_events",
        metadata,
        Column("event_id", String, primary_key=True),
        Column("source_id", String, nullable=False),
        Column("title", String, nullable=False),
        Column("category", String, nullable=False),
        Column("start_time", DateTime, nullable=False),
        Column("end_time", DateTime),
        Column("cost", Numeric),
        Column("location", String, nullable=False),
        Column("solo_friendly", Boolean),
        Column("source_url", String),
        Column("last_checked", Date),
        Column("zip_code", String),
        Column("lat", Float),
        Column("lon", Float),
        Column("vibe_tags", String),
        Column("image_url", String),
    )

    return metadata, activity_sources, activity_events


def ensure_schema(engine: Engine, schema: str) -> None:
    """Create `schema` if it doesn't already exist. No-op on SQLite."""
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))


def run_pending_migrations(engine: Engine, schema: str) -> None:
    """Apply additive column migrations that `metadata.create_all()` can't
    handle on its own -- it only creates tables that don't yet exist, it
    never alters existing tables. No-op on SQLite (tests build fresh
    metadata each run, so there's nothing to migrate).

    Each statement uses `ADD COLUMN IF NOT EXISTS`, so this is safe to call
    on every `make ingest` run, not just once.
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(
            text(f'ALTER TABLE "{schema}".activity_sources ADD COLUMN IF NOT EXISTS image_url TEXT')
        )
        conn.execute(
            text(f'ALTER TABLE "{schema}".activity_events ADD COLUMN IF NOT EXISTS image_url TEXT')
        )


def upsert_rows(
    engine: Engine, table: Table, rows: list[dict], conflict_column: str
) -> tuple[int, int]:
    """Insert new rows and update existing ones, keyed on `conflict_column`.

    Selects the Postgres or SQLite dialect's upsert construct based on the
    engine so the same function backs both production (Postgres) and tests
    (in-memory SQLite). Returns (inserted_count, updated_count).
    """
    if not rows:
        return 0, 0

    insert = postgresql.insert if engine.dialect.name == "postgresql" else sqlite.insert

    inserted = 0
    updated = 0
    with engine.begin() as conn:
        for row in rows:
            existing = conn.execute(
                table.select().where(table.c[conflict_column] == row[conflict_column])
            ).first()

            update_cols = {
                c.name: row[c.name]
                for c in table.columns
                if c.name != conflict_column and c.name in row
            }
            stmt = insert(table).values(**row)
            stmt = stmt.on_conflict_do_update(index_elements=[conflict_column], set_=update_cols)
            conn.execute(stmt)

            if existing is None:
                inserted += 1
            else:
                updated += 1

    return inserted, updated
