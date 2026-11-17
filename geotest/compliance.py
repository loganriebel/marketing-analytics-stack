"""Rule 5, the market-compliance check: did the plan happen in each market?

Registered with the design (design.json "compliance", PREREGISTRATION.md rule 5)
before the test runs, and applied as written by the readout. Spend only; it never
moves a lift.

* Spend change: the ratio difference-in-differences on the moved channel's spend
  over the test weeks, against the plan's dollars. An arm whose realized change
  misses its plan by more than MAX_SPEND_MISS voids the readout.
* Plan file: plans/2026_test.yaml, the plan that drove 2026 spend, must assign the
  registered markets, moves and dates, or the readout is void.
* Each assigned move must show in the spend:
  - grow channel, per market (void if an assigned market misses): the add runs every test week, so the market's lowest weekly spend
    per size unit over the test weeks is at least CELL_ADD_SHARE of the planned add.
    (A median would not do: national flights lift every market's median in season.)
  - cut channel, per arm (void if the arm as a whole misses): a step test at the test
    start. Always-on budgets are re-split across markets every calendar quarter, so
    spend in the test weeks of the test's quarter is compared with spend in that
    quarter's weeks before the test, against the same step in the markets outside the
    arm. The arm, its markets summed, shows the cut when its step is nearer, in logs, to
    the plan's multiplier than to 1. Each market gets the same test on its own; an
    assigned market that misses is named, and the lifts are recomputed without it as
    exploratory. One noise unit comes from the same layout in every earlier full
    quarter. (Logan's call, 2026-11-16, before the test: one market's quarterly
    re-split noise would void a per-market rule about 1 time in 9.)
* Drift: a market outside an arm whose spend shows that arm's move. It is named, the
  lifts are recomputed without it as exploratory, and it never voids the readout.

The design also runs these checks on last year's same weeks, when nothing was tested
(dry_run), so the false-flag rate is known before the test.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .data import Markets

MAX_SPEND_MISS = 0.20      # an arm's realized spend change within 20% of its plan
CELL_ADD_SHARE = 0.5       # a grow market shows at least half the planned weekly add
PLAN_FILE = "plans/2026_test.yaml"


def _norm_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def registered(add: float, keep: float) -> dict:
    """The rule-5 method and its numbers, written into design.json before the test."""
    return {
        "spend_change": {
            "method": "ratio difference-in-differences on the moved channel's spend over the test weeks, "
                      "with the registered pre-period",
            "plan_dollars": {"grow": "the add per week per size unit x the arm's size units x the test weeks",
                             "cut": "observed spend / multiplier - observed spend"},
            "max_miss": MAX_SPEND_MISS},
        "plan_file": {"path": PLAN_FILE, "rule": "assigns the registered markets, moves and dates"},
        "grow_seen": {"stat": "lowest weekly grow-channel spend per size unit over the test weeks",
                      "line_share_of_add": CELL_ADD_SHARE, "line": CELL_ADD_SHARE * add},
        "cut_seen": {"stat": "step at the test start inside its quarter, relative to the markets outside the arm",
                     "rule": "step nearer, in logs, to the multiplier than to 1; decided for the arm, its markets "
                             "summed; each market tested the same way on its own",
                     "market_miss": "an assigned market whose own step misses: named, lifts recomputed without it "
                                    "as exploratory; never voids the readout",
                     "line": float(np.sqrt(keep)),
                     "noise": "sd of the log step in the same layout in every earlier full quarter"},
        "void_if": ["an arm's realized spend change misses its plan by more than max_miss",
                    "the plan file does not assign the registered markets, moves and dates",
                    "an assigned grow market's spend does not show the add",
                    "the search arm's summed spend does not show the cut"],
        "drift": "a market outside an arm whose spend shows that arm's move: named, lifts recomputed without "
                 "it as exploratory; never voids the readout and never changes the registered lift",
    }


def spend_did(x: np.ndarray, t: np.ndarray, start: int, n_pre: int, n_weeks: int) -> tuple[float, float]:
    """Observed spend in markets t over n_weeks from start, and what they would have
    spent: the other markets' spend scaled by the pre-period ratio."""
    pre = x[start - n_pre:start].sum(0)
    win = x[start:start + n_weeks].sum(0)
    return float(win[t].sum()), float(pre[t].sum() / pre[~t].sum() * win[~t].sum())


