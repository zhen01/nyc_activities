"""Shared test fixtures.

`sample_activities` rebuilds the curated CSV sample data into the exact
column shape `load_activities()` returns from the dbt mart. Tests inject it
via `filter_activities(..., activities=...)` so the filtering and scoring
assertions stay deterministic: the production path now reads a live NYC
Parks feed whose contents change daily, which is the right thing for the
product and the wrong thing to assert `evt-001 is in the result` against.

The CSVs therefore keep earning their place as a fixture even though they
no longer serve traffic.
"""

from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_CSV = REPO_ROOT / "data" / "sample" / "sources.csv"
EVENTS_CSV = REPO_ROOT / "data" / "sample" / "events.csv"


def _build_sample_activities() -> pd.DataFrame:
    sources = pd.read_csv(SOURCES_CSV)
    events = pd.read_csv(EVENTS_CSV, dtype={"zip_code": str})

    merged = events.merge(
        sources[
            ["source_id", "name", "last_checked", "channel_type", "update_cadence", "notes"]
        ].rename(
            columns={
                "name": "source_name",
                "last_checked": "source_last_checked",
                "notes": "source_notes",
            }
        ),
        on="source_id",
        how="left",
    )

    merged = merged.rename(columns={"title": "title", "category": "category"})
    merged["start_time"] = pd.to_datetime(merged["start_time"])
    merged["end_time"] = pd.to_datetime(merged["end_time"])
    merged["solo_friendly"] = merged["solo_friendly"].astype(str).str.lower() == "true"
    merged["source_last_checked"] = pd.to_datetime(merged["source_last_checked"]).dt.date
    merged["cost"] = pd.to_numeric(merged["cost"], errors="coerce")

    # Columns the mart supplies that the CSVs don't carry. beginner_friendly
    # is left absent on purpose so presentation.py's fallback path is what
    # these fixtures exercise; the mart-backed path is covered separately.
    merged["is_virtual"] = False
    merged["audience_data_available"] = True
    return merged


@pytest.fixture
def sample_activities() -> pd.DataFrame:
    return _build_sample_activities()
