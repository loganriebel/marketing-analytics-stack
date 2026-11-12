select
    cast(week_start as date) as week_start,
    region_code as region_id,
    'affiliates' as channel_id,
    cast(partner_fees as decimal(18, 2)) as spend,
    cast(partner_clicks as bigint) as clicks,
    cast(referred_signups as double) as platform_conversions
from {{ source('raw', 'partners_weekly') }}
