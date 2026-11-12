-- Inside the reporting window, fct_funnel must count every lead, opportunity and
-- closed deal in the CRM exactly once.
with window_bounds as (
    select min(week_start) as first_week, max(week_start) as last_week
    from {{ ref('int_week_spine') }}
),

crm as (
    select
        (select count(*) from {{ ref('stg_crm_leads') }}, window_bounds
         where created_week between first_week and last_week) as leads,
        (select count(*) from {{ ref('stg_crm_opportunities') }}, window_bounds
         where created_week between first_week and last_week) as opportunities,
        (select sum(amount) from {{ ref('stg_crm_opportunities') }}, window_bounds
         where created_week between first_week and last_week) as pipeline_amount,
        (select sum(amount) from {{ ref('stg_crm_opportunities') }}, window_bounds
         where is_won and close_week between first_week and last_week) as won_revenue
),

mart as (
    select
        sum(leads) as leads,
        sum(opportunities) as opportunities,
        sum(pipeline_amount) as pipeline_amount,
        sum(won_revenue) as won_revenue
    from {{ ref('fct_funnel') }}
)

select *
from crm, mart
where crm.leads <> mart.leads
   or crm.opportunities <> mart.opportunities
   or crm.pipeline_amount <> mart.pipeline_amount
   or crm.won_revenue <> mart.won_revenue
