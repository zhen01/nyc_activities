"""Generates the "why this fits, what's uncertain" text shown per
recommendation (product principle #4).

Rule-based only, built from fields already present in the scored row --
no invented content (principle #2, "discovery without hallucination").
Every sentence traces back to a value the user can see elsewhere in the
response (constraints they set, or the row's own score breakdown).
"""

from __future__ import annotations

import pandas as pd

from app.models.schema import UserConstraints


def build_explanation(row: pd.Series, constraints: UserConstraints) -> str:
    """Build a short explanation string for one scored activity row."""
    reasons = []

    if constraints.mode == "specific" and constraints.category:
        reasons.append(f"matches your interest in {row['category']}")
    if constraints.max_cost is not None:
        reasons.append(f"costs ${row['cost']:g}, within your ${constraints.max_cost:g} budget")
    if constraints.solo_friendly:
        reasons.append("welcomes solo attendees")
    if constraints.date is not None:
        reasons.append(f"is happening on {row['start_time'].date()}")

    if constraints.mode == "mood" and constraints.vibe:
        if row["vibe_score"] == 100.0:
            reasons.append(f"matches the '{constraints.vibe}' vibe you asked for")
        else:
            reasons.append(f"was the closest available match for a '{constraints.vibe}' vibe")

    if constraints.mode == "surprise":
        reasons.append("was picked as a surprise from your top-ranked feasible options")

    if row["distance_miles"] is not None:
        reasons.append(f"is about {row['distance_miles']:g} miles from ZIP {constraints.zip_code}")

    if not reasons:
        reasons.append(f"is a {row['category']} activity happening {row['start_time'].date()}")

    fit = f"Fits because it {', '.join(reasons)}."
    scoring = (
        f"Score: {row['total_score']:g}/100 "
        f"(confidence: {row['confidence_label']} -- {row['confidence_reason']})."
    )
    provenance = f"Source: {row['source_name']} -- last checked {row['source_last_checked']}."
    return f"{fit} {scoring} {provenance}"
