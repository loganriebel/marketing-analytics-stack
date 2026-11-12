"""Load the MMM panel from the golden marts in data/warehouse.duckdb.

Only the marts are read: fct_funnel (KPI), fct_channel_weekly (spend, plus the
platform and last-touch views used as baselines), fct_controls_weekly (controls).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from . import config as C


@dataclass
class Panel:
    weeks: pd.DatetimeIndex
    regions: list[str]
    channels: list[str]
    spend: np.ndarray          # (T, G, C) dollars
    deals: np.ndarray          # (T, G) closed-won deals, all sources
    won_revenue: np.ndarray    # (T, G) closed-won first-year revenue
    accounts: np.ndarray       # (G,) target accounts
    controls_raw: pd.DataFrame  # long, one row per week x region

    @property
    def size(self) -> np.ndarray:
        """Region size index: target accounts over the regional mean."""
        return self.accounts / self.accounts.mean()

    def subset(self, regions: list[str] | None = None, n_weeks: int | None = None) -> "Panel":
        # sorted, because PyMC-Marketing orders the geo coordinate alphabetically
        g = sorted(self.regions.index(r) for r in regions) if regions else list(range(len(self.regions)))
        t = slice(0, n_weeks)
        weeks = self.weeks[t]
        regs = [self.regions[i] for i in g]
        ctrl = self.controls_raw[self.controls_raw.region_id.isin(regs)
                                 & self.controls_raw.week_start.isin(weeks)].reset_index(drop=True)
        return Panel(weeks, regs, self.channels, self.spend[t][:, g], self.deals[t][:, g],
                     self.won_revenue[t][:, g], self.accounts[g], ctrl)


def connect(path: Path = C.WAREHOUSE) -> duckdb.DuckDBPyConnection:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found: run python -m sim and dbt build first")
    return duckdb.connect(str(path), read_only=True)


def _cube(df: pd.DataFrame, value: str, weeks, regions, channels=None) -> np.ndarray:
    if channels is None:
        wide = df.pivot(index="week_start", columns="region_id", values=value)
        return wide.reindex(index=weeks, columns=regions).fillna(0.0).to_numpy(float)
    idx = pd.MultiIndex.from_product([weeks, regions, channels])
    s = df.set_index(["week_start", "region_id", "channel_id"])[value].reindex(idx).fillna(0.0)
    return s.to_numpy(float).reshape(len(weeks), len(regions), len(channels))


def load_panel(path: Path = C.WAREHOUSE) -> Panel:
    con = connect(path)
    try:
        spend = con.sql(
            "select week_start, region_id, channel_id, spend::double as spend "
            "from fct_channel_weekly"
        ).df()
        funnel = con.sql(
            "select week_start, region_id, sum(won_deals)::double as won_deals, "
            "sum(won_revenue)::double as won_revenue from fct_funnel group by 1, 2"
        ).df()
        controls = con.sql("select * from fct_controls_weekly order by week_start, region_id").df()
    finally:
        con.close()

    for df in (spend, funnel, controls):
        df["week_start"] = pd.to_datetime(df["week_start"])
    weeks = pd.DatetimeIndex(sorted(funnel.week_start.unique()))
    regions = sorted(funnel.region_id.unique())
    missing = set(C.CHANNELS) - set(spend.channel_id)
    if missing:
        raise ValueError(f"channels missing from fct_channel_weekly: {sorted(missing)}")
    accounts = controls.groupby("region_id").target_accounts.first().reindex(regions).to_numpy(float)
    return Panel(
        weeks=weeks,
        regions=regions,
        channels=list(C.CHANNELS),
        spend=_cube(spend, "spend", weeks, regions, C.CHANNELS),
        deals=_cube(funnel, "won_deals", weeks, regions),
        won_revenue=_cube(funnel, "won_revenue", weeks, regions),
        accounts=accounts,
        controls_raw=controls,
    )


def affiliate_spend_check(path: Path = C.WAREHOUSE) -> dict:
    """Confirm affiliate spend in the mart is placement fees only.

    The mart's affiliate spend must equal the partner platform's fee column summed
    through staging, and must not move with affiliate-sourced closed deals the way a
    per-deal commission would.
    """
    con = connect(path)
    try:
        mart = con.sql("select sum(spend)::double from fct_channel_weekly where channel_id = 'affiliates'").fetchall()[0][0]
        fees = con.sql("select sum(spend)::double from stg_partners").fetchall()[0][0]
        lineage = con.sql("select sql from duckdb_views() where view_name = 'stg_partners'").fetchall()
        weekly = con.sql("""
            select s.week_start, s.spend, coalesce(f.won, 0) as won
            from (select week_start, sum(spend)::double spend from fct_channel_weekly
                  where channel_id = 'affiliates' group by 1) s
            left join (select week_start, sum(won_deals)::double won from fct_funnel
                       where channel_id = 'affiliates' group by 1) f using (week_start)
        """).df()
    finally:
        con.close()
    lineage_sql = (lineage[0][0] if lineage else "").lower()
    weekly = weekly.sort_values("week_start")
    # A per-deal commission would move week to week with affiliate-sourced wins.
    diff_corr = float(np.corrcoef(weekly.spend.diff()[1:], weekly.won.diff()[1:])[0, 1])
    return {
        "mart_affiliate_spend": round(mart, 2),
        "partner_fee_spend": round(fees, 2),
        "mart_equals_fees": abs(mart - fees) < 0.01,
        "staging_reads_partner_fees": "partner_fees" in lineage_sql and "commission" not in lineage_sql,
        "weekly_change_corr_spend_vs_affiliate_won_deals": round(diff_corr, 3),
    }
