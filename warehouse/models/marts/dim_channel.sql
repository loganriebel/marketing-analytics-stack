select
    channel_id,
    channel_name,
    channel_group,
    marketing_role,
    source_system,
    is_paid,
    has_delivery_metrics,
    sort_order
from {{ ref('channels') }}
