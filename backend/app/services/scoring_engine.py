"""Transparent scoring -- ranks the already-feasible candidates.

Product principle: scoring must be explainable, not a black box. Every
component here is a simple, inspectable function of fields already on the
row (or the user's constraints) -- no learned weights, no hidden model.
filter_engine.py does the hard pass/fail feasibility work first; this module
only ranks what already passed.

Components (each normalized to 0..1, then blended into a 0..100 total):
  - vibe_score:       does the event's vibe_tags match the requested mood?
  - proximity_score:  how close is the event to the user's ZIP centroid?
  - confidence_score: how trustworthy/fresh is the source for this event?

Any component whose input wasn't provided (no ZIP, no mood) is dropped from
the blend and the remaining weights are renormalized -- we never fabricate
a score for information the user didn't give us.
"""

from __future__ import annotations

from datetime import date as date_type
from typing import Optional

import pandas as pd

from app.models.schema import UserConstraints
from app.services.geo import haversine_miles, zip_to_latlon

MAX_PROXIMITY_RADIUS_MILES = 8.0

CHANNEL_TRUST = {
    "website": 1.0,
    # A machine-ingested public Open Data feed is the most reliably current
    # channel here -- it is refreshed daily by the publisher rather than
    # depending on a volunteer remembering to update a page.
    "api": 1.0,
    "meetup": 0.85,
    "instagram": 0.6,
}
DEFAULT_CHANNEL_TRUST = 0.5

# How many days a source can go unchecked, relative to its own update
# cadence, before we consider it fully stale.
CADENCE_DAYS = {
    "daily": 1,
    "weekly": 7,
    "seasonal": 90,
}
DEFAULT_CADENCE_DAYS = 30
STALE_MULTIPLIER = 3  # fully stale at cadence_days * this many days overdue

WEIGHTS = {"vibe": 0.4, "proximity": 0.35, "confidence": 0.25}

