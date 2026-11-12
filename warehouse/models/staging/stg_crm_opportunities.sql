with opps as (
    select
        opportunity_id,
        lead_id,
        cast(created_date as date) as created_date,
        cast(amount as decimal(18, 2)) as amount,
        lower(replace(trim(stage), ' ', '_')) as stage,
        cast(close_date as date) as close_date
    from {{ source('raw', 'crm_opportunities') }}
)

select
    opportunity_id,
    lead_id,
    created_date,
    cast(date_trunc('week', created_date) as date) as created_week,
    amount,
    stage,
    stage = 'closed_won' as is_won,
    stage <> 'open' as is_closed,
    close_date,
    cast(date_trunc('week', close_date) as date) as close_week
from opps
