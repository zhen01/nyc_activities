"""GET /organizations -- data for the Discover page's "Discover hidden
gems" row: active sources plus how many recommendable events each one
currently has.

Reads `analytics.mart_organizations` rather than counting the raw event
table. That matters for correctness, not just tidiness: a raw count applies
none of the business rules, so it would advertise organizations on the
strength of events that are cancelled, expired, or from a source stale
enough to be excluded. It also lets machine-ingested feeds appear here at
all -- the raw source directory only contains hand-curated organizations.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db import get_engine

router = APIRouter()

MART_RELATION = "analytics.mart_organizations"


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
    stmt = text(
        f"""
        select
            source_id,
            source_name as name,
            source_category as category,
            channel_type,
            source_url as url,
            source_image_url as image_url,
            upcoming_event_count
        from {MART_RELATION}
        order by upcoming_event_count desc, source_name
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(stmt).mappings().all()
    return [Organization(**row) for row in rows]