VIBE_TAG_SETS = {
    "chill": {"chill"},
    "energetic": {"energetic"},
    "social": {"social"},
    "solo_focus": {"solo_focus"},
    "creative": {"creative"},
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def confidence_score(
    channel_type: str, update_cadence: str, last_checked: date_type, today: Optional[date_type] = None
) -> tuple[float, str, str]:
    """Returns (score 0..1, label, human-readable reason)."""
    today = today or date_type.today()
    channel_weight = CHANNEL_TRUST.get(str(channel_type).lower(), DEFAULT_CHANNEL_TRUST)
    cadence_days = CADENCE_DAYS.get(str(update_cadence).lower(), DEFAULT_CADENCE_DAYS)

    days_since_checked = (today - last_checked).days
    staleness_ceiling = cadence_days * STALE_MULTIPLIER
    freshness = _clamp(1 - (days_since_checked / staleness_ceiling)) if staleness_ceiling > 0 else 0.0

    score = 0.5 * channel_weight + 0.5 * freshness

    if score >= 0.75:
        label = "High"
    elif score >= 0.45:
        label = "Medium"
    else:
        label = "Low"

    reason = (
        f"{channel_type} source, last verified {days_since_checked} day(s) ago "
        f"(usually updated {update_cadence})"
    )
    return score, label, reason


def vibe_score(event_vibe_tags: str, desired_vibe: Optional[str]) -> Optional[float]:
    """Returns None if no vibe was requested (component excluded from blend)."""
    if not desired_vibe:
        return None
    tags = {t.strip().lower() for t in str(event_vibe_tags).split("|") if t.strip()}
    return 1.0 if desired_vibe.lower() in tags else 0.0


# Applied when the user *did* tell us where they are but the event itself
# has no usable coordinates. Dropping the component instead (as we do when
# the user gave no ZIP at all) would renormalise the remaining weights and
# hand the event a strictly higher total than an event we could actually
# locate nearby -- i.e. it would reward missing data. A neutral half-score
# neither rewards nor punishes the gap.
UNKNOWN_LOCATION_PROXIMITY = 0.5


def proximity_score(distance_miles: Optional[float]) -> Optional[float]:
    """Returns None if distance couldn't be computed (component excluded)."""
    if distance_miles is None:
        return None
    return _clamp(1 - (distance_miles / MAX_PROXIMITY_RADIUS_MILES))


def compute_distance_miles(row: pd.Series, zip_code: Optional[str]) -> Optional[float]:
    """None whenever distance genuinely can't be computed -- either the
    user gave no/unmapped ZIP, or the event itself has no coordinates.

    The second case only started occurring once API-sourced events joined
    the mart: a handful publish no usable location. Letting those through
    would yield a NaN distance, which is not None and therefore silently
    survives every `is None` guard downstream.
    """
    if not zip_code:
        return None
    origin = zip_to_latlon(zip_code)
    if origin is None:
        return None
    lat, lon = row.get("lat"), row.get("lon")
    if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
        return None
    return haversine_miles(origin[0], origin[1], lat, lon)


def score_row(row: pd.Series, constraints: UserConstraints, today: Optional[date_type] = None) -> dict:
    """Compute the full transparent score breakdown for one candidate row."""
    distance_miles = compute_distance_miles(row, constraints.zip_code)
    desired_vibe = constraints.vibe if constraints.mode == "mood" else None
    # intent="meet_people" reuses the existing vibe-match component rather
    # than adding a new scoring dimension/weight -- "meet people" is
    # treated as wanting the "social" vibe tag, same as mood mode's vibe
    # matching. No new tunables in WEIGHTS.
    if constraints.intent == "meet_people":
        desired_vibe = "social"

    conf_score, conf_label, conf_reason = confidence_score(
        row["channel_type"], row["update_cadence"], row["source_last_checked"], today
    )
    prox_score = proximity_score(distance_miles)
    if prox_score is None and constraints.zip_code and zip_to_latlon(constraints.zip_code):
        # The user asked a proximity question we cannot answer for this
        # specific event. That is different from them never asking.
        prox_score = UNKNOWN_LOCATION_PROXIMITY
    vibe_component = vibe_score(row["vibe_tags"], desired_vibe)

    components = {
        "confidence": conf_score,
        "proximity": prox_score,
        "vibe": vibe_component,
    }
    active_weights = {k: WEIGHTS[k] for k, v in components.items() if v is not None}
    weight_total = sum(active_weights.values()) or 1.0

    total = sum(components[k] * (active_weights[k] / weight_total) for k in active_weights)

    return {
        "total_score": round(total * 100, 1),
        "confidence_score": round(conf_score * 100, 1),
        "confidence_label": conf_label,
        "confidence_reason": conf_reason,
        "proximity_score": round(prox_score * 100, 1) if prox_score is not None else None,
        "distance_miles": round(distance_miles, 1) if distance_miles is not None else None,
        "vibe_score": round(vibe_component * 100, 1) if vibe_component is not None else None,
    }


def rank_candidates(df: pd.DataFrame, constraints: UserConstraints, today: Optional[date_type] = None) -> pd.DataFrame:
    """Attach score columns to every row and sort by total_score desc.
    Does not truncate to top N -- that's the caller's job (and differs for
    "surprise me" mode, which samples rather than truncates).
    """
    if df.empty:
        return df.assign(
            total_score=pd.Series(dtype=float),
            confidence_score=pd.Series(dtype=float),
            confidence_label=pd.Series(dtype=str),
            confidence_reason=pd.Series(dtype=str),
            proximity_score=pd.Series(dtype=float),
            distance_miles=pd.Series(dtype=float),
            vibe_score=pd.Series(dtype=float),
        )

    scores = df.apply(lambda row: score_row(row, constraints, today), axis=1, result_type="expand")
    scored = pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)
    return scored.sort_values("total_score", ascending=False)
