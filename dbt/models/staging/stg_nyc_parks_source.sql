{#
    The NYC Parks Open Data feed has no row in the curated source directory
    (raw.activity_sources) -- that table is a human-maintained list of small
    organizations, and this is a public API.

    But conceptually the API *is* a source, and every piece of downstream
    logic (freshness bucketing, confidence scoring, discovery scoring) is
    already written in terms of a source's channel_type / update_cadence /
    last_checked. Rather than branching all of that on "is this row from the
    API or the CSV?", this model synthesizes the single source row the API
    deserves, so the existing logic applies to both feeds unchanged.

    The one genuinely different property is what "last checked" means: for a
    curated source it is the date a human re-verified it; here it is the
    date the pipeline last successfully ingested the feed, derived from the
    data itself rather than hardcoded, so a pipeline that silently stops
    running shows up as a decaying freshness_status instead of staying
    permanently "fresh".
#}

select
    '{{ var("nyc_parks_source_id") }}' as source_id,
    'NYC Parks Open Data' as source_name,
    'outdoors' as source_category,
    'api' as channel_type,
    'https://data.cityofnewyork.us/resource/w3wp-dpdi.json' as source_url,
    'daily' as update_cadence,
    max(ingested_at)::date as source_last_checked,
    'Public Socrata feed of NYC Parks events for the upcoming 14 days. '
    || 'Ingested by ingestion/nyc_parks.py; no human curation step.' as source_notes,
    true as is_active,
    null::varchar as source_image_url
from {{ source('raw', 'nyc_parks_events') }}
