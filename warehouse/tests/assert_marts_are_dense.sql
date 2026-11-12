-- All facts are zero-filled grids: every week x region (x channel) row exists.
with sizes as (
    select
        (select count(*) from {{ ref('int_week_spine') }}) as weeks,
        (select count(*) from {{ ref('stg_regions') }}) as regions,
        (select count(*) from {{ ref('dim_channel') }} where is_paid) as paid_channels,
        (select count(*) from {{ ref('dim_channel') }}) as all_channels
)

select 'fct_channel_weekly' as model
from sizes
where (select count(*) from {{ ref('fct_channel_weekly') }}) <> weeks * regions * paid_channels
union all
select 'fct_funnel'
from sizes
where (select count(*) from {{ ref('fct_funnel') }}) <> weeks * regions * all_channels
union all
select 'fct_controls_weekly'
from sizes
where (select count(*) from {{ ref('fct_controls_weekly') }}) <> weeks * regions
