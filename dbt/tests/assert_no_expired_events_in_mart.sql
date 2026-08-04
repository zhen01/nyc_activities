-- Business rule: expired events cannot appear in the recommendation mart.
-- "Expired" is evaluated in NYC local time, matching the model -- using the
-- warehouse's UTC here would make this test disagree with the model it
-- guards for several hours every evening (see macros/nyc_time.sql).
-- A dbt test fails if this query returns any rows.
select event_id
from {{ ref('mart_activity_candidates') }}
where coalesce(end_at, start_at) < {{ nyc_now() }}
