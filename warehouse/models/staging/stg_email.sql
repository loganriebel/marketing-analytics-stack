select
    cast(week_start as date) as week_start,
    region_code as region_id,
    cast(emails_sent as bigint) as emails_sent,
    cast(unique_opens as bigint) as email_opens,
    cast(unique_clicks as bigint) as email_clicks
from {{ source('raw', 'email_weekly') }}
