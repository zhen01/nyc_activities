"""
Database connection/session setup (SQLAlchemy engine + session factory).

Reads DATABASE_URL from app.config.Settings. Defaults to a local SQLite
file for development; swap to Postgres via env var when deploying.
"""

# TODO: create engine, SessionLocal, and a get_db() dependency for FastAPI.
