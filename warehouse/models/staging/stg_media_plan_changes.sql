select
    cast(change_date as date) as change_date,
    channel as channel_id,
    cast(budget_change_pct as integer) as budget_change_pct,
    reason
from {{ source('raw', 'media_plan_changes') }}
