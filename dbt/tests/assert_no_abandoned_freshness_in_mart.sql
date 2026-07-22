-- Business rule: events older than the freshness threshold get flagged
-- and excluded from the recommendation mart.
select event_id
from {{ ref('mart_activity_candidates') }}
where freshness_status = 'abandoned'
