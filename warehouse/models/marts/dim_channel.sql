select
    channel_id,
    channel_name,
    channel_group,
    marketing_role,
    source_system,
    is_paid,
    reports_impressions,
    reports_clicks,
    sort_order,
    buying_model
from {{ ref('channels') }}
