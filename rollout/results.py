"""Chapter 8's numbers: the rollout's year-end readout, as registered (January 2027).

    .venv\\Scripts\\python -m rollout.results

Everything that decides was written down in May (rollout/outputs/plan.json "holdout",
rollout/PLAN.md): the 15 rollout markets against the 5 holdout markets, won deals by
close week over the rollout weeks, the ratio method with the pre-period before the
spring test, the placebo interval, and the rules. Only weeks up to the year-end
snapshot are read, from that snapshot's data cut.

Also reports the year: won deals, paid spend and cost per deal in 2025 and 2026, and
the dollars the rollout moved. The refit MMM's own view of the rollout
(rollout/outputs/model_view.json, from python -m rollout.crosscheck) goes beside the
readout when it exists, and decides nothing.

Writes rollout/outputs/results.json and rollout/RESULTS.md.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from geotest import estimator as E
from geotest.data import Markets, load

from . import holdout as H

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "rollout" / "outputs"
PLAN_JSON = OUT_DIR / "plan.json"
MODEL_VIEW = OUT_DIR / "model_view.json"
RESULTS_JSON = OUT_DIR / "results.json"
RESULTS_MD = REPO / "rollout" / "RESULTS.md"
PLAN_FILE = REPO / "plans" / "2026_rollout.yaml"
DESIGN = REPO / "geotest" / "outputs" / "design.json"
BRAND_SEARCH = "paid_search_brand"


def cut_warehouse(plan: dict) -> Path:
    snap = plan["holdout"]["readout_snapshot"]
    default = REPO / "data" / f"cut_{snap}" / "data" / "warehouse.duckdb"
    return Path(os.environ.get("ROLLOUT_RESULTS_WAREHOUSE", default))


def plan_check(plan: dict, plan_file: dict) -> dict:
    """Does the plan that drove 2026 spend hold the registered markets, moves and dates?"""
    reg = plan["holdout"]
    t = plan_file.get("test") or {}
    arms = t.get("arms") or []
    want_moves = {c: {"multiplier": m} for c, m in plan["rollout"]["plan"]["multipliers"].items()}
    ok = (t.get("id") == reg["test_id"] and len(arms) == 1
          and sorted(arms[0]["markets"]) == sorted(reg["rollout_markets"]) and arms[0]["moves"] == want_moves
          and str(t.get("start")) == plan["dates"]["start"] and str(t.get("end")) == plan["dates"]["last_week"])
    return {"plan_file": PLAN_FILE.relative_to(REPO).as_posix(), "matches": bool(ok)}


def _did(x: np.ndarray, rollout: np.ndarray, s: int, n: int, gap: int) -> tuple[float, float]:
    """Observed in the rollout markets, and what the holdout's ratio says they would have been."""
    pre, win = H.sums(x, s, n, gap)
    return float(win[rollout].sum()), float(pre[rollout].sum() / pre[~rollout].sum() * win[~rollout].sum())


def plan_rows(path: Path) -> list[tuple]:
    """fct_media_plan_weekly as (week ISO, region, channel, planned, delivered) rows, read-only."""
    import duckdb
    con = duckdb.connect(str(path), read_only=True)
    try:
        return con.execute("select strftime(week_start, '%Y-%m-%d'), region_id, channel_id, planned_spend, spend "
                           "from fct_media_plan_weekly").fetchall()
    finally:
        con.close()


def year_totals(m: Markets) -> dict:
    """Won deals, paid spend (every paid channel) and cost per deal per year, weeks by their Monday."""
    out = {}
    all_spend = sum(m.spend.values())
    for y in (2025, 2026):
        t = m.weeks.year == y
        deals, spend = float(m.deals[t].sum()), float(all_spend[t].sum())
        out[str(y)] = {"weeks": int(t.sum()), "won_deals": deals, "paid_spend": spend,
                       "cost_per_deal": spend / deals}
    a, b = out["2025"], out["2026"]
    out["change_pct"] = {k: 100 * (b[k] / a[k] - 1) for k in ("won_deals", "paid_spend", "cost_per_deal")}
    return out


