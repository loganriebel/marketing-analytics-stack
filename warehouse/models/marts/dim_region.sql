select
    region_id,
    region_name,
    state,
    sales_area,
    target_accounts,
    latitude
from {{ ref('stg_regions') }}
