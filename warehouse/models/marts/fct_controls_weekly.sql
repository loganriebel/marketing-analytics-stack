-- Golden controls table: one row per week x region with everything besides paid
-- media that moves deals. Monthly headcount applies to every week that starts in
-- the month. Promo and price flags follow the finance calendar.
with spine as (
    select
        weeks.week_start,
        regions.region_id,
        regions.region_name,
        regions.sales_area,
        regions.target_accounts
    from {{ ref('int_week_spine') }} as weeks
    cross join {{ ref('stg_regions') }} as regions
),

promo_flags as (
    select
        weeks.week_start,
        bool_or(
            promos.promo_type = 'discount'
            and weeks.week_start between promos.start_date and promos.end_date
        ) as is_discount_promo,
        1 + sum(
            case
                when promos.promo_type = 'price_change' and promos.start_date <= weeks.week_start
                    then promos.price_change_pct
                else 0
            end
        ) / 100.0 as list_price_index
    from {{ ref('int_week_spine') }} as weeks
    cross join {{ ref('stg_promo_calendar') }} as promos
    group by 1
)

select
    spine.week_start,
    spine.region_id,
    spine.region_name,
    spine.sales_area,
    spine.target_accounts,
    capacity.sdr_headcount,
    capacity.ae_headcount,
    coalesce(email.emails_sent, 0) as emails_sent,
    coalesce(email.email_opens, 0) as email_opens,
    coalesce(email.email_clicks, 0) as email_clicks,
    promo_flags.is_discount_promo,
    promo_flags.list_price_index,
    fleet.fleet_activity_index
from spine
left join {{ ref('stg_sales_capacity') }} as capacity
    on spine.region_id = capacity.region_id
    and cast(date_trunc('month', spine.week_start) as date) = capacity.month_start
left join {{ ref('stg_email') }} as email
    on spine.region_id = email.region_id
    and spine.week_start = email.week_start
left join promo_flags
    on spine.week_start = promo_flags.week_start
left join {{ ref('stg_fleet_activity_index') }} as fleet
    on spine.week_start = fleet.week_start
