"""The rollout plan: the exact budget solver, the optimum check, and the committed plan file.

Runs in the MMM environment (mmm.optimize imports the model code)."""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pymc_marketing")

from mmm.optimize import GRID, optimality, solve_exact  # noqa: E402
from scipy import interpolate  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "rollout" / "outputs" / "plan.json"


def _curves(scales: dict) -> dict:
    """Concave curves a * (1 - exp(-b m)) - their value at m = 1, splined on the optimizer's grid."""
    out = {}
    for c, (a, b) in scales.items():
        y = a * (1 - np.exp(-b * GRID)) - a * (1 - np.exp(-b))
        out[c] = interpolate.CubicSpline(GRID, y)
    return out


def test_exact_solver_matches_brute_force():
    levers = ["a", "b", "c"]
    curves = _curves({"a": (300, 1.0), "b": (200, 2.5), "c": (80, 0.6)})
    spend = np.array([1000.0, 500.0, 800.0])
    m = solve_exact(curves, levers, spend)
    assert m @ spend == pytest.approx(spend.sum(), rel=1e-9)
    assert np.all((m >= 0.5 - 1e-12) & (m <= 1.5 + 1e-12))
    best = -np.inf
    for x in np.linspace(0.5, 1.5, 201):
        for y in np.linspace(0.5, 1.5, 201):
            z = (spend.sum() - x * spend[0] - y * spend[1]) / spend[2]
            if 0.5 <= z <= 1.5:
                best = max(best, sum(float(curves[c](v)) for c, v in zip(levers, (x, y, z))))
    got = sum(float(curves[c](v)) for c, v in zip(levers, m))
    assert got >= best - 1e-3
    assert optimality(curves, levers, spend, m)["optimum"]


def test_optimality_flags_a_plan_that_is_not_the_optimum():
    levers = ["a", "b"]
    curves = _curves({"a": (300, 1.0), "b": (300, 1.0)})
    spend = np.array([1000.0, 1000.0])
    assert optimality(curves, levers, spend, [1.0, 1.0])["optimum"]
    lopsided = optimality(curves, levers, spend, [1.2, 0.8])
    assert not lopsided["optimum"]
    assert not optimality(curves, levers, spend, [1.2, 1.0])["budget_holds"]


@pytest.mark.skipif(not PLAN.exists(), reason="python -m rollout.plan writes the plan")
def test_committed_plan_is_the_checked_optimum():
    d = json.loads(PLAN.read_text(encoding="utf-8"))
    c = d["refit_plan_check"]
    assert c["rebuilt_deal_change_mean"] == pytest.approx(c["committed_deal_change_mean"], rel=1e-6)
    assert d["rollout"]["solved"]["check"]["optimum"]
    plan = d["rollout"]["plan"]
    lo, hi = d["bounds"]
    assert all(lo <= m <= hi for m in plan["multipliers"].values())
    assert abs(plan["spend_change"]) < 1e-3 * d["rollout"]["lever_spend_in_proxy_weeks"]
