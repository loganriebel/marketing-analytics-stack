select
    cast(start_date as date) as week_start,
    region_code as region_id,
    'linkedin' as channel_id,
    cast(cost_usd as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks,
    cast(conversions as double) as platform_conversions
from {{ source('raw', 'ads_linkedin_weekly') }}
