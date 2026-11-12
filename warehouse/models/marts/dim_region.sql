select
    region_id,
    region_name,
    sales_area,
    target_accounts,
    latitude
from {{ ref('stg_regions') }}
