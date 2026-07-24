"""
Unit tests for filter_engine's feasibility logic (expiry, budget, solo,
category, date) and the scoring/selection pipeline built on top of it
(proximity, vibe match, confidence, surprise-me sampling). These are the
tests to write first -- the filter+scoring pipeline is the core trust
mechanism of the product.
"""

from datetime import datetime, time

from app.models.schema import UserConstraints
from app.services.filter_engine import build_recommendations, filter_activities
from app.services.scoring_engine import confidence_score, proximity_score, vibe_score

NOW = datetime(2026, 7, 20, 12, 0, 0)


def test_expired_events_are_excluded():
    constraints = UserConstraints(mode="specific")
    df = filter_activities(constraints, now=NOW)
    assert "evt-009" not in df["event_id"].values, "evt-009 starts in the past and must be excluded"


def test_category_is_a_hard_filter_in_specific_mode():
    constraints = UserConstraints(mode="specific", category="active")
    df = filter_activities(constraints, now=NOW)
    assert set(df["category"]) == {"active"}


def test_category_is_not_a_hard_filter_in_mood_mode():
    constraints = UserConstraints(mode="mood", vibe="chill")
    df = filter_activities(constraints, now=NOW)
    assert len(set(df["category"])) > 1, "mood mode should not restrict to a single category"


def test_max_cost_excludes_pricier_events():
    constraints = UserConstraints(mode="specific", max_cost=0)
    df = filter_activities(constraints, now=NOW)
    assert (df["cost"] <= 0).all()


def test_solo_friendly_hard_filter():
    constraints = UserConstraints(mode="specific", solo_friendly=True)
    df = filter_activities(constraints, now=NOW)
    assert df["solo_friendly"].all()


def test_specific_mode_never_returns_more_than_five():
    constraints = UserConstraints(mode="specific")
    result = build_recommendations(constraints, now=NOW)
    assert len(result) <= 5


def test_specific_mode_is_ranked_by_total_score_descending():
    constraints = UserConstraints(mode="specific")
    result = build_recommendations(constraints, now=NOW)
    scores = list(result["total_score"])
    assert scores == sorted(scores, reverse=True)


def test_zip_proximity_ranks_nearby_events_higher():
    # ZIP 10003 (East Village) should rank the East Village open mic
    # (evt-005) above events on the far side of Brooklyn, all else equal.
    constraints = UserConstraints(mode="mood", vibe="social", zip_code="10003")
    result = build_recommendations(constraints, now=NOW)
    assert "distance_miles" in result.columns
    nearby = result[result["event_id"] == "evt-005"]
    assert not nearby.empty
    assert nearby.iloc[0]["distance_miles"] < 1.0


def test_unknown_zip_does_not_crash_and_drops_proximity_component():
    constraints = UserConstraints(mode="specific", zip_code="99999")
    result = build_recommendations(constraints, now=NOW)
    assert result["distance_miles"].isna().all()


def test_mood_mode_prefers_matching_vibe_tag():
    constraints = UserConstraints(mode="mood", vibe="creative")
    result = build_recommendations(constraints, now=NOW)
    assert result.iloc[0]["vibe_score"] == 100.0


def test_surprise_mode_respects_hard_constraints_and_returns_up_to_five():
    constraints = UserConstraints(mode="surprise", max_cost=0)
    result = build_recommendations(constraints, now=NOW, random_state=42)
    assert len(result) <= 5
    assert (result["cost"] <= 0).all()


def test_surprise_mode_sampling_is_reproducible_with_same_seed():
    constraints = UserConstraints(mode="surprise")
    first = build_recommendations(constraints, now=NOW, random_state=7)
    second = build_recommendations(constraints, now=NOW, random_state=7)
    assert list(first["event_id"]) == list(second["event_id"])


def test_confidence_score_rewards_recently_checked_website_sources():
    score, label, _ = confidence_score("website", "weekly", NOW.date().replace(day=19))
    assert label in {"High", "Medium"}
    assert 0.0 <= score <= 1.0


def test_confidence_score_penalizes_stale_sources():
    from datetime import date

    fresh_score, _, _ = confidence_score("website", "weekly", date(2026, 7, 19), today=date(2026, 7, 20))
    stale_score, _, _ = confidence_score("website", "weekly", date(2026, 1, 1), today=date(2026, 7, 20))
    assert stale_score < fresh_score


def test_vibe_score_is_none_when_no_vibe_requested():
    assert vibe_score("chill|social", None) is None


def test_vibe_score_matches_tag_exactly():
    assert vibe_score("chill|social", "chill") == 1.0
    assert vibe_score("chill|social", "energetic") == 0.0


def test_proximity_score_is_none_without_distance():
    assert proximity_score(None) is None


def test_proximity_score_decreases_with_distance():
    close = proximity_score(0.5)
    far = proximity_score(7.0)
    assert close > far


def test_hours_free_excludes_events_longer_than_stated_free_time():
    constraints = UserConstraints(mode="specific", hours_free=1.0)
    df = filter_activities(constraints, now=NOW)
    assert "evt-001" not in df["event_id"].values, "2-hour event exceeds 1 hour free"
    assert "evt-010" in df["event_id"].values, "1-hour event fits exactly"


def test_after_time_excludes_earlier_start_times():
    constraints = UserConstraints(mode="specific", after_time=time(15, 0))
    df = filter_activities(constraints, now=NOW)
    assert "evt-002" not in df["event_id"].values, "starts at 09:00, before 15:00"
    assert "evt-001" in df["event_id"].values, "starts at 18:30, after 15:00"
