"""The rollout: the holdout estimator and rules, the committed plan and readout, and the
wall around the answer key. Main environment (rollout/plan.py and crosscheck.py need the
MMM environment and are only read as text here)."""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from rollout import holdout as H
from rollout.plan_md import plan_md

REPO = Path(__file__).resolve().parents[1]
ROLLOUT = REPO / "rollout"
PLAN = json.loads((ROLLOUT / "outputs" / "plan.json").read_text(encoding="utf-8"))
YEAR_END = REPO / "data" / f"cut_{PLAN['holdout']['readout_snapshot']}" / "data" / "warehouse.duckdb"
needs_year_end = pytest.mark.skipif(not YEAR_END.exists(), reason="run the yearend stage first")


def test_rollout_code_never_reads_the_answer_key():
    for p in sorted(ROLLOUT.glob("*.py")):
        text = p.read_text(encoding="utf-8").lower()
        assert "truth" not in text and "grading" not in text and "mmm.grade" not in text, p.name
        assert not re.search(r"^\s*(from|import)\s+sim\b", text, re.M), p.name
        assert "data/raw" not in text and "data\\raw" not in text, p.name


def test_committed_rollout_outputs_hold_no_answer_key():
    for p in (ROLLOUT / "outputs").glob("*.json"):
        assert "truth" not in p.read_text(encoding="utf-8").lower(), p.name


def test_lift_is_the_ratio_contrast():
    rng = np.random.default_rng(0)
    deals = rng.poisson(50, (120, 6)).astype(float)
    rollout = np.array([True, True, True, True, False, False])
    deals[100:, rollout] += 10  # a lift of 10 a week in each of 4 markets over the 20-week window
    pre, win = H.sums(deals, 100, 20, 17)
    r = pre[rollout].sum() / pre[~rollout].sum()
    assert H.lift(pre, win, rollout) == pytest.approx(win[rollout].sum() - r * win[~rollout].sum())
    assert pre.sum() == deals[100 - 17 - H.PRE_WEEKS:100 - 17].sum()
    assert 600 < H.lift(pre, win, rollout) < 1000


def test_rules_as_registered():
    assert H.decide(100, 10, 190, 150, True)["rule_1_rollout_works"]
    d = H.decide(50, -40, 190, 150, True)
    assert d["rule_3_not_clear"] and not d["rule_1_rollout_works"] and d["rule_2_against_forecast"] == "agrees with the forecast"
    assert H.decide(-200, -290, -110, 150, True)["rule_3_drop_is_clear"]
    assert H.decide(400, 310, 490, 150, True)["rule_2_against_forecast"] == "beats the forecast"


def test_holdout_is_the_springs_neither_cell():
    design = json.loads((REPO / "geotest" / "outputs" / "design.json").read_text(encoding="utf-8"))
    assert sorted(H.HOLDOUT) == sorted(design["cells"]["neither"])
    h = PLAN["holdout"]
    assert sorted(h["holdout"] + h["rollout_markets"]) == sorted(design["market_names"])
    assert h["pre_period"][1] < design["dates"]["test_start"]  # the spring test cannot leak into the ratio


def test_plan_file_matches_the_registration():
    plan = yaml.safe_load((REPO / "plans" / "2026_rollout.yaml").read_text(encoding="utf-8"))
    from rollout.results import plan_check
    assert plan_check(PLAN, plan)["matches"]
    from sim.plans import load
    p = load(REPO / "plans" / "2026_rollout.yaml")
    assert p.budget is None and p.test.id == H.TEST_ID and len(p.test.arms) == 1


def test_move_check_sees_every_move_and_its_dry_run_passes_and_fails():
    mult = PLAN["rollout"]["plan"]["multipliers"]
    markets = PLAN["holdout"]["rollout_markets"]
    on_plan = {c: {"rollout": 1.02, "holdout": 0.98, "markets": {}} for c in mult}
    assert H.plan_check(on_plan, mult, markets)["passes"]
    assert not H.plan_check(on_plan, mult, markets, ran=False)["passes"]
    for c, m in mult.items():  # each move alone left undone fails the check
        stuck = {k: dict(v) for k, v in on_plan.items()}
        stuck[c]["rollout"] = 1.0 / m
        assert not H.plan_check(stuck, mult, markets)["channels"][c]["move_shows"], c
        leak = {k: dict(v) for k, v in on_plan.items()}
        leak[c]["holdout"] = m
        assert not H.plan_check(leak, mult, markets)["channels"][c]["holdout_stays"], c
    pc = PLAN["holdout"]["plan_check"]
    assert pc["if_the_plan_ran"]["passes"] and not pc["if_it_had_not_run"]["passes"]
    assert not any(v["move_shows"] for v in pc["if_it_had_not_run"]["channels"].values())


def test_committed_plan_md_matches_plan_json():
    assert (ROLLOUT / "PLAN.md").read_text(encoding="utf-8") == plan_md(PLAN)


def test_registered_power_is_what_the_docs_say():
    h = PLAN["holdout"]
    sd = h["placebo"]["sd_used"]
    assert sd == max(max(h["placebo"]["rms_by_start_year"].values()), h["placebo"]["count_noise_floor"])
    assert h["smallest_detectable_lift"] == pytest.approx(H.E.MDE_Z * sd)
    assert f"{h['power_at_forecast']:.0%} power" in (ROLLOUT / "PLAN.md").read_text(encoding="utf-8")


@needs_year_end
def test_committed_readout_matches_a_fresh_one():
    from geotest.data import load
    from rollout.results import RESULTS_JSON, RESULTS_MD, results, results_md
    plan_file = yaml.safe_load((REPO / "plans" / "2026_rollout.yaml").read_text(encoding="utf-8"))
    fresh = json.loads(json.dumps(results(PLAN, load(YEAR_END), plan_file, YEAR_END)))
    committed = json.loads(RESULTS_JSON.read_text(encoding="utf-8"))
    assert fresh == committed
    assert RESULTS_MD.read_text(encoding="utf-8") == results_md(committed)


@needs_year_end
def test_year_end_cut_holds_the_registered_markets():
    import duckdb
    con = duckdb.connect(str(YEAR_END), read_only=True)
    try:
        groups = dict(con.sql("select region_id, rollout_group from dim_region").fetchall())
        weeks = con.execute("select min(week_start), max(week_start) from fct_funnel").fetchone()
    finally:
        con.close()
    assert sorted(r for r, g in groups.items() if g == "holdout") == sorted(H.HOLDOUT)
    assert str(pd.Timestamp(weeks[1]).date()) == PLAN["dates"]["last_week"]
