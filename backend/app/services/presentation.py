"""Presentation-layer fields for the redesigned Discover page: category
labels, short descriptive badges/tags, and a documented distance-to-time
estimate.

Purely derived, display-only logic computed from fields already present on
a scored row (vibe_tags, solo_friendly, category) -- no new data is
fabricated.

`beginner_friendly` is no longer re-derived here: it is computed once in
dbt/models/intermediate/int_activity_enriched.sql and read straight off the
mart row, so the two layers can no longer disagree. The local keyword
heuristic remains only as a fallback for rows that predate that column.
"""

from __future__ import annotations

from typing import List, Optional, Set

import pandas as pd

CATEGORY_LABELS = {
    "active": "Active",
    "outdoors": "Outdoors",
    "social": "Social",
    "culture": "Culture",
    "food_drink": "Food & Drink",
    "learn": "Learn",
    "volunteer": "Volunteer",
}

# Estimated, not routed: distance / assumed blended walk+wait+subway speed.
# No geocoding/routing API key required -- see the redesign plan's
# "Assumptions requiring confirmation" #2 and STATUS.md's no-geocoding-API
# principle. Real transit routing is explicitly out of scope this pass.
DEFAULT_TRANSIT_MPH = 12.0


def category_label(category: str) -> str:
    """Human-readable label for a category value; falls back to
    title-casing unknown values rather than erroring.
    """
    return CATEGORY_LABELS.get(str(category).lower(), str(category).title())


def _vibe_tags(row: pd.Series) -> Set[str]:
    return {t.strip().lower() for t in str(row.get("vibe_tags", "")).split("|") if t.strip()}


def compute_badges(row: pd.Series) -> List[str]:
    """Primary category badge, plus an optional secondary vibe-derived
    badge for the mockup's combined labels (e.g. "Active" + "Social").
    Mirrors int_activity_enriched.sql's secondary_badge case statement.
    """
    tags = _vibe_tags(row)
    category = str(row["category"]).lower()
    badges = [category_label(category)]

    if category == "active" and "social" in tags:
        badges.append("Social")
    elif category == "outdoors" and "chill" in tags:
        badges.append("Chill")
    elif category == "culture" and "creative" in tags:
        badges.append("Creative")
    elif "social" in tags:
        badges.append("Social")
    elif "chill" in tags:
        badges.append("Chill")

    return badges


def _is_beginner_friendly(row: pd.Series) -> bool:
    """Prefer the value the analytics layer already computed; fall back to
    the original keyword heuristic only when that column is absent.
    """
    precomputed = row.get("beginner_friendly")
    if precomputed is not None and not pd.isna(precomputed):
        return bool(precomputed)
    haystack = f"{row.get('source_notes') or ''} {row.get('title') or ''}".lower()
    return "beginner" in haystack


def compute_tags(row: pd.Series) -> List[str]:
    """Short descriptive pills shown on each card."""
    tags = _vibe_tags(row)
    category = str(row["category"]).lower()

    result: List[str] = []
    if _is_beginner_friendly(row):
        result.append("Beginner friendly")
    if row.get("solo_friendly") and "solo_focus" in tags:
        result.append("Great for solo")
    if "social" in tags:
        result.append("Meet people")
    if "chill" in tags:
        result.append("Casual")
    if category == "outdoors":
        result.append("Outdoor")
    return result


def estimate_transit_minutes(
    distance_miles: Optional[float], mph: float = DEFAULT_TRANSIT_MPH
) -> Optional[int]:
    """Estimated (not routed) transit time in minutes. Returns None when
    distance is unknown -- never fabricates a time.
    """
    if distance_miles is None or pd.isna(distance_miles):
        return None
    return round((distance_miles / mph) * 60)


def compute_duration_minutes(row: pd.Series) -> Optional[int]:
    """Event duration in minutes when both start and end are known;
    None (never fabricated) when end_time is missing.
    """
    end_time = row.get("end_time")
    if end_time is None or pd.isna(end_time):
        return None
    delta = end_time - row["start_time"]
    return round(delta.total_seconds() / 60)
