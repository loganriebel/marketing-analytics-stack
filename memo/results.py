"""The January 2027 results memo: its facts pack, its chart and its writer spec.

    python -m memo --memo results --retries 4     # facts, chart, memo, grounding
    python -m memo.results                         # the facts pack and the chart only

Same pipeline as the proposal memo: a facts pack every number must come from, one chart
drawn from the pack, headless Claude as the writer, and the grounding check at 100%.
The pack reads what the team itself wrote down during 2026: the spring test's readout
(geotest/outputs/readout.json), the rollout plan and its registered holdout
(rollout/outputs/plan.json), and the year-end holdout readout (rollout/outputs/results.json).
Nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from . import facts as F  # noqa: E402
from . import grounding as G  # noqa: E402
from .writer import APPENDIX_MAX_WORDS, BODY_WORDS, Spec  # noqa: E402

REPO = F.REPO
OUT_DIR = F.OUT_DIR
FACTS_PATH = OUT_DIR / "results_facts.json"
MEMO_PATH = OUT_DIR / "results_memo.md"
GROUNDING_PATH = OUT_DIR / "results_grounding.json"
LOG_PATH = OUT_DIR / "results_writer.json"
CHART_PATH = OUT_DIR / "results_chart.png"
READOUT = REPO / "geotest" / "outputs" / "readout.json"
PLAN = REPO / "rollout" / "outputs" / "plan.json"
HOLDOUT_READOUT = REPO / "rollout" / "outputs" / "results.json"
SRC = {READOUT: "geotest/outputs/readout.json", PLAN: "rollout/outputs/plan.json",
       HOLDOUT_READOUT: "rollout/outputs/results.json"}

SECTIONS = ["What we did", "What happened", "Did it work", "What it cost", "What's next", "Appendix: the ranges"]
CHART_LINE = "![Forecast against result: the spring test and the rollout, with 90% ranges](results_chart.png)"
RESULTS_BODY_MAX = 450                 # five sections of results need a little more room than the proposal
NAMES = {"paid_search_nonbrand": "non-brand search", "meta": "Meta", "linkedin": "LinkedIn", "youtube": "YouTube",
         "ctv": "connected TV (CTV)", "display": "display retargeting", "affiliates": "affiliates and partners"}


def _read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def build(readout_path: Path = READOUT, plan_path: Path = PLAN, results_path: Path = HOLDOUT_READOUT) -> dict:
    ro, pl, rs = _read(readout_path), _read(plan_path), _read(results_path)
    R, P, S = SRC[READOUT], SRC[PLAN], SRC[HOLDOUT_READOUT]
    p = F.Pack()

    # The year, from the year-end data cut.
    y = rs["year"]
    for yr in ("2025", "2026"):
        v = y[yr]
        p.add(f"deals_{yr}", v["won_deals"], "deals", S, f"year.{yr}.won_deals",
              f"Closed-won deals in {yr} (weeks by their Monday)", "input")
        p.add(f"paid_spend_{yr}", v["paid_spend"], "USD", S, f"year.{yr}.paid_spend",
              f"Paid media spend in {yr}, all 9 paid channels", "input")
        p.add(f"cost_per_deal_{yr}", v["cost_per_deal"], "USD", S, f"year.{yr}.cost_per_deal",
              f"Blended cost per deal in {yr}: paid spend / all deals", "input")
    for k, what in (("won_deals", "deals"), ("paid_spend", "paid spend"), ("cost_per_deal", "cost per deal")):
        p.add(f"{k}_change_pct", y["change_pct"][k], "percent", S, f"year.change_pct.{k}",
              f"Change in {what} from 2025 to 2026. Holds everything that moved in 2026, not just marketing",
              "derived", how="100 x (2026 / 2025 - 1)")

    # The spring test, as read out in May.
    g, c = ro["arms"]["grow"], ro["arms"]["cut"]
    w = ro["window"]
    p.add("test_weeks", w["test_weeks"], "weeks", R, "window.test_weeks", "Spring test length", "input")
    p.add("test_arm_markets", len(g["markets"]), "markets", R, "arms.grow.markets",
          "Markets in each half of the spring test", "input")
    p.add("test_youtube_lift", g["lift"], "deals", R, "arms.grow.lift",
          "Measured extra deals from the YouTube push in the spring test", "estimate",
          low=g["interval_90"][0], high=g["interval_90"][1])
    p.add("test_youtube_forecast", g["forecast"]["lift_mean"], "deals", R, "arms.grow.forecast",
          "The model's January forecast for the YouTube push", "estimate",
          low=g["forecast"]["hdi_90"][0], high=g["forecast"]["hdi_90"][1], stat="mean")
    sg = ro["secondary"]["grow"]
    lo_c, hi_c = sg["cost_per_extra_deal_range"]
    p.add("test_youtube_cost_per_deal", sg["cost_per_extra_deal"], "USD", R, "secondary.grow.cost_per_extra_deal",
          "Cost per extra deal from the YouTube push, counting the brand search that followed", "derived",
          low=lo_c, high=hi_c, how="extra spend / measured lift; range from the lift's interval")
    p.add("test_youtube_model_cost_per_deal", sg["mmm_marginal_cpa"], "USD", R, "secondary.grow.mmm_marginal_cpa",
          "The model's cost per extra deal for YouTube before the test", "estimate")
    p.add("test_search_lift", c["lift"], "deals", R, "arms.cut.lift",
          "Measured deal change from pulling non-brand search back (negative = lost)", "estimate",
          low=c["interval_90"][0], high=c["interval_90"][1])
    p.add("test_search_forecast", c["forecast"]["lift_mean"], "deals", R, "arms.cut.forecast",
          "The model's January forecast for pulling search back (negative = lost)", "estimate",
          low=c["forecast"]["hdi_90"][0], high=c["forecast"]["hdi_90"][1], stat="mean")
    p.add("test_search_power", 100 * c["power_at_forecast"], "percent", R, "arms.cut.power_at_forecast",
          "Odds the search side could see the drop the model expected: a guardrail, not a measurement", "design")
    p.add("test_search_saved", ro["secondary"]["cut"]["spend_saved"], "USD", R, "secondary.cut.spend_saved",
          "Non-brand search spend saved during the spring test", "input")

    # The rollout plan, set in May from the refit model.
    rp, h, d = pl["rollout"]["plan"], pl["holdout"], pl["dates"]
    p.add("rollout_weeks", d["weeks"], "weeks", P, "dates.weeks", "Rollout length, June 1 to the end of December",
          "design")
    p.add("rollout_markets", len(h["rollout_markets"]), "markets", P, "holdout.rollout_markets",
          "Markets on the new plan", "design")
    p.add("holdout_markets", len(h["holdout"]), "markets", P, "holdout.holdout",
          "Markets kept on the old plan all year to measure the rollout", "design")
    p.add("holdout_share", 100 * (1 - h["rollout_share_of_pre_period_deals"]), "percent", P,
          "holdout.rollout_share_of_pre_period_deals", "The holdout markets' share of deals", "design",
          how="100 x (1 - rollout share)")
    for row in rp["by_channel"]:
        ch = row["channel"]
        p.add(f"rollout_{ch}_change_pct", 100 * (row["multiplier"] - 1), "percent", P,
              f"rollout.plan.multipliers.{ch}", f"{NAMES[ch]}: spend change in the rollout markets", "design",
              how="100 x (multiplier - 1)")
    moved = sum(r["spend_change"] for r in rp["by_channel"] if r["spend_change"] > 0)
    p.add("rollout_moved", moved, "USD", P, "rollout.plan.by_channel[].spend_change",
          "Spend the plan moves from the cut channels to the grown ones over the rollout (last year's same weeks)",
          "derived", how="sum of positive spend_change")
    f = h["forecast"]
    p.add("rollout_forecast", f["mean"], "deals", P, "holdout.forecast",
          "The refit model's May forecast: extra deals in the rollout markets closing by year end", "estimate",
          low=f["hdi_90"][0], high=f["hdi_90"][1], stat="mean")
    p.add("rollout_power", 100 * h["power_at_forecast"], "percent", P, "holdout.power_at_forecast",
          "Odds the holdout could see the forecast lift clearly, from placebo tests before the rollout", "design")
    p.add("rollout_bar", h["smallest_detectable_lift"], "deals", P, "holdout.smallest_detectable_lift",
          "Smallest lift the holdout can reliably see (80% power)", "design")

    # The year-end readout, by the rules written down in May.
    m = rs["measured"]
    p.add("rollout_lift", m["lift"], "deals", S, "measured.lift",
          "Measured extra deals in the rollout markets against the holdout, June to December", "estimate",
          low=m["interval_90"][0], high=m["interval_90"][1])
    mv = rs.get("model_view")
    if mv:
        dv = mv["deal_change_in_window"]
        p.add("rollout_model_view", dv["mean"], "deals", S, "model_view.deal_change_in_window",
              "The refit model's own view of the realized rollout (a cross-check that decides nothing)",
              "estimate", low=dv["hdi_90"][0], high=dv["hdi_90"][1], stat="mean")
    sec = rs["secondary"]
    p.add("rollout_brand_search", sec["brand_search_spend_change"], "USD", S, "secondary.brand_search_spend_change",
          "Extra brand-search spend that followed the extra searches in the rollout markets", "estimate")
    bc = sec["blended_cost_per_deal_in_window"]
    p.add("rollout_markets_cost_per_deal", bc["rollout_markets"], "USD", S,
          "secondary.blended_cost_per_deal_in_window.rollout_markets",
          "Blended cost per deal in the rollout markets, June to December", "input")
    p.add("holdout_markets_cost_per_deal", bc["holdout_markets"], "USD", S,
          "secondary.blended_cost_per_deal_in_window.holdout_markets",
          "Blended cost per deal in the holdout markets, June to December", "input")
    p.add("hdi_prob", 90, "percent", P, "holdout.rules", "Every range is a 90% range", "input")

    dec = rs["decision"]
    if not dec["valid"]:
        raise SystemExit("the rollout readout is void by its registered rules; the memo reports only a valid readout")
    verdict = ("works" if dec["rule_1_rollout_works"] else "drop" if dec["rule_3_drop_is_clear"] else "not clear")
    return {
        "meta": {"built_by": "memo/results.py", "reads": sorted({fx["source"] for fx in p.facts}),
                 "units": "USD; deals; percent (already x100); weeks; markets"},
        "facts": p.facts,
        "test_readout": {
            "youtube": "The YouTube push worked: its whole range is a gain. It came in above the model's "
                       "forecast but inside its range, so it agrees with the model.",
            "search": "Pulling non-brand search back showed no clear drop. That side was a guardrail with low "
                      "odds of seeing the drop the model expected, so it does not show search does nothing. It "
                      "only rules out a big hidden loss.",
            "rules": "Neither guardrail tripped, so the rollout followed the refit model, as written down before "
                     "the test.",
        },
        "rollout": {
            "what": "From June, the refit model's plan in the rollout markets at the same total budget: more Meta, "
                    "YouTube, connected TV, LinkedIn and affiliates, less display retargeting and less non-brand "
                    "search. The holdout markets, the ones in neither group of the spring test, stayed on the old "
                    "plan so the rollout could be measured against them.",
            "readout": {"works": "The rollout worked: its whole measured range is a gain.",
                        "not clear": "The measured gain is not clear: its range runs from a loss to a gain. The holdout was "
                                     "always likely to read this way, even if the plan works as forecast, so this "
                                     "is not evidence the plan failed. A clear drop would have been.",
                        "drop": "The rollout cost deals: its whole measured range is a loss."}[verdict],
            "verdict": verdict,
            "against_forecast": dec["rule_2_against_forecast"],
            "model_view": "The model's own view of the rollout is shown beside the holdout as a cross-check. It "
                          "uses no outcomes and decides nothing, and the model is likely to under-credit paid media.",
            "budget": "The rollout moved money between channels inside the same budget; it added no new spend "
                      "except the brand search that follows extra searches.",
            "totals": "The year's totals hold everything that moved in 2026: the spring test, the rollout, sales "
                      "headcount, the market and the season. They describe the year; they do not measure the "
                      "rollout. The holdout does.",
        },
        "next": [
            "Keep the rollout plan into the new year, and refit the model on the full year with the holdout result "
            "added.",
            "Keep a smaller holdout running, because a holdout this size can only see a large effect.",
            "Test non-brand search again with a bigger and longer pullback. It is still the biggest and least "
            "measured channel.",
            "Hold Meta flat in a few markets through a busy season, so the model can tell Meta from the season.",
        ],
    }


def write(path: Path = FACTS_PATH) -> dict:
    pack = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack, indent=2) + "\n", encoding="utf-8", newline="\n")
    return pack


SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
RESULT, FORECAST = "#2a78d6", "#a3a29c"


def draw(pack: dict | None = None, path: Path = CHART_PATH) -> dict:
    """Forecast against result for the YouTube push, the search pullback and the rollout, from the pack."""
    pack = pack or json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    facts = {fx["id"]: fx for fx in pack["facts"]}
    rows = [("Spring test: YouTube push", "test_youtube_forecast", "test_youtube_lift"),
            ("Spring test: search pullback", "test_search_forecast", "test_search_lift"),
            ("Rollout, June to December", "rollout_forecast", "rollout_lift")]
    plotted = []
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(6.4, 3.0), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for i, (label, fid, rid) in enumerate(rows):
        y = len(rows) - 1 - i
        for fact_id, color, dy in ((fid, FORECAST, 0.14), (rid, RESULT, -0.14)):
            fx = facts[fact_id]
            ax.plot([fx["low"], fx["high"]], [y + dy, y + dy], color=color, lw=2.2, solid_capstyle="round", zorder=2)
            ax.scatter([fx["value"]], [y + dy], s=40, color=color, edgecolor=SURFACE, linewidth=1.8, zorder=3)
            plotted.append({"fact": fact_id, "value": fx["value"], "low": fx["low"], "high": fx["high"]})
    ax.axvline(0, color=INK_2, lw=0.9, zorder=1)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in reversed(rows)], color=INK)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0, pad=6, labelsize=8)
    ax.tick_params(axis="x", colors=INK_2)
    ax.set_xlabel("Extra deals (dot: estimate; line: its 90% range)", color=INK_2, fontsize=8)
    fig.suptitle("Forecast against result", x=0.02, y=0.985, ha="left", fontsize=10.5, color=INK,
                 fontweight="bold")
    handles = [plt.Line2D([], [], color=FORECAST, marker="o", lw=2, label="Model's forecast, made in advance"),
               plt.Line2D([], [], color=RESULT, marker="o", lw=2, label="Measured result")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 0.92), ncol=2, frameon=False,
               fontsize=7.5, labelcolor=INK_2, handlelength=1.6, columnspacing=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.84))
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return {"path": str(path), "plotted": plotted}


SYSTEM = f"""You write a one-page results memo to the CFO of Fernhook Software, a fleet-maintenance software company. It is January 2027. A year ago the CFO approved a spring market test. Its readout went into the marketing mix model (MMM), and the refit model set a budget rollout from June, measured against a few markets held on the old plan. The facts pack in the prompt holds what the team measured and forecast. It is your only source.

