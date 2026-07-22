-- Business rule: events without a source URL cannot appear in the
-- recommendation mart (nothing to verify or act on).
select event_id
from {{ ref('mart_activity_candidates') }}
where source_url is null or source_url = ''
