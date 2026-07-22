"""Pydantic request/response models for the /recommendations endpoint.

UserConstraints: what the frontend sends -- category, budget, solo-friendly,
    an optional date, a starting ZIP code (for proximity), and a mode/vibe
    pair that controls how results are ranked:
      - mode="specific": category is a hard filter (today's behavior).
      - mode="mood": category is not required; events are ranked by how
        well their vibe_tags match the requested `vibe`.
      - mode="surprise": hard constraints still apply, but ranking ignores
        vibe and the top results are weighted-sampled rather than a strict
        top-N, for variety.
Recommendation: what the API returns -- activity fields, the transparent
    score breakdown (principle: no black-box ranking), and an explanation
    of why it fits (principle #4).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel

Mode = Literal["specific", "mood", "surprise"]


class UserConstraints(BaseModel):
    category: Optional[str] = None
    max_cost: Optional[float] = None
    solo_friendly: Optional[bool] = None
    date: Optional[date] = None
    zip_code: Optional[str] = None
    mode: Mode = "specific"
    vibe: Optional[str] = None


class Recommendation(BaseModel):
    event_id: str
    title: str
    category: str
    start_time: datetime
    end_time: Optional[datetime]
    cost: float
    location: str
    solo_friendly: bool
    source_url: Optional[str]
    source_name: str
    source_verified_date: date
    distance_miles: Optional[float]
    confidence_label: str
    confidence_score: float
    score: float
    explanation: str
