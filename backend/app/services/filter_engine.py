"""Feasibility filtering -- product principle #1: "feasibility before
attractiveness".

Data source: `analytics.mart_activity_candidates`, the dbt mart. This
replaced a direct read of `data/sample/*.csv`, which had become actively
misleading -- every curated sample event has since expired, so the CSV path
served an empty (or stale) result set while a live NYC Parks feed sat
ingested and unused in Postgres.

Reading the mart also means the business rules now live in exactly one
place. Expired events, inactive sources, abandoned-freshness sources,
cancelled events and structurally invalid rows are already excluded
upstream by `mart_activity_candidates`, each with a matching singular test
in `dbt/tests/` -- this module no longer re-implements any of them, and
only applies the constraints that depend on the specific user request.

Consequence worth knowing: Postgres is now required to serve
recommendations (`make db-up`). The previous "runs with no Docker" property
is gone, deliberately.

Two-stage pipeline:
  1. filter_activities(): hard pass/fail feasibility -- excludes anything
     violating a user constraint. Never ranks by attractiveness.
  2. build_recommendations(): hands the feasible set to scoring_engine for
     transparent ranking, then selects the final top 5 (or, in "surprise"
     mode, a weighted-random sample from the top-ranked pool).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd

from app import db as app_db
from app.models.schema import UserConstraints
from app.services.scoring_engine import rank_candidates

MAX_RESULTS = 5
SURPRISE_POOL_SIZE = 10

MART_RELATION = "analytics.mart_activity_candidates"

# The mart's column names are warehouse-facing; the serving layer (scoring,
# presentation, the API schema) speaks in the names below. Renaming here
# keeps that one translation in a single place instead of scattering
# mart-specific names through the request path.
_MART_TO_SERVING = {
    "event_name": "title",
    "activity_category": "category",
    "start_at": "start_time",
    "end_at": "end_time",
    "price_amount": "cost",
}


def load_activities() -> pd.DataFrame:
    """Read recommendable candidates from the dbt mart.

    Every row returned here has already passed the mart's business rules,
    so this is a straight read plus a column rename -- no filtering.
    """
    engine = app_db.get_engine()
    df = pd.read_sql(f"select * from {MART_RELATION}", engine)
    df = df.rename(columns=_MART_TO_SERVING)

    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    # Postgres DATE -> datetime.date, which is what confidence_score expects.
    df["source_last_checked"] = pd.to_datetime(df["source_last_checked"]).dt.date
    # Numeric in Postgres arrives as Decimal; downstream comparisons and the
    # Pydantic float field both want a plain float. NULL stays NaN -> None.
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")
    return df


def filter_activities(
    constraints: UserConstraints,
    now: Optional[datetime] = None,
    activities: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Return the set of activities that satisfy the given hard
    constraints -- expired and incompatible events are excluded. Never
    ranks by attractiveness; that's scoring_engine's job.

    `activities` overrides the mart read. Tests pass a fixed fixture
    through it: asserting filter behaviour against a live feed whose
    contents change every day would make the suite both non-deterministic
    and dependent on a running database.
    """
    df = load_activities() if activities is None else activities.copy()
    now = now or datetime.now()

    # Expiry is enforced by the mart (in NYC local time), not here. This
    # second pass exists only because `now` is injectable for tests and can
    # therefore differ from the mart's own "now".
    df = df[df["start_time"] >= now]

    # Category is only a hard constraint in "specific" mode. In "mood" and
    # "surprise" modes, category is not required -- vibe/ranking decides.
    if constraints.mode == "specific" and constraints.category:
        df = df[df["category"].str.lower() == constraints.category.lower()]

    if constraints.max_cost is not None:
        # An unknown cost never satisfies a budget: NaN <= x is False, so
        # those rows drop out. That is intentional -- promising an event
        # fits a budget we cannot verify would be the same "unknown price
        # is free" error the analytics layer explicitly forbids.
        df = df[df["cost"] <= constraints.max_cost]

    if constraints.solo_friendly is True:
        # Unknown (NULL) solo-friendliness is treated as "cannot promise",
        # not as "yes". The API-sourced feed publishes no solo_friendly
        # flag at all, so this filter legitimately returns very little --
        # a visible coverage gap rather than a fabricated reassurance.
        df = df[df["solo_friendly"].astype("boolean").fillna(False).astype(bool)]

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
        weights = pool["total_score"].clip(lower=1.0).to_numpy(dtype=float)
        n = min(top_n, len(pool))
        # pandas 3.0 dropped weighted sampling with replace=False, so draw the
        # row positions with numpy instead. Same thing we asked pandas for --
        # n distinct rows, picked with probability proportional to score --
        # and still reproducible from random_state.
        rng = np.random.default_rng(random_state)
        picks = rng.choice(len(pool), size=n, replace=False, p=weights / weights.sum())
        return pool.iloc[picks]

    return scored_df.head(top_n)


def build_recommendations(
    constraints: UserConstraints,
    now: Optional[datetime] = None,
    random_state: Optional[int] = None,
    activities: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Full pipeline: filter (feasibility) -> rank (transparent scoring)
    -> select (top 5, or weighted sample for "surprise" mode).
    """
    feasible = filter_activities(constraints, now=now, activities=activities)
    scored = rank_candidates(feasible, constraints, today=(now or datetime.now()).date())
    return select_recommendations(scored, constraints, random_state=random_state)
