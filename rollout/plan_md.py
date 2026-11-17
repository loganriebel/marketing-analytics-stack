"""Write rollout/PLAN.md from rollout/outputs/plan.json. Pure Python.

    python -m rollout.plan_md
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN_JSON = REPO / "rollout" / "outputs" / "plan.json"
PLAN_MD = REPO / "rollout" / "PLAN.md"
NAMES = {"paid_search_nonbrand": "non-brand search", "meta": "Meta", "linkedin": "LinkedIn", "youtube": "YouTube",
         "ctv": "connected TV", "display": "display retargeting", "affiliates": "affiliates"}


def _money(x: float) -> str:
    return f"-${-x:,.0f}" if x < 0 else f"${x:,.0f}"


def _pct(m: float) -> str:
    return f"{100 * (m - 1):+.0f}%"


def plan_md(d: dict) -> str:
    c, r, h, dt = d["refit_plan_check"], d["rollout"], d["holdout"], d["dates"]
    cm, plan, asis = c["committed"], r["plan"], r["refit_multipliers_as_is"]
    lo, hi = d["bounds"]
    inside = [x for x in cm["levers"] if x["where"] == "inside"]
    capped = [x for x in cm["levers"] if x["where"] == "cap"]
    floor = [x for x in cm["levers"] if x["where"] == "floor"]
    f, fa = plan["deal_change_in_window"], plan["deal_change"]
    pl = h["placebo"]
    lines = [
        "# Rollout plan and holdout registration: RO2026H2", "",
        f"Approved {d['approved']}, before the rollout starts. Written by `python -m rollout.plan` from "
        "`rollout/outputs/plan.json`; every number below comes from that file. Data: the May 2026 cut "
        f"({d['source']['data_cut']}) and the refit MMM.", "",
        "## Why this plan", "",
        "The spring test's rule 3 says the rollout follows the refit model, not the test plan. Rule 4's "
        "guardrails did not trip: YouTube showed a lift, and pulling non-brand search back did not cost more "
        "than modeled. So the refit model's budget optimizer sets the plan, inside the same "
        f"{_pct(lo)} to {_pct(hi)} limits on every channel. The model has never seen a channel moved further, "
        "so the plan does not move one further.", "",
        "## The optimizer's flag", "",
        f"The refit optimizer's solver stopped with `converged: false` (\"{c['solver_message']}\"), with "
        f"{len(capped) + len(floor)} of its {len(cm['levers'])} channels at a limit. That flag was a false alarm. "
        "Rebuilt from the saved posterior, the same curves give the same plan "
        f"({c['rebuilt_deal_change_mean']:,.0f} extra deals over 2023 to 2025), and the plan meets the optimum's "
        "conditions (`mmm.optimize.optimality`):", "",
        f"- The {len(inside)} channels inside their limits ("
        + ", ".join(f"{NAMES[x['channel']]} at {x['multiplier']:.2f}x" for x in inside)
        + f") each earn {cm['price_extra_deals_per_extra_1000_dollars']:.3f} extra deals per extra $1,000, "
          "so no move between them adds deals.",
        "- The channels at the cap earn more ("
        + ", ".join(f"{NAMES[x['channel']]} {x['extra_deals_per_extra_1000_dollars']:.3f}" for x in capped)
        + "), and the channel at the floor earns less ("
        + ", ".join(f"{NAMES[x['channel']]} {x['extra_deals_per_extra_1000_dollars']:.3f}" for x in floor)
        + "). They would move further if the limits allowed.",
        f"- An exact solver (`mmm.optimize.solve_exact`) finds the same plan: "
        f"{c['exact']['deal_change_mean']:,.0f} extra deals.", "",
        f"The limits bind for {len(capped) + len(floor)} channels. That is a choice, not a failure: past them the "
        "model is guessing.", "",
        "## The plan", "",
        f"The refit plan's multipliers were set on 2023 to 2025 spend. 2026 runs on 2025's mix, heavier on "
        f"non-brand search, so the same multipliers would spend {_money(-asis['spend_change'])} less over the "
        "rollout weeks and forecast "
        f"{asis['deal_change_in_window']['mean']:,.0f} extra deals. So the same objective, posterior and limits "
        f"are solved again on the rollout's own weeks and markets, at the same total, with last year's same weeks "
        f"({r['proxy_weeks']}) as the stand-in for 2026 spend:", "",
        "| Channel | Move | Spend now (stand-in weeks) | Change | Extra deals in the window |",
        "|---|---:|---:|---:|---:|",
    ]
    for x in plan["by_channel"]:
        lines.append(f"| {NAMES[x['channel']]} | {x['multiplier']:.2f}x ({_pct(x['multiplier'])}) | "
                     f"{_money(x['spend_now'])} | {_money(x['spend_change'])} | "
                     f"{x['deal_change_in_window']['mean']:+,.0f} |")
    lines += [
        "",
        f"- **Dates:** the {dt['weeks']} weeks from {dt['start']} through the week of {dt['last_week']}.",
        f"- **Markets:** the {len(h['rollout_markets'])} rollout markets. Brand search is not a lever; it follows "
        f"searches, and the plan's upper-funnel moves add about {_money(plan['brand_search_spend_change'])} of it.",
        f"- **Net spend change:** {_money(plan['spend_change'])} (rounding the multipliers).",
        f"- **Check:** the solved plan meets the optimum's conditions "
        f"({'yes' if r['solved']['check']['optimum'] else 'no'}).",
        f"- **Why it differs from the refit plan:** in 2025's mix LinkedIn and affiliates had been cut back, so "
        "their next dollar is cheaper than on the 2023 to 2025 average, and the model now grows them.", "",
        "## Forecast", "",
        f"In the {len(h['rollout_markets'])} rollout markets, the refit model expects "
        f"{f['mean']:+,.0f} extra deals closing inside the rollout weeks "
        f"(90% range {f['hdi_90'][0]:+,.0f} to {f['hdi_90'][1]:+,.0f}), and {fa['mean']:+,.0f} "
        f"({fa['hdi_90'][0]:+,.0f} to {fa['hdi_90'][1]:+,.0f}) counting deals that close after the year ends. "
        "The always-on channels never pause, so the model is likely to under-credit paid media, and the "
        "forecast may run low.", "",
        "## How we'll know: the holdout readout, registered now", "",
        f"- **Holdout:** {', '.join(h['holdout'])} stay on the old plan all year. They are the spring test's "
        "\"neither\" cell, untouched by either arm, and hold "
        f"{100 * (1 - h['rollout_share_of_pre_period_deals']):.0f}% of deals.",
        f"- **Metric:** won deals, all sources, by close week, summed over the {h['window_weeks']} rollout weeks "
        f"({h['window'][0]} to {h['window'][1]}).",
        f"- **Estimator:** the spring test's ratio difference-in-differences with one arm: rollout-market deals "
        f"minus holdout deals scaled by their ratio in the {h['pre_period_weeks']} weeks before the spring test "
        f"({h['pre_period'][0]} to {h['pre_period'][1]}), so the test's own effect cannot leak in.",
        f"- **Interval:** 90%, from {pl['windows']} placebo windows with the same shape on weeks before the spring "
        f"test ({pl['first_start']} to {pl['last_start']} starts). Placebo error "
        + " / ".join(f"{v:,.0f} ({k} starts)" for k, v in pl["rms_by_start_year"].items())
        + f", count-noise floor {pl['count_noise_floor']:,.0f}; the sd used is {pl['sd_used']:,.0f} deals.",
        f"- **Power:** the smallest lift it can reliably see is {h['smallest_detectable_lift']:,.0f} deals. At the "
        f"forecast it has **{h['power_at_forecast']:.0%} power**. A \"not clear\" result is the likely read even if "
        "the plan works as forecast.",
        f"- **Readout:** from the {h['readout_snapshot']} data cut.", "",
        "**Rules:**", "",
    ]
    lines += [f"{i}. {t}" for i, t in enumerate(h["rules"], 1)]
    return "\n".join(lines) + "\n"


def main() -> int:
    PLAN_MD.write_text(plan_md(json.loads(PLAN_JSON.read_text(encoding="utf-8"))), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
