select
    event_id,
    cast(event_date as date) as event_date,
    cast(date_trunc('week', cast(event_date as date)) as date) as event_week,
    region_code as region_id,
    topic,
    cast(total_cost as decimal(18, 2)) as cost,
    cast(registrants as integer) as registrants,
    cast(attendees as integer) as attendees
from {{ source('raw', 'webinar_events') }}
