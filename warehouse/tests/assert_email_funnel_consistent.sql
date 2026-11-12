-- Unique opens cannot exceed sends, and unique clicks cannot exceed opens.
select week_start, region_id, emails_sent, email_opens, email_clicks
from {{ ref('stg_email') }}
where email_opens > emails_sent
   or email_clicks > email_opens
