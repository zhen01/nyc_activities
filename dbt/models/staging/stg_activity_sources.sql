with source as (
    select * from {{ source('raw', 'activity_sources') }}
)

select
    source_id,
    name as source_name,
    category as source_category,
    channel_type,
    url as source_url,
    update_cadence,
    last_checked as source_last_checked,
    notes as source_notes,
    is_active,
    image_url as source_image_url
from source