def spend_did_noise(x: np.ndarray, t: np.ndarray, start: int, n_pre: int, n_weeks: int) -> float:
    """Relative error sd of spend_did's counterfactual on windows before the test."""
    errs = []
    for s in range(n_pre, start - n_weeks + 1):
        obs, cf = spend_did(x, t, s, n_pre, n_weeks)
        errs.append(obs / cf - 1)
    return float(np.sqrt(np.mean(np.square(errs))))


def _quarter(ts: pd.Timestamp) -> tuple[int, int]:
    return ts.year, (ts.month - 1) // 3


def step_ratios(x: np.ndarray, others: np.ndarray, before: slice, after: slice) -> np.ndarray:
    """(G,) each market's mean spend after over before, relative to the same step in
    the `others` markets (a market is left out of its own reference)."""
    out = np.zeros(x.shape[1])
    for i in range(x.shape[1]):
        ref = others.copy()
        ref[i] = False
        own = x[after, i].mean() / x[before, i].mean()
        out[i] = own / (x[after][:, ref].sum(1).mean() / x[before][:, ref].sum(1).mean())
    return out


def step_check(m: Markets, d: dict, arms: np.ndarray, start: int, n_test: int) -> dict:
    """The cut channel's move, as a step at the test start inside the test's quarter."""
    c = d["arms"]["cut"]
    x = sum(m.spend[ch] for ch in c["channels"])
    q = _quarter(m.weeks[start])
    in_q = np.array([_quarter(w) == q for w in m.weeks])
    before = slice(int(np.argmax(in_q)), start)
    after = slice(start, min(start + n_test, int(np.where(in_q)[0].max()) + 1))
    n_before, n_after = before.stop - before.start, after.stop - after.start
    others = ~arms[1]
    ratio = step_ratios(x, others, before, after)
    arm_log = _pooled_log_step(x, arms[1], before, after)
    # Noise: the same layout in each earlier full quarter, every market against the same reference.
    noise, arm_noise, seen = [], [], set()
    for t, w in enumerate(m.weeks[:start]):
        qq = _quarter(w)
        if qq in seen or qq == q:
            continue
        seen.add(qq)
        if t + n_before + n_after <= start and _quarter(m.weeks[t + n_before + n_after - 1]) == qq:
            b, a = slice(t, t + n_before), slice(t + n_before, t + n_before + n_after)
            noise.append(np.log(step_ratios(x, others, b, a)))
            arm_noise.append(_pooled_log_step(x, arms[1], b, a))
    sd = float(np.std(np.concatenate(noise), ddof=1))
    arm_sd = float(np.std(arm_noise, ddof=1))
    log_r, log_keep = np.log(ratio), np.log(c["value"])
    seen_cut = np.abs(log_r - log_keep) < np.abs(log_r)
    rows = [{"market": code, "cut_arm": bool(arms[1, i]), "step": float(ratio[i]),
             "z_if_no_move": float(log_r[i] / sd), "z_if_cut": float((log_r[i] - log_keep) / sd),
             "cut_seen": bool(seen_cut[i]), "in_cell": bool(seen_cut[i] == arms[1, i])}
            for i, code in enumerate(m.regions)]
    arm = {"step": float(np.exp(arm_log)), "noise_log_sd": arm_sd, "z_if_no_move": float(arm_log / arm_sd),
           "z_if_cut": float((arm_log - log_keep) / arm_sd), "cut_seen": bool(abs(arm_log - log_keep) < abs(arm_log))}
    return {"weeks_before": n_before, "weeks_after": n_after, "line": float(np.sqrt(c["value"])),
            "noise_log_sd": sd, "noise_quarters": len(noise), "arm": arm, "markets": rows,
            "all_in_cell": all(r["in_cell"] for r in rows)}


