select
    region_id,
    region_name,
    sales_area,
    target_accounts
from {{ ref('stg_regions') }}
