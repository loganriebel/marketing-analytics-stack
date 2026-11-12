-- fct_channel_weekly must carry every dollar and claimed conversion from the
-- platform exports, with no fan-out, and its CRM-sourced leads and pipeline must
-- match fct_funnel for the paid channels.
with mart as (
    select
        channel_id,
        sum(spend) as spend,
        sum(platform_conversions) as platform_conversions,
        sum(sourced_leads) as leads,
        sum(sourced_pipeline) as pipeline
    from {{ ref('fct_channel_weekly') }}
    group by 1
),

platforms as (
    select channel_id, sum(spend) as spend, sum(platform_conversions) as platform_conversions
    from {{ ref('int_paid_media_weekly') }}
    group by 1
),

funnel as (
    select channel_id, sum(leads) as leads, sum(pipeline_amount) as pipeline
    from {{ ref('fct_funnel') }}
    group by 1
)

select mart.channel_id
from mart
left join platforms on mart.channel_id = platforms.channel_id
left join funnel on mart.channel_id = funnel.channel_id
where platforms.channel_id is null
   or mart.spend <> platforms.spend
   or abs(mart.platform_conversions - platforms.platform_conversions) > 0.001
   or mart.leads <> funnel.leads
   or mart.pipeline <> funnel.pipeline
