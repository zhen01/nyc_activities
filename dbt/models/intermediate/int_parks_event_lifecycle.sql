{#
    One row per event, summarising its life across every version the
    snapshot has captured: when we first saw it, how often it changed,
    whether it was cancelled, and -- where knowable -- how much notice the
    cancellation gave.

    The hard part here is what we are *not* entitled to compute.

    Left-censoring
    --------------
    13 of the events currently in the feed were already carrying a
    `CANCELED:` prefix the first time this pipeline ever saw them. For those,
    the cancellation happened at some unknown point before our observation
    window opened. Subtracting our first-capture timestamp from the event
    date would produce a number -- and that number would be an artefact of
    when we happened to start collecting, not a fact about the publisher.

    So `cancellation_lead_hours` is only populated where the transition from
    live to cancelled was actually *observed* between two snapshot versions.
    Everything else is NULL and flagged, so downstream aggregates can use an
    honest denominator instead of quietly averaging in fabricated values.

    The same reasoning applies to `first_captured_at`: it is when *we* first
    saw the event, never when the publisher created it. Those are different
    facts and the column name says which one this is.
#}

with versions as (
    select
        source_record_id,
        title,
        startdate,
        starttime,
        location,
        dbt_valid_from,
        dbt_valid_to,
        (title ilike 'CANCELED%' or title ilike 'CANCELLED%') as is_cancelled_version
    from {{ ref('snap_nyc_parks_events') }}
),

first_version as (
    select distinct on (source_record_id)
        source_record_id,
        dbt_valid_from as first_captured_at,
        is_cancelled_version as was_cancelled_at_first_capture
    from versions
    order by source_record_id, dbt_valid_from
),

current_version as (
    select
        source_record_id,
        title as current_title,
        is_cancelled_version as is_cancelled_now
    from versions
    where dbt_valid_to is null
),

change_counts as (
    select
        source_record_id,
        count(*) as version_count,
        -- Concatenated rather than a row constructor so the pair counts as
        -- one distinct value; NULL times coalesce to a sentinel so an
        -- unscheduled version isn't silently dropped from the count.
        count(distinct startdate::text || '@' || coalesce(starttime, '?')) as distinct_schedules,
        count(distinct location) as distinct_locations,
        min(dbt_valid_from) filter (where is_cancelled_version) as cancelled_first_seen_at
    from versions
    group by source_record_id
),

joined as (
    select
        first_version.source_record_id,
        first_version.first_captured_at,
        first_version.was_cancelled_at_first_capture,
        current_version.current_title,
        current_version.is_cancelled_now,
        change_counts.version_count,
        change_counts.distinct_schedules,
        change_counts.distinct_locations,
        change_counts.cancelled_first_seen_at,
        staged.start_at as scheduled_start_at,
        staged.activity_category,
        staged.event_last_checked as last_seen_in_feed_on
    from first_version
    inner join current_version
        on first_version.source_record_id = current_version.source_record_id
    inner join change_counts
        on first_version.source_record_id = change_counts.source_record_id
    left join {{ ref('stg_nyc_parks_events') }} as staged
        on 'parks-' || first_version.source_record_id = staged.event_id
)

select
    source_record_id,
    current_title,
    activity_category,
    scheduled_start_at,
    first_captured_at,
    last_seen_in_feed_on,
    version_count,
    is_cancelled_now,
    was_cancelled_at_first_capture,
    cancelled_first_seen_at,
    'parks-' || source_record_id as event_id,
    distinct_schedules > 1 as was_rescheduled,
    distinct_locations > 1 as was_relocated,

    -- True only when the live -> cancelled transition happened inside our
    -- observation window. This is the flag that makes the lead time below
    -- trustworthy, and the correct denominator for any cancellation-rate
    -- metric built on top.
    (is_cancelled_now and not was_cancelled_at_first_capture) as cancellation_observed,

    -- Hours of notice between us first seeing the cancellation and the event
    -- being due to start. NULL when the cancellation predates our first
    -- capture (unknowable) or never happened. A negative value is legitimate
    -- and meaningful: the feed sometimes marks events cancelled after their
    -- scheduled start time.
    case
        when is_cancelled_now
            and not was_cancelled_at_first_capture
            and scheduled_start_at is not null
            then round(
                extract(epoch from (scheduled_start_at - cancelled_first_seen_at)) / 3600.0,
                1
            )
    end as cancellation_lead_hours
from joined
