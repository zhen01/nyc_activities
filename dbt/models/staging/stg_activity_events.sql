with source as (
    select * from {{ source('raw', 'activity_events') }}
)

select
    event_id,
    source_id,
    title as event_name,
    category as activity_category,
    start_time as start_at,
    end_time as end_at,
    -- Keep NULL as NULL here (never coalesced to 0): an unknown price must
    -- not be silently treated as free. Every downstream model must preserve
    -- this NULL rather than defaulting it -- see
    -- tests/assert_unknown_price_stays_null.sql.
    cost as price_amount,
    location,
    solo_friendly,
    source_url as event_source_url,
    last_checked as event_last_checked,
    zip_code,
    lat,
    lon,
    vibe_tags,
    image_url
from source
