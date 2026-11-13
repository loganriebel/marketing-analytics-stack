"""Design the 2026 market test from 2023 to 2025 data, and pre-register it.

    .venv-mmm\\Scripts\\python -m geotest.design

Two questions decide the 2026 budget. Where should the next dollar go (the MMM says:
the channel with the lowest cost per extra deal)? And is the money poured into the
biggest always-on channel, non-brand search, still working? They rest on different
evidence, so the test checks both at once. Two arms cross the 20 markets (a 2x2
factorial):

* grow arm: more of the best next-dollar channel, a flat amount per week per unit of
  market size, so the model sees spend levels it has never seen;
* cut arm: the biggest always-on channel goes back to its first-year budget level
  (first-year spend over last-year spend, from the marts).

Each arm is measured on all 20 markets (its markets against the rest), so neither
arm halves the other's power. Markets sit in 5 blocks of 4 similar-size markets, and
each block gets one market of each cell. Among many random assignments, the one whose
worst placebo error (over both arms, on 2024 windows and on 2025 windows) is smallest
is kept. Picking on 2024 alone overfit: the pick's error doubled on 2025 windows.

Power comes from placebo tests: the pre-registered estimator run on 2023 to 2025
windows where nothing was tested. The smallest detectable lift (80% power, one-sided
5%) is 2.49 placebo standard deviations, never below the count-noise floor. The grow
arm's size is the smallest step whose MMM forecast clears that bar.

Reads the December 2025 marts and the MMM's outputs and saved posterior. Writes
geotest/outputs/design.json, geotest/PREREGISTRATION.md and plans/2026_test.yaml.
"""

from __future__ import annotations

import itertools
import json
import os
from datetime import date, timedelta
from pathlib import Path

os.environ.setdefault("PYTENSOR_FLAGS", "cxx=")

import numpy as np  # noqa: E402
import yaml  # noqa: E402
from scipy import stats  # noqa: E402

from . import estimator as E  # noqa: E402
from .data import REPO, Markets, load  # noqa: E402
from .prereg import prereg_md  # noqa: E402

OUT_DIR = REPO / "geotest" / "outputs"
PLAN_PATH = REPO / "plans" / "2026_test.yaml"
PREREG_PATH = REPO / "geotest" / "PREREGISTRATION.md"
MMM_OUT = REPO / "mmm" / "outputs"

TEST_ID = "MT2026Q1"
APPROVED = date(2026, 1, 26)
TEST_START = date(2026, 2, 2)         # ISO 2026-W06, after the January slow weeks begin to lift
TEST_WEEKS = 12
TAIL_WEEKS = 4                         # deals close one to four weeks after the lead
PRE_WEEKS = 52
PROXY_START = date(2025, 2, 3)         # last year's same ISO week: the forecast's stand-in
DURATIONS = (8, 12, 16)
CANDIDATES = 4000
DESIGN_SEED = 20260126
MAX_CROSS = 0.15                       # cross-arm dose imbalance allowed, as a share of the arm's own
ADD_GRID = np.arange(500, 8001, 250)   # grow-arm step, $ per week per unit of market size
TARGET_POWER = 0.80


ALWAYS_ON_SHARE = 0.95                 # a channel bought in at least this share of market-weeks never pauses


def _mmm_choices(m: Markets) -> dict:
    """The grow channel from the MMM (lowest cost per extra deal), and the cut channel
    from the marts: the always-on lever with the most spend, taken back to its first
    year's budget level."""
    ch = json.loads((MMM_OUT / "channels.json").read_text(encoding="utf-8"))["channels"]
    opt = json.loads((MMM_OUT / "optimizer.json").read_text(encoding="utf-8"))

    def mcpa(c):
        v = ch[c]
        return (v.get("marginal_cpa_total") or v["marginal_cpa"])["median"]

    levers = opt["levers"]
    grow = min(levers, key=mcpa)
    always_on = [c for c in levers if (m.spend[c] > 0).mean() >= ALWAYS_ON_SHARE]
    cut = max(always_on, key=lambda c: m.spend[c].sum())
    years = sorted(set(m.weeks.year))
    by_year = {int(y): float(m.spend[cut][m.weeks.year == y].sum()) for y in years}
    weeks = {int(y): int((m.weeks.year == y).sum()) for y in years}
    rate = {y: by_year[y] / weeks[y] for y in years}  # weekly pace, so 53- and 51-week years compare
    value = round(rate[years[0]] / rate[years[-1]], 2)
    return {"grow": grow, "cuts": [cut], "cut_value": value, "cut_spend_by_year": by_year,
            "always_on": always_on, "mcpa": {c: mcpa(c) for c in levers},
            "plan_multipliers": {r["channel"]: r["multiplier"] for r in opt["plan"]}}


