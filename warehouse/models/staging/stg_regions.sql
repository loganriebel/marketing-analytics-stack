select
    region_code as region_id,
    region_name,
    sales_area,
    cast(target_accounts as integer) as target_accounts,
    cast(latitude as double) as latitude
from {{ source('raw', 'regions') }}
