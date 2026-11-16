"""Render the pre-registration from geotest/outputs/design.json. Pure Python, so a
test in either environment can check the committed file against the design."""

from __future__ import annotations


def _money(x):
    return f"${x:,.0f}"


NAMES = {"paid_search_brand": "brand search", "paid_search_nonbrand": "non-brand search", "meta": "Meta",
         "linkedin": "LinkedIn", "youtube": "YouTube", "ctv": "connected TV", "display": "display retargeting",
         "affiliates": "affiliates"}


def _and(items):
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _markets(codes, names):
    return ", ".join(f"{names[c]} ({c})" for c in codes)


def _duration_line(d: dict) -> str:
    rows = {r["test_weeks"]: r for r in d["durations"]}
    w = d["dates"]["test_weeks"]
    short = max(k for k in rows if k < w)
    long = min(k for k in rows if k > w)
    return (f"- Duration: {short} weeks gives the grow arm {rows[short]['grow']['power']:.0%} power. {w} weeks is "
            f"the shortest that clears 80% ({rows[w]['grow']['power']:.0%}). {long} weeks reaches "
            f"{rows[long]['grow']['power']:.0%}, but runs past the spring busy season into the readout.")


def prereg_md(d: dict, market_names: dict) -> str:
    g, c, f, pl, dt = d["arms"]["grow"], d["arms"]["cut"], d["forecast"], d["placebo"], d["dates"]
    gname = NAMES[g["channel"]]
    cuts = _and(NAMES[x] for x in c["channels"])
    keep = f"{100 * c['value']:.0f}%"
    by = d["mmm"]["cut_spend_by_year"]
    first, last = min(by), max(by)
    lines = [
        f"# Pre-registration: market test {d['test_id']}",
        "",
        f"Registered {d['approved']}, before the test starts. Written by `python -m geotest.design` from "
        "`geotest/outputs/design.json`; every number below comes from that file. Data: the December 2025 cut "
        f"({d['data_cut']['first_week']} to {d['data_cut']['last_week']}).",
        "",
        "## Why this test",
        "",
        f"Two questions decide the 2026 budget. First, where should the next dollar go? The MMM says {gname}, "
        f"its lowest cost per extra deal. {gname} runs in flights, so the data show it on and off, but never at "
        f"the level the model recommends. Second, is the money poured into {cuts} still working? It is the "
        f"biggest channel and always on, so the data never show life without it, and its spend went from "
        f"{_money(by[first])} in {first} to {_money(by[last])} in {last}. The test checks both at once.",
        "",
        "## Design",
        "",
        f"- **Dates:** {dt['test_weeks']} test weeks, {dt['test_start']} to {dt['test_end']}. The measurement "
        f"window adds {dt['tail_weeks']} weeks for deals to close: {dt['window_start']} to {dt['window_end']}. "
        f"Readout from the {dt['readout_snapshot']} data cut.",
        f"- **Grow arm ({len(g['markets'])} markets):** {gname} adds {_money(g['value'])} a week per unit of "
        f"market size (target accounts over the market average), on top of plan. Markets: "
        f"{_markets(g['markets'], market_names)}.",
        f"- **Search arm ({len(c['markets'])} markets):** {cuts} runs at {keep} of plan, its {first} weekly "
        f"pace. Markets: {_markets(c['markets'], market_names)}.",
        "- **Cells (a 2x2 factorial):** " + "; ".join(f"{k}: {', '.join(v)}" for k, v in d["cells"].items()) + ".",
        f"- **Assignment:** markets sit in {len(d['blocks'])} blocks of 4 similar-size markets, and each block "
        f"gives one market to each cell. Of {d['assignment']['candidates']:,} random assignments, "
        f"{d['assignment']['kept_after_balance']:,} kept each arm's dose balanced across the other arm's sides "
        f"(within {int(d['assignment']['max_cross'] * 100)}%), and the one whose worst placebo error, over both "
        "arms and over 2024 and 2025 windows, was smallest was chosen.",
        "- **Everything else** runs on the 2026 plan: every channel at its end-2025 budget, with its usual "
        "flighting and market split. Brand search follows searches, as always.",
        "",
        "## Metrics",
        "",
        "- **Primary: won deals.** Closed-won deals, all lead sources, counted in their close week "
        "(`fct_funnel.won_deals`), summed over each arm's markets and the measurement window.",
        f"- **Secondary: cost per deal.** For the grow arm, extra spend (with the brand-search spend that follows "
        f"the extra searches) per extra deal, against the MMM's {gname} cost per extra deal of "
        f"{_money(d['mmm']['mcpa'][g['channel']])}. For the search arm, dollars saved per deal lost. Blended cost per deal "
        "in each arm's markets against the rest is reported beside them.",
        "",
        "## Analysis",
        "",
        f"- **Estimator:** ratio difference-in-differences per arm. An arm's markets are compared with the "
        f"other {sum(len(v) for v in d['cells'].values()) - len(g['markets'])} markets, scaled by their deal "
        f"ratio over the {dt['pre_period_weeks']} weeks before the test. The two "
        "arms' contrasts form a 2x2 system in each arm's effect per planned dollar, which removes the other arm's "
        "effect (`geotest/estimator.py`).",
        f"- **Interval:** 90%, from the placebo spread: the estimator run on {pl['windows']} 2024 and 2025 "
        f"windows where nothing was tested. The standard deviation used is the largest of the 2024 placebo error, "
        "the 2025 placebo error and the count-noise floor.",
        "- **Cross-check:** a Bayesian synthetic control (CausalPy) on the same window. It does not decide.",
        "- **Comparison with the model:** the MMM's forecast for each arm, made now from the same posterior "
        "the plan came from, with last year's same weeks as the stand-in for 2026 spend.",
        "",
        "## Power",
        "",
        "| Arm | Placebo error (2024 / 2025 / floor) | Smallest detectable lift | MMM forecast (90% range) | Power |",
        "|---|---:|---:|---:|---:|",
    ]
    for k, name in ((0, "grow"), (1, "cut")):
        fk = f[name]
        label = "grow" if name == "grow" else "search"
        lines.append(f"| {label} | {pl['rms_2024'][k]:.0f} / {pl['rms_2025'][k]:.0f} / {pl['count_noise_floor'][k]:.0f} | "
                     f"{d['mde'][name]:.0f} deals | {fk['lift_mean']:+.0f} ({fk['lift_hdi_90'][0]:+.0f} to "
                     f"{fk['lift_hdi_90'][1]:+.0f}) | {fk['power']:.0%} |")
    lines += [
        "",
        f"- The grow step is the smallest on a {_money(d['forecast']['grid_step'])} grid whose forecast clears the "
        f"bar at 80% power. It adds {_money(f['grow']['spend_change'])} over the test; the MMM expects "
        f"{f['grow']['lift_mean']:.0f} extra deals in the window, {_money(f['grow']['cost_per_extra_deal'])} each. "
        f"Averaged over the forecast's own uncertainty, the chance of a clear result is {f['grow']['assurance']:.0%}.",
        f"- The search arm saves {_money(-f['cut']['spend_change'])}. At the forecast it has "
        f"{f['cut']['power']:.0%} power; it reaches 80% if pulling search back costs "
        f"{f['cut']['multiple_of_forecast_for_80pct_power']:.1f} times what the model expects. It is a guardrail: "
        "it catches search being worth much more than modeled.",
        f"- Net, the test spends {_money(f['grow']['spend_change'] + f['cut']['spend_change'])} against plan "
        "(negative means it saves money).",
        f"- Placebo false-positive rate at the 90% edge: {pl['false_positive_rate_max']:.0%}. A calibrated bar "
        "would give 5%; this one is lower because it uses the largest of the three errors.",
        _duration_line(d),
        "",
        "| Test weeks | Grow: bar / forecast / power | Search: bar / forecast / power |",
        "|---:|---:|---:|",
    ]
    for r in d["durations"]:
        lines.append(f"| {r['test_weeks']} | {r['grow']['mde']:.0f} / {r['grow']['lift_mean']:.0f} / "
                     f"{r['grow']['power']:.0%} | {r['cut']['mde']:.0f} / {r['cut']['lift_mean']:.0f} / "
                     f"{r['cut']['power']:.0%} |")
    lines += [
        "",
        "## Decision rules",
        "",
        f"1. **{gname} works** if the grow arm's 90% interval is above zero.",
        f"2. **Against the model:** the grow lift beats the forecast if its 90% interval lies above the forecast "
        f"({f['grow']['lift_mean']:.0f}), falls short if it lies below, and agrees otherwise. Pulling {cuts} "
        f"back costs more than modeled if the search arm's 90% interval lies below the forecast "
        f"({f['cut']['lift_mean']:.0f}), and less if it lies above.",
        f"3. **Either way, the model learns:** each arm moved 1 channel, so each enters the MMM as a lift test "
        f"(`add_lift_test_measurements`): {gname} for the grow arm, {cuts} for the search arm. The MMM is refit "
        "on data through the readout and the optimizer runs again. The rollout follows the refit model, not "
        "this plan.",
        f"4. **Guardrail:** if pulling {cuts} back costs more than modeled (rule 2), the rollout does not cut it "
        f"below today's spend. If {gname} shows no lift (rule 1 fails), the rollout does not grow it.",
        "5. **Validity, the market-compliance check.** Set now, before the test, and applied as written "
        "(`compliance` in the design file, `geotest/compliance.py`). It reads spend only and never moves a lift.",
    ]
    lines += _compliance_lines(d, gname, cuts)
    lines.append("")
    return "\n".join(lines)


