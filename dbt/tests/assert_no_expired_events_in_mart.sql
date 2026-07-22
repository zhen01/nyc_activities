-- Business rule: expired events cannot appear in the recommendation mart.
-- A dbt test fails if this query returns any rows.
select event_id
from {{ ref('mart_activity_candidates') }}
where coalesce(end_at, start_at) < current_timestamp
