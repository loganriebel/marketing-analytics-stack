"""The 2026 extension: plans drive spend, earlier weeks never change, and the
2023 to 2025 world stays exactly as it was.

Runs on a development seed, so no test reads the graded world's 2026 outcomes."""

from datetime import date

import pandas as pd
import pytest

from sim import simulate
from sim.extend import simulate_through
from sim.plans import load

SEED = 7
WEEK_COL = {"ads_google_weekly": "week_start_date", "ads_meta_weekly": "date_start",
            "ads_linkedin_weekly": "start_date", "ads_display_weekly": "week", "ctv_weekly": "week_start",
            "partners_weekly": "week_start", "email_weekly": "week_start",
            "fleet_activity_index_weekly": "week_start", "webinar_events": "event_date",
            "sales_capacity_monthly": "month_start"}

TEST_PLAN = """
name: test plan
approved: 2026-01-26
test:
  id: MT
  start: 2026-02-02
  end: 2026-04-20
  arms:
    - id: up
      markets: [CHI, MSP, CLE, DSM, MSN]
      moves:
        youtube: {add_per_week_per_size: 2000}
    - id: dark
      markets: [CMH, CVG, DAY, CID, RFD]
      moves:
        linkedin: {multiplier: 0}
        affiliates: {multiplier: 0}
"""
LATER_PLAN = """
name: later plan
approved: 2026-05-28
national:
  start: 2026-06-01
  end: 2026-12-28
  moves:
    youtube: {multiplier: 2.0}
    display: {multiplier: 0.5}
"""


def _csv(df: pd.DataFrame) -> pd.DataFrame:
    """Tables as written: text, so dtype differences from concatenation do not matter."""
    return df.astype(str).reset_index(drop=True)


@pytest.fixture(scope="module")
def plans(tmp_path_factory):
    d = tmp_path_factory.mktemp("plans")
    (d / "test.yaml").write_text(TEST_PLAN, encoding="utf-8")
    (d / "later.yaml").write_text(LATER_PLAN, encoding="utf-8")
    return d / "test.yaml", d / "later.yaml"


@pytest.fixture(scope="module")
def runs(plans):
    test, later = plans
    return {
        "base": simulate(SEED),
        "may": simulate_through(SEED, date(2026, 5, 31), [test]),
        "year": simulate_through(SEED, date(2027, 1, 3), [test, later]),
    }


def test_base_years_unchanged(runs):
    base, may = runs["base"].tables, runs["may"].tables
    assert runs["may"].truth == runs["base"].truth
    for t, c in WEEK_COL.items():
        a, z = _csv(may[t]), _csv(base[t])
        assert a[a[c] <= z[c].max()].reset_index(drop=True).equals(z), t
    keys = ["lead_id", "created_date", "region_code", "utm_source", "utm_medium", "utm_campaign"]
    z, a = _csv(base["crm_leads"]), _csv(may["crm_leads"])
    assert a[keys].iloc[: len(z)].equals(z[keys])
    filled = z.mql_date != ""
    assert (a.mql_date.iloc[: len(z)][filled] == z.mql_date[filled]).all()
    zo, ao = _csv(base["crm_opportunities"]), _csv(may["crm_opportunities"])
    k = ["opportunity_id", "lead_id", "created_date", "amount"]
    assert ao[k].iloc[: len(zo)].equals(zo[k])
    closed = zo.stage != "Open"
    assert (ao[["stage", "close_date"]].iloc[: len(zo)][closed].values == zo[["stage", "close_date"]][closed].values).all()


def test_later_plan_never_changes_earlier_weeks(runs):
    may, year = runs["may"].tables, runs["year"].tables
    for t, c in WEEK_COL.items():
        a, b = _csv(may[t]), _csv(year[t])
        assert b[b[c] <= a[c].max()].reset_index(drop=True).equals(a), t
    a, b = _csv(may["crm_leads"]), _csv(year["crm_leads"])
    assert b.lead_id.iloc[: len(a)].equals(a.lead_id)
    assert b.created_date.iloc[: len(a)].equals(a.created_date)


def test_plans_drive_spend(runs):
    t = runs["may"].tables
    li = t["ads_linkedin_weekly"]
    test_weeks = li[(li.start_date >= "2026-02-02") & (li.start_date <= "2026-04-20")]
    assert not set(test_weeks.region_code) & {"CMH", "CVG", "DAY", "CID", "RFD"}  # dark in the arm
    assert set(test_weeks.region_code) >= {"CHI", "MSP"}
    g = t["ads_google_weekly"]
    yt = g[g.campaign_name == "FH_YouTube_Prospecting"].assign(spend=lambda d: d.cost_micros / 1e6)
    up = yt[yt.geo_target_region.isin(["CHI", "MSP", "CLE", "DSM", "MSN"])]
    during = up[(up.week_start_date >= "2026-02-02") & (up.week_start_date <= "2026-04-20")].spend.sum()
    before = up[(up.week_start_date >= "2025-02-03") & (up.week_start_date <= "2025-04-21")].spend.sum()
    assert during > before + 100_000
    mt = t["market_tests"]
    assert set(mt.arm_id) == {"up", "dark"} and len(mt) == 5 + 10
    assert runs["may"].truth_2026["cells"]["up"]["spend_change_by_channel"]["youtube"] > 0


def test_same_inputs_same_bytes(plans):
    test, _ = plans
    a = simulate_through(SEED, date(2026, 3, 1), [test])
    b = simulate_through(SEED, date(2026, 3, 1), [test])
    for name in a.tables:
        assert a.tables[name].equals(b.tables[name]), name
    assert a.truth_2026 == b.truth_2026


def test_plan_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text(TEST_PLAN.replace("youtube: {add_per_week_per_size: 2000}", "paid_search_brand: {multiplier: 2}"),
                   encoding="utf-8")
    with pytest.raises(ValueError, match="not a planned channel"):
        load(bad)
    bad.write_text(TEST_PLAN.replace("2026-02-02", "2026-02-03"), encoding="utf-8")
    with pytest.raises(ValueError, match="Monday"):
        load(bad)
