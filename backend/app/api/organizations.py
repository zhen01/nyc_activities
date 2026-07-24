"""GET /organizations -- data for the Discover page's "Discover hidden
gems" row: active sources plus a count of their upcoming (not-yet-started)
events. Queries Postgres directly via SQLAlchemy Core against the same
table definitions ingestion/db.py uses, rather than the CSV-backed MVP
pipeline in filter_engine.py -- see app/db.py and STATUS.md for why these
two data paths currently coexist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from app.db import get_engine, schema_for
from ingestion.db import build_metadata

router = APIRouter()


class Organization(BaseModel):
    source_id: str
    name: str
    category: str
    channel_type: str
    url: str
    image_url: Optional[str] = None
    upcoming_event_count: int


@router.get("/organizations", response_model=List[Organization])
def list_organizations(engine: Engine = Depends(get_engine)) -> List[Organization]:
    _, sources, events = build_metadata(schema=schema_for(engine))

    upcoming_counts = (
        select(events.c.source_id, func.count().label("upcoming_event_count"))
        .where(events.c.start_time >= datetime.now(timezone.utc).replace(tzinfo=None))
        .group_by(events.c.source_id)
        .subquery()
    )

    stmt = (
        select(
            sources.c.source_id,
            sources.c.name,
            sources.c.category,
            sources.c.channel_type,
            sources.c.url,
            sources.c.image_url,
            func.coalesce(upcoming_counts.c.upcoming_event_count, 0).label("upcoming_event_count"),
        )
        .select_from(
            sources.outerjoin(upcoming_counts, sources.c.source_id == upcoming_counts.c.source_id)
        )
        .where(sources.c.is_active.is_(True))
        .order_by(func.coalesce(upcoming_counts.c.upcoming_event_count, 0).desc())
    )

    with engine.begin() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [Organization(**row) for row in rows]
