{#
    One row per source, with how much recommendable content it is actually
    producing right now.

    This exists because "how many upcoming events does this org have?" was
    previously answered by counting raw.activity_events directly, which
    applies none of the business rules -- it would happily count a cancelled
    event, an event from an abandoned source, or one with no URL. Counting
    mart_activity_candidates instead means the number shown next to an
    organization is, by construction, the number of things this product
    would genuinely recommend from it.

    It also makes the API-sourced feed visible as a source in its own right,
    which the raw source directory cannot do -- that table only contains
    hand-curated organizations.
#}

with sources as (
    select * from {{ ref('stg_activity_sources') }}
    union all
    select * from {{ ref('stg_nyc_parks_source') }}
),

recommendable_counts as (
    select
        source_id,
        count(*) as upcoming_event_count,
        min(start_at) as next_event_at
    from {{ ref('mart_activity_candidates') }}
    group by source_id
)

select
    sources.source_id,
    sources.source_name,
    sources.source_category,
    sources.channel_type,
    sources.source_url,
    sources.source_image_url,
    sources.update_cadence,
    sources.source_last_checked,
    sources.is_active,
    recommendable_counts.next_event_at,
    coalesce(recommendable_counts.upcoming_event_count, 0) as upcoming_event_count
from sources
left join recommendable_counts on sources.source_id = recommendable_counts.source_id
where sources.is_active
