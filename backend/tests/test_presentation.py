"""Unit tests for presentation.py's badges/tags/category-label/transit
estimate -- purely derived, display-only logic (see module docstring).
"""

import pandas as pd

from app.services.presentation import (
    category_label,
    compute_badges,
    compute_duration_minutes,
    compute_tags,
    estimate_transit_minutes,
)


def _row(**overrides) -> pd.Series:
    base = dict(
        category="active",
        vibe_tags="energetic|social",
        solo_friendly=True,
        title="Wednesday Pickup Volleyball",
        source_notes="Pickup and league play; solo signups welcome",
        start_time=pd.Timestamp("2026-07-22T18:30:00"),
        end_time=pd.Timestamp("2026-07-22T20:30:00"),
    )
    base.update(overrides)
    return pd.Series(base)


def test_category_label_maps_known_categories():
    assert category_label("food_drink") == "Food & Drink"
    assert category_label("active") == "Active"


def test_category_label_falls_back_to_title_case_for_unknown_categories():
    assert category_label("mystery") == "Mystery"


def test_compute_badges_includes_primary_category_and_social_secondary():
    badges = compute_badges(_row(category="active", vibe_tags="energetic|social"))
    assert badges[0] == "Active"
    assert "Social" in badges


def test_compute_badges_has_no_secondary_when_no_matching_tag():
    badges = compute_badges(_row(category="active", vibe_tags="energetic"))
    assert badges == ["Active"]


def test_compute_tags_flags_beginner_friendly_from_source_notes():
    tags = compute_tags(_row(source_notes="Weekly meetups; beginner friendly"))
    assert "Beginner friendly" in tags


def test_compute_tags_flags_great_for_solo():
    tags = compute_tags(
        _row(solo_friendly=True, vibe_tags="solo_focus|chill", source_notes="")
    )
    assert "Great for solo" in tags


def test_estimate_transit_minutes_is_none_without_distance():
    assert estimate_transit_minutes(None) is None


def test_estimate_transit_minutes_scales_with_distance():
    near = estimate_transit_minutes(1.0, mph=12.0)
    far = estimate_transit_minutes(4.0, mph=12.0)
    assert near == 5
    assert far == 20


def test_compute_duration_minutes_known_end_time():
    assert compute_duration_minutes(_row()) == 120


def test_compute_duration_minutes_none_when_end_time_missing():
    row = _row(end_time=None)
    assert compute_duration_minutes(row) is None
