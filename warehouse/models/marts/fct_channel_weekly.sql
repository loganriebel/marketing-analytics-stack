-- Golden table for paid media: one row per week x region x paid channel, zero-filled.
-- Platform conversions are what each platform claims. Sourced leads and pipeline
-- are what the CRM credits by last-touch UTM. Neither is incremental.
with spine as (
    select
        weeks.week_start,
        regions.region_id,
        regions.region_name,
        regions.sales_area,
        channels.channel_id,
        channels.has_delivery_metrics
    from {{ ref('int_week_spine') }} as weeks
    cross join {{ ref('stg_regions') }} as regions
    cross join {{ ref('dim_channel') }} as channels
    where channels.is_paid
),

media as (
    select * from {{ ref('int_paid_media_weekly') }}
),

leads as (
    select
        created_week as week_start,
        region_id,
        channel_id,
        count(*) as sourced_leads
    from {{ ref('stg_crm_leads') }}
    group by 1, 2, 3
),

opportunities as (
    select
        opps.created_week as week_start,
        leads.region_id,
        leads.channel_id,
        count(*) as sourced_opportunities,
        sum(opps.amount) as sourced_pipeline
    from {{ ref('stg_crm_opportunities') }} as opps
    inner join {{ ref('stg_crm_leads') }} as leads
        on opps.lead_id = leads.lead_id
    group by 1, 2, 3
)

select
    spine.week_start,
    spine.region_id,
    spine.region_name,
    spine.sales_area,
    spine.channel_id,
    coalesce(media.spend, 0) as spend,
    case when spine.has_delivery_metrics then coalesce(media.impressions, 0) end as impressions,
    case when spine.has_delivery_metrics then coalesce(media.clicks, 0) end as clicks,
    coalesce(media.platform_conversions, 0) as platform_conversions,
    coalesce(leads.sourced_leads, 0) as sourced_leads,
    coalesce(opportunities.sourced_opportunities, 0) as sourced_opportunities,
    coalesce(opportunities.sourced_pipeline, 0) as sourced_pipeline
from spine
left join media
    on spine.week_start = media.week_start
    and spine.region_id = media.region_id
    and spine.channel_id = media.channel_id
left join leads
    on spine.week_start = leads.week_start
    and spine.region_id = leads.region_id
    and spine.channel_id = leads.channel_id
left join opportunities
    on spine.week_start = opportunities.week_start
    and spine.region_id = opportunities.region_id
    and spine.channel_id = opportunities.channel_id
