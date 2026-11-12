select
    cast(month_start as date) as month_start,
    region_code as region_id,
    cast(sdr_headcount as integer) as sdr_headcount,
    cast(ae_headcount as integer) as ae_headcount
from {{ source('raw', 'sales_capacity_monthly') }}