def _blocks(m: Markets) -> list[list[int]]:
    recent = m.deals[-52:].sum(0)
    order = list(np.argsort(-recent, kind="stable"))
    return [order[i:i + 4] for i in range(0, len(order), 4)]


def _assignments(blocks, n_markets: int, rng) -> np.ndarray:
    """(CANDIDATES, G) cells: 0 grow only, 1 cut only, 2 both, 3 neither."""
    perms = list(itertools.permutations(range(4)))
    out = np.zeros((CANDIDATES, n_markets), int)
    for i in range(CANDIDATES):
        for b in blocks:
            for g, c in zip(b, perms[rng.integers(len(perms))]):
                out[i, g] = c
    return out


def _arms(cells: np.ndarray) -> np.ndarray:
    return np.stack([np.isin(cells, [0, 2]), np.isin(cells, [1, 2])])


def _doses(m: Markets, arms: np.ndarray, cuts: list[str], proxy: int, keep: float) -> np.ndarray:
    """Planned dollars each market's move adds (grow) or removes (cut), up to scale:
    grow is a flat amount per unit of size; cut removes (1 - keep) of last year's
    same-week spend."""
    grow = m.size * arms[0]
    cut = sum(m.spend[c][proxy:proxy + TEST_WEEKS].sum(0) for c in cuts) * (1 - keep) * arms[1]
    return np.stack([grow, cut])


def _rms(x: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(x ** 2, axis=0))


def _power(mean: float, sd: float) -> float:
    return float(stats.norm.cdf(abs(mean) / sd - E.Z_90))


