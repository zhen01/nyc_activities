-- Business rule: a cancelled event must never be recommendable.
--
-- This one exists because the live NYC Parks feed keeps publishing events
-- after they are called off, recording the cancellation only as a
-- "CANCELED:"/"CANCELLED:" prefix on the title rather than as a status
-- field. Without an explicit rule those rows look completely healthy --
-- upcoming, active source, fresh, valid URL -- and would be recommended.
--
-- A dbt test fails if this query returns any rows.
select event_id
from {{ ref('mart_activity_candidates') }}
where event_name ilike 'CANCELED%'
   or event_name ilike 'CANCELLED%'
