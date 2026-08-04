{#
    Append-only fact table: one row per (event, date the event was confirmed
    present in the source feed).

    Why this exists
    ---------------
    The API serves a rolling 14-day window with no history endpoint. Raw
    ingestion upserts on guid, so `raw.nyc_parks_events` holds exactly one
    row per event no matter how many times it has been seen. That means the
    answer to "was this event in the feed last Tuesday?" is destroyed on
    every run unless something records it. This model is that record.

    Grain and honesty
    -----------------
    One row per (event_id, observed_on). A row asserts only that the event
    was confirmed present in the feed on that date -- it never asserts
    absence, and gaps must not be read as "the event was withdrawn". A gap
    is equally consistent with the pipeline not having run that day, which
    is currently common.

    The initial load is necessarily sparse: because prior runs overwrote
    `ingested_at`, the only historical observation recoverable per event is
    its most recent one. Density improves from the first scheduled run
    onward. This is a real limitation of starting to record history late,
    not something to paper over by interpolating dates we never observed.

    Materialization
    ---------------
    Incremental, because this is genuinely append-only and grows by roughly
    the feed size (~200 rows) every day, indefinitely. `delete+insert` on
    the composite key rather than plain append so that re-running the
    pipeline twice in one day is idempotent instead of double-counting.
#}

{{
    config(
        materialized='incremental',
        unique_key=['event_id', 'observed_on'],
        incremental_strategy='delete+insert'
    )
}}

with feed as (
    select
        source_record_id,
        ingested_at,
        title,
        startdate
    from {{ source('raw', 'nyc_parks_events') }}

    {% if is_incremental() %}
    -- `>=` rather than `>`: combined with delete+insert on the composite
    -- key, this makes a same-day re-run replace that day's rows instead of
    -- duplicating or silently skipping them.
    where ingested_at::date >= (
        select coalesce(max(recorded.observed_on), date '1900-01-01')
        from {{ this }} as recorded
    )
    {% endif %}
)

select
    source_record_id,
    startdate as scheduled_for,
    ingested_at::date as observed_on,
    'parks-' || source_record_id as event_id,
    -- Captured per observation because it is the feed's only cancellation
    -- signal, and knowing *when* it started saying this is the entire point.
    (title ilike 'CANCELED%' or title ilike 'CANCELLED%') as was_cancelled_on_that_date,
    startdate - ingested_at::date as days_ahead_of_event
from feed
