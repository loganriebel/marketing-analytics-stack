-- The reporting window is the span of the ad exports. The CRM holds older leads,
-- which stay out of the marts.
with bounds as (
    select min(week_start) as first_week, max(week_start) as last_week
    from {{ ref('int_paid_media_weekly') }}
)

select
    cast(unnest(generate_series(
        cast(first_week as timestamp), cast(last_week as timestamp), interval 7 day
    )) as date) as week_start
from bounds