def design() -> dict:
    m = load()
    mmm = _mmm_choices(m)
    keep = mmm["cut_value"]
    T = len(m.weeks)
    proxy = m.week_index(PROXY_START)
    n_win = TEST_WEEKS + TAIL_WEEKS
    starts = np.arange(PRE_WEEKS, T - n_win + 1)
    week_year = np.array([m.weeks[s].year for s in starts])
    sel, val = week_year == 2024, week_year == 2025

    blocks = _blocks(m)
    rng = np.random.default_rng(DESIGN_SEED)
    cands = _assignments(blocks, len(m.regions), rng)
    pre_last = m.deals[T - PRE_WEEKS:].sum(0)
    best, kept = None, 0
    for cells in cands:
        arms = _arms(cells)
        doses = _doses(m, arms, mmm["cuts"], proxy, keep)
        A = E.dose_matrix(pre_last, arms, doses)
        if abs(A[0, 1] / A[1, 1]) > MAX_CROSS or abs(A[1, 0] / A[0, 0]) > MAX_CROSS:
            continue
        kept += 1
        p = E.placebo(m.deals, arms, doses, starts, PRE_WEEKS, n_win)
        score = max(_rms(p[sel]).max(), _rms(p[val]).max())
        if best is None or score < best[0]:
            best = (score, cells)
    cells = best[1]
    arms = _arms(cells)
    doses = _doses(m, arms, mmm["cuts"], proxy, keep)
    p_all = E.placebo(m.deals, arms, doses, starts, PRE_WEEKS, n_win)
    floor = E.count_noise_floor(m.deals, arms, n_win)
    rms_sel, rms_val, rms_all = _rms(p_all[sel]), _rms(p_all[val]), _rms(p_all)
    sd = np.maximum.reduce([rms_sel, rms_val, floor])
    mde = E.MDE_Z * sd

    # The MMM's forecast for each arm, and the grow step that clears the bar.
    from .forecast import Forecaster
    fc = Forecaster()
    cut = fc.arm(m, arms[1], {c: ("mult", keep) for c in mmm["cuts"]}, proxy, TEST_WEEKS, n_win)
    grid = []
    for a in ADD_GRID:
        f = fc.arm(m, arms[0], {mmm["grow"]: ("add", float(a))}, proxy, TEST_WEEKS, n_win)
        grid.append({"add_per_week_per_size": float(a), "spend_change": f["spend_change"],
                     "lift_mean": float(f["in_window"].mean()),
                     "lift_hdi_90": _hdi(f["in_window"]),
                     "power": _power(f["in_window"].mean(), sd[0]),
                     "assurance": float(np.mean(stats.norm.cdf(f["in_window"] / sd[0] - E.Z_90))),
                     "_draws": f})
    ok = [g for g in grid if g["power"] >= TARGET_POWER]
    pick = ok[0] if ok else max(grid, key=lambda g: g["power"])
    add = pick["add_per_week_per_size"]
    grow = pick["_draws"]

    # Duration: the same move for 8, 12 or 16 weeks, each with its own placebo bar.
    durations = []
    for w in DURATIONS:
        nw = w + TAIL_WEEKS
        st = np.arange(PRE_WEEKS, T - nw + 1)
        yr = np.array([m.weeks[s].year for s in st])
        pz = E.placebo(m.deals, arms, doses, st, PRE_WEEKS, nw)
        sdz = np.maximum.reduce([_rms(pz[yr == 2024]), _rms(pz[yr == 2025]), E.count_noise_floor(m.deals, arms, nw)])
        fg = fc.arm(m, arms[0], {mmm["grow"]: ("add", add)}, proxy, w, nw)
        fcut = fc.arm(m, arms[1], {c: ("mult", keep) for c in mmm["cuts"]}, proxy, w, nw)
        durations.append({"test_weeks": w, "window_weeks": nw,
                          "grow": {"mde": float(E.MDE_Z * sdz[0]), "lift_mean": float(fg["in_window"].mean()),
                                   "power": _power(fg["in_window"].mean(), sdz[0]), "spend_change": fg["spend_change"]},
                          "cut": {"mde": float(E.MDE_Z * sdz[1]), "lift_mean": float(fcut["in_window"].mean()),
                                  "power": _power(fcut["in_window"].mean(), sdz[1]),
                                  "spend_change": fcut["spend_change"]}})

    cut_mean = float(cut["in_window"].mean())
    cut_multiple_80 = float(mde[1] / abs(cut_mean))
    win_deals = m.deals[proxy:proxy + n_win]
    cell_names = {0: "grow only", 1: "search only", 2: "grow and search", 3: "neither"}
    test_end = TEST_START + timedelta(weeks=TEST_WEEKS - 1)
    window_end = TEST_START + timedelta(weeks=n_win) - timedelta(days=1)
    fp_rate = float(np.mean(p_all / sd > E.Z_90, axis=0).max())
    out = {
        "test_id": TEST_ID,
        "approved": str(APPROVED),
        "data_cut": {"warehouse": "data/warehouse.duckdb", "first_week": str(m.weeks[0].date()),
                     "last_week": str(m.weeks[-1].date()), "by_year": _by_year(m)},
        "dates": {"test_start": str(TEST_START), "test_last_week": str(test_end),
                  "test_end": str(test_end + timedelta(days=6)), "window_start": str(TEST_START),
                  "window_end": str(window_end), "readout_snapshot": str(window_end + timedelta(days=7)),
                  "pre_period_weeks": PRE_WEEKS, "test_weeks": TEST_WEEKS, "tail_weeks": TAIL_WEEKS,
                  "window_weeks": n_win, "forecast_proxy_start": str(PROXY_START)},
        "mmm": {"source": "mmm/outputs (holdout fit, 2023-01-02 to 2025-12-22)", **mmm},
        "arms": {
            "grow": {"channel": mmm["grow"], "move": "add_per_week_per_size", "value": add,
                     "markets": [m.regions[g] for g in np.where(arms[0])[0]]},
            "cut": {"channels": mmm["cuts"], "move": "multiplier", "value": keep,
                    "basis": "the channel's first-year weekly pace over its last-year weekly pace",
                    "markets": [m.regions[g] for g in np.where(arms[1])[0]]},
        },
        "cells": {cell_names[c]: [m.regions[g] for g in np.where(cells == c)[0]] for c in range(4)},
        "market_names": dict(zip(m.regions, m.names)),
        "blocks": [[m.regions[g] for g in b] for b in blocks],
        "assignment": {"candidates": CANDIDATES, "kept_after_balance": kept, "seed": DESIGN_SEED,
                       "rule": "smallest placebo RMS, worst of the two arms and the two years (2024 and 2025 windows)",
                       "max_cross": MAX_CROSS},
        "placebo": {
            "windows": int(len(starts)), "windows_2024": int(sel.sum()), "windows_2025": int(val.sum()),
            "rms_2024": rms_sel.tolist(), "rms_2025": rms_val.tolist(), "rms_all": rms_all.tolist(),
            "mean_all": p_all.mean(0).tolist(), "count_noise_floor": floor.tolist(),
            "sd_used": sd.tolist(), "false_positive_rate_max": fp_rate,
            "arms": ["grow", "cut"],
        },
        "mde": {"grow": float(mde[0]), "cut": float(mde[1]), "z": E.MDE_Z,
                "rule": "2.49 x the largest of the 2024 placebo RMS, the 2025 placebo RMS and the count-noise floor"},
        "window_deals_last_year": {"grow_markets": float(win_deals[:, arms[0]].sum()),
                                   "cut_markets": float(win_deals[:, arms[1]].sum()),
                                   "all_markets": float(win_deals.sum())},
        "forecast": {
            "grow": {"lift_mean": float(grow["in_window"].mean()), "lift_hdi_90": _hdi(grow["in_window"]),
                     "lift_total_mean": float(grow["total"].mean()), "spend_change": grow["spend_change"],
                     "power": pick["power"], "assurance": pick["assurance"],
                     "cost_per_extra_deal": grow["spend_change"] / float(grow["in_window"].mean())},
            "cut": {"lift_mean": cut_mean, "lift_hdi_90": _hdi(cut["in_window"]),
                    "lift_total_mean": float(cut["total"].mean()), "spend_change": cut["spend_change"],
                    "power": _power(cut_mean, sd[1]),
                    "multiple_of_forecast_for_80pct_power": cut_multiple_80,
                    "by_channel": cut["by_channel"]},
            "grid_step": float(ADD_GRID[1] - ADD_GRID[0]),
            "grid": [{k: v for k, v in g.items() if k != "_draws"} for g in grid],
        },
        "durations": durations,
    }
    return out


