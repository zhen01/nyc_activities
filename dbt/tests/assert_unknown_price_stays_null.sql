-- Business rule: unknown price must not be treated as free. Any raw event
-- with a NULL cost must still have a NULL price_amount if it appears in the
-- mart -- never silently coalesced to 0.
select
    mart.event_id
from {{ ref('mart_activity_candidates') }} as mart
inner join {{ ref('stg_activity_events') }} as events
    on mart.event_id = events.event_id
where events.price_amount is null
  and mart.price_amount is not null
