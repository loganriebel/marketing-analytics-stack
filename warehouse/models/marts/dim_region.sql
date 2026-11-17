-- Each market's role in the two registered 2026 tests, read from the planned moves in the
-- market test registry: the spring market test (which arms it is in) and the rollout
-- (rolled out, or kept on the old plan as the holdout). Before a test is registered
-- every market is 'no test' for it.
with registry as (
    select * from {{ ref('stg_market_tests') }}
),

spring as (
    select
        region_id,
        bool_or(channel_id = 'youtube') as in_youtube_arm,
        bool_or(channel_id = 'paid_search_nonbrand') as in_search_arm
    from registry
    where test_id = '{{ var("market_test_id") }}'
    group by 1
),

rolled as (
    select distinct region_id from registry where test_id = '{{ var("rollout_test_id") }}'
),

registered as (
    select
        max(case when test_id = '{{ var("market_test_id") }}' then test_id end) as market_test_id,
        bool_or(test_id = '{{ var("rollout_test_id") }}') as has_rollout
    from registry
)

select
    r.region_id,
    r.region_name,
    r.state,
    r.sales_area,
    r.target_accounts,
    r.latitude,
    t.market_test_id,
    case
        when t.market_test_id is null then 'no test'
        when s.in_youtube_arm and s.in_search_arm then 'youtube and search'
        when s.in_youtube_arm then 'youtube only'
        when s.in_search_arm then 'search only'
        else 'neither'
    end as market_test_cell,
    case
        when t.market_test_id is null then 'no test'
        when coalesce(s.in_youtube_arm, false) then 'test'
        else 'control'
    end as youtube_test_group,
    case
        when t.market_test_id is null then 'no test'
        when coalesce(s.in_search_arm, false) then 'test'
        else 'control'
    end as search_test_group,
    case
        when not coalesce(t.has_rollout, false) then 'no rollout'
        when o.region_id is not null then 'rollout'
        else 'holdout'
    end as rollout_group
from {{ ref('stg_regions') }} as r
cross join registered as t
left join spring as s on r.region_id = s.region_id
left join rolled as o on r.region_id = o.region_id