def _by_year(m: Markets) -> dict:
    """Won deals and paid spend (all 9 paid channels) per year, weeks by their Monday."""
    out = {}
    for y in sorted(set(m.weeks.year)):
        t = m.weeks.year == y
        deals = float(m.deals[t].sum())
        spend = float(sum(x[t].sum() for x in m.spend.values()))
        role_spend = {}
        for ch, x in m.spend.items():
            role_spend[m.roles.get(ch, "other")] = role_spend.get(m.roles.get(ch, "other"), 0.0) + float(x[t].sum())
        perf, brand = role_spend.get("performance", 0.0), role_spend.get("brand", 0.0)
        out[str(y)] = {"weeks": int(t.sum()), "won_deals": deals, "paid_spend": spend,
                       "cost_per_deal": spend / deals, "spend_by_role": role_spend,
                       "performance_share": perf / (perf + brand)}
    return out


def _hdi(x, prob=0.9):
    s = np.sort(x)
    k = int(np.floor(prob * len(s)))
    i = int(np.argmin(s[k:] - s[:len(s) - k]))
    return [float(s[i]), float(s[i + k])]


def plan_yaml(d: dict) -> str:
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    plan = {
        "name": "2026 market test",
        "approved": d["approved"],
        "budget": "hold_2025_exit",
        "test": {
            "id": d["test_id"], "start": d["dates"]["test_start"], "end": d["dates"]["test_last_week"],
            "arms": [
                {"id": f"{g['channel']}_up", "markets": g["markets"],
                 "moves": {g["channel"]: {"add_per_week_per_size": g["value"]}}},
                {"id": "search_back", "markets": c["markets"],
                 "moves": {ch: {"multiplier": c["value"]} for ch in c["channels"]}},
            ],
        },
    }
    head = ("# Written by python -m geotest.design from the pre-registered design\n"
            "# (geotest/outputs/design.json). Do not edit by hand.\n")
    return head + yaml.safe_dump(plan, sort_keys=False, default_flow_style=None)


def main() -> int:
    d = design()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "design.json").write_text(json.dumps(d, indent=2) + "\n", encoding="utf-8", newline="\n")
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLAN_PATH.write_text(plan_yaml(d), encoding="utf-8", newline="\n")
    PREREG_PATH.write_text(prereg_md(d, d["market_names"]), encoding="utf-8", newline="\n")
    print(json.dumps({k: d[k] for k in ("arms", "mde")}, indent=1))
    print({k: {kk: vv for kk, vv in v.items() if kk != "by_channel"} for k, v in d["forecast"].items()
           if isinstance(v, dict)})
    print(d["placebo"])
    for r in d["durations"]:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
