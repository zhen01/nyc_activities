with candidates as (
    select * from {{ ref('int_activity_enriched') }}
),

filtered as (
    select *
    from candidates
    where
        -- 1. event not ended: use end_at when known, otherwise start_at
        coalesce(end_at, start_at) >= current_timestamp
        -- 2. source active
        and is_active
        -- 3. valid time (defensive re-check; also enforced NOT NULL upstream)
        and start_at is not null
        -- 4. URL exists
        and event_source_url is not null
        and event_source_url != ''
        -- 5. not invalid data: the fields every recommendation needs to render
        and event_name is not null
        and location is not null
        and activity_category is not null
        -- 6. price legal: NULL (unknown) is allowed and stays NULL --
        --    only a negative price is "illegal"
        and (price_amount is null or price_amount >= 0)
        -- 7. freshness not too old
        and freshness_status != 'abandoned'
)

select
    event_id,
    event_name,
    activity_family,
    secondary_badge,
    social_structure,
    group_suitability,
    solo_private_score,
    solo_social_score,
    couple_score,
    small_group_score,
    beginner_friendly,
    price_amount,
    start_at,
    end_at,
    borough,
    freshness_status,
    actionability_score,
    discovery_score,
    image_url,
    event_source_url as source_url
from filtered
