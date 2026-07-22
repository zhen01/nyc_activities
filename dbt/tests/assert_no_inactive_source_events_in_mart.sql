-- Business rule: inactive sources cannot appear in the recommendation mart.
select
    mart.event_id
from {{ ref('mart_activity_candidates') }} as mart
inner join {{ ref('stg_activity_events') }} as events
    on mart.event_id = events.event_id
inner join {{ ref('stg_activity_sources') }} as sources
    on events.source_id = sources.source_id
where sources.is_active = false
