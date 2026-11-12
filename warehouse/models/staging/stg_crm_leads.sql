with leads as (
    select
        lead_id,
        cast(created_date as date) as created_date,
        region_code as region_id,
        -- A blank UTM pair is a direct visit.
        lower(trim(coalesce(utm_source, '(direct)'))) as utm_source,
        lower(trim(coalesce(utm_medium, '(none)'))) as utm_medium,
        lower(trim(utm_campaign)) as utm_campaign,
        cast(mql_date as date) as mql_date,
        cast(sql_date as date) as sql_date
    from {{ source('raw', 'crm_leads') }}
),

utm_map as (
    select * from {{ ref('utm_channel_map') }}
)

select
    leads.lead_id,
    leads.created_date,
    cast(date_trunc('week', leads.created_date) as date) as created_week,
    leads.region_id,
    leads.utm_source,
    leads.utm_medium,
    leads.utm_campaign,
    utm_map.channel_id,
    leads.mql_date,
    cast(date_trunc('week', leads.mql_date) as date) as mql_week,
    leads.sql_date,
    cast(date_trunc('week', leads.sql_date) as date) as sql_week
from leads
left join utm_map
    on leads.utm_source = utm_map.utm_source
    and leads.utm_medium = utm_map.utm_medium
    and (utm_map.utm_campaign is null or leads.utm_campaign = utm_map.utm_campaign)
