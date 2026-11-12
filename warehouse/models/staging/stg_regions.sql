select
    region_code as region_id,
    region_name,
    sales_area,
    cast(target_accounts as integer) as target_accounts
from {{ source('raw', 'regions') }}