def _compliance_lines(d: dict, gname: str, cuts: str) -> list[str]:
    cp, g, c = d["compliance"], d["arms"]["grow"], d["arms"]["cut"]
    dr, keep = cp["dry_run"], c["value"]
    gl, cl = cp["grow_seen"]["line"], cp["cut_seen"]["line"]
    n_cut = len(c["markets"])

    def flagged(codes):
        return ", ".join(codes) if codes else "no market"

    return [
        f"   - **Spend:** each arm's realized spend change, by the same ratio difference-in-differences on the "
        f"moved channel's spend over the {d['dates']['test_weeks']} test weeks, lands within "
        f"{cp['spend_change']['max_miss']:.0%} of its plan. The grow plan is {_money(g['value'])} a week per size "
        "unit; the search plan is observed spend over the multiplier, minus observed spend.",
        f"   - **Plan file:** `{cp['plan_file']['path']}`, the plan that drives 2026 spend, assigns these markets, "
        "moves and dates.",
        f"   - **Moves:** the spend shows every move. {gname[0].upper() + gname[1:]}, for each grow market: its "
        f"lowest weekly {gname} spend per size unit over the test weeks is at least {_money(gl)}, half the add "
        "(the add runs every test week; a median would not do, because national flights lift every market's "
        "median in season). "
        f"{cuts[0].upper() + cuts[1:]}, for the arm as a whole: the arm's summed spend in the test weeks of the "
        "test's quarter, over its spend in that quarter's weeks before the test, and against the same step in the "
        f"markets outside the arm, is nearer in logs to {keep:.2f} than to 1 (the line is {cl:.2f}). Budgets for "
        "always-on channels are re-split across markets every quarter, so the step stays inside one quarter. Each "
        "search market gets the same test on its own.",
        "   - **Void** if the spend change misses, the plan file does not match, a grow market does not show the "
        "add, or the search arm does not show the cut.",
        "   - **Named, never void:** a search market whose own step misses the line, and a market outside an arm "
        "whose spend shows that arm's move (drift). The readout names each one and recomputes the lifts without "
        "it, as exploratory. Neither changes the registered lift. Deciding the cut for the arm rather than market "
        "by market was Logan's call, made before the test, from the dry run below.",
        f"   - **Dry run** on last year's same weeks (from {dr['weeks_start']}), when nothing was tested: the "
        f"{gname} check flags {flagged(dr['grow']['flagged'])} (highest lowest week "
        f"{_money(dr['grow']['max_lowest_weekly_per_size'])} against {_money(gl)}; over all "
        f"{dr['grow']['windows']} earlier 12-week windows, at most "
        f"{_money(dr['grow']['windows_max_lowest_weekly_per_size'])}); the step test flags "
        f"{flagged(dr['cut']['flagged'])}. One noise unit of a market's step, from {dr['cut']['noise_quarters']} "
        f"earlier quarters, is {dr['cut']['noise_log_sd']:.2f} in logs, and of the arm's step "
        f"{dr['cut']['arm_noise_log_sd']:.2f}. At that noise, the arm misses the line by chance "
        f"{dr['cut']['p_arm_misses_line']:.1%} of the time. Decided market by market, one of the {n_cut} would "
        f"miss {dr['cut']['p_any_assigned_market_misses_line']:.0%} of the time; a market outside the arm crosses "
        f"the line {dr['cut']['p_market_flagged_without_a_move']:.1%} of the time.",
    ]
