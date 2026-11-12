select
    promo_id,
    promo_name,
    promo_type,
    cast(start_date as date) as start_date,
    cast(end_date as date) as end_date,
    cast(discount_pct as integer) as discount_pct,
    cast(price_change_pct as integer) as price_change_pct
from {{ source('raw', 'promo_calendar') }}
