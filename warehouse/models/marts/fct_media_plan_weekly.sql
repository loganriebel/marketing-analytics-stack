-- Planned spend beside delivered spend, by week, market and planned channel. Delivered
-- spend comes from fct_channel_weekly; a planned line with no delivery shows 0.
select
    p.week_start,
    p.region_id,
    p.channel_id,
    p.planned_spend,
    coalesce(c.spend, 0)::double as spend
from {{ ref('stg_media_plan_weekly') }} as p
left join {{ ref('fct_channel_weekly') }} as c
    on p.week_start = c.week_start
    and p.region_id = c.region_id
    and p.channel_id = c.channel_id
