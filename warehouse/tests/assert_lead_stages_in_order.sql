-- A lead reaches MQL no earlier than it was created, and SQL only after MQL.
select lead_id, created_date, mql_date, sql_date
from {{ ref('stg_crm_leads') }}
where mql_date < created_date
   or sql_date < mql_date
   or (sql_date is not null and mql_date is null)
