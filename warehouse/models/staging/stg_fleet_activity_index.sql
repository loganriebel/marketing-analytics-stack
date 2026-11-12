select
    cast(week_start as date) as week_start,
    cast(fleet_activity_index as double) as fleet_activity_index
from {{ source('raw', 'fleet_activity_index_weekly') }}
