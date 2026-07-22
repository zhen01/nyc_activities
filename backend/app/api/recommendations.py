"""GET /recommendations

Accepts a user's category/budget/solo/date/zip/mode/vibe constraints as
query params, runs them through filter_engine (feasibility exclusion +
transparent scoring) and explain_engine (why-it-fits copy), and returns
the top 5 (or a weighted-random surprise sample of 5) Recommendation
objects.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter

from app.models.schema import Mode, Recommendation, UserConstraints
from app.services.explain_engine import build_explanation
from app.services.filter_engine import build_recommendations

router = APIRouter()


@router.get("/recommendations", response_model=List[Recommendation])
def get_recommendations(
    category: Optional[str] = None,
    max_cost: Optional[float] = None,
    solo_friendly: Optional[bool] = None,
    date: Optional[date] = None,
    zip_code: Optional[str] = None,
    mode: Mode = "specific",
    vibe: Optional[str] = None,
) -> List[Recommendation]:
    constraints = UserConstraints(
        category=category,
        max_cost=max_cost,
        solo_friendly=solo_friendly,
        date=date,
        zip_code=zip_code,
        mode=mode,
        vibe=vibe,
    )
    matches = build_recommendations(constraints)

    return [
        Recommendation(
            event_id=row["event_id"],
            title=row["title"],
            category=row["category"],
            start_time=row["start_time"],
            end_time=row["end_time"] if pd.notna(row["end_time"]) else None,
            cost=row["cost"],
            location=row["location"],
            solo_friendly=row["solo_friendly"],
            source_url=row["source_url"],
            source_name=row["source_name"],
            source_verified_date=row["source_last_checked"],
            distance_miles=row["distance_miles"],
            confidence_label=row["confidence_label"],
            confidence_score=row["confidence_score"],
            score=row["total_score"],
            explanation=build_explanation(row, constraints),
        )
        for _, row in matches.iterrows()
    ]
