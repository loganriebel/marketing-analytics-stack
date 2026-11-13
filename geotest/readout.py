"""Read out market test MT2026Q1 exactly as pre-registered.

    .venv\\Scripts\\python -m geotest.readout

Everything that decides comes from geotest/PREREGISTRATION.md and its design file
(geotest/outputs/design.json): the metric (won deals by close week, all sources),
the markets, the 52 pre-test weeks, the 16-week measurement window, the ratio
difference-in-differences with the 2x2 dose solve (geotest/estimator.py), the 90%
interval from the registered placebo spread, and the five decision rules. Only weeks
up to the readout snapshot are read, from that snapshot's data cut.

Rule 5 names two validity checks without a method. They get one here, on spend only:

* spend change: the same ratio difference-in-differences on the moved channel's
  spend over the 12 test weeks, against the plan's dollars;
* cells: the plan file that drove 2026 spend (plans/2026_test.yaml) must assign every
  market to its registered cell, and the spend data must show every assigned move:
  - grow channel: a grow market's median weekly spend per size unit is at least half
    the planned add;
  - search channel: a step test at the test start. Always-on budgets are re-split
    across markets every calendar quarter, so each market's spend in the test weeks of
    the test's quarter is compared with its spend in that quarter's weeks before the
    test, against the same step in the markets outside the arm. A market shows the
    cut when its step is nearer (in logs) to the plan's multiplier than to 1. The
    step's noise comes from the same layout in every earlier quarter.
  A market outside an arm whose spend looks moved has drifted, not left its cell: it
  is named, and the lifts are recomputed without it (exploratory).

Disclosure: the cells check was first set as each market's test-week search spend
against its 52-week pre-test share (cell_check_first, kept in the output), read as
void on any mismatch. It flagged two markets outside the arm whose budgets fell at
the October and January re-splits, before the test. The step test and the reading
above replaced it after the lifts were computed. They decide validity only, never a
lift.

Anything else is labeled exploratory and decides nothing.

Writes geotest/outputs/readout.json (with the MMM's lift-test rows) and
geotest/READOUT.md. Puts the CausalPy cross-check (geotest/outputs/synthetic_control.json,
from python -m geotest.crosscheck) in READOUT.md when it exists.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import estimator as E
from .data import REPO, Markets, load
from .prereg import NAMES

OUT_DIR = REPO / "geotest" / "outputs"
DESIGN_PATH = OUT_DIR / "design.json"
READOUT_PATH = OUT_DIR / "readout.json"
CROSSCHECK_PATH = OUT_DIR / "synthetic_control.json"
READOUT_MD = REPO / "geotest" / "READOUT.md"
PLAN_PATH = REPO / "plans" / "2026_test.yaml"

MAX_SPEND_MISS = 0.20      # rule 5: realized spend change within 20% of plan
CELL_ADD_SHARE = 0.5       # a grow market shows at least half the planned weekly add
BRAND_SEARCH = "paid_search_brand"   # follows searches; the grow arm's extra searches cost extra here
ARM_KEYS = ("grow", "cut")


def cut_warehouse(d: dict) -> Path:
    """The readout snapshot's data cut, from python -m sim --through <snapshot> --out data/cut_<snapshot>."""
    default = REPO / "data" / f"cut_{d['dates']['readout_snapshot']}" / "data" / "warehouse.duckdb"
    return Path(os.environ.get("GEOTEST_READOUT_WAREHOUSE", default))


def arm_masks(d: dict, regions: list[str]) -> np.ndarray:
    return np.stack([np.isin(regions, d["arms"]["grow"]["markets"]), np.isin(regions, d["arms"]["cut"]["markets"])])


