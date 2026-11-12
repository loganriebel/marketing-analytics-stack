select
    cast(week_start as date) as week_start,
    market as region_id,
    'tv' as channel_id,
    buy_type,
    cast(gross_cost as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(vendor_attributed_leads as double) as platform_conversions
from {{ source('raw', 'tv_weekly') }}
