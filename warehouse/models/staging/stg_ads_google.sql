select
    cast(week_start_date as date) as week_start,
    geo_target_region as region_id,
    case campaign_type
        when 'SEARCH' then 'paid_search'
        when 'VIDEO' then 'youtube'
    end as channel_id,
    cast(round(cast(cost_micros as bigint) / 1000000.0, 2) as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks,
    cast(conversions as double) as platform_conversions
from {{ source('raw', 'ads_google_weekly') }}