Numbers. A script checks every number in your memo against the facts pack, and the memo is thrown out if one fails.
- Use only numbers that are in the facts pack: a fact's value, or its low and high. Never compute a number yourself: no sums, differences, ratios, conversions or "about double".
- Round for a reader (2 or 3 significant figures), never below two, and round correctly: 472,478 is $472K or $470K, never $473K; 1,491,623 is $1.5M, never $1M.
- A range must be one fact's own low and high. Never pair ends from different facts.
- Write every number in digits. Never use number words like two, eight, dozen, half, double or twice. The word "one" is fine.
- Money as $1.5M, $472K or $2,841. Percents with %. Durations as "12 weeks".
- Month names and dates such as June 1 are fine. Years such as 2026 are fine.
- A negative fact is fine written without its sign when the words carry the direction ("fell 3%", "saved $1.6M", "lost 79 deals").
- If a sentence needs a number that is not in the pack, rewrite the sentence without it.

Form. Executive style: the CFO reads the headline and the first lines and should know what happened.
- First line: a # headline that says what the year showed in plain words, with at most 3 numbers.
- Then these sections as ## headings, in this order, with these exact names: {", ".join(SECTIONS)}.
- Put this chart line, exactly as written, on its own line at the end of "Did it work": {CHART_LINE}
- Above the appendix: point estimates only. No ranges at all and no "90% range" wording. Every range goes in the appendix, next to its point estimate.
- Above the appendix: {BODY_WORDS[0]} to {RESULTS_BODY_MAX} words and at most 16 numbers. Fewer numbers is better. Short paragraphs; a few bullets are fine. No tables.
- The appendix: short bullets, each an estimate with its 90% range, at most {APPENDIX_MAX_WORDS} words. Say once that every range is a 90% range.

