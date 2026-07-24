"""GET/POST/DELETE /favorites -- server-side, device-scoped favorites.

No login/auth: device_id is a random UUID generated client-side and
persisted in localStorage (see frontend/src/api/client.ts). This is a
deliberately lightweight persistence model, not a real user-account
system.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import Engine

from app.db import build_favorites_metadata, get_engine, schema_for

router = APIRouter()


class FavoriteRequest(BaseModel):
    device_id: str
    event_id: str


@router.get("/favorites", response_model=List[str])
def list_favorites(device_id: str, engine: Engine = Depends(get_engine)) -> List[str]:
    _, app_favorites = build_favorites_metadata(schema_for(engine))
    with engine.begin() as conn:
        rows = conn.execute(
            select(app_favorites.c.event_id).where(app_favorites.c.device_id == device_id)
        ).all()
    return [row.event_id for row in rows]


@router.post("/favorites", status_code=204)
def add_favorite(payload: FavoriteRequest, engine: Engine = Depends(get_engine)) -> None:
    _, app_favorites = build_favorites_metadata(schema_for(engine))
    insert = postgresql.insert if engine.dialect.name == "postgresql" else sqlite.insert
    stmt = insert(app_favorites).values(device_id=payload.device_id, event_id=payload.event_id)
    stmt = stmt.on_conflict_do_nothing(index_elements=["device_id", "event_id"])
    with engine.begin() as conn:
        conn.execute(stmt)


@router.delete("/favorites/{device_id}/{event_id}", status_code=204)
def remove_favorite(device_id: str, event_id: str, engine: Engine = Depends(get_engine)) -> None:
    """Idempotent: deleting a favorite that doesn't exist is not an error."""
    _, app_favorites = build_favorites_metadata(schema_for(engine))
    with engine.begin() as conn:
        conn.execute(
            delete(app_favorites).where(
                app_favorites.c.device_id == device_id, app_favorites.c.event_id == event_id
            )
        )
