select
    test_id,
    test_name,
    arm_id,
    region_code as region_id,
    channel as channel_id,
    move,
    cast(move_value as double) as move_value,
    cast(start_date as date) as start_date,
    cast(end_date as date) as end_date,
    cast(approved_date as date) as approved_date
from {{ source('raw', 'market_tests') }}
