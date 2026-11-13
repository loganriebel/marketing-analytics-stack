"""The market test readout: its rules, its validity checks, its MMM rows, and its committed files.

Runs in either environment. The reproduction test needs the readout's data cut
(python -m sim --through 2026-05-31 --plan plans/2026_test.yaml --out data/cut_2026-05-31,
then dbt build from that folder) and skips without it.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from geotest import readout as R
from geotest.data import Markets, load

REPO = Path(__file__).resolve().parents[1]
DESIGN = json.loads((REPO / "geotest" / "outputs" / "design.json").read_text(encoding="utf-8"))
COMMITTED = json.loads((REPO / "geotest" / "outputs" / "readout.json").read_text(encoding="utf-8"))
CROSS_PATH = REPO / "geotest" / "outputs" / "synthetic_control.json"


def _arm(lift, sd, forecast):
    return {"lift": lift, "low": lift - 1.645 * sd, "high": lift + 1.645 * sd, "forecast": forecast}


def test_decide_follows_the_registered_rules():
    agree = R.decide(_arm(130, 47, 119), _arm(-37, 54, -83), True)
    assert agree["rule_1_grow_works"] and agree["rule_2_grow"] == "agrees with the forecast"
    assert agree["rule_2_cut"] == "agrees with the forecast" and not agree["cut_drop_is_clear"]
    assert not agree["rule_4_keep_cut_channels_at_todays_spend"] and not agree["rule_4_do_not_grow"]

    beats = R.decide(_arm(300, 47, 119), _arm(-300, 54, -83), True)
    assert beats["rule_2_grow"] == "beats the forecast"
    assert beats["rule_2_cut"] == "costs more than modeled" and beats["cut_drop_is_clear"]
    assert beats["rule_4_keep_cut_channels_at_todays_spend"]

    short = R.decide(_arm(20, 47, 119), _arm(150, 54, -83), False)
    assert not short["rule_1_grow_works"] and short["rule_4_do_not_grow"]
    assert short["rule_2_grow"] == "falls short of the forecast"
    assert short["rule_2_cut"] == "costs less than modeled" and not short["valid"]


def _markets(cut_markets, keep, start="2026-02-02", seed=0):
    """A small panel with always-on search spend that follows market size, cut by `keep`
    in `cut_markets` from `start`."""
    rng = np.random.default_rng(seed)
    weeks = pd.date_range("2023-01-02", "2026-05-25", freq="W-MON")
    regions = [f"M{i:02d}" for i in range(12)]
    size = np.exp(rng.normal(0, 0.3, len(regions)))
    base = 1000.0 * size[None, :] * np.exp(rng.normal(0, 0.05, (len(weeks), len(regions))))
    x = base.copy()
    t = weeks >= pd.Timestamp(start)
    x[np.ix_(t & (weeks <= pd.Timestamp("2026-04-20")), np.isin(regions, cut_markets))] *= keep
    deals = np.full((len(weeks), len(regions)), 10.0)
    accounts = size * 1000
    return Markets(weeks, regions, deals, {"paid_search_nonbrand": x, "youtube": base}, accounts,
                   np.zeros(len(regions)), ["a"] * len(regions), regions, {})


def test_spend_check_recovers_the_planned_cut():
    cut = ["M00", "M02", "M04", "M06", "M08", "M10"]
    m = _markets(cut, 0.39)
    t = np.isin(m.regions, cut)
    s = m.week_index("2026-02-02")
    obs, cf = R.spend_did(m.spend["paid_search_nonbrand"], t, s, 52, 12)
    plan = obs * (1 - 1 / 0.39)
    assert abs((obs - cf) / plan - 1) < 0.05


def test_step_check_sees_the_cut_and_names_drift():
    cut = ["M00", "M02", "M04", "M06", "M08", "M10"]
    d = {"arms": {"cut": {"channels": ["paid_search_nonbrand"], "value": 0.39, "markets": cut},
                  "grow": {"channel": "youtube", "value": 2500.0, "markets": []}}}
    m = _markets(cut + ["M11"], 0.39)          # M11 is outside the arm but gets cut too
    arms = np.stack([np.zeros(12, bool), np.isin(m.regions, cut)])
    res = R.step_check(m, d, arms, m.week_index("2026-02-02"), 12)
    seen = {r["market"]: r["cut_seen"] for r in res["markets"]}
    assert all(seen[c] for c in cut) and seen["M11"]
    assert not any(seen[c] for c in m.regions if c not in cut + ["M11"])
    assert res["weeks_before"] == 4 and res["weeks_after"] == 9   # Jan 5 to Jan 26; Feb 2 to Mar 30
    assert not res["all_in_cell"]


def test_plan_check_matches_the_committed_plan():
    plan = yaml.safe_load((REPO / "plans" / "2026_test.yaml").read_text(encoding="utf-8"))
    assert R.plan_check(DESIGN, plan)["matches"]
    plan["test"]["arms"][1]["markets"] = plan["test"]["arms"][1]["markets"][:-1] + ["DLH"]
    assert not R.plan_check(DESIGN, plan)["matches"]


def test_committed_lift_rows_are_in_mmm_units():
    rows = {r["arm"]: r for r in COMMITTED["mmm_lift_tests"]["rows"]}
    f = DESIGN["forecast"]
    for k in ("grow", "cut"):
        r, a = rows[k], COMMITTED["arms"][k]
        assert np.isclose(r["window_share"], f[k]["lift_mean"] / f[k]["lift_total_mean"])
        per = r["test_weeks"] * r["window_share"] * r["size_units"]
        assert np.isclose(r["delta_y"] * per, a["lift"]) and np.isclose(r["sigma"] * per, a["sd"])
    assert rows["grow"]["delta_x"] == DESIGN["arms"]["grow"]["value"]
    assert np.isclose(rows["cut"]["delta_x"] / rows["cut"]["x"], DESIGN["arms"]["cut"]["value"] - 1)
    assert rows["grow"]["channel"] == DESIGN["arms"]["grow"]["channel"]
    assert [rows["cut"]["channel"]] == DESIGN["arms"]["cut"]["channels"]


def test_committed_decision_and_report_follow_from_the_numbers():
    a = COMMITTED["arms"]

    def arm(k):
        return {"lift": a[k]["lift"], "low": a[k]["interval_90"][0], "high": a[k]["interval_90"][1],
                "forecast": DESIGN["forecast"][k]["lift_mean"]}

    assert R.decide(arm("grow"), arm("cut"), COMMITTED["validity"]["valid"]) == COMMITTED["decision"]
    for k in ("grow", "cut"):
        lo, hi = a[k]["interval_90"]
        assert np.isclose(hi - a[k]["lift"], 1.6448536269514722 * DESIGN["placebo"]["sd_used"][R.ARM_KEYS.index(k)])
        assert np.isclose(a[k]["lift"] - lo, hi - a[k]["lift"])
    cross = json.loads(CROSS_PATH.read_text(encoding="utf-8")) if CROSS_PATH.exists() else None
    committed_md = (REPO / "geotest" / "READOUT.md").read_text(encoding="utf-8")
    assert committed_md == R.readout_md(COMMITTED, DESIGN, cross)
    assert "—" not in committed_md


def _cut_markets():
    path = R.cut_warehouse(DESIGN)
    if not path.exists():
        pytest.skip("readout data cut not built")
    return load(path, through=DESIGN["dates"]["readout_snapshot"])


def test_readout_reproduces_from_the_data_cut():
    m = _cut_markets()
    plan = yaml.safe_load(R.PLAN_PATH.read_text(encoding="utf-8"))
    again = json.loads(json.dumps(R.readout(DESIGN, m, plan)))
    assert again == COMMITTED


def test_readout_refuses_weeks_past_the_snapshot():
    m = _cut_markets()
    nxt = m.weeks[-1] + pd.Timedelta(weeks=1)
    later = Markets(m.weeks.append(pd.DatetimeIndex([nxt])), m.regions, np.vstack([m.deals, m.deals[-1:]]),
                    {k: np.vstack([v, v[-1:]]) for k, v in m.spend.items()}, m.accounts, m.latitude,
                    m.sales_area, m.names, m.roles)
    with pytest.raises(ValueError, match="past the readout snapshot"):
        R.readout(DESIGN, later, yaml.safe_load(R.PLAN_PATH.read_text(encoding="utf-8")))
