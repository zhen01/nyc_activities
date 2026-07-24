"""Feasibility filtering -- product principle #1: "feasibility before
attractiveness".

MVP data source: reads directly from data/sample/*.csv (the same curated
sample data used by the ingestion module), rather than from Postgres.
This keeps the MVP runnable without Docker. Swapping this for a query
against raw.activity_events/raw.activity_sources is a drop-in change once
Docker/Postgres is available -- see STATUS.md.

Two-stage pipeline:
  1. filter_activities(): hard pass/fail feasibility -- excludes expired
     and incompatible events. Never ranks by attractiveness.
  2. build_recommendations(): hands the feasible set to scoring_engine for
     transparent ranking, then selects the final top 5 (or, in "surprise"
     mode, a weighted-random sample from the top-ranked pool).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from app.models.schema import UserConstraints
from app.services.scoring_engine import rank_candidates

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCES_CSV = REPO_ROOT / "data" / "sample" / "sources.csv"
EVENTS_CSV = REPO_ROOT / "data" / "sample" / "events.csv"

MAX_RESULTS = 5
SURPRISE_POOL_SIZE = 10


def load_activities() -> pd.DataFrame:
    """Load and join events with their source organizations."""
    sources = pd.read_csv(SOURCES_CSV)
    events = pd.read_csv(EVENTS_CSV, dtype={"zip_code": str})

    events["start_time"] = pd.to_datetime(events["start_time"])
    events["end_time"] = pd.to_datetime(events["end_time"])
    events["solo_friendly"] = events["solo_friendly"].astype(str).str.lower() == "true"

    merged = events.merge(
        sources[
            ["source_id", "name", "last_checked", "channel_type", "update_cadence", "notes"]
        ].rename(columns={"name": "source_name", "last_checked": "source_last_checked", "notes": "source_notes"}),
        on="source_id",
        how="left",
    )
    merged["source_last_checked"] = pd.to_datetime(merged["source_last_checked"]).dt.date
    return merged


def filter_activities(constraints: UserConstraints, now: Optional[datetime] = None) -> pd.DataFrame:
    """Return the set of activities that satisfy the given hard
    constraints -- expired and incompatible events are excluded. Never
    ranks by attractiveness; that's scoring_engine's job.
    """
    df = load_activities()
    now = now or datetime.now()

    # Exclude expired events -- always, regardless of mode.
    df = df[df["start_time"] >= now]

    # Category is only a hard constraint in "specific" mode. In "mood" and
    # "surprise" modes, category is not required -- vibe/ranking decides.
    if constraints.mode == "specific" and constraints.category:
        df = df[df["category"].str.lower() == constraints.category.lower()]

    if constraints.max_cost is not None:
        df = df[df["cost"] <= constraints.max_cost]

    if constraints.solo_friendly is True:
        df = df[df["solo_friendly"]]

    if constraints.date is not None:
        df = df[df["start_time"].dt.date == constraints.date]

    if constraints.after_time is not None:
        df = df[df["start_time"].dt.time >= constraints.after_time]

    if constraints.hours_free is not None:
        # Only exclude events whose duration is known and exceeds the
        # user's stated free time -- an unknown end_time is never treated
        # as "too long", since that would fabricate a constraint violation.
        known_duration = df["end_time"].notna()
        duration_hours = (df["end_time"] - df["start_time"]).dt.total_seconds() / 3600
        too_long = known_duration & (duration_hours > constraints.hours_free)
        df = df[~too_long]

    return df


def select_recommendations(
    scored_df: pd.DataFrame,
    constraints: UserConstraints,
    top_n: int = MAX_RESULTS,
    random_state: Optional[int] = None,
) -> pd.DataFrame:
    """Pick the final set from an already-scored, already-sorted (desc)
    DataFrame. Strict top-N normally; a weighted-random sample from the
    top-scored pool in "surprise" mode, so repeated surprise requests
    don't always return the exact same five events.
    """
    if scored_df.empty:
        return scored_df

    if constraints.mode == "surprise":
        pool = scored_df.head(min(SURPRISE_POOL_SIZE, len(scored_df)))
        weights = pool["total_score"].clip(lower=1.0)
        n = min(top_n, len(pool))
        return pool.sample(n=n, weights=weights, random_state=random_state)

    return scored_df.head(top_n)


def build_recommendations(
    constraints: UserConstraints,
    now: Optional[datetime] = None,
    random_state: Optional[int] = None,
) -> pd.DataFrame:
    """Full pipeline: filter (feasibility) -> rank (transparent scoring)
    -> select (top 5, or weighted sample for "surprise" mode).
    """
    feasible = filter_activities(constraints, now=now)
    scored = rank_candidates(feasible, constraints, today=(now or datetime.now()).date())
    return select_recommendations(scored, constraints, random_state=random_state)
