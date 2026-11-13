"""The market test's estimator, its committed design, and its read boundaries."""

import json
import re
from pathlib import Path

import numpy as np

from geotest import estimator as E
from sim.plans import load

REPO = Path(__file__).resolve().parents[1]
DESIGN = REPO / "geotest" / "outputs" / "design.json"


def _panel(seed=0, T=80, G=12):
    rng = np.random.default_rng(seed)
    size = np.exp(rng.normal(0, 0.5, G))
    season = 1 + 0.2 * np.sin(np.arange(T) / 52 * 2 * np.pi)
    return 10.0 * size[None, :] * season[:, None], size


def test_recovers_each_arm_and_removes_the_other():
    mu, size = _panel()
    G = mu.shape[1]
    arms = np.zeros((2, G), bool)
    arms[0, ::2] = True          # grow
    arms[1, :6] = True           # cut, crossing the grow arm
    doses = np.stack([size * arms[0], 2.0 * size * arms[1]])
    start, n_pre, n_win = 60, 52, 16
    y = mu.copy()
    theta = np.array([0.4, -0.25])  # deals per dose unit over the window
    effect = (theta[:, None] * doses).sum(0) / n_win
    y[start:start + n_win] += effect[None, :]
    pre, win = E.window_sums(y, start, n_pre, n_win)
    lift = E.lifts(pre, win, arms, doses)
    np.testing.assert_allclose(lift, theta * doses.sum(1), rtol=1e-9)
    # without the joint solve, each simple contrast mixes in the other arm
    naive = E.contrasts(pre, win, arms)
    assert not np.allclose(naive, lift)


def test_placebo_is_zero_without_noise():
    mu, size = _panel(1)
    arms = np.zeros((2, mu.shape[1]), bool)
    arms[0, :6], arms[1, 3:9] = True, True
    doses = np.stack([size * arms[0], size * arms[1]])
    p = E.placebo(mu, arms, doses, np.arange(52, 64), 52, 16)
    assert np.abs(p).max() < 1e-8


def test_committed_plan_matches_design():
    d = json.loads(DESIGN.read_text(encoding="utf-8"))
    plan = load(REPO / "plans" / "2026_test.yaml")
    arms = {a.id: a for a in plan.test.arms}
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    grow = arms[f"{g['channel']}_up"]
    assert grow.markets == g["markets"]
    assert grow.moves[0].add_per_week_per_size == g["value"]
    assert arms["cuts_dark"].markets == c["markets"]
    assert sorted(m.channel for m in arms["cuts_dark"].moves) == sorted(c["channels"])
    assert all(m.multiplier == 0.0 for m in arms["cuts_dark"].moves)
    assert str(plan.test.start) == d["dates"]["test_start"]
    assert str(plan.approved) == d["approved"]
    assert d["forecast"]["grow"]["power"] >= 0.8


def test_preregistration_matches_design():
    from geotest.prereg import prereg_md
    d = json.loads(DESIGN.read_text(encoding="utf-8"))
    committed = (REPO / "geotest" / "PREREGISTRATION.md").read_text(encoding="utf-8")
    assert committed == prereg_md(d, d["market_names"])


def test_geotest_never_reads_the_answer_key():
    for p in (REPO / "geotest").glob("*.py"):
        text = p.read_text(encoding="utf-8")
        assert "truth" not in text.lower(), p.name
        assert not re.search(r"^\s*(from|import)\s+sim\b", text, re.M), p.name
        assert "data/raw" not in text, p.name
