-- Every paid channel at one grain: week x region x channel. Rows exist only where
-- there was spend, the same way the platforms export them.
with ads as (
    select week_start, region_id, channel_id, spend, impressions, clicks, platform_conversions
    from {{ ref('stg_ads_google') }}
    union all
    select week_start, region_id, channel_id, spend, impressions, clicks, platform_conversions
    from {{ ref('stg_ads_meta') }}
    union all
    select week_start, region_id, channel_id, spend, impressions, clicks, platform_conversions
    from {{ ref('stg_ads_linkedin') }}
    union all
    select week_start, region_id, channel_id, spend, impressions, clicks, platform_conversions
    from {{ ref('stg_ads_display') }}
),

webinars as (
    -- Webinar registrants are the webinar tool's claim, so they sit with the platform claims.
    select
        event_week as week_start,
        region_id,
        'webinars' as channel_id,
        sum(cost) as spend,
        cast(null as bigint) as impressions,
        cast(null as bigint) as clicks,
        cast(sum(registrants) as double) as platform_conversions
    from {{ ref('stg_webinar_events') }}
    group by 1, 2, 3
)

select * from ads
union all
select * from webinars
