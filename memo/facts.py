"""Facts pack for the step 5 funding memo.

Reads mmm/outputs/ and nothing else, and writes memo/outputs/facts.json: every
number the memo may use, each with an id, value, unit and source file. The memo
writer sees only this file, and memo/grounding.py checks the memo against it.

* "A year" is the average year of the MMM window (156 weeks = 3 years at
  2023 to 2025 spend). The MMM scores whole-window spend paths, so a per-year
  number is the window number divided by 3. That is exact for means and for
  90% ranges, because it rescales every posterior draw the same way.
* Ranges are the MMM's 90% HDIs. A few derived ranges (revenue, payback, cost
  per extra deal) map a deal range through a fixed formula; `how` says so.
* Deal changes use posterior means (the optimizer's objective, and means add
  up). Channel CPAs and deals use medians, as docs/mmm/README.md does.
* kind: estimate (an MMM output), input (spend or observed deals the MMM used),
  derived (arithmetic on outputs, shown in `how`), design (the test plan,
  from the MMM's "Limits and next steps").

    python -m memo.facts
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MMM_OUT = REPO / "mmm" / "outputs"
OUT_DIR = REPO / "memo" / "outputs"
FACTS_PATH = OUT_DIR / "facts.json"

WEEKS_PER_YEAR = 52
MONTHS_PER_YEAR = 12
UPPER_FUNNEL = ("meta", "youtube", "ctv")
NAMES = {
    "paid_search_brand": "brand search",
    "paid_search_nonbrand": "non-brand search",
    "meta": "Meta",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
    "ctv": "connected TV (CTV)",
    "display": "display retargeting",
    "affiliates": "affiliates and partners",
}

# The market test comes from its pre-registered design (python -m geotest.design),
# which also carries the 2024 and 2025 totals from the same December 2025 data cut.
DESIGN = REPO / "geotest" / "outputs" / "design.json"


def _src(name: str) -> str:
    return f"mmm/outputs/{name}"


class Pack:
    def __init__(self):
        self.facts: list[dict] = []
        self._ids: set[str] = set()

    def add(self, id: str, value, unit: str, source: str, field: str, desc: str, kind: str = "estimate",
            low=None, high=None, stat: str | None = None, how: str | None = None) -> None:
        assert id not in self._ids, id
        self._ids.add(id)
        f = {"id": id, "value": _r(value), "unit": unit, "kind": kind, "source": source, "field": field,
             "desc": desc}
        if low is not None or high is not None:
            f["low"], f["high"] = _r(low), _r(high)
        if stat:
            f["stat"] = stat
        if how:
            f["how"] = how
        self.facts.append(f)

    def get(self, id: str) -> dict:
        return next(f for f in self.facts if f["id"] == id)


def _r(x):
    return None if x is None else round(float(x), 4)


def _read_json(mmm_out: Path, name: str) -> dict:
    return json.loads((mmm_out / name).read_text(encoding="utf-8"))


def _day(iso: str) -> str:
    """2026-02-02 -> February 2 (a month-day date, exempt from the grounding check)."""
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{d:%B} {d.day}"


def _read_design(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _read_csv(mmm_out: Path, name: str) -> list[dict]:
    with (mmm_out / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build(mmm_out: Path = MMM_OUT, design_path: Path = DESIGN) -> dict:
    ch = _read_json(mmm_out, "channels.json")
    opt = _read_json(mmm_out, "optimizer.json")
    meta = ch["meta"]
    diag_name = f"diagnostics_{meta['fit']}.json"
    diag = _read_json(mmm_out, diag_name)
    curves = _read_csv(mmm_out, "response_curves_total.csv")
    CH, OPT, DIAG, CURVE = _src("channels.json"), _src("optimizer.json"), _src(diag_name), \
        _src("response_curves_total.csv")

    weeks = meta["train_weeks"] + meta["holdout_weeks"]
    years = weeks / WEEKS_PER_YEAR
    per_year = f"window total / {years:g} years"
    s, chans = ch["summary"], ch["channels"]
    p = Pack()

    # Context
    p.add("markets", meta["regions"], "markets", CH, "meta.regions", "Markets in the model", "input")
    p.add("window_weeks", weeks, "weeks", CH, "meta.train_weeks + meta.holdout_weeks",
          "Weeks of data the model covers", "input")
    p.add("window_years", years, "years", CH, "meta", "Years of data the model covers", "derived",
          how=f"{weeks} weeks / {WEEKS_PER_YEAR}")
    p.add("hdi_prob", 100 * meta["hdi_prob"], "percent", CH, "meta.hdi_prob",
          "Every range is a 90% range: the model gives 90% odds the true value is inside", "input")
    hold = diag["diagnostics"]["holdout"]
    p.add("holdout_weeks", hold["weeks"], "weeks", DIAG, "diagnostics.holdout.weeks",
          "Final weeks hidden from the model to test its predictions", "input")
    p.add("holdout_weekly_error", 100 * hold["national_weekly_mape"], "percent", DIAG,
          "diagnostics.holdout.national_weekly_mape",
          "Average miss on weekly national deals in the hidden weeks", "estimate")
    p.add("paid_spend_per_year", s["paid_spend"] / years, "USD", CH, "summary.paid_spend",
          "Paid media spend a year, 8 channels", "input", how=per_year)
    p.add("observed_deals_per_year", s["observed_deals_in_window"] / years, "deals", CH,
          "summary.observed_deals_in_window", "All closed-won deals a year, from every cause", "input",
          how=per_year)
    p.add("blended_cpa", s["blended_cpa"], "USD", CH, "summary.blended_cpa",
          "Paid spend / all deals. Counts deals marketing did not cause", "input")
    d = s["incremental_deals_paid_media"]
    p.add("paid_deals_per_year", d["median"] / years, "deals", CH, "summary.incremental_deals_paid_media",
          "Deals a year that paid media causes", low=d["hdi_90"][0] / years, high=d["hdi_90"][1] / years,
          stat="median", how=per_year)
    d = s["incremental_cpa_paid_media"]
    p.add("paid_cpa", d["median"], "USD", CH, "summary.incremental_cpa_paid_media",
          "Paid media cost per deal it causes (incremental CPA)", low=d["hdi_90"][0], high=d["hdi_90"][1],
          stat="median")
    d = s["paid_media_share_of_deals"]
    p.add("paid_share_of_deals", 100 * d["median"], "percent", CH, "summary.paid_media_share_of_deals",
          "Share of all deals that paid media causes", low=100 * d["hdi_90"][0], high=100 * d["hdi_90"][1],
          stat="median")
    rev = sum(c["roi_revenue"]["mean"] * c["spend"] for c in chans.values())
    deals = sum(c["incremental_deals"]["mean"] for c in chans.values())
    value = rev / deals
    p.add("revenue_per_deal", value, "USD", CH, "channels.*.roi_revenue, spend, incremental_deals",
          "First-year revenue per deal. The MMM values each deal at its market's average won-deal revenue",
          "derived", how="sum(roi_revenue.mean * spend) / sum(incremental_deals.mean) over the 8 channels")

    # Every channel: spend, deals, CPA, cost per extra deal. Upper-funnel channels include
    # the deals they create through brand search, as the optimizer does.
    for c, v in chans.items():
        tot = "_total" if c in UPPER_FUNNEL else ""
        name = NAMES[c]
        p.add(f"{c}_spend_per_year", v["spend"] / years, "USD", CH, f"channels.{c}.spend",
              f"{name}: spend a year", "input", how=per_year)
        d = v[f"incremental_deals{tot}"]
        p.add(f"{c}_deals_per_year", d["median"] / years, "deals", CH, f"channels.{c}.incremental_deals{tot}",
              f"{name}: deals a year it causes", low=d["hdi_90"][0] / years, high=d["hdi_90"][1] / years,
              stat="median", how=per_year)
        d = v[f"cpa{tot}"]
        p.add(f"{c}_cpa", d["median"], "USD", CH, f"channels.{c}.cpa{tot}", f"{name}: cost per deal (CPA)",
              low=d["hdi_90"][0], high=d["hdi_90"][1], stat="median")
        d = v[f"marginal_cpa{tot}"]
        p.add(f"{c}_mcpa", d["median"], "USD", CH, f"channels.{c}.marginal_cpa{tot}",
              f"{name}: cost per extra deal from the next dollar (marginal CPA)",
              low=d["hdi_90"][0], high=d["hdi_90"][1], stat="median")
    best = min(chans, key=lambda c: p.get(f"{c}_mcpa")["value"])

    # Variant A: the optimizer's same-budget reallocation.
    plan = {r["channel"]: r for r in opt["plan"]}
    dc = opt["deal_change"]
    p.add("realloc_budget_per_year", opt["total_spend"] / years, "USD", OPT, "total_spend",
          "Budget a year on the channels the plan can move (all but brand search). Stays the same",
          "input", how=per_year)
    moved = sum(r["spend_change"] for r in opt["plan"] if r["spend_change"] > 0)
    p.add("realloc_moved_per_year", moved / years, "USD", OPT, "plan[].spend_change",
          "Spend moved a year from the cut channels to the grown ones", "derived",
          how="sum of positive spend_change / window years")
    p.add("realloc_deals_per_year", dc["mean"] / years, "deals", OPT, "deal_change",
          "Extra deals a year from the reallocation", low=dc["hdi_90"][0] / years,
          high=dc["hdi_90"][1] / years, stat="mean", how=per_year)
    d = opt["deal_change_pct_of_paid_incremental"]
    p.add("realloc_deals_pct_of_paid", d["mean"], "percent", OPT, "deal_change_pct_of_paid_incremental",
          "Extra deals as a share of the deals paid media causes today", low=d["hdi_90"][0],
          high=d["hdi_90"][1], stat="mean")
    p.add("realloc_prob_gain", 100 * opt["prob_gain_positive"], "percent", OPT, "prob_gain_positive",
          "Odds the reallocation adds deals at all")
    rf = p.get("realloc_deals_per_year")
    p.add("realloc_revenue_per_year", rf["value"] * value, "USD", OPT, "deal_change",
          "Extra first-year revenue a year", "derived", low=rf["low"] * value, high=rf["high"] * value,
          how="realloc_deals_per_year (and its range) x revenue_per_deal")
    brand = opt["brand_search_spend_change"] / years
    p.add("realloc_brand_search_per_year", brand, "USD", OPT, "brand_search_spend_change",
          "Extra brand-search spend a year: more people search for Fernhook by name after more "
          "upper-funnel ads, and brand search is always on, so its spend follows", "estimate", how=per_year)
    rv = p.get("realloc_revenue_per_year")
    p.add("realloc_payback_months", MONTHS_PER_YEAR * brand / rv["value"], "months", OPT,
          "brand_search_spend_change, deal_change", "Months of extra revenue to cover the only new cost, "
          "the extra brand-search spend", "derived",
          low=MONTHS_PER_YEAR * brand / rv["high"], high=MONTHS_PER_YEAR * brand / rv["low"] if rv["low"] > 0 else None,
          how="12 x realloc_brand_search_per_year / realloc_revenue_per_year; range from the revenue range")
    for c, r in plan.items():
        name = NAMES[c]
        p.add(f"realloc_{c}_spend_change_per_year", r["spend_change"] / years, "USD", OPT,
              f"plan[{c}].spend_change", f"{name}: spend change a year (negative = cut)", "estimate",
              how=per_year)
        p.add(f"realloc_{c}_change_pct", 100 * (r["multiplier"] - 1), "percent", OPT, f"plan[{c}].multiplier",
              f"{name}: spend change in percent (negative = cut)", "estimate", how="100 x (multiplier - 1)")
        d = r["deal_change"]
        p.add(f"realloc_{c}_deals_per_year", d["mean"] / years, "deals", OPT, f"plan[{c}].deal_change",
              f"{name}: deal change a year from its move (negative = lost)", low=d["hdi_90"][0] / years,
              high=d["hdi_90"][1] / years, stat="mean", how=per_year)
    cuts = [c for c, r in plan.items() if r["spend_change"] < 0]
    grows = [c for c, r in plan.items() if r["spend_change"] > 0]
    p.add("channels", len(chans), "channels", CH, "channels", "Paid media channels in the model", "input")
    p.add("realloc_cut_channels", len(cuts), "channels", OPT, "plan[].spend_change", "Channels the plan cuts",
          "derived")
    p.add("realloc_grow_channels", len(grows), "channels", OPT, "plan[].spend_change", "Channels the plan grows",
          "derived")
    levels = [100 * plan[c]["multiplier"] for c in cuts]
    p.add("realloc_cut_levels", None, "percent", OPT, "plan[].multiplier",
          "The cut channels run at this share of today's spend", "derived", low=min(levels), high=max(levels),
          how="lowest and highest 100 x multiplier among the cut channels")
    loss = -sum(plan[c]["deal_change"]["mean"] for c in cuts) / years
    p.add("realloc_cut_loss_per_year", loss, "deals", OPT, "plan[].deal_change",
          "Deals a year the model expects the cuts to cost", "derived", stat="mean",
          how="minus the sum of the cut channels' deal_change.mean / window years")
    flighted = [c for c in ("youtube", "ctv") if c in grows]
    p.add("realloc_gain_flighted_per_year", sum(plan[c]["deal_change"]["mean"] for c in flighted) / years,
          "deals", OPT, "plan[].deal_change", "Deals a year the plan gains on YouTube and CTV, the channels "
          "with on and off flights the model can measure", "derived", stat="mean",
          how="sum of youtube and ctv deal_change.mean / window years")

    # Variant B: more budget for the channel with the lowest cost per extra deal, sized on
    # its response curve up to the optimizer's 1.5x limit, where the plan also puts it.
    yt = plan[best]
    m = yt["multiplier"]
    ask, ask_brand = yt["spend_change"] / years, yt["brand_search_spend_change"] / years
    name = NAMES[best]
    p.add("ask_spend_per_year", ask, "USD", OPT, f"plan[{best}].spend_change",
          f"Extra {name} budget a year, on top of today's mix", "estimate", how=per_year)
    p.add("ask_change_pct", 100 * (m - 1), "percent", OPT, f"plan[{best}].multiplier",
          f"{name} spend increase in percent", "estimate", how="100 x (multiplier - 1)")
    p.add("ask_share_of_paid_budget", 100 * ask / p.get("paid_spend_per_year")["value"], "percent", OPT,
          f"plan[{best}].spend_change, channels.json summary.paid_spend", "The ask as a share of paid media spend",
          "derived", how="100 x ask_spend_per_year / paid_spend_per_year")
    p.add("ask_spend_after_per_year", yt["spend_plan"] / years, "USD", OPT, f"plan[{best}].spend_plan",
          f"{name} spend a year after the ask", "estimate", how=per_year)
    p.add("ask_brand_search_per_year", ask_brand, "USD", OPT, f"plan[{best}].brand_search_spend_change",
          "Extra brand-search spend a year that follows the extra searches", "estimate", how=per_year)
    d = yt["deal_change"]
    p.add("ask_deals_per_year", d["mean"] / years, "deals", OPT, f"plan[{best}].deal_change",
          f"Extra deals a year from the {name} ask", low=d["hdi_90"][0] / years, high=d["hdi_90"][1] / years,
          stat="mean", how=per_year + "; the optimizer scored this exact multiplier on every draw")
    af = p.get("ask_deals_per_year")
    p.add("ask_revenue_per_year", af["value"] * value, "USD", OPT, f"plan[{best}].deal_change",
          "Extra first-year revenue a year from the ask", "derived", low=af["low"] * value,
          high=af["high"] * value, how="ask_deals_per_year (and its range) x revenue_per_deal")
    cost = ask + ask_brand
    p.add("ask_cost_per_deal", cost / af["value"], "USD", OPT, f"plan[{best}]",
          "Cost per extra deal from the ask, counting the extra brand-search spend", "derived",
          low=cost / af["high"], high=cost / af["low"],
          how="(ask_spend_per_year + ask_brand_search_per_year) / ask_deals_per_year; range from the deal range")
    cf = p.get("ask_cost_per_deal")
    p.add("ask_payback_months", MONTHS_PER_YEAR * cf["value"] / value, "months", OPT, f"plan[{best}]",
          "Months of first-year revenue from the extra deals to repay the ask", "derived",
          low=MONTHS_PER_YEAR * cf["low"] / value, high=MONTHS_PER_YEAR * cf["high"] / value,
          how="12 x ask_cost_per_deal / revenue_per_deal; range from the deal range")
    # The response curve in steps: each step of the same size buys fewer deals.
    rows = {round(float(r["spend_multiplier"]), 4): r for r in curves if r["channel"] == best}
    created = chans[best]["brand_search_spend_created"]
    grid = [1.0] + [x for x in sorted(rows) if 1.0 < x <= 2.0]
    for k, (a, b) in enumerate(zip(grid, grid[1:]), 1):
        dd = float(rows[b]["incremental_deals_total_mean"]) - float(rows[a]["incremental_deals_total_mean"])
        ds = float(rows[b]["spend"]) - float(rows[a]["spend"])
        p.add(f"ask_step{k}_spend_per_year", ds / years, "USD", CURVE, f"{best} x{a:g} to x{b:g}",
              f"{name} response curve, step {k}: added spend a year from {a:g}x to {b:g}x today's",
              "derived", how=per_year)
        p.add(f"ask_step{k}_deals_per_year", dd / years, "deals", CURVE, f"{best} x{a:g} to x{b:g}",
              f"{name} response curve, step {k}: added deals a year", "derived", stat="mean", how=per_year)
        p.add(f"ask_step{k}_cost_per_deal", (ds + created * (b - a)) / dd, "USD", CURVE,
              f"{best} x{a:g} to x{b:g}; channels.json {best}.brand_search_spend_created",
              f"{name} response curve, step {k}: cost per added deal, counting extra brand-search spend"
              + ("" if b <= opt["bounds"][1] else ". Past the optimizer's limit"), "derived",
              how="(step spend + brand_search_spend_created x step) / step deals")

    # The market test, as designed and pre-registered from 2023 to 2025 data (geotest/).
    dz = _read_design(design_path)
    D = "geotest/outputs/design.json"
    ga, fc, dt = dz["arms"]["grow"], dz["forecast"], dz["dates"]
    p.add("test_markets", sum(len(v) for v in dz["cells"].values()), "markets", D, "cells",
          "Markets in the test: every market is in it", "design")
    p.add("test_arm_markets", len(ga["markets"]), "markets", D, "arms.grow.markets",
          "Markets in each half of the test (each half is compared with the other markets)", "design")
    p.add("test_weeks", dt["test_weeks"], "weeks", D, "dates.test_weeks", "Test length", "design")
    p.add("test_tail_weeks", dt["tail_weeks"], "weeks", D, "dates.tail_weeks",
          "Weeks after the test in which its deals are still counted, because deals close a few weeks after the lead",
          "design")
    p.add("test_window_weeks", dt["window_weeks"], "weeks", D, "dates.window_weeks",
          "Weeks of deals the readout counts", "design")
    p.add("test_grow_step", ga["value"], "USD", D, "arms.grow.value",
          "Extra YouTube spend a week in each grow market, per unit of market size (an average market is one unit)",
          "design")
    p.add("test_grow_spend", fc["grow"]["spend_change"], "USD", D, "forecast.grow.spend_change",
          "Extra YouTube spend over the test, all grow markets", "design")
    p.add("test_cut_saving", -fc["cut"]["spend_change"], "USD", D, "forecast.cut.spend_change",
          "Spend not spent on the cut channels over the test, all cut markets (last year's same weeks)", "design")
    p.add("test_net_cost", fc["grow"]["spend_change"] + fc["cut"]["spend_change"], "USD", D, "forecast",
          "Net extra spend for the whole test: the YouTube push minus what the cuts save", "derived",
          how="test_grow_spend - test_cut_saving")
    g, c = fc["grow"], fc["cut"]
    p.add("test_grow_forecast", g["lift_mean"], "deals", D, "forecast.grow.lift_mean",
          "Extra deals the MMM expects from the YouTube push in the readout window", "estimate",
          low=g["lift_hdi_90"][0], high=g["lift_hdi_90"][1], stat="mean")
    base = dz["window_deals_last_year"]["grow_markets"]
    p.add("test_grow_forecast_pct", 100 * g["lift_mean"] / base, "percent", D, "forecast.grow, window_deals_last_year",
          "That lift as a share of the grow markets' deals in the same weeks last year", "derived",
          how="100 x test_grow_forecast / grow markets' deals in last year's window")
    p.add("test_grow_cost_per_deal", g["cost_per_extra_deal"], "USD", D, "forecast.grow.cost_per_extra_deal",
          "The MMM's expected cost per extra deal from the YouTube push, at the test's spend level", "estimate")
    p.add("test_cut_forecast", c["lift_mean"], "deals", D, "forecast.cut.lift_mean",
          "Deals the MMM expects the cuts to cost in the readout window (negative = lost)", "estimate",
          low=c["lift_hdi_90"][0], high=c["lift_hdi_90"][1], stat="mean")
    p.add("test_grow_bar", dz["mde"]["grow"], "deals", D, "mde.grow",
          "Smallest YouTube lift the test can reliably see (80% power), from placebo tests on 2023 to 2025 data",
          "design")
    p.add("test_grow_power", 100 * g["power"], "percent", D, "forecast.grow.power",
          "Odds the test sees the YouTube lift if the model is right", "design")
    p.add("test_cut_bar", dz["mde"]["cut"], "deals", D, "mde.cut",
          "Smallest drop from the cuts the test can reliably see (80% power)", "design")
    p.add("test_cut_power", 100 * c["power"], "percent", D, "forecast.cut.power",
          "Odds the test sees the cuts' drop if the model is right", "design")
    p.add("test_cut_multiple", c["multiple_of_forecast_for_80pct_power"], "multiplier", D,
          "forecast.cut.multiple_of_forecast_for_80pct_power",
          "How many times the model's expected drop the cuts must cost for the test to reliably see it", "design")
    short = next(r for r in dz["durations"] if r["test_weeks"] < dt["test_weeks"])
    p.add("test_short_weeks", short["test_weeks"], "weeks", D, "durations", "A shorter test that was considered",
          "design")
    p.add("test_short_power", 100 * short["grow"]["power"], "percent", D, "durations",
          "Odds a test that short would see the YouTube lift if the model is right", "design")

    # Context: the problem, from the same December 2025 data cut.
    by = dz["data_cut"]["by_year"]
    for y in ("2024", "2025"):
        v = by[y]
        p.add(f"deals_{y}", v["won_deals"], "deals", D, f"data_cut.by_year.{y}.won_deals",
              f"Closed-won deals in {y} (weeks by their Monday)", "input")
        p.add(f"paid_spend_{y}", v["paid_spend"], "USD", D, f"data_cut.by_year.{y}.paid_spend",
              f"Paid media spend in {y}, all 9 paid channels", "input")
        p.add(f"cost_per_deal_{y}", v["cost_per_deal"], "USD", D, f"data_cut.by_year.{y}.cost_per_deal",
              f"Blended cost per deal in {y}: paid spend / all deals", "input")
    for k, unit in (("won_deals", "deals"), ("paid_spend", "spend"), ("cost_per_deal", "cost per deal")):
        p.add(f"{k}_change_pct", 100 * (by["2025"][k] / by["2024"][k] - 1), "percent", D, f"data_cut.by_year.*.{k}",
              f"Change in {unit} from 2024 to 2025", "derived", how="100 x (2025 / 2024 - 1)")

    pack = {
        "meta": {
            "built_by": "memo/facts.py",
            "reads": sorted({f["source"] for f in p.facts}),
            "fit": meta["fit"],
            "window": meta["window"],
            "years_in_window": years,
            "a_year_means": "the average year of the window, at 2023 to 2025 spend",
            "hdi_prob": meta["hdi_prob"],
            "units": "USD; deals; percent (already x100); weeks; months; markets; channels; years; multiplier",
        },
        "channel_names": NAMES,
        "facts": p.facts,
        "variants": {
            "reallocation": {
                "what": "Same total budget. Grow the channels the model rates best, cut the ones it rates worst.",
                "grows": grows, "cuts": cuts,
                "moves": [{"channel": c, "multiplier": _r(plan[c]["multiplier"]),
                           "curve": "total" if c in UPPER_FUNNEL else "direct"} for c in plan],
                "deals_fact": "realloc_deals_per_year",
            },
            "youtube_ask": {
                "what": f"New money: grow {name}, the channel with the lowest cost per extra deal, by the "
                        "largest step the optimizer allows. Every other channel stays as it is.",
                "channel": best,
                "moves": [{"channel": best, "multiplier": _r(m), "curve": "total" if best in UPPER_FUNNEL else "direct"}],
                "deals_fact": "ask_deals_per_year",
            },
        },
        "risks": [
            {"id": "wide_ranges", "text": "The ranges are wide. The plan's range runs from a small gain to a "
             "large one, and the always-on channels' costs per deal span a wide band.",
             "facts": ["realloc_deals_per_year", "linkedin_cpa", "display_cpa", "affiliates_cpa"]},
            {"id": "always_on_not_measured", "text": "Non-brand search, LinkedIn, display and affiliates run every "
             "week in every market and never pause, so the data never show what happens without them. Their "
             "numbers lean on the model's starting assumptions. Every cut in the plan lands on these channels.",
             "facts": ["realloc_cut_loss_per_year", "realloc_cut_levels"]},
            {"id": "meta_season", "text": "Meta pushes into the busy seasons in every market, the same weeks fleets "
             "shop anyway, so the model cannot tell Meta's effect from the season. Meta's range runs from "
             "almost nothing to a lot, and the plan grows Meta.",
             "facts": ["meta_deals_per_year", "realloc_meta_change_pct"]},
            {"id": "paid_under_credited", "text": "Paid media is likely under-credited. On simulated worlds with a "
             "known answer, this kind of model gave always-on channels too little credit until a test anchored "
             "them. If so, the cuts cost more than shown, and the plan's gain is smaller.",
             "facts": ["paid_share_of_deals"]},
            {"id": "fit_is_not_proof", "text": "The model predicts weekly deals well on weeks it never saw, but a "
             "model can predict the total well and still split it wrongly between channels.",
             "facts": ["holdout_weeks", "holdout_weekly_error"]},
            {"id": "youtube_ask_scale", "text": "The YouTube ask rests on YouTube's on and off flights, the best "
             "measured channel. Each step up buys fewer deals than the last, and the model has not seen YouTube "
             "much past the size of the ask.",
             "facts": ["ask_step1_cost_per_deal", "ask_step2_cost_per_deal"]},
        ],
        "test": {
            "what": "A spring market test of both sides of the plan at once. In one group of markets, YouTube "
                    "runs far above plan, a level the model has never seen. In a crossing group, LinkedIn, display "
                    "and affiliates go dark. Each group is measured against the markets outside it, so every market "
                    "counts for both. Markets were matched by size and picked by how well they tracked each other "
                    "in past placebo tests.",
            "decision_rule": "Rules written down before the test: YouTube works if its lift is clearly positive. "
                             "The cuts cost more than modeled if their drop is clearly bigger than the model expects; "
                             "then no cut channel goes below today's spend. Either way, the result goes into the model "
                             "as a lift test, the model is refit, and the rollout follows the refit model.",
            "limits": "The YouTube group is sized to see the lift the model expects. The cut group is a guardrail: it "
                      "only sees the cuts if they cost far more than the model thinks. YouTube runs far past any "
                      "level in the data, so the forecast there is a stretch.",
            "readout": "Late May, after the last deals in the window have had time to close.",
            "dates": "Test: {} to {}. Deals counted through {}. Readout from the data as of {}.".format(
                *(_day(dz["dates"][k]) for k in ("test_start", "test_end", "window_end", "readout_snapshot"))),
            "facts": ["test_markets", "test_arm_markets", "test_weeks", "test_tail_weeks", "test_window_weeks",
                      "test_grow_step", "test_grow_spend", "test_cut_saving", "test_net_cost", "test_grow_forecast",
                      "test_grow_forecast_pct", "test_grow_cost_per_deal", "test_cut_forecast", "test_grow_bar",
                      "test_grow_power", "test_cut_bar", "test_cut_power", "test_cut_multiple", "test_short_weeks",
                      "test_short_power"],
        },
        "recommendation": [
            "Now: approve the spring market test. It needs a little new money, because the YouTube push costs more "
            "than the cuts save.",
            "In late May: the test result goes into the model, and the refit model sets the rollout for the rest of "
            "the year. Approve that rollout then, not now.",
            "Not now: the full reallocation. It rests on cuts to channels the data cannot see.",
        ],
    }
    return pack


def write(path: Path = FACTS_PATH, mmm_out: Path = MMM_OUT) -> dict:
    pack = build(mmm_out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8", newline="\n")
    return pack


def main() -> int:
    pack = write()
    print(f"wrote {FACTS_PATH.relative_to(REPO).as_posix()}: {len(pack['facts'])} facts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
