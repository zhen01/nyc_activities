"""GET /recommendations

Accepts a user's category/budget/solo/date/zip/mode/vibe constraints as
query params, runs them through filter_engine (feasibility exclusion +
transparent scoring) and explain_engine (why-it-fits copy), and returns
the top 5 (or a weighted-random surprise sample of 5) Recommendation
objects.
"""

from __future__ import annotations

from datetime import date, time
from typing import List, Optional, Set

import pandas as pd
from fastapi import APIRouter
from sqlalchemy import select

from app import db as app_db
from app.models.schema import Intent, Mode, Recommendation, UserConstraints
from app.services.explain_engine import build_explanation
from app.services.filter_engine import build_recommendations
from app.services.presentation import (
    category_label,
    compute_badges,
    compute_duration_minutes,
    compute_tags,
    estimate_transit_minutes,
)

router = APIRouter()


def _favorited_event_ids(device_id: Optional[str]) -> Set[str]:
    """Batch-lookup of this device's favorited event_ids. Returns an empty
    set (never None/error) when no device_id was supplied -- deliberately
    lazy: plain /recommendations requests (no device_id) never touch
    Postgres, preserving the CSV-only, Docker-free MVP demo path.
    """
    if not device_id:
        return set()
    engine = app_db.get_engine()
    _, app_favorites = app_db.build_favorites_metadata(app_db.schema_for(engine))
    with engine.begin() as conn:
        rows = conn.execute(
            select(app_favorites.c.event_id).where(app_favorites.c.device_id == device_id)
        ).all()
    return {row.event_id for row in rows}


@router.get("/recommendations", response_model=List[Recommendation])
def get_recommendations(
    category: Optional[str] = None,
    max_cost: Optional[float] = None,
    solo_friendly: Optional[bool] = None,
    date: Optional[date] = None,
    zip_code: Optional[str] = None,
    mode: Mode = "specific",
    vibe: Optional[str] = None,
    hours_free: Optional[float] = None,
    intent: Optional[Intent] = None,
    after_time: Optional[time] = None,
    device_id: Optional[str] = None,
) -> List[Recommendation]:
    constraints = UserConstraints(
        category=category,
        max_cost=max_cost,
        solo_friendly=solo_friendly,
        date=date,
        zip_code=zip_code,
        mode=mode,
        vibe=vibe,
        hours_free=hours_free,
        intent=intent,
        after_time=after_time,
        device_id=device_id,
    )
    matches = build_recommendations(constraints)
    favorited_ids = _favorited_event_ids(device_id)

    return [
        Recommendation(
            event_id=row["event_id"],
            title=row["title"],
            category=row["category"],
            start_time=row["start_time"],
            end_time=row["end_time"] if pd.notna(row["end_time"]) else None,
            cost=row["cost"] if pd.notna(row["cost"]) else None,
            location=row["location"],
            solo_friendly=bool(row["solo_friendly"]) if pd.notna(row["solo_friendly"]) else None,
            source_url=row["source_url"] if pd.notna(row["source_url"]) else None,
            source_name=row["source_name"],
            source_verified_date=row["source_last_checked"],
            # None round-trips through a float DataFrame column as NaN,
            # which is not JSON-serialisable -- so this needs pd.notna, not
            # an `is None` check.
            distance_miles=row["distance_miles"] if pd.notna(row["distance_miles"]) else None,
            confidence_label=row["confidence_label"],
            confidence_score=row["confidence_score"],
            score=row["total_score"],
            explanation=build_explanation(row, constraints),
            image_url=row["image_url"] if pd.notna(row.get("image_url")) else None,
            category_label=category_label(row["category"]),
            badges=compute_badges(row),
            tags=compute_tags(row),
            estimated_transit_minutes=estimate_transit_minutes(row["distance_miles"]),
            duration_minutes=compute_duration_minutes(row),
            is_favorited=(row["event_id"] in favorited_ids) if device_id else None,
        )
        for _, row in matches.iterrows()
    ]
