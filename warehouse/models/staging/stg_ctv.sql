select
    cast(week_start as date) as week_start,
    geo_region as region_id,
    'ctv' as channel_id,
    cast(spend as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(completed_views as bigint) as completed_views,
    cast(attributed_leads as double) as platform_conversions
from {{ source('raw', 'ctv_weekly') }}
