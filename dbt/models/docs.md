{% docs freshness_status %}
How recently the *source* (not the event) was checked, relative to that
source's own `update_cadence` (`daily` → 1 day, `weekly` → 7 days,
`seasonal` → 90 days; unmapped cadences default to the weekly bucket).
Computed once per source in `int_activity_enriched` as
`days_since_checked = {{ "{{ nyc_today() }}" }} - source_last_checked` (NYC
local time, not the warehouse's UTC -- see macros/nyc_time.sql), then
bucketed:

- `fresh` — checked within 2x the source's expected cadence
- `stale` — checked within 8x the expected cadence (kept in the mart, but
  flagged — a signal for confidence scoring, not exclusion)
- `abandoned` — anything staler than that (excluded from
  `mart_activity_candidates` entirely — see
  `dbt/tests/assert_no_abandoned_freshness_in_mart.sql`)

The same `daily`/`weekly`/`seasonal` → day-count mapping (`CADENCE_DAYS`)
is duplicated in `backend/app/services/scoring_engine.py` so "freshness"
means the same thing in the live API's confidence score as it does here —
the mart uses a third, more permissive multiplier bucket because it needs
an outright-exclusion tier, not just a confidence penalty.
{% enddocs %}

{% docs activity_family %}
Collapses the 7-value display taxonomy used by the frontend/API
(`active`, `outdoors`, `social`, `culture`, `food_drink`, `learn`,
`volunteer` — see `data/sample/events.csv`) into 5 broader buckets used
only for audience-fit grouping in this model:
`active`/`outdoors` → `active`, `volunteer` → `community`,
`social` → `social_learning`, `culture` → `creative`, anything else →
`other`. This is a modeling-layer grouping, independent of the
user-facing category label the API returns.
{% enddocs %}

{% docs secondary_badge %}
A second, combined display label for cards that show two badges at once
(e.g. "Social & Active" — see the frontend mockup). Purely a display
convenience built from the same `has_*_tag` vibe-tag flags used by the
audience-fit scores below; it is not an independent scoring dimension and
has no effect on ranking.
{% enddocs %}

{% docs discovery_score %}
0-100. How hard this event would be to find *without* this tool, based on
its source's `channel_type`: `instagram` (100) and `meetup` (80) posts are
easy to miss outside their own feed/group; a `website` (50) is more
likely already indexed by search engines and therefore less of a
"discovery" win. Unknown channel types default to 40. This is a fixed,
documented point assignment, not a learned weighting.
{% enddocs %}

{% docs actionability_score %}
0-100 average of two independent 0-100 signals: can this listing be
trusted as current right now (`freshness_status`: fresh=100, stale=50,
abandoned=0 — though abandoned rows never reach the mart), and can a user
actually act on it (100 if `event_source_url` is present and non-empty,
else 0). Two events with identical freshness can still have different
actionability if one is missing a link to register/verify.
{% enddocs %}

{% docs audience_fit_scores %}
Four independent 0-100 scores (`solo_private_score`, `solo_social_score`,
`couple_score`, `small_group_score`), each a simple, documented point sum
over `solo_friendly` and the `vibe_tags` flags (`has_solo_tag`,
`has_social_tag`, `has_chill_tag`, `has_creative_tag`,
`has_energetic_tag`). Rule-based on purpose, not a model — every point in
every score is traceable back to a specific input field, consistent with
the "no black-box scoring" principle already established for the live
API's `scoring_engine.py`. `group_suitability` is just the label of
whichever of the four scores is highest for that row (ties broken in
solo_private > solo_social > couple > small_group order).
{% enddocs %}

{% docs social_structure %}
A coarser, three-way read on who an event actually works for, independent
of the four numeric audience-fit scores above: `group_required` (not
`solo_friendly`), `solo_friendly` (solo-friendly and explicitly tagged for
solo focus), `solo_or_social` (solo-friendly and tagged social), or the
`solo_or_group` fallback for solo-friendly events with neither tag.
{% enddocs %}