def decide(grow: dict, cut: dict, valid: bool) -> dict:
    """The pre-registered decision rules, as written. Each arm: lift, low, high, forecast."""
    works = grow["low"] > 0
    if grow["low"] > grow["forecast"]:
        grow_vs = "beats the forecast"
    elif grow["high"] < grow["forecast"]:
        grow_vs = "falls short of the forecast"
    else:
        grow_vs = "agrees with the forecast"
    if cut["high"] < cut["forecast"]:
        cut_vs = "costs more than modeled"
    elif cut["low"] > cut["forecast"]:
        cut_vs = "costs less than modeled"
    else:
        cut_vs = "agrees with the forecast"
    return {
        "valid": bool(valid),
        "rule_1_grow_works": bool(works),
        "rule_2_grow": grow_vs,
        "rule_2_cut": cut_vs,
        "cut_drop_is_clear": bool(cut["high"] < 0),
        "rule_3_lift_tests_enter_mmm": ["grow", "cut"],
        "rule_4_keep_cut_channels_at_todays_spend": cut_vs == "costs more than modeled",
        "rule_4_do_not_grow": not works,
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
    """The search channel's cut, as a step at the test start inside the test's quarter."""
    c = d["arms"]["cut"]
    x = sum(m.spend[ch] for ch in c["channels"])
    q = _quarter(m.weeks[start])
    in_q = np.array([_quarter(w) == q for w in m.weeks])
    before = slice(int(np.argmax(in_q)), start)
    after = slice(start, min(start + n_test, int(np.where(in_q)[0].max()) + 1))
    n_before, n_after = before.stop - before.start, after.stop - after.start
    others = ~arms[1]
    ratio = step_ratios(x, others, before, after)
    # Noise: the same layout in each earlier full quarter, every market against the same reference.
    noise, seen = [], set()
    for t, w in enumerate(m.weeks[:start]):
        qq = _quarter(w)
        if qq in seen or qq == q:
            continue
        seen.add(qq)
        if t + n_before + n_after <= start and _quarter(m.weeks[t + n_before + n_after - 1]) == qq:
            noise.append(np.log(step_ratios(x, others, slice(t, t + n_before),
                                            slice(t + n_before, t + n_before + n_after))))
    sd = float(np.std(np.concatenate(noise), ddof=1))
    log_r, log_keep = np.log(ratio), np.log(c["value"])
    seen_cut = np.abs(log_r - log_keep) < np.abs(log_r)
    rows = [{"market": code, "cut_arm": bool(arms[1, i]), "step": float(ratio[i]),
             "z_if_no_move": float(log_r[i] / sd), "z_if_cut": float((log_r[i] - log_keep) / sd),
             "cut_seen": bool(seen_cut[i]), "in_cell": bool(seen_cut[i] == arms[1, i])}
            for i, code in enumerate(m.regions)]
    return {"weeks_before": n_before, "weeks_after": n_after, "line": float(np.sqrt(c["value"])),
            "noise_log_sd": sd, "noise_quarters": len(noise), "markets": rows,
            "all_in_cell": all(r["in_cell"] for r in rows)}


def plan_check(d: dict, plan: dict) -> dict:
    """Does the plan that drove 2026 spend assign each market to its registered cell?"""
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    want = {f"{g['channel']}_up": (sorted(g["markets"]), {g["channel"]: {"add_per_week_per_size": g["value"]}}),
            "search_back": (sorted(c["markets"]), {ch: {"multiplier": c["value"]} for ch in c["channels"]})}
    got = {a["id"]: (sorted(a["markets"]), a["moves"]) for a in plan["test"]["arms"]}
    t = plan["test"]
    dates_ok = str(t["start"]) == d["dates"]["test_start"] and str(t["end"]) == d["dates"]["test_last_week"]
    return {"plan_file": "plans/2026_test.yaml", "arms_match": got == want, "dates_match": dates_ok,
            "matches": bool(got == want and dates_ok)}


def grow_cell_check(m: Markets, d: dict, arms: np.ndarray, start: int, n_test: int) -> dict:
    g = d["arms"]["grow"]
    weekly = m.spend[g["channel"]][start:start + n_test] / m.size[None, :]
    median = np.median(weekly, axis=0)
    seen = median >= CELL_ADD_SHARE * g["value"]
    rows = [{"market": code, "grow_arm": bool(arms[0, i]), "median_weekly_per_size": float(median[i]),
             "grow_seen": bool(seen[i]), "in_cell": bool(seen[i] == arms[0, i])} for i, code in enumerate(m.regions)]
    return {"line_per_size_week": CELL_ADD_SHARE * g["value"], "markets": rows,
            "all_in_cell": all(r["in_cell"] for r in rows)}


def cell_check_first(m: Markets, d: dict, arms: np.ndarray, start: int, n_pre: int, n_test: int) -> dict:
    """The first cells check, kept for the record (see the module docstring)."""
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    weekly = m.spend[g["channel"]][start:start + n_test] / m.size[None, :]
    grow_median = np.median(weekly, axis=0)
    grow_seen = grow_median >= CELL_ADD_SHARE * g["value"]
    x = sum(m.spend[ch] for ch in c["channels"])
    pre, win = x[start - n_pre:start].sum(0), x[start:start + n_test].sum(0)
    ratio = np.zeros(len(m.regions))
    for i in range(len(m.regions)):
        others = ~arms[1]
        others[i] = False
        ratio[i] = win[i] / (pre[i] / pre[others].sum() * win[others].sum())
    cut_line = (1 + c["value"]) / 2
    cut_seen = ratio < cut_line
    rows = []
    for i, code in enumerate(m.regions):
        rows.append({"market": code, "grow_arm": bool(arms[0, i]), "cut_arm": bool(arms[1, i]),
                     "grow_channel_median_weekly_per_size": float(grow_median[i]), "grow_move_seen": bool(grow_seen[i]),
                     "cut_spend_ratio": float(ratio[i]), "cut_move_seen": bool(cut_seen[i]),
                     "in_cell": bool(grow_seen[i] == arms[0, i] and cut_seen[i] == arms[1, i])})
    return {"grow_line_per_size_week": CELL_ADD_SHARE * g["value"], "cut_line": cut_line,
            "markets": rows, "all_in_cell": all(r["in_cell"] for r in rows)}


def _ratio_range(num: float, lo: float, hi: float) -> list | None:
    """num / x over the interval [lo, hi], or None when the interval reaches zero."""
    if lo > 0 or hi < 0:
        return sorted([num / lo, num / hi])
    return None


def readout(d: dict, m: Markets, plan: dict) -> dict:
    dt, f, pl = d["dates"], d["forecast"], d["placebo"]
    g, c = d["arms"]["grow"], d["arms"]["cut"]
    s = m.week_index(dt["test_start"])
    n_test, n_win, n_pre = dt["test_weeks"], dt["window_weeks"], dt["pre_period_weeks"]
    if str((m.weeks[s + n_win - 1] + pd.Timedelta(days=6)).date()) != dt["window_end"]:
        raise ValueError("measurement window does not match the design")
    if m.weeks[-1] > pd.Timestamp(dt["readout_snapshot"]):
        raise ValueError("data past the readout snapshot")
    arms = arm_masks(d, m.regions)
    keep = c["value"]
    size_units = np.array([m.size[a].sum() for a in arms])

    # Primary: the registered estimator, doses and interval.
    proxy = m.week_index(dt["forecast_proxy_start"])
    doses = E.planned_doses(m.size, arms, sum(m.spend[ch][proxy:proxy + n_test].sum(0) for ch in c["channels"]), keep)
    pre, win = E.window_sums(m.deals, s, n_pre, n_win)
    lift = E.lifts(pre, win, arms, doses)
    sd = np.asarray(pl["sd_used"], float)
    low, high = lift - E.Z_90 * sd, lift + E.Z_90 * sd

    # Rule 5: did the plan happen?
    grow_plan = g["value"] * size_units[0] * n_test
    cut_x = sum(m.spend[ch] for ch in c["channels"])
    cut_observed = float(cut_x[s:s + n_test][:, arms[1]].sum())
    cut_plan = cut_observed * (1 - 1 / keep)
    spend = {}
    for k, x, planned in (("grow", m.spend[g["channel"]], grow_plan), ("cut", cut_x, cut_plan)):
        t = arms[ARM_KEYS.index(k)]
        obs, cf = spend_did(x, t, s, n_pre, n_test)
        spend[k] = {"observed": obs, "without_move": cf, "realized_change": obs - cf, "plan_change": planned,
                    "registered_change": f[k]["spend_change"], "miss": (obs - cf) / planned - 1,
                    "check_noise_rel_sd": spend_did_noise(x, t, s, n_pre, n_test),
                    "within_limit": bool(abs((obs - cf) / planned - 1) <= MAX_SPEND_MISS)}
    cells = {"plan": plan_check(d, plan), "grow": grow_cell_check(m, d, arms, s, n_test),
             "cut": step_check(m, d, arms, s, n_test)}
    cells["assigned_moves_seen"] = (all(r["grow_seen"] for r in cells["grow"]["markets"] if r["grow_arm"])
                                    and all(r["cut_seen"] for r in cells["cut"]["markets"] if r["cut_arm"]))
    cells["drifted"] = ([r["market"] for r in cells["grow"]["markets"] if r["grow_seen"] and not r["grow_arm"]]
                        + [r["market"] for r in cells["cut"]["markets"] if r["cut_seen"] and not r["cut_arm"]])
    cells["all_in_cell"] = bool(cells["plan"]["matches"] and cells["assigned_moves_seen"])
    first = cell_check_first(m, d, arms, s, n_pre, n_test)
    first["out_of_cell"] = [r["market"] for r in first["markets"] if not r["in_cell"]]
    valid = all(v["within_limit"] for v in spend.values()) and cells["all_in_cell"]

    arms_out = {}
    for i, k in enumerate(ARM_KEYS):
        t = arms[i]
        r = pre[t].sum() / pre[~t].sum()
        arms_out[k] = {
            "channels": [g["channel"]] if k == "grow" else c["channels"],
            "markets": g["markets"] if k == "grow" else c["markets"],
            "lift": float(lift[i]), "interval_90": [float(low[i]), float(high[i])], "sd": float(sd[i]),
            "forecast": {"lift_mean": f[k]["lift_mean"], "hdi_90": f[k]["lift_hdi_90"]},
            "power_at_forecast": f[k]["power"], "smallest_detectable_lift": d["mde"][k],
            "window_deals": float(win[t].sum()),
            "window_deals_other_markets_scaled": float(r * win[~t].sum()),
            "simple_contrast": float(win[t].sum() - r * win[~t].sum()),
        }
    decision = decide({"lift": lift[0], "low": low[0], "high": high[0], "forecast": f["grow"]["lift_mean"]},
                      {"lift": lift[1], "low": low[1], "high": high[1], "forecast": f["cut"]["lift_mean"]}, valid)

    # Secondary: cost per deal.
    b_obs, b_cf = spend_did(m.spend[BRAND_SEARCH], arms[0], s, n_pre, n_win)
    extra = grow_plan + (b_obs - b_cf)
    saved = -cut_plan
    all_spend = sum(m.spend.values())
    blended = {}
    for i, k in enumerate(ARM_KEYS):
        t = arms[i]
        sp, dl = all_spend[s:s + n_win], m.deals[s:s + n_win]
        blended[k] = {"arm_markets": float(sp[:, t].sum() / dl[:, t].sum()),
                      "other_markets": float(sp[:, ~t].sum() / dl[:, ~t].sum())}
    secondary = {
        "grow": {"channel_spend_added": grow_plan, "brand_search_spend_change": b_obs - b_cf,
                 "extra_spend": extra, "cost_per_extra_deal": extra / lift[0],
                 "cost_per_extra_deal_range": _ratio_range(extra, low[0], high[0]),
                 "mmm_marginal_cpa": d["mmm"]["mcpa"][g["channel"]],
                 "forecast_cost_per_extra_deal": f["grow"]["cost_per_extra_deal"]},
        "cut": {"spend_saved": saved,
                "saved_per_deal_lost": saved / -lift[1] if lift[1] < 0 else None,
                "saved_per_deal_lost_range": _ratio_range(saved, -high[1], -low[1]),
                "mmm_marginal_cpa": {ch: d["mmm"]["mcpa"][ch] for ch in c["channels"]}},
        "blended_cost_per_deal_in_window": blended,
    }

    # Exploratory: decides nothing.
    realized_doses = E.planned_doses(m.size, arms, cut_x[s:s + n_test].sum(0) / keep, keep)
    lift_rd = E.lifts(pre, win, arms, realized_doses)
    bias = np.asarray(pl["mean_all"], float)
    keep_m = ~np.isin(m.regions, cells["drifted"])
    lift_dd = E.lifts(pre[keep_m], win[keep_m], arms[:, keep_m], doses[:, keep_m])
    dec_dd = decide({"lift": lift_dd[0], "low": lift_dd[0] - E.Z_90 * sd[0], "high": lift_dd[0] + E.Z_90 * sd[0],
                     "forecast": f["grow"]["lift_mean"]},
                    {"lift": lift_dd[1], "low": lift_dd[1] - E.Z_90 * sd[1], "high": lift_dd[1] + E.Z_90 * sd[1],
                     "forecast": f["cut"]["lift_mean"]}, valid)
    exploratory = {
        "drifted_markets_dropped": {
            "note": "lifts without the markets whose spend drifted outside their arm, with the registered sd",
            "dropped": cells["drifted"],
            "lift": {k: float(lift_dd[i]) for i, k in enumerate(ARM_KEYS)},
            "interval_90": {k: [float(lift_dd[i] - E.Z_90 * sd[i]), float(lift_dd[i] + E.Z_90 * sd[i])]
                            for i, k in enumerate(ARM_KEYS)},
            "same_decision": dec_dd == decision},
        "realized_doses": {"note": "search doses from the 2026 test weeks' spend instead of last year's same weeks",
                           "lift": {k: float(lift_rd[i]) for i, k in enumerate(ARM_KEYS)}},
        "placebo_mean_removed": {"note": "lift minus the placebo windows' mean error; the registered interval is "
                                         "centered on the raw lift",
                                 "placebo_mean": {k: float(bias[i]) for i, k in enumerate(ARM_KEYS)},
                                 "lift": {k: float(lift[i] - bias[i]) for i, k in enumerate(ARM_KEYS)}},
    }

    return {
        "test_id": d["test_id"],
        "readout_snapshot": dt["readout_snapshot"],
        "data_cut": {"warehouse": f"data/cut_{dt['readout_snapshot']}/data/warehouse.duckdb",
                     "first_week": str(m.weeks[0].date()), "last_week": str(m.weeks[-1].date())},
        "window": {k: dt[k] for k in ("test_start", "test_end", "window_start", "window_end", "pre_period_weeks",
                                      "test_weeks", "window_weeks")},
        "arms": arms_out,
        "decision": decision,
        "validity": {"spend": spend, "cells": cells, "cells_first_check": first, "valid": bool(valid),
                     "max_spend_miss": MAX_SPEND_MISS},
        "secondary": secondary,
        "exploratory": exploratory,
        "mmm_lift_tests": lift_test_rows(d, m, arms, lift, sd, s, n_test, cut_observed),
    }


def lift_test_rows(d: dict, m: Markets, arms: np.ndarray, lift: np.ndarray, sd: np.ndarray, s: int,
                   n_test: int, cut_observed: float) -> dict:
    """add_lift_test_measurements rows, one per arm, in the MMM's units (per size unit, per week).

    PyMC-Marketing compares a measured lift with saturation(x + delta_x) - saturation(x):
    a steady weekly effect at spend level x. A 12-week move counted over a 16-week
    window holds the share of its effect that closes inside the window; that share is
    the pre-test MMM forecast's in-window lift over its total lift (design.json).
    """
    f, g, c = d["forecast"], d["arms"]["grow"], d["arms"]["cut"]
    if len(c["channels"]) != 1:
        raise ValueError("the search arm moved more than one channel: no single-channel lift test")
    rows = []
    for i, k in enumerate(ARM_KEYS):
        units = float(m.size[arms[i]].sum())
        share = f[k]["lift_mean"] / f[k]["lift_total_mean"]
        per = n_test * share * units
        if k == "grow":
            observed = float(m.spend[g["channel"]][s:s + n_test][:, arms[i]].sum()) / (n_test * units)
            dx = g["value"]
            x = observed - dx
            ch = g["channel"]
        else:
            x = cut_observed / c["value"] / (n_test * units)
            dx = x * (c["value"] - 1)
            ch = c["channels"][0]
        rows.append({"arm": k, "channel": ch, "x": x, "delta_x": dx, "delta_y": float(lift[i]) / per,
                     "sigma": float(sd[i]) / per, "size_units": units, "test_weeks": n_test,
                     "window_share": share, "lift_in_window": float(lift[i])})
    return {"units": "dollars and deals per week per size unit (market value / size index), the MMM's own units",
            "x": "spend level without the move: grow = observed minus the planned add; search = observed / multiplier",
            "delta_y": "lift in window / (test weeks x window share x size units)",
            "rows": rows}


# --- READOUT.md ----------------------------------------------------------------------------

def _money(x):
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def _signed(x):
    return f"{x:+,.0f}"


def _rng(lo, hi):
    return f"{_signed(lo)} to {_signed(hi)}"


def readout_md(r: dict, d: dict, cross: dict | None = None) -> str:
    a, dec, v, sec = r["arms"], r["decision"], r["validity"], r["secondary"]
    g, c = a["grow"], a["cut"]
    gname = NAMES[g["channels"][0]]
    cname = " and ".join(NAMES[x] for x in c["channels"])
    lines = [
        f"# Readout: market test {r['test_id']}",
        "",
        f"Written by `python -m geotest.readout` from `geotest/outputs/readout.json`; every number below comes "
        f"from that file. Data: the {r['readout_snapshot']} cut, weeks {r['data_cut']['first_week']} to "
        f"{r['data_cut']['last_week']}. Method, markets, windows and rules: "
        "[PREREGISTRATION.md](PREREGISTRATION.md), unchanged.",
        "",
        "## Results",
        "",
        "| Arm | Measured lift, deals (90% interval) | MMM forecast (90% range) | Power at forecast |",
        "|---|---:|---:|---:|",
        f"| grow: {gname} | {_signed(g['lift'])} ({_rng(*g['interval_90'])}) | "
        f"{_signed(g['forecast']['lift_mean'])} ({_rng(*g['forecast']['hdi_90'])}) | {g['power_at_forecast']:.0%} |",
        f"| search: {cname} at {d['arms']['cut']['value']:.0%} of plan | {_signed(c['lift'])} ({_rng(*c['interval_90'])}) | "
        f"{_signed(c['forecast']['lift_mean'])} ({_rng(*c['forecast']['hdi_90'])}) | {c['power_at_forecast']:.0%} |",
        "",
        f"Deals in the window, {r['window']['window_start']} to {r['window']['window_end']}: the grow markets closed "
        f"{g['window_deals']:,.0f}, and the other markets scaled by their pre-test ratio point to "
        f"{g['window_deals_other_markets_scaled']:,.0f}. The search markets closed {c['window_deals']:,.0f} against "
        f"{c['window_deals_other_markets_scaled']:,.0f}. The 2x2 solve then takes out each arm's effect on the other.",
        "",
        "## Decision rules, as registered",
        "",
    ]
    if dec["rule_1_grow_works"]:
        lines.append(f"1. **{gname} works.** The grow arm's 90% interval, {_rng(*g['interval_90'])}, is above zero.")
    else:
        lines.append(f"1. **{gname} shows no clear lift.** The grow arm's 90% interval, {_rng(*g['interval_90'])}, "
                     "reaches zero.")
    f_g, f_c = g["forecast"]["lift_mean"], c["forecast"]["lift_mean"]
    grow_line = {"beats the forecast": f"the whole interval lies above the forecast ({_signed(f_g)}), so the lift beats it",
                 "falls short of the forecast": f"the whole interval lies below the forecast ({_signed(f_g)}), so the "
                                                "lift falls short of it",
                 "agrees with the forecast": f"the interval holds the forecast ({_signed(f_g)}), so the lift agrees "
                                             "with the model"}[dec["rule_2_grow"]]
    cut_line = {"costs more than modeled": f"the whole interval lies below the forecast ({_signed(f_c)}), so pulling "
                                           f"{cname} back costs more than modeled",
                "costs less than modeled": f"the whole interval lies above the forecast ({_signed(f_c)}), so pulling "
                                           f"{cname} back costs less than modeled",
                "agrees with the forecast": f"the interval holds the forecast ({_signed(f_c)}), so the cost of pulling "
                                            f"{cname} back agrees with the model"}[dec["rule_2_cut"]]
    lines.append(f"2. **Against the model.** Grow arm: {grow_line}. Search arm: {cut_line}.")
    if dec["cut_drop_is_clear"]:
        cut_note = (f"   The search arm's drop is clear: its interval, {_rng(*c['interval_90'])}, is below zero.")
    else:
        cut_note = (f"   The search arm's drop is not clear: its interval, {_rng(*c['interval_90'])}, reaches zero. This "
                    f"arm had {c['power_at_forecast']:.0%} power at the forecast and was registered as a guardrail, so "
                    f"this is not evidence that {cname} does nothing. The test can only rule out a loss larger than "
                    f"{-c['interval_90'][0]:,.0f} deals over the window.")
    lines.append(cut_note)
    lines.append(f"3. **The model learns.** Both arms enter the MMM as lift tests: {gname} from the grow arm, {cname} "
                 "from the search arm (rows below). The refit and its grade are in "
                 "[docs/mmm/README.md](../docs/mmm/README.md#the-2026-market-test-and-the-refit).")
    g4 = []
    if dec["rule_4_keep_cut_channels_at_todays_spend"]:
        g4.append(f"the rollout does not cut {cname} below today's spend")
    if dec["rule_4_do_not_grow"]:
        g4.append(f"the rollout does not grow {gname}")
    lines.append("4. **Guardrail.** " + ("Tripped: " + "; ".join(g4) + "." if g4 else
                                          f"Not tripped. The search arm did not show {cname} worth more than modeled, "
                                          f"and {gname} showed a lift."))
    sg, sc = v["spend"]["grow"], v["spend"]["cut"]
    cells, first = v["cells"], v["cells_first_check"]
    cg, cc = cells["grow"], cells["cut"]
    names = d["market_names"]

    def who(codes):
        return " and ".join(f"{names[x]} ({x})" for x in codes)

    drift = r["exploratory"]["drifted_markets_dropped"]
    steps = {row["market"]: row for row in cc["markets"]}
    lines += [
        f"5. **Validity: {'the readout stands' if v['valid'] else 'the readout is void'}.** "
        f"Realized spend change against plan: grow {_money(sg['realized_change'])} against "
        f"{_money(sg['plan_change'])} ({sg['miss']:+.0%}); search {_money(sc['realized_change'])} against "
        f"{_money(sc['plan_change'])} ({sc['miss']:+.0%}); the limit is {v['max_spend_miss']:.0%}. "
        + ("The plan file puts every market in its registered cell, and the spend data show every assigned move."
           if cells["all_in_cell"] else "A market left its cell, or an assigned move does not show in the spend."),
    ]
    if cells["drifted"]:
        dd = cells["drifted"]

        def each(key, fmt):
            return ", ".join(format(steps[x][key], fmt) for x in dd)

        lines.append(
            f"   Drift: {who(dd)}, outside the search arm, also ran less {cname} during the test than its own "
            f"pace before it (step {each('step', '.2f')}, against a line of {cc['line']:.2f}; "
            f"{each('z_if_no_move', '+.1f')} noise units from no move and {each('z_if_cut', '+.1f')} from the cut). "
            f"The plan gives it no move. Without it, grow reads {_signed(drift['lift']['grow'])} and search "
            f"{_signed(drift['lift']['cut'])}, and "
            + ("no decision changes." if drift["same_decision"] else "a decision changes.")
        )
    lines += [
        "",
        "**How rule 5 was checked.** The registration named no method, so these were set on spend only.",
        "",
        f"- Spend change: the same ratio difference-in-differences on the moved channel's spend over the test "
        f"weeks. Its error on earlier windows is {sg['check_noise_rel_sd']:.0%} of {gname} spend and "
        f"{sc['check_noise_rel_sd']:.0%} of {cname} spend, so the {gname} check is rough. The plan's dollars: the "
        f"grow add is {_money(d['arms']['grow']['value'])} a week per size unit; the search change is observed "
        "spend over the multiplier, minus observed spend.",
        f"- Cells: `{cells['plan']['plan_file']}`, the plan that drove 2026 spend, must match the registered arms "
        f"and dates ({'it does' if cells['plan']['matches'] else 'it does not'}), and every assigned move must "
        "show in the spend.",
        f"- {gname} add: a market shows it when its median weekly {gname} spend per size unit is at least "
        f"{_money(cg['line_per_size_week'])}.",
        f"- {cname[0].upper() + cname[1:]} cut: a step test at the test start. Budgets for always-on channels are re-split across markets "
        f"every quarter, so each market's spend in the {cc['weeks_after']} test weeks of the test's quarter is "
        f"compared with its {cc['weeks_before']} weeks of that quarter before the test, against the same step in "
        "the markets outside the arm. A market shows the cut when its step is nearer, in logs, to "
        f"{d['arms']['cut']['value']:.2f} than to 1 (the line is {cc['line']:.2f}). One noise unit, from the same "
        f"layout in {cc['noise_quarters']} earlier quarters, is {cc['noise_log_sd']:.2f} in logs.",
        "- A market outside an arm whose spend looks moved has drifted, not left its cell. It is named, and the "
        "lifts are recomputed without it.",
        f"- **Disclosure.** The cells check was first set as each market's test-week {cname} spend against its "
        f"{r['window']['pre_period_weeks']}-week pre-test share, with any mismatch voiding the readout. It flagged "
        f"{who(first['out_of_cell']) or 'no market'}, outside the arm, whose budgets fell at quarterly re-splits "
        "before the test began. The checks above replaced it after the lifts were computed. They decide validity "
        "only, never a lift.",
        "",
        "## Cost per deal (secondary)",
        "",
    ]
    gs, cs = sec["grow"], sec["cut"]
    rng = gs["cost_per_extra_deal_range"]
    lines.append(f"- **Grow arm:** {_money(gs['channel_spend_added'])} of {gname} plus "
                 f"{_money(gs['brand_search_spend_change'])} of brand search that followed the extra searches, "
                 f"{_money(gs['extra_spend'])} in all: {_money(gs['cost_per_extra_deal'])} per extra deal"
                 + (f" ({_money(rng[0])} to {_money(rng[1])})" if rng else " (range unbounded: the lift's interval "
                                                                            "reaches zero)")
                 + f". The MMM's cost per extra deal for {gname} was {_money(gs['mmm_marginal_cpa'])}.")
    rng = cs["saved_per_deal_lost_range"]
    per = cs["saved_per_deal_lost"]
    lines.append(f"- **Search arm:** {_money(cs['spend_saved'])} saved"
                 + (f", {_money(per)} per deal lost" if per is not None else ", with no deals lost on the point estimate")
                 + (f" ({_money(rng[0])} to {_money(rng[1])})" if rng else " (range unbounded: the interval reaches zero)")
                 + ". The MMM's cost per extra deal for " + cname + " was "
                 + _money(next(iter(cs["mmm_marginal_cpa"].values()))) + ".")
    bl = sec["blended_cost_per_deal_in_window"]
    lines.append(f"- **Blended cost per deal in the window:** grow markets {_money(bl['grow']['arm_markets'])} against "
                 f"{_money(bl['grow']['other_markets'])} in the rest; search markets {_money(bl['cut']['arm_markets'])} "
                 f"against {_money(bl['cut']['other_markets'])}.")
    lines += ["", "## Cross-check: Bayesian synthetic control (does not decide)", ""]
    if cross:
        for k, label in (("grow", "Grow arm"), ("cut", "Search arm")):
            x = cross["arms"][k]
            lines.append(f"- **{label}:** {_signed(x['lift_mean'])} deals ({_rng(*x['lift_hdi_90'])}), pre-test fit "
                         f"R² {x['pre_r2']:.2f}; {x['weight_on_other_arm']:.0%} of the donor weight sits on the other "
                         "arm's markets.")
        lines.append(f"- {cross['note']}")
        if min(cross["arms"][k]["pre_r2"] for k in ARM_KEYS) < 0.5:
            lines.append("- One market's weekly deals are noisy, so a weighted mix of single markets tracks an arm "
                         "only loosely before the test (low R²). The registered estimator sums whole windows, "
                         "which averages that noise out.")
    else:
        lines.append("- Not run yet: `python -m geotest.crosscheck` in `.venv-mmm`.")
    ex = r["exploratory"]
    lines += [
        "",
        "## Exploratory (does not decide)",
        "",
        f"- **Search doses from 2026 spend:** grow {_signed(ex['realized_doses']['lift']['grow'])}, search "
        f"{_signed(ex['realized_doses']['lift']['cut'])}. The registered doses use last year's same weeks.",
        f"- **Placebo mean removed:** the placebo windows erred by {_signed(ex['placebo_mean_removed']['placebo_mean']['grow'])} "
        f"(grow) and {_signed(ex['placebo_mean_removed']['placebo_mean']['cut'])} (search) on average. Taking that "
        f"out gives grow {_signed(ex['placebo_mean_removed']['lift']['grow'])} and search "
        f"{_signed(ex['placebo_mean_removed']['lift']['cut'])}.",
        "",
        "## Into the MMM",
        "",
        f"Each arm becomes one `add_lift_test_measurements` row, in {r['mmm_lift_tests']['units']}. "
        f"delta_y = {r['mmm_lift_tests']['delta_y']}; the window share is the pre-test MMM forecast's in-window "
        "lift over its total lift.",
        "",
        "| Arm | Channel | x | delta_x | delta_y | sigma | Window share |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in r["mmm_lift_tests"]["rows"]:
        lines.append(f"| {row['arm']} | {row['channel']} | {row['x']:,.0f} | {row['delta_x']:+,.0f} | "
                     f"{row['delta_y']:+.3f} | {row['sigma']:.3f} | {row['window_share']:.3f} |")
    lines.append("")
    return "\n".join(lines)


def write(r: dict, d: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    READOUT_PATH.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8", newline="\n")
    cross = json.loads(CROSSCHECK_PATH.read_text(encoding="utf-8")) if CROSSCHECK_PATH.exists() else None
    READOUT_MD.write_text(readout_md(r, d, cross), encoding="utf-8", newline="\n")


def main() -> int:
    d = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    m = load(cut_warehouse(d), through=d["dates"]["readout_snapshot"])
    r = readout(d, m, yaml.safe_load(PLAN_PATH.read_text(encoding="utf-8")))
    write(r, d)
    print(json.dumps({k: r[k] for k in ("arms", "decision")}, indent=1))
    print(json.dumps(r["validity"]["spend"], indent=1))
    print("cells all in:", r["validity"]["cells"]["all_in_cell"])
    print(json.dumps(r["secondary"], indent=1))
    print(json.dumps(r["exploratory"], indent=1))
    print(json.dumps(r["mmm_lift_tests"]["rows"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
