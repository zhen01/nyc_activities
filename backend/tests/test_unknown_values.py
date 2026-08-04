"""Tests for how genuinely-unknown values are treated once a feed that
doesn't publish them (the NYC Parks API) shares the mart with one that does.

The rule under test is the same one the analytics layer enforces for price:
an absent value is "unknown", never a convenient default. Getting this wrong
is silent and user-facing -- it would mean promising an event is free, or
solo-friendly, on no evidence at all.
"""

from datetime import datetime

import pandas as pd

from app.models.schema import UserConstraints
from app.services.filter_engine import build_recommendations, filter_activities
from app.services.presentation import compute_tags

NOW = datetime(2026, 7, 20, 12, 0, 0)


def _row(**overrides) -> dict:
    base = dict(
        event_id="parks-1",
        title="Mat Pilates",
        category="active",
        start_time=pd.Timestamp("2026-07-21 18:00"),
        end_time=pd.Timestamp("2026-07-21 19:00"),
        cost=None,
        location="Highbridge Park",
        solo_friendly=None,
        vibe_tags=None,
        source_url="https://example.org/e",
        source_name="NYC Parks Open Data",
        channel_type="api",
        update_cadence="daily",
        source_last_checked=datetime(2026, 7, 20).date(),
        zip_code=None,
        lat=40.84,
        lon=-73.93,
        image_url=None,
        beginner_friendly=False,
    )
    base.update(overrides)
    return base


def _frame(*rows) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    df["cost"] = pd.to_numeric(df["cost"], errors="coerce")
    return df


def test_unknown_solo_friendly_is_not_treated_as_solo_friendly():
    df = _frame(_row(solo_friendly=None), _row(event_id="csv-1", solo_friendly=True))
    result = filter_activities(
        UserConstraints(mode="specific", solo_friendly=True), now=NOW, activities=df
    )
    assert list(result["event_id"]) == ["csv-1"]


def test_unknown_solo_friendly_is_kept_when_the_user_did_not_ask_for_solo():
    df = _frame(_row(solo_friendly=None))
    result = filter_activities(UserConstraints(mode="specific"), now=NOW, activities=df)
    assert list(result["event_id"]) == ["parks-1"]


def test_unknown_cost_never_satisfies_a_budget():
    # The inverse of "unknown price is free" -- an unverifiable price must
    # not be presented as fitting a budget the user set.
    df = _frame(_row(cost=None), _row(event_id="csv-1", cost=0.0))
    result = filter_activities(
        UserConstraints(mode="specific", max_cost=0), now=NOW, activities=df
    )
    assert list(result["event_id"]) == ["csv-1"]


def test_unknown_vibe_tags_do_not_crash_tag_rendering():
    tags = compute_tags(pd.Series(_row(vibe_tags=None)))
    assert "Meet people" not in tags
    assert "Casual" not in tags


def test_precomputed_beginner_friendly_is_preferred_over_the_keyword_heuristic():
    # The mart computes this once (including from the API's description
    # field, which the serving layer never sees), so a True there must win
    # even though the title contains no keyword.
    tags = compute_tags(pd.Series(_row(beginner_friendly=True)))
    assert "Beginner friendly" in tags


def test_beginner_friendly_falls_back_to_keywords_when_column_absent():
    row = _row(title="Beginner Volleyball")
    del row["beginner_friendly"]
    assert "Beginner friendly" in compute_tags(pd.Series(row))


def test_missing_coordinates_do_not_outrank_a_genuinely_nearby_event():
    # Regression: dropping the proximity component for an unlocatable event
    # renormalised the remaining weights and pushed it *above* an event we
    # could confirm was 0.3 miles away -- i.e. missing data scored better
    # than good data.
    df = _frame(
        _row(event_id="no-coords", lat=None, lon=None),
        _row(event_id="nearby", lat=40.7506, lon=-73.9972),
    )
    result = build_recommendations(
        # 10001 is Midtown and is present in data/sample/zip_centroids.csv.
        UserConstraints(mode="specific", zip_code="10001"),
        now=NOW,
        activities=df,
    )
    ranked = list(result["event_id"])
    assert ranked.index("nearby") < ranked.index("no-coords")


def test_unlocatable_event_is_still_returned_rather_than_dropped():
    df = _frame(_row(event_id="no-coords", lat=None, lon=None))
    result = build_recommendations(
        UserConstraints(mode="specific", zip_code="10001"), now=NOW, activities=df
    )
    assert list(result["event_id"]) == ["no-coords"]
    assert pd.isna(result.iloc[0]["distance_miles"])