def _pooled_log_step(x: np.ndarray, arm: np.ndarray, before: slice, after: slice) -> float:
    """Log step of the arm's summed spend, relative to the same step in the other markets."""
    a = x[after][:, arm].sum(1).mean() / x[before][:, arm].sum(1).mean()
    o = x[after][:, ~arm].sum(1).mean() / x[before][:, ~arm].sum(1).mean()
    return float(np.log(a / o))


def grow_cell_check(m: Markets, d: dict, arms: np.ndarray, start: int, n_test: int) -> dict:
    g = d["arms"]["grow"]
    line = d["compliance"]["grow_seen"]["line"]
    weekly = m.spend[g["channel"]][start:start + n_test] / m.size[None, :]
    low = weekly.min(axis=0)
    seen = low >= line
    rows = [{"market": code, "grow_arm": bool(arms[0, i]), "lowest_weekly_per_size": float(low[i]),
             "grow_seen": bool(seen[i]), "in_cell": bool(seen[i] == arms[0, i])} for i, code in enumerate(m.regions)]
    return {"line_per_size_week": line, "markets": rows, "all_in_cell": all(r["in_cell"] for r in rows)}


def plan_check(d: dict, plan: dict) -> dict:
    """Does the plan that drove 2026 spend assign each market to its registered cell?"""
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    want = {f"{g['channel']}_up": (sorted(g["markets"]), {g["channel"]: {"add_per_week_per_size": g["value"]}}),
            "search_back": (sorted(c["markets"]), {ch: {"multiplier": c["value"]} for ch in c["channels"]})}
    got = {a["id"]: (sorted(a["markets"]), a["moves"]) for a in plan["test"]["arms"]}
    t = plan["test"]
    dates_ok = str(t["start"]) == d["dates"]["test_start"] and str(t["end"]) == d["dates"]["test_last_week"]
    return {"plan_file": PLAN_FILE, "arms_match": got == want, "dates_match": dates_ok,
            "matches": bool(got == want and dates_ok)}


def dry_run(m: Markets, d: dict, arms: np.ndarray, start: int, n_test: int) -> dict:
    """The move checks on weeks when nothing was tested (last year's same weeks): what
    they flag there is false. Also the chance, from the step's noise, that the arm or an
    assigned market shows a step past the line when the cut did happen."""
    grow = grow_cell_check(m, d, arms, start, n_test)
    cut = step_check(m, d, arms, start, n_test)
    keep, sd = d["arms"]["cut"]["value"], cut["noise_log_sd"]
    p_miss = _norm_sf(float(np.log(cut["line"]) - np.log(keep)) / sd)
    n_cut = int(arms[1].sum())
    lows = [r["lowest_weekly_per_size"] for r in grow["markets"]]
    x = m.spend[d["arms"]["grow"]["channel"]] / m.size[None, :]
    every = np.array([x[t:t + n_test].min(0) for t in range(0, start + 1)])  # every window up to these weeks
    return {
        "weeks_start": str(m.weeks[start].date()), "test_weeks": n_test,
        "grow": {"line_per_size_week": grow["line_per_size_week"], "max_lowest_weekly_per_size": float(max(lows)),
                 "flagged": [r["market"] for r in grow["markets"] if r["grow_seen"]],
                 "windows": int(every.shape[0]), "windows_max_lowest_weekly_per_size": float(every.max()),
                 "windows_flag_rate": float((every >= grow["line_per_size_week"]).mean())},
        "cut": {"line": cut["line"], "noise_log_sd": sd, "noise_quarters": cut["noise_quarters"],
                "weeks_before": cut["weeks_before"], "weeks_after": cut["weeks_after"],
                "flagged": [r["market"] for r in cut["markets"] if r["cut_seen"]],
                "p_assigned_market_misses_line": p_miss,
                "p_any_assigned_market_misses_line": float(1 - (1 - p_miss) ** n_cut),
                "p_market_flagged_without_a_move": _norm_sf(-float(np.log(cut["line"])) / sd),
                "arm_step": cut["arm"]["step"], "arm_noise_log_sd": cut["arm"]["noise_log_sd"],
                "p_arm_misses_line": _norm_sf(float(np.log(cut["line"]) - np.log(keep)) / cut["arm"]["noise_log_sd"])},
    }
