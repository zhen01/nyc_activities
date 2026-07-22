with events as (
    select * from {{ ref('stg_activity_events') }}
),

sources as (
    select * from {{ ref('stg_activity_sources') }}
),

zip_lookup as (
    select * from {{ ref('zip_centroids') }}
),

joined as (
    select
        events.*,
        sources.source_name,
        sources.channel_type,
        sources.update_cadence,
        sources.source_last_checked,
        sources.source_notes,
        sources.is_active,
        zip_lookup.borough
    from events
    left join sources on events.source_id = sources.source_id
    left join zip_lookup on events.zip_code = zip_lookup.zip_code
),

-- Cadence-to-days mirrors CADENCE_DAYS in backend/app/services/scoring_engine.py
-- so "freshness" means the same thing in the API's confidence score and in this
-- mart. The mart uses two multipliers instead of the backend's one because it
-- needs a third, more permissive bucket ('abandoned') for outright exclusion,
-- not just a confidence penalty.
freshness_days as (
    select
        *,
        case update_cadence
            when 'daily' then 1
            when 'weekly' then 7
            when 'seasonal' then 90
            else 7
        end as cadence_days,
        current_date - source_last_checked as days_since_checked
    from joined
),

freshness as (
    select
        *,
        case
            when days_since_checked <= cadence_days * 2 then 'fresh'
            when days_since_checked <= cadence_days * 8 then 'stale'
            else 'abandoned'
        end as freshness_status
    from freshness_days
),

vibe_signals as (
    select
        *,
        vibe_tags like '%solo_focus%' as has_solo_tag,
        vibe_tags like '%social%' as has_social_tag,
        vibe_tags like '%chill%' as has_chill_tag,
        vibe_tags like '%creative%' as has_creative_tag,
        vibe_tags like '%energetic%' as has_energetic_tag
    from freshness
),

scored as (
    select
        *,
        -- activity_category now stores the mockup's 7-value taxonomy directly
        -- (active/outdoors/social/culture/food_drink/learn/volunteer) -- see
        -- data/sample/events.csv and sources.csv. activity_family collapses
        -- that down to the five broader buckets used for audience-fit
        -- grouping elsewhere in this model (unchanged bucket names).
        case activity_category
            when 'active' then 'active'
            when 'outdoors' then 'active'
            when 'volunteer' then 'community'
            when 'social' then 'social_learning'
            when 'culture' then 'creative'
            else 'other'
        end as activity_family,

        -- secondary_badge: a second, combined label for the mockup's
        -- two-badge cards (e.g. "Social & Active"). Purely a display label
        -- reusing the existing vibe-tag flags below -- not a new scoring
        -- dimension.
        case
            when activity_category = 'active' and has_social_tag then 'social'
            when activity_category = 'outdoors' and has_chill_tag then 'chill'
            when activity_category = 'culture' and has_creative_tag then 'creative'
            when has_social_tag then 'social'
            when has_chill_tag then 'chill'
            else null
        end as secondary_badge,

        (
            lower(coalesce(source_notes, '')) like '%beginner%'
            or lower(event_name) like '%beginner%'
        ) as beginner_friendly,

        -- discovery_score: channels that are harder to stumble on (Instagram
        -- Stories, meetup groups) score higher -- a well-indexed website is
        -- "discoverable" without this tool's help, so it scores lower.
        case channel_type
            when 'instagram' then 100
            when 'meetup' then 80
            when 'website' then 50
            else 40
        end as discovery_score,

        -- actionability_score: average of two 0-100 signals -- can this
        -- listing be trusted as current (freshness), and can a user actually
        -- act on it (a source link to verify or register).
        (
            (case freshness_status
                when 'fresh' then 100
                when 'stale' then 50
                else 0
            end)
            + (case
                when event_source_url is not null and event_source_url != '' then 100
                else 0
            end)
        ) / 2.0 as actionability_score,

        -- Four audience-fit scores (0-100). Each is a simple, documented
        -- point sum from solo_friendly + vibe_tags -- rule-based, not a
        -- model, so every point is traceable back to a specific input.
        greatest(0, least(100,
            (case when solo_friendly then 50 else 0 end)
            + (case when has_solo_tag then 30 else 0 end)
            + (case when has_chill_tag then 20 else 0 end)
            - (case when has_social_tag then 20 else 0 end)
        )) as solo_private_score,

        greatest(0, least(100,
            (case when solo_friendly then 50 else 0 end)
            + (case when has_social_tag then 40 else 0 end)
            + (case when has_energetic_tag then 10 else 0 end)
        )) as solo_social_score,

        greatest(0, least(100,
            60
            + (case when has_chill_tag or has_creative_tag then 20 else 0 end)
            + (case when not solo_friendly then 10 else 0 end)
        )) as couple_score,

        greatest(0, least(100,
            50
            + (case when not solo_friendly then 30 else 0 end)
            + (case when activity_category in ('active', 'outdoors') then 20 else 0 end)
        )) as small_group_score

    from vibe_signals
)

select
    event_id,
    event_name,
    source_id,
    source_name,
    channel_type,
    is_active,
    activity_category,
    activity_family,
    secondary_badge,
    start_at,
    end_at,
    price_amount,
    location,
    solo_friendly,
    event_source_url,
    image_url,
    zip_code,
    borough,
    vibe_tags,
    freshness_status,
    beginner_friendly,
    discovery_score,
    actionability_score,
    solo_private_score,
    solo_social_score,
    couple_score,
    small_group_score,
    case
        when solo_private_score >= solo_social_score
            and solo_private_score >= couple_score
            and solo_private_score >= small_group_score
            then 'solo_private'
        when solo_social_score >= couple_score
            and solo_social_score >= small_group_score
            then 'solo_social'
        when couple_score >= small_group_score
            then 'couple'
        else 'small_group'
    end as group_suitability,
    case
        when not solo_friendly then 'group_required'
        when has_solo_tag then 'solo_friendly'
        when has_social_tag then 'solo_or_social'
        else 'solo_or_group'
    end as social_structure
from scored
