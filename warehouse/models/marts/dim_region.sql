-- Each market's role in the registered 2026 market test (MT2026Q1): which arms it is in,
-- read from the planned moves. Before any test is registered every market is 'no test'.
with registered as (
    select max(test_id) as test_id from {{ ref('stg_market_tests') }}
),

arms as (
    select
        region_id,
        bool_or(channel_id = 'youtube') as in_youtube_arm,
        bool_or(channel_id = 'paid_search_nonbrand') as in_search_arm
    from {{ ref('stg_market_tests') }}
    group by 1
)

select
    r.region_id,
    r.region_name,
    r.state,
    r.sales_area,
    r.target_accounts,
    r.latitude,
    t.test_id as market_test_id,
    case
        when t.test_id is null then 'no test'
        when a.in_youtube_arm and a.in_search_arm then 'youtube and search'
        when a.in_youtube_arm then 'youtube only'
        when a.in_search_arm then 'search only'
        else 'neither'
    end as market_test_cell,
    case
        when t.test_id is null then 'no test'
        when coalesce(a.in_youtube_arm, false) then 'test'
        else 'control'
    end as youtube_test_group,
    case
        when t.test_id is null then 'no test'
        when coalesce(a.in_search_arm, false) then 'test'
        else 'control'
    end as search_test_group
from {{ ref('stg_regions') }} as r
cross join registered as t
left join arms as a on r.region_id = a.region_id