def results(plan: dict, m: Markets, plan_file: dict, warehouse: Path) -> dict:
    reg = plan["holdout"]
    start = m.week_index(plan["dates"]["start"])
    n, gap = reg["window_weeks"], reg["gap_weeks"]
    if start + n != len(m.weeks):
        raise ValueError("the year-end cut must end with the rollout's last week")
    if m.weeks[-1] > pd.Timestamp(reg["readout_snapshot"]):
        raise ValueError("data past the readout snapshot")
    rollout = np.isin(m.regions, reg["rollout_markets"])
    if sorted(np.array(m.regions)[~rollout]) != sorted(reg["holdout"]):
        raise ValueError("holdout markets do not match the registration")

    pre, win = H.sums(m.deals, start, n, gap)
    lift = H.lift(pre, win, rollout)
    sd = reg["placebo"]["sd_used"]
    low, high = lift - E.Z_90 * sd, lift + E.Z_90 * sd
    r = pre[rollout].sum() / pre[~rollout].sum()

    mult = plan["rollout"]["plan"]["multipliers"]
    ratios = H.plan_ratios(plan_rows(warehouse), reg["rollout_markets"], plan["dates"]["start"],
                           plan["dates"]["last_week"])
    moves = H.plan_check(ratios, mult, reg["rollout_markets"])
    pc = plan_check(plan, plan_file)
    valid = pc["matches"] and moves["passes"]
    forecast = reg["forecast"]
    decision = H.decide(lift, low, high, forecast["mean"], valid)

    b_obs, b_cf = _did(m.spend[BRAND_SEARCH], rollout, start, n, gap)
    all_spend = sum(m.spend.values())
    sp, dl = all_spend[start:start + n], m.deals[start:start + n]
    names = json.loads(DESIGN.read_text(encoding="utf-8"))["market_names"]
    out = {
        "test_id": reg["test_id"], "readout_snapshot": reg["readout_snapshot"],
        "data_cut": {"warehouse": f"data/cut_{reg['readout_snapshot']}/data/warehouse.duckdb",
                     "first_week": str(m.weeks[0].date()), "last_week": str(m.weeks[-1].date())},
        "window": {"start": plan["dates"]["start"], "end": reg["window"][1], "weeks": n,
                   "pre_period": reg["pre_period"]},
        "markets": {"rollout": reg["rollout_markets"], "holdout": reg["holdout"],
                    "holdout_names": [names[c] for c in reg["holdout"]]},
        "measured": {"method": "standing holdout", "lift": lift, "interval_90": [low, high], "sd": sd,
                     "window_deals_rollout": float(win[rollout].sum()),
                     "window_deals_holdout": float(win[~rollout].sum()),
                     "holdout_scaled": float(r * win[~rollout].sum()), "pre_period_ratio": float(r)},
        "registered": {"power_at_forecast": reg["power_at_forecast"],
                       "smallest_detectable_lift": reg["smallest_detectable_lift"],
                       "forecast": forecast},
        "decision": decision,
        "validity": {"plan": pc, "moves": moves, "valid": bool(valid)},
        "secondary": {
            "brand_search_spend_change": b_obs - b_cf,
            "blended_cost_per_deal_in_window": {"rollout_markets": float(sp[:, rollout].sum() / dl[:, rollout].sum()),
                                                "holdout_markets": float(sp[:, ~rollout].sum() / dl[:, ~rollout].sum())},
            "paid_spend_in_window": {"rollout_markets": float(sp[:, rollout].sum()),
                                     "holdout_markets": float(sp[:, ~rollout].sum())},
        },
        "exploratory": {"placebo_mean_removed": {"placebo_mean": reg["placebo"]["mean"],
                                                 "lift": lift - reg["placebo"]["mean"]}},
        "year": year_totals(m),
    }
    if MODEL_VIEW.exists():
        out["model_view"] = json.loads(MODEL_VIEW.read_text(encoding="utf-8"))
    return out


def _money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def _n(x: float) -> str:
    return f"{x:+,.0f}"


