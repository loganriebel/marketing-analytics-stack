with meta as (
    select * from {{ source('raw', 'ads_meta_weekly') }}
),

regions as (
    select region_id, region_name from {{ ref('stg_regions') }}
)

select
    cast(meta.date_start as date) as week_start,
    regions.region_id,
    'meta' as channel_id,
    cast(meta.spend as decimal(18, 2)) as spend,
    cast(meta.impressions as bigint) as impressions,
    cast(meta.clicks as bigint) as clicks,
    cast(meta.leads as double) as platform_conversions
from meta
left join regions
    on meta.region = regions.region_name
