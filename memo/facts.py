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

# The MMM's limits call for a budget test of an always-on channel in a few markets
# at 50% to 70% of plan for 6 to 8 weeks. The memo's test runs the plan's own cuts
# that way, so the channels the model cannot see get tested before the big move.
DESIGN_SOURCE = "docs/mmm/README.md"
TEST_MARKETS = 4
TEST_WEEKS = 8
TEST_WEEKS_RANGE = (6, 8)


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


def _read_csv(mmm_out: Path, name: str) -> list[dict]:
    with (mmm_out / name).open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def build(mmm_out: Path = MMM_OUT) -> dict:
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

    # The test: the plan's cuts, in a few markets, before the full move.
    n = meta["regions"]
    share = TEST_MARKETS / n * TEST_WEEKS / weeks
    p.add("test_markets", TEST_MARKETS, "markets", DESIGN_SOURCE, "Limits and next steps",
          "Markets that run the cuts in the test", "design")
    p.add("test_control_markets", n - TEST_MARKETS, "markets", DESIGN_SOURCE, "Limits and next steps",
          "Markets that stay at today's spend, to compare against", "design")
    p.add("test_weeks", TEST_WEEKS, "weeks", DESIGN_SOURCE, "Limits and next steps", "Test length", "design")
    p.add("test_weeks_range", None, "weeks", DESIGN_SOURCE, "Limits and next steps",
          "Test length the MMM's limits call for", "design", low=TEST_WEEKS_RANGE[0], high=TEST_WEEKS_RANGE[1])
    held = sum(-plan[c]["spend_change"] for c in cuts) * share
    p.add("test_spend_held_back", held, "USD", OPT, "plan[].spend_change",
          "Spend not spent in the test markets during the test (average-size markets)", "derived",
          how=f"cut channels' spend cut x {TEST_MARKETS}/{n} markets x {TEST_WEEKS}/{weeks} weeks")
    base = s["observed_deals_in_window"] * share
    p.add("test_market_deals", base, "deals", CH, "summary.observed_deals_in_window",
          "Deals the test markets close in the test weeks (average-size markets)", "derived",
          how=f"observed deals x {TEST_MARKETS}/{n} x {TEST_WEEKS}/{weeks}")
    drop = loss * years * share
    p.add("test_expected_drop", drop, "deals", OPT, "plan[].deal_change",
          "Deals the model expects the cuts to cost in the test markets during the test", "derived",
          stat="mean", how="the cuts' window deal loss x the test's share of market-weeks (straight-line)")
    p.add("test_expected_drop_pct", 100 * drop / base, "percent", OPT, "plan[].deal_change",
          "That drop as a share of the test markets' deals", "derived", how="100 x test_expected_drop / test_market_deals")
    seen = 2 * base ** 0.5
    p.add("test_detectable_drop", seen, "deals", CH, "summary.observed_deals_in_window",
          "Smallest drop the test can tell from chance: about 2 standard deviations of count noise in the test "
          "markets' deals. It leaves out noise in the matched markets, so the real bar is a little higher",
          "derived", how="2 x sqrt(test_market_deals)")
    p.add("test_detectable_multiple", seen / drop, "multiplier", OPT, "plan[].deal_change",
          "How many times the model's expected drop the test needs to see before it can call the cuts costlier "
          "than the model thinks", "derived", how="test_detectable_drop / test_expected_drop")

    pack = {
        "meta": {
            "built_by": "memo/facts.py",
            "reads": sorted({f["source"] for f in p.facts if f["source"].startswith("mmm/outputs/")}),
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
            "what": "Run the plan's cuts to LinkedIn, display and affiliates in a few markets first, against "
                    "matched markets at today's spend. It costs no new budget and spends a little less.",
            "decision_rule": "If deals in the test markets fall about as much as the model expects, make the full "
                             "reallocation. If they fall clearly more, the model is giving these channels too "
                             "little credit: stop the cuts and refit the model with the test as a lift test.",
            "limits": "The test can catch a large miss, not a small one.",
            "facts": ["test_markets", "test_control_markets", "test_weeks", "test_weeks_range", "realloc_cut_levels",
                      "test_spend_held_back", "test_market_deals", "test_expected_drop", "test_expected_drop_pct",
                      "test_detectable_drop", "test_detectable_multiple"],
        },
        "recommendation": [
            "Now: approve the market test of the cuts. No new budget.",
            "After the test: if it holds up, approve the same-budget reallocation.",
            "Alternative, if you would rather add budget than cut: the YouTube ask. It rests on the best measured "
            "channel, so it does not need the test, but it is new money.",
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
