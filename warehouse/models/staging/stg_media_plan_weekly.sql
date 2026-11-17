select
    cast(week_start as date) as week_start,
    region_code as region_id,
    channel as channel_id,
    cast(planned_spend as double) as planned_spend
from {{ source('raw', 'media_plan_weekly') }}