Content.
- What we did: the spring test in plain words and what its readout said; then the rollout from June, what it moved, and the holdout markets kept on the old plan to measure it.
- What happened: the year's deals, paid spend and cost per deal against 2025. Say plainly that these totals hold everything that moved in 2026 and do not measure the rollout.
- Did it work: for the spring test and the rollout, the model's forecast against the measured result. Follow the pack's readout text exactly on whether the rollout result is clear. If it is not clear, say plainly that the holdout had low odds of a clear read even if the plan works, using the pack's power fact, and that this is not evidence the plan failed. Whichever way it read, state the holdout's odds of a clear read, using the pack's power fact. Mention the model's own view only as a cross-check that decides nothing.
- What it cost: the rollout stayed inside the budget; what moved, the brand search that followed, and cost per deal in the rollout markets against the holdout markets.
- What's next: follow the pack's next steps.
- No claims the pack does not support. Do not mention how the pack was built.

Style.
- CFO voice: direct, plain words, short sentences. No marketing jargon. Say "cost per deal" for CPA, "cost per extra deal" for marginal CPA. Say "a gain" or "a loss", never "above zero" or "below zero".
- No em dashes or en dashes anywhere. Use commas, periods, colons or parentheses.
- Output only the memo in Markdown. No preamble, no closing note."""

RESULTS = Spec("results", SYSTEM, SECTIONS, CHART_LINE, "Did it work", MEMO_PATH, FACTS_PATH, GROUNDING_PATH,
               LOG_PATH, write, draw, body_words=(BODY_WORDS[0], RESULTS_BODY_MAX))


def main() -> int:
    pack = write()
    draw(pack)
    print(f"wrote {FACTS_PATH.relative_to(REPO).as_posix()}: {len(pack['facts'])} facts, and the chart")
    if MEMO_PATH.exists():
        print(G.summary(G.run(MEMO_PATH, FACTS_PATH, GROUNDING_PATH)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
