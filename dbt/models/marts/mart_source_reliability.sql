{#
    Per-source reliability metrics: how often this publisher cancels or
    reschedules, how much notice it gives, and how far ahead it posts.

    None of this is obtainable from the source API. It publishes a rolling
    window of current state and no history, so cancellation rate and notice
    period simply do not exist as queryable facts anywhere upstream -- they
    only become computable once something has been recording the feed over
    time. That is what this pipeline now does.

    Reading the numbers honestly
    ---------------------------
    Two guards are built into the output rather than left to the reader:

    - `observation_window_days` reports how much history actually backs the
      row. Early on this is small, and a cancellation rate over a few days
      of observation should not be read as a stable property of the
      publisher.

    - Cancellation metrics use `events_with_observed_lifecycle` as their
      denominator, not the total event count. Events that were already
      cancelled when first captured are excluded, because their cancellation
      timing is unknowable (see int_parks_event_lifecycle). Including them
      would bias the rate upward and the notice period toward zero.
#}

with lifecycle as (
    select * from {{ ref('int_parks_event_lifecycle') }}
),

observations as (
    select
        min(observed_on) as first_observed_on,
        max(observed_on) as last_observed_on,
        count(distinct observed_on) as distinct_observation_days
    from {{ ref('fct_event_observations') }}
),

aggregated as (
    select
        count(*) as events_tracked,
        count(*) filter (where cancellation_observed) as cancellations_observed,
        count(*) filter (where was_cancelled_at_first_capture) as cancelled_before_tracking,
        count(*) filter (
            where not was_cancelled_at_first_capture
        ) as events_with_observed_lifecycle,
        count(*) filter (where was_rescheduled) as reschedules_observed,
        count(*) filter (where was_relocated) as relocations_observed,
        avg(version_count) as avg_versions_per_event,
        percentile_cont(0.5) within group (
            order by cancellation_lead_hours
        ) as median_cancellation_lead_hours,
        min(cancellation_lead_hours) as min_cancellation_lead_hours
    from lifecycle
)

select
    '{{ var("nyc_parks_source_id") }}' as source_id,
    'NYC Parks Open Data' as source_name,
    observations.first_observed_on,
    observations.last_observed_on,
    observations.distinct_observation_days,
    aggregated.events_tracked,
    aggregated.events_with_observed_lifecycle,
    aggregated.cancelled_before_tracking,
    aggregated.cancellations_observed,
    aggregated.reschedules_observed,
    aggregated.relocations_observed,
    aggregated.median_cancellation_lead_hours,
    aggregated.min_cancellation_lead_hours,
    round(aggregated.avg_versions_per_event, 2) as avg_versions_per_event,
    observations.last_observed_on - observations.first_observed_on as observation_window_days,

    -- Denominator excludes events whose cancellation predates tracking --
    -- see the header note. NULL rather than 0 when nothing is yet
    -- observable, so "no data yet" cannot be misread as "never cancels".
    case
        when aggregated.events_with_observed_lifecycle > 0
            then round(
                100.0 * aggregated.cancellations_observed
                / aggregated.events_with_observed_lifecycle,
                2
            )
    end as observed_cancellation_rate_pct,

    case
        when aggregated.events_tracked > 0
            then round(100.0 * aggregated.reschedules_observed / aggregated.events_tracked, 2)
    end as reschedule_rate_pct
from aggregated
cross join observations
