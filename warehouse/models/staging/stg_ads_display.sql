select
    cast(week as date) as week_start,
    region_code as region_id,
    'display' as channel_id,
    cast(media_cost as decimal(18, 2)) as spend,
    cast(impressions as bigint) as impressions,
    cast(clicks as bigint) as clicks,
    cast(post_click_conversions as bigint) as post_click_conversions,
    cast(post_view_conversions as bigint) as post_view_conversions,
    cast(post_click_conversions as double) + cast(post_view_conversions as double) as platform_conversions
from {{ source('raw', 'ads_display_weekly') }}
