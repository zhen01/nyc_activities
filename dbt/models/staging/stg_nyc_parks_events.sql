{#
    Staging layer for the live NYC Parks Open Data feed.

    Unlike the other staging models, this one is not rename-only: the API's
    shape genuinely differs from the curated CSV feed, and four real
    data-quality problems have to be resolved here (each documented inline
    below) before the two streams can be unioned. What this model still
    refuses to do is *invent* values -- price, solo_friendly and vibe_tags
    simply do not exist in this feed, and they stay NULL rather than being
    defaulted to free/false/empty.
#}

with source as (
    select * from {{ source('raw', 'nyc_parks_events') }}
),

parsed as (
    select
        source_record_id,
        title,
        startdate,
        enddate,
        categories,
        location,
        parknames,
        link_url,
        registration_url,
        lat,
        lon,
        description,
        ingested_at,

        -- PROBLEM 1: starttime/endtime carry a meaningless date component.
        -- The API returns them as full timestamps, but the date part is the
        -- feed's publication date (every row currently reads 2026-07-20),
        -- not the day the event happens -- that lives in startdate/enddate.
        -- Only the time-of-day portion is trustworthy, so it is extracted
        -- and recombined with the real date below. The regex guard keeps a
        -- single malformed value from failing the whole model.
        case
            when starttime ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
                then starttime::timestamp::time
        end as start_time_of_day,
        case
            when endtime ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
                then endtime::timestamp::time
        end as end_time_of_day
    from source
),

recombined as (
    select
        *,
        startdate + coalesce(start_time_of_day, time '00:00') as start_at_raw,
        case
            when end_time_of_day is not null
                then coalesce(enddate, startdate) + end_time_of_day
        end as end_at_raw
    from parsed
)

select
    -- Namespaced so an API guid can never collide with a curated event_id.
    'parks-' || source_record_id as event_id,
    -- Every row from this feed belongs to one synthetic source row
    -- representing the API itself -- see stg_nyc_parks_source.
    '{{ var("nyc_parks_source_id") }}' as source_id,
    title as event_name,

    -- PROBLEM 2: `categories` is a pipe-delimited multi-value string with
    -- 28 distinct values in the live feed, dominated by fitness variants
    -- ("Fitness" and "Exercise Classes" appear on ~60% of rows). Mapping it
    -- onto this project's 7-value taxonomy therefore needs a *priority*
    -- order, not a first-match: the rarer, more specific signal must win,
    -- otherwise a volunteer gardening event tagged "Fitness | Volunteer |
    -- Gardening" would land in `active`. `active` is deliberately last --
    -- it is the broad catch-all here, not a precise label.
    -- Audience/format tags (Best for Kids, Seniors, Virtual/Online) are
    -- intentionally absent: they describe *who/how*, not *what*, and are
    -- surfaced as separate flags instead of overwriting the category.
    case
        when categories ilike '%Volunteer%' then 'volunteer'
        when categories ilike '%Food%' then 'food_drink'
        when categories ilike '%Nature%'
            or categories ilike '%Wildlife%'
            or categories ilike '%Gardening%'
            or categories ilike '%Waterfront%'
            or categories ilike '%Fishing%'
            or categories ilike '%Birding%'
            or categories ilike '%Urban Park Rangers%'
            then 'outdoors'
        when categories ilike '%Education%'
            or categories ilike '%STEM%'
            or categories ilike '%Talk%'
            or categories ilike '%Tour%'
            then 'learn'
        when categories ilike '%Games%' then 'social'
        when categories ilike '%Art%'
            or categories ilike '%Film%'
            or categories ilike '%Concert%'
            or categories ilike '%Movie%'
            or categories ilike '%History%'
            or categories ilike '%Theater%'
            or categories ilike '%Literary%'
            then 'culture'
        when categories ilike '%Fitness%'
            or categories ilike '%Exercise%'
            or categories ilike '%Dance%'
            or categories ilike '%Running%'
            or categories ilike '%Jogging%'
            or categories ilike '%Yoga%'
            or categories ilike '%Pilates%'
            or categories ilike '%Sports%'
            or categories ilike '%Recreation Center%'
            then 'active'
    end as activity_category,

    start_at_raw as start_at,
    -- PROBLEM 3: a few rows produce an end before their start once the
    -- time-of-day is recombined (contradictory source data). Rather than
    -- guessing a midnight rollover, an impossible end time is treated as
    -- *unknown* -- consistent with how end_time is handled everywhere else
    -- in this project, where unknown duration is never turned into a
    -- constraint violation.
    case when end_at_raw > start_at_raw then end_at_raw end as end_at,

    -- PROBLEM 4: this feed has no price field at all. NYC Parks events are
    -- usually free, but "usually" is not data -- price stays NULL so the
    -- existing "unknown price is not free" rule keeps holding.
    -- See tests/assert_unknown_price_stays_null.sql.
    null::numeric as price_amount,

    coalesce(nullif(location, ''), parknames) as location,

    -- Not published by this feed. NULL means "unknown", not "no".
    null::boolean as solo_friendly,
    null::varchar as vibe_tags,
    -- No ZIP in the feed; proximity is served by lat/lon instead.
    null::varchar as zip_code,
    null::varchar as image_url,

    lat,
    lon,
    coalesce(nullif(registration_url, ''), link_url) as event_source_url,
    description as event_description,

    -- The feed keeps serving events after they are called off, with the
    -- cancellation recorded only as a title prefix. Both spellings appear
    -- upstream, hence the two patterns.
    (title ilike 'CANCELED%' or title ilike 'CANCELLED%') as is_cancelled,
    (categories ilike '%Virtual/Online%') as is_virtual,

    -- This feed is machine-ingested, so "when was this last verified" is
    -- the ingestion timestamp rather than a human check date.
    ingested_at::date as event_last_checked
from recombined
