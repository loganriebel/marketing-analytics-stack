-- An opportunity comes from an SQL, opens on or after the SQL date, and has a
-- close date exactly when it is closed.
select opps.opportunity_id, leads.sql_date, opps.created_date, opps.close_date, opps.stage
from {{ ref('stg_crm_opportunities') }} as opps
inner join {{ ref('stg_crm_leads') }} as leads
    on opps.lead_id = leads.lead_id
where leads.sql_date is null
   or opps.created_date < leads.sql_date
   or opps.close_date < opps.created_date
   or (opps.is_closed and opps.close_date is null)
   or (not opps.is_closed and opps.close_date is not null)