def results_md(d: dict) -> str:
    mz, dec, reg, v = d["measured"], d["decision"], d["registered"], d["validity"]
    f = reg["forecast"]
    lo, hi = mz["interval_90"]
    y = d["year"]
    sec = d["secondary"]
    lines = [
        f"# Results: the 2026 rollout ({d['test_id']})", "",
        f"Written by `python -m rollout.results` from `rollout/outputs/results.json`; every number below comes "
        f"from that file. Data: the {d['readout_snapshot']} cut, weeks {d['data_cut']['first_week']} to "
        f"{d['data_cut']['last_week']}. Method, markets, window and rules: [PLAN.md](PLAN.md), registered in May, "
        "unchanged.", "",
        "## The readout", "",
        "| What | Extra deals in the rollout markets, " + f"{d['window']['start']} to {d['window']['end']} |",
        "|---|---:|",
        f"| Measured: 15 rollout markets against the 5 holdout markets (90% interval) | {_n(mz['lift'])} "
        f"({_n(lo)} to {_n(hi)}) |",
        f"| May forecast, refit MMM (90% range) | {_n(f['mean'])} ({_n(f['hdi_90'][0])} to {_n(f['hdi_90'][1])}) |",
        "",
        f"The rollout markets closed {mz['window_deals_rollout']:,.0f} deals in the window. The holdout markets "
        f"closed {mz['window_deals_holdout']:,.0f}, and scaled by their ratio before the spring test they point "
        f"to {mz['holdout_scaled']:,.0f}.", "",
        "## The rules, as registered", "",
        f"1. **Does the rollout work?** {'Yes: the interval is above zero.' if dec['rule_1_rollout_works'] else 'Not shown: the interval reaches zero.'}",
        f"2. **Against the forecast:** the readout {dec['rule_2_against_forecast']} ({_n(f['mean'])}).",
    ]
    if dec["rule_3_not_clear"]:
        lines.append(f"3. **Not clear.** The interval, {_n(lo)} to {_n(hi)}, reaches zero. The holdout had "
                     f"{reg['power_at_forecast']:.0%} power at the forecast, so this was the likely read even if "
                     "the forecast is right. It is not evidence the plan failed; a clear drop would be.")
    elif dec["rule_3_drop_is_clear"]:
        lines.append("3. **A clear drop.** The whole interval is below zero: the rollout cost deals.")
    else:
        lines.append(f"3. **Clear.** The interval does not reach zero, though the holdout had only "
                     f"{reg['power_at_forecast']:.0%} power at the forecast.")
    mv = d.get("model_view")
    if mv:
        a, b = mv["deal_change_in_window"]["hdi_90"]
        lines.append(f"4. **Cross-check (decides nothing):** the refit MMM, scoring the realized 2026 spend with "
                     f"and without the rollout's moves, puts the gain at {_n(mv['deal_change_in_window']['mean'])} "
                     f"({_n(a)} to {_n(b)}) in the same markets and weeks.")
    else:
        lines.append("4. **Cross-check (decides nothing):** run `python -m rollout.crosscheck` for the model's view.")
    mv_ = v["moves"]
    lines += [
        f"5. **Validity: the readout {'stands' if v['valid'] else 'is void'}.** The plan file "
        f"{'matches' if v['plan']['matches'] else 'does not match'} the registration. Every moved channel's "
        f"delivered spend {'sits' if mv_['passes'] else 'does not sit'} nearer to its new budget line than to the "
        "old one in the rollout markets, with the holdout on the old line"
        + (f"; named, never void: {', '.join(sorted({x['market'] + ' ' + x['channel'] for x in mv_['named_markets']}))}."
           if mv_["named_markets"] else "; no market missed."), "",
        "## The year", "",
        "| | 2025 | 2026 | Change |", "|---|---:|---:|---:|",
        f"| Won deals | {y['2025']['won_deals']:,.0f} | {y['2026']['won_deals']:,.0f} | "
        f"{y['change_pct']['won_deals']:+.1f}% |",
        f"| Paid spend | {_money(y['2025']['paid_spend'])} | {_money(y['2026']['paid_spend'])} | "
        f"{y['change_pct']['paid_spend']:+.1f}% |",
        f"| Cost per deal | {_money(y['2025']['cost_per_deal'])} | {_money(y['2026']['cost_per_deal'])} | "
        f"{y['change_pct']['cost_per_deal']:+.1f}% |", "",
        f"Weeks by their Monday: {y['2025']['weeks']} in 2025 and {y['2026']['weeks']} in 2026. Paid spend counts "
        "all 9 paid channels. These totals hold everything that moved in 2026: the spring test, the rollout, sales "
        "headcount, the market and the season. They do not measure the rollout; the holdout does.", "",
        "## Cost (secondary)", "",
        f"- **Brand search that followed the extra searches:** {_money(sec['brand_search_spend_change'])} in the "
        "rollout markets, by the ratio method.",
        f"- **Blended cost per deal in the window:** rollout markets "
        f"{_money(sec['blended_cost_per_deal_in_window']['rollout_markets'])}, holdout markets "
        f"{_money(sec['blended_cost_per_deal_in_window']['holdout_markets'])}.",
        "", "## Delivered against the media plan, rollout weeks", "",
        "| Channel | Move | Rollout markets: delivered / new line | Line | Holdout: delivered / old line |",
        "|---|---:|---:|---:|---:|",
    ]
    for c, r in mv_["channels"].items():
        lines.append(f"| {c} | x{r['multiplier']:.2f} | {r['rollout_ratio']:.3f} | {r['rollout_line']:.3f} | "
                     f"{r['holdout_ratio']:.3f} |")
    lines.append("")
    lines.append("A move shows when delivered over planned sits nearer, in logs, to 1 than to the old line over the "
                 "new one (the line is halfway, in logs).")
    ex = d["exploratory"]["placebo_mean_removed"]
    lines += ["", "## Exploratory (does not decide)", "",
              f"- **Placebo mean removed:** the placebo windows erred by {_n(ex['placebo_mean'])} on average; "
              f"taking that out gives {_n(ex['lift'])}.", ""]
    return "\n".join(lines)


def main() -> int:
    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    wh = cut_warehouse(plan)
    m = load(wh)
    plan_file = yaml.safe_load(PLAN_FILE.read_text(encoding="utf-8"))
    out = results(plan, m, plan_file, wh)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    RESULTS_MD.write_text(results_md(out), encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("measured", "decision", "year")}, indent=1))
    print(out["validity"]["valid"], out["validity"]["moves"]["named_markets"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
