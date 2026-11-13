"""Market-week deals and spend from the golden marts, read-only.

The default warehouse is the December 2025 data cut (data/warehouse.duckdb). Set
GEOTEST_WAREHOUSE to read a later cut, such as data/cut_2026-05-31/data/warehouse.duckdb.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = Path(os.environ.get("GEOTEST_WAREHOUSE", REPO / "data" / "warehouse.duckdb"))


@dataclass
class Markets:
    weeks: pd.DatetimeIndex
    regions: list[str]
    deals: np.ndarray           # (T, G) closed-won deals, all sources, by close week
    spend: dict[str, np.ndarray]  # channel -> (T, G)
    accounts: np.ndarray        # (G,)
    latitude: np.ndarray
    sales_area: list[str]
    names: list[str]
    roles: dict[str, str]       # channel -> dim_channel.marketing_role

    @property
    def size(self) -> np.ndarray:
        return self.accounts / self.accounts.mean()

    def week_index(self, monday) -> int:
        return int(self.weeks.get_loc(pd.Timestamp(monday)))


def load(path: Path | None = None, through=None) -> Markets:
    con = duckdb.connect(str(path or WAREHOUSE), read_only=True)
    try:
        f = con.sql("select week_start, region_id, sum(won_deals)::double d from fct_funnel group by 1, 2").df()
        s = con.sql("select week_start, region_id, channel_id, spend::double s from fct_channel_weekly").df()
        r = con.sql("select region_id, region_name, target_accounts, latitude, sales_area "
                    "from dim_region order by region_id").df()
        roles = dict(con.sql("select channel_id, marketing_role from dim_channel").fetchall())
    finally:
        con.close()
    for df in (f, s):
        df["week_start"] = pd.to_datetime(df["week_start"])
        if through is not None:
            df.drop(df.index[df.week_start > pd.Timestamp(through)], inplace=True)
    weeks = pd.DatetimeIndex(sorted(f.week_start.unique()))
    regions = list(r.region_id)
    deals = f.pivot(index="week_start", columns="region_id", values="d").reindex(index=weeks, columns=regions)
    spend = {}
    for ch, g in s.groupby("channel_id"):
        spend[ch] = (g.pivot(index="week_start", columns="region_id", values="s")
                     .reindex(index=weeks, columns=regions).fillna(0.0).to_numpy())
    return Markets(weeks, regions, deals.fillna(0.0).to_numpy(), spend, r.target_accounts.to_numpy(float),
                   r.latitude.to_numpy(float), list(r.sales_area), list(r.region_name), roles)
