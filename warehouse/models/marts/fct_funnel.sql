-- Golden table for the funnel: one row per week x region x lead source channel,
-- zero-filled. Each stage is counted in the week it was reached (event week), so
-- a lead created in March can add pipeline in April and revenue in July.
-- Channel is the CRM's last-touch source, including the unpaid sources.
with spine as (
    select
        weeks.week_start,
        regions.region_id,
        regions.region_name,
        regions.sales_area,
        channels.channel_id
    from {{ ref('int_week_spine') }} as weeks
    cross join {{ ref('stg_regions') }} as regions
    cross join {{ ref('dim_channel') }} as channels
),

leads as (
    select * from {{ ref('stg_crm_leads') }}
),

opps as (
    select
        opps.*,
        leads.region_id,
        leads.channel_id
    from {{ ref('stg_crm_opportunities') }} as opps
    inner join leads
        on opps.lead_id = leads.lead_id
),

created as (
    select created_week as week_start, region_id, channel_id, count(*) as leads
    from leads
    group by 1, 2, 3
),

mqls as (
    select mql_week as week_start, region_id, channel_id, count(*) as mqls
    from leads
    where mql_date is not null
    group by 1, 2, 3
),

sqls as (
    select sql_week as week_start, region_id, channel_id, count(*) as sqls
    from leads
    where sql_date is not null
    group by 1, 2, 3
),

pipeline as (
    select
        created_week as week_start,
        region_id,
        channel_id,
        count(*) as opportunities,
        sum(amount) as pipeline_amount
    from opps
    group by 1, 2, 3
),

closes as (
    select
        close_week as week_start,
        region_id,
        channel_id,
        count(*) filter (where is_won) as won_deals,
        coalesce(sum(amount) filter (where is_won), 0) as won_revenue,
        count(*) filter (where not is_won) as lost_deals
    from opps
    where is_closed
    group by 1, 2, 3
)

select
    spine.week_start,
    spine.region_id,
    spine.region_name,
    spine.sales_area,
    spine.channel_id,
    coalesce(created.leads, 0) as leads,
    coalesce(mqls.mqls, 0) as mqls,
    coalesce(sqls.sqls, 0) as sqls,
    coalesce(pipeline.opportunities, 0) as opportunities,
    coalesce(pipeline.pipeline_amount, 0) as pipeline_amount,
    coalesce(closes.won_deals, 0) as won_deals,
    coalesce(closes.won_revenue, 0) as won_revenue,
    coalesce(closes.lost_deals, 0) as lost_deals
from spine
left join created
    on spine.week_start = created.week_start
    and spine.region_id = created.region_id
    and spine.channel_id = created.channel_id
left join mqls
    on spine.week_start = mqls.week_start
    and spine.region_id = mqls.region_id
    and spine.channel_id = mqls.channel_id
left join sqls
    on spine.week_start = sqls.week_start
    and spine.region_id = sqls.region_id
    and spine.channel_id = sqls.channel_id
left join pipeline
    on spine.week_start = pipeline.week_start
    and spine.region_id = pipeline.region_id
    and spine.channel_id = pipeline.channel_id
left join closes
    on spine.week_start = closes.week_start
    and spine.region_id = closes.region_id
    and spine.channel_id = closes.channel_id
