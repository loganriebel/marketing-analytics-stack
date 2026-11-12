select
    cast(week_start_date as date) as week_start,
    geo_target_region as region_id,
    case
        when campaign_type = 'VIDEO' then 'youtube'
        when campaign_name ilike '%nonbrand%' then 'paid_search_nonbrand'
        when campaign_name ilike '%brand%' then 'paid_search_brand'
    end as channel_id,
    campaign_name,
    cast(round(cast(cost_micros as bigint) / 1000000.0, 2) as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks,
    cast(conversions as double) as platform_conversions
from {{ source('raw', 'ads_google_weekly') }}
