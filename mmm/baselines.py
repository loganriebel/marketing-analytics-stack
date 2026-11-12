"""The two views finance sees today, from the marts, scored the same way as the MMM.

* CRM last touch: closed-won deals credited to the channel's last UTM touch
  (fct_funnel.won_deals by channel).
* Platform reported: conversions each platform claims (fct_channel_weekly.
  platform_conversions), turned into deals at the company-wide lead-to-won rate.
"""

from __future__ import annotations

from . import config as C
from .data import connect


def compute() -> dict:
    con = connect()
    try:
        spend = dict(con.sql(
            "select channel_id, sum(spend)::double from fct_channel_weekly group by 1").fetchall())
        platform = dict(con.sql(
            "select channel_id, sum(platform_conversions)::double from fct_channel_weekly group by 1"
        ).fetchall())
        crm = dict(con.sql(
            "select channel_id, sum(won_deals)::double from fct_funnel group by 1").fetchall())
        won, leads = con.sql(
            "select sum(won_deals)::double, sum(leads)::double from fct_funnel").fetchall()[0]
    finally:
        con.close()
    lead_to_won = won / leads
    out = {"lead_to_won_rate": lead_to_won, "channels": {}}
    for ch in C.CHANNELS:
        s = spend.get(ch, 0.0)
        crm_deals = crm.get(ch, 0.0)
        plat_deals = platform.get(ch, 0.0) * lead_to_won
        out["channels"][ch] = {
            "spend": s,
            "crm_last_touch": {"deals": crm_deals, "cpa": s / crm_deals if crm_deals else None},
            "platform_reported": {"conversions": platform.get(ch, 0.0), "deals": plat_deals,
                                  "cpa": s / plat_deals if plat_deals else None},
        }
    return out
