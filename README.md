# marketing-analytics-stack

**AI-first Marketing Measurement: Claude on governed metrics, a full MMM build, Matched market test, and actionable insights digestable for exectuive stakeholders.**

## The year in one page

Fernhook, a fictional fleet-software company, spent more on paid media every year, mostly on non-brand search, and its deals fell 10% in 2025. Its CFO stopped trusting marketing's numbers. Over 2026 the measurement team did five things:

1. **Diagnosed.** A Bayesian geo MMM said YouTube was the cheapest next dollar and non-brand search the most saturated.
2. **Tested before moving money.** A Matched market test pushed YouTube in 10 markets and pulled non-brand search back to its 2023 pace in the test markets. YouTube added **+463 deals (+246 to +679)** against a +334 forecast. The search pullback showed no clear drop (-79, -328 to +170).
3. **Refit.** Both results went into the MMM as lift tests, and the refit model set the budget.
4. **Rolled out, with a holdout.** From June the refit plan ran in 15 markets at the same budget: Meta, YouTube, CTV, LinkedIn and affiliates up 50%, display down 50%, non-brand search down 12%. The 5 markets that weren't part of the test kept the BAU budget splits.
5. **Measured it.** The holdout reads **+464 extra deals (+18 to +911)** against a +533 forecast: the rollout works and agrees with the model. The year closed with 28,054 deals (+10.8%), paid spend -1.8% and cost per deal $1,525 (-11.3%).

**What the results say:** the rollout truly added **+882** deals in those weeks. Validating Fernhook's need for more upper funnel investment and less focus on demand capture tactics.

## The story in 8 chapters

1. **The Problem:** Spend climbs, deals fall, and nobody agrees on what works. [The problem](#the-problem) and the [EDA report](docs/eda/EDA.md).
2. **The Diagnosis:** A geo MMM estimates what each channel adds to sales and gives them all a CPA and saturation curves. [docs/mmm/README.md](docs/mmm/README.md)
3. **The Proposal:** A one-pager asks the CFO to approve a market test how realinging the marketing mix to spend more in brand will bring in more total deals. [memo/outputs/proposal_memo.md](memo/outputs/proposal_memo.md)
4. **The Test:** Control and Test markets are assigned. We use the BAU channel mix in the Control and higher upper funnel investment in the Test. [geotest/PREREGISTRATION.md](geotest/PREREGISTRATION.md)
5. **The Readout:** The geo test is statistically validated using a paired t-test. [geotest/READOUT.md](geotest/READOUT.md)
6. **The Refit:** The MMM learns from the test and new actuals and is ran again with fresh data. [docs/mmm/README.md](docs/mmm/README.md#the-refit)
7. **The Rollout:** The refit model's plan runs in 15 markets with the new channels splits, and 5 markets stay on the old BAU plan to measure it. [rollout/PLAN.md](rollout/PLAN.md)
8. **The Results:** The model results are validated, proving that Fernhook can close more deals at a cheaper CPA by optimizing their channel mix. By using the MMM, Fernhook understand where the next best dollar can be allocated across their marketing mix. [rollout/RESULTS.md](rollout/RESULTS.md) and [memo/outputs/results_memo.md](memo/outputs/results_memo.md)

## The company

**Fernhook Software** Sells fleet-maintenance and work-order software to small fleets (5 to 50 vehicles).

- Sales-assisted motion: inbound lead, SDR call, demo, 14-day trial, close.
- Short cycle: a lead closes in about two weeks; nine in ten close in 6 to 27 days.
- First-year contracts run about $2,800 on average, and it closes about 500 deals a week.
- Paid media across nine channels: $33.75M in 2023, $37.13M in 2024 and $43.08M in 2025.
- Sold only in seven Midwest states: Minnesota, Wisconsin, Illinois, Iowa, Ohio, North Dakota, and South Dakota. They split into 20 metro markets in four sales areas.
- About 125 SDRs and 170 AEs.

| Sales area | Markets |
|---|---|
| Illinois and Iowa | Chicago, Rockford, Peoria, Quad Cities, Des Moines, Cedar Rapids |
| Ohio | Cleveland, Columbus, Cincinnati, Dayton, Toledo, Akron |
| Wisconsin | Milwaukee, Madison, Green Bay |
| Upper Midwest | Minneapolis-St. Paul, Rochester, Duluth, Fargo (ND), Sioux Falls (SD) |

**The Seasons Drive the Business.** Fleets shop for software when the season turns: AC switches on in late spring (May and June) and heat switches on in late fall (October and November). The slowest stretch runs from mid-July into September, when crews are busy with AC calls and then coast before heat. Winter after the holidays is soft, and the holidays dip hard. The seasons arrive a little earlier or later by latitude: heat season starts in Fargo and Duluth a few weeks before Cincinnati and Columbus.

## The Problem

Fernhook grew on paid search, and its CRM credits every deal to the last touch.

- **The Money Went to Search.** Budget reviews reward the channels closest to the click, and non-brand search is closest of all. Its budget went from $8.45M in 2023 to $21.08M in 2025, paid for partly by trimming Meta, YouTube, Connected TV and LinkedIn. Performance against Brand went from 60/40 in 2023 to 70/30 in 2024 and 80/20 in 2025.
- **Spend Kept Climbing.** Total paid media rose 10% in 2024 and 16% in 2025.
- **Search Keeps Getting More Expensive.** Non-brand cost per click rose from $7.97 in 2023 to $10.83 in 2025, and its last-touch cost per lead from $117 to $184. Its leads close less often too: the win rate fell from 31% to 26%.
- **Growth Stalled.** Closed-won deals rose 4% in 2024, then fell 10% in 2025. Blended cost per deal went from $1,267 to $1,342 to $1,731.
- **Nobody Agrees on the Numbers.** Every ad platform claims credit for the same deals, so their totals add up to far more than the CRM has. Last touch never credits upper funnel tactics like Connected TV at all.
- **Finance has Stopped Trusting Marketing.** When the CFO asks what a channel returns, the team can show last-touch numbers or platform numbers, and neither holds up. This is a classic bottom of funnel marketing doom loop.

**The Goal:** Use an MMM to give finance one honest number, the overall marketing cost per acquisition (CPA), plus the true CPA of each channel. Then lower it by moving budget between channels at the same total spend.

**The Questions the MMM has to Answer:**

1. How many deals does each channel add, after controls?
2. What is Fernhook's real marketing cost per deal, overall and by channel?
3. Where should the next dollar go, and what would a budget shift do to overall deal volume at the same spend total?
4. How much of the 2025 drop came from marketing, and how much from the hiring freeze, pricing, and the general fleet-maintenance market?

## Claude on governed metrics

Ad-hoc questions are where speed matters, causing analyst to spend a lot of their time on them. Each department, or each AI prompt, defines "paid media" or "a 2025 deal" a little differently, and the numbers drift. So every metric is defined once in a MetricFlow semantic layer on top of the dbt golden tables (35 metrics, from spend and leads to CPL, CPA, and ROAS), and Claude reaches the data through a small MCP server that only answers with those definitions. This allows non-technical stakeholders to answer ad-hoc questions about their marketing data quickly and analyst to work on larger roadmap initiatives that drive innovation to marketing measurment.

To test it, headless Claude answered 50 ad-hoc questions twice: once through the governed MCP server, and once with read-only SQL on the raw source tables. 42 questions have an answer computed in plain SQL; 8 should be refused (churn, NPS, true incremental CTV cost, a channel Fernhook doesn't buy).

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost |
|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 | 0 | 50/50
| Claude + raw tables (SQL) | 23/42 (55%) | 8/8 | 3 | 31/50

Model `claude-sonnet-5-5`, one pass per arm, same instructions, built-in tools off, run on the 2.5x world (budgets drift from brand to search, every volume 2.5 times the first build). Per-question results: [evals/RESULTS.md](evals/RESULTS.md). The run hit the Claude session limit after 25 questions, so the 75 errored questions were run again; 2 governed questions whose metrics server never loaded (Claude saw no tools) were run again too. Earlier runs are kept: the same world at 1x (50/50 and 31/50) in `evals/results/archive_1x_world/`, the balanced-mix seven-state world (50/50 and 31/50) in `evals/results/archive_balanced_mix_world/`, and the first 20-region world (50/50 and 30/50) in `evals/results/archive_global_world/`.

**The 2026 questions.** The governed layer gained the test and rollout dimensions (each market's test cell, its group in each arm, and rollout or holdout), and 9 new questions were asked of the year-end data cut, both ways: governed 8/9 ($0.69), raw SQL 6/9 ($1.47) ([evals/RESULTS_2026.md](evals/RESULTS_2026.md)). Both arms answered "how many extra deals did the YouTube test cause?" with a number, a test-minus-control difference, instead of saying a causal lift is not a defined metric. Governed definitions settle what a number means, not whether a causal claim is allowed.

Why the raw arm missed: it had to invent definitions. It left partner fees and webinars out of "paid media", grouped search and YouTube as "Google", counted deals by calendar close date instead of the house week rule, read "CPA" as cost per lead, and could not answer share-of-spend questions without channel roles. Every one of those is a definition the semantic layer settles once.

## The Model Setup

Every table is weekly, by region, for 156 weeks (2023 to 2025).

**Dependent Variable:** closed-won deals per region per week (`fct_funnel.won_deals`, summed across sources). New first-year contract value and pipeline sit beside it for revenue and payback views.

**Independent Variables:** weekly spend in nine paid channels (`fct_channel_weekly.spend`).

| Channel | Role | What Fernhook buys | Raw export |
|---|---|---|---|
| Paid Search, Non-Brand | Performance | Google ads on category searches like "fleet maintenance software". From 58% of search spend in 2023 to 77% in 2025. | `ads_google_weekly` |
| Paid Search, Brand | Performance | Google ads on searches for "Fernhook". Grows about 3% a year; week to week, spend follows searches. | `ads_google_weekly` |
| LinkedIn | Brand | Lead-gen form ads to fleet and operations managers. Always on. | `ads_linkedin_weekly` |
| Display Retargeting | Performance | Programmatic ads that follow past site visitors. | `ads_display_weekly` |
| Affiliates and Partners | Performance | Placement and sponsor fees with resellers, fleet consultants, and review sites. | `partners_weekly` |
| Meta | Brand | Prospecting video to small-business owners. | `ads_meta_weekly` |
| YouTube | Brand | Prospecting video. | `ads_google_weekly` |
| Connected TV (CTV) | Brand | Streaming TV ads, run as a test in 8 of the 20 markets. Cheaper to start and geo-target than broadcast TV. | `ctv_weekly` |

**Controls:** what moves deals besides paid media (`fct_controls_weekly`).

| Control | Why it is in the model | Raw export |
|---|---|---|
| SDR and AE headcount | More SDRs book more calls; more AEs close more trials. A hiring freeze from July 2024 to January 2025 cut both. | `sales_capacity_monthly` |
| Email sends, opens, clicks | Newsletters and nurture emails bring known contacts back. Owned media, so no spend. | `email_weekly` |
| Year-end Promo | 15% off annual plans for trials started mid-November to mid-December. Lifts the win rate. | `promo_calendar` |
| List Price | Rose 10% in July 2024. Bigger deals, slightly lower win rate. | `promo_calendar` |
| Fleet Activity Index | Market demand. When fleets are busy, more of them shop for software. | `fleet_activity_index_weekly` |
| Seasonality and Rrend | Busy at the spring and fall switchovers, a lull from mid-July into September, a soft winter, holiday dips, and steady organic growth. Timing shifts a little by latitude. | the calendar; `dim_region.latitude` |
| Webinars | Events | Regional live webinars. | `webinar_events` |

Three modeling traps are built in on purpose, because real teams hit them:

- **Brand Search Spend Follows Demand.** Brand search spend rises and falls with how many people search "Fernhook". Part of that demand is created by the upper funnel: people see Fernhook on Meta, YouTube, or CTV and search for it by name later. Brand search never pauses, so no test separates what it adds from the demand it follows.
- **Brand Pushes are Timed to Demand.** Meta, YouTube, and CTV push before and into the busy seasons, the same weeks fleets shop anyway. A model without seasonality will mix up the season and the media. Each market's push lands on its own week and at its own size, and the size changes from season to season, so a model with market-level seasonality can still tell them apart.
- **Affiliate Commissions are not Media Spend.** Commissions are paid per closed deal, so they follow sales instead of causing them. Only placement and sponsor fees enter the model.

## Three views of the same spend

| View | Where it Lives | What it gets Wrong |
|---|---|---|
| Platform-reported Conversions | `ads_*`, `ctv_weekly`, `partners_weekly`; `fct_channel_weekly.platform_conversions` | Each platform counts conversions it touched, not ones it caused, so their totals overlap. |
| CRM Last Touch | `crm_leads` UTMs; `fct_channel_weekly.sourced_*` | It credits the final click. Channels people watch but rarely click, like CTV and YouTube, get little; brand search gets a lot. |
| The Truth | `sim/truth/truth.json` only | Nothing. It is the answer key, and no dbt model or later agent may read it. For Meta, YouTube, and CTV it holds both the direct effect and the deals they add through the brand searches they create. |

The True Effects are Built in: carryover (adstock), diminishing returns (saturation), lead quality that differs by channel, seasonality, trend, and noise. Each run draws every true parameter from a realistic range, so nothing in the answer key is typed into the code. The simulator holds the ranges; the drawn values live only in `truth.json`, and the MMM step is graded against them.

## How the Spend is Set up

Spend has to move a lot, and not in lockstep, or no model can tell the channels apart.

- **Performance Channels and LinkedIn are Aalways Oon.** Brand search, non-brand search, display, affiliates and LinkedIn run every week in every market. They never pause.
- **Upper-funnel Ads Create Brand Searches.** When Meta, YouTube, or CTV reach more people in a market, more of them search for Fernhook by name in the next few weeks, with diminishing returns as reach fills up. Brand search bids on every search, so brand-search spend rises with the upper funnel. Cut one of those channels and brand searches and brand-search spend fall with it.
- **Brand Channels Follow the Season.** YouTube runs national flights several weeks ahead of each busy season, and each flight skips about one market in four. Meta is always on and pushes closer to the season and into it. CTV runs its own flight in each test market. All three ease off in the slow weeks.
- **Pushes are not in Lockstep.** Each market's Meta and CTV push starts on its own week and runs at its own size, and each season's push gets its own budget.
- **Markets:** each channel is spread unevenly across the 20 markets, and always-on budgets are re-split across markets every quarter. CTV runs in only 8 markets.
- **Webinars** are regional events, so their spend lands in one market and one week at a time.
- **Affiliate Fees** step up or down when each market's partner contracts renew every quarter.
- **Budget History:** every channel is paced to an annual budget, and the team made seven changes inside the years. Examples: an attribution review in April 2024 cut YouTube and CTV and added search, the hiring freeze in August 2024 trimmed LinkedIn and Meta while protecting search, and Meta got a retest in June 2025.
- **Budgets Drift Together on Purpose:** search goes up while brand goes down, so yearly levels are correlated. Inside each year, week-to-week spend on any two planned channels correlates at under 0.6.

## Quality Control

The daily quality control runs in a separate workflow, not in this repo. It works like this:

1. **Scripts Run Every Day.** They build the pipeline and check the output for errors, anomalies, and missing data.
2. **An Agent Reads the Results.** When a check fails, an AI agent reviews the output and opens a GitHub issue with a short synopsis of what is wrong and the likely causes.
3. **A Person Investigates.** Someone on the team reviews the issue, digs into the cause, and fixes it.

In this repo the same kinds of checks run on demand: the dbt tests in `dbt build`, the validation checks in the [EDA report](docs/eda/EDA.md), and `pytest`.

## How to Run

Python 3.11, from the repo root. The MMM gets its own environment, so PyMC never moves the pinned warehouse stack. On Windows:

```bash
py -3.11 -m venv .venv
```

```bash
.venv\Scripts\python -m pip install -r requirements.txt
```

```bash
py -3.11 -m venv .venv-mmm
```

```bash
.venv-mmm\Scripts\python -m pip install -r requirements-mmm.txt
```

Then one command runs the whole story, in chapter order:

```bash
.venv\Scripts\python -m stack.run
```

- **Stages:** sim, dbt, eda, evals, mmm, design, memo, test, readout, refit, rollout, yearend, results, results_memo, evals_2026, tableau. Each one calls the repo's own commands.
- **Look First:** `--dry-run` prints every command and runs nothing.
- **Pick Stages:** `--only sim,dbt` runs just those. `--from readout` starts there and runs to the end.
- **The Evals are Off by Default** (both sets). They cost real money in Claude usage. Add `--with-evals` to run them.
- **The Claude CLI:** the two memo stages and the evals need it signed in (`claude auth login`). The evals save each answer as it lands and pick up where they left off.
- **Slow Stages:** the MMM fit, the refit and the evals take the longest; the rollout and results stages take a few minutes each (they refit the brand-search stage). The rest are quick.
- **Two Environments:** main steps use `.venv` and MMM steps use `.venv-mmm`. Use `--python` and `--mmm-python` to point somewhere else. On Mac or Linux the runner finds `.venv/bin/python` by itself.
- **Same seed, same files:** the simulator writes byte-identical files every time.
- **Tests:** `.venv\Scripts\python -m pytest -q` runs the main suite. The MMM tests are listed in [docs/mmm/README.md](docs/mmm/README.md). CI runs both on every pull request.

Each step's own commands and options are in its README: [MMM](docs/mmm/README.md), [memo](memo/README.md), [Tableau](tableau/LAYOUT.md). The rollout's are in [rollout/PLAN.md](rollout/PLAN.md) and the module docstrings in `rollout/`.

## Repo Map

How the pieces connect, and the wall around the answer key: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

```
sim/         seeded simulator (python -m sim) and the answer key in sim/truth/
data/        raw CSVs, the DuckDB warehouse and 2026 data cuts (generated, not committed)
warehouse/   dbt project on DuckDB: staging, intermediate, marts, semantic layer
servers/     MCP servers: governed metrics, and raw SQL for the eval baseline
evals/       eval set, runner, scorer, results
eda/         EDA and validation report (python -m eda), reads the warehouse only
mmm/         geo MMM, its outputs, and mmm/grade.py, the only reader of the answer key
geotest/     the 2026 market test: design, pre-registration, readout, cross-check
rollout/     the June to December rollout: plan, holdout registration, year-end readout, the model's view
plans/       2026 spend plans the simulator runs
memo/        facts pack, Claude memo writer, grounding check
tableau/     Tableau CSV export and the dashboard build plan
stack/       python -m stack.run, one command for the whole story
docs/        the architecture, the EDA report and the MMM write-up
tests/       pytest for every step
.github/     CI
```

Golden Tables:

- `fct_channel_weekly`: week x region x paid channel. Spend, delivery, platform claims, last-touch leads and pipeline.
- `fct_funnel`: week x region x lead source. Leads, MQLs, SQLs, opportunities, pipeline, won deals, revenue. Each stage is counted in the week it happened.
- `fct_controls_weekly`: week x region. Headcount, email, promo and price flags, fleet activity index.
- `dim_channel`: channel names, groups, and roles.
- `dim_region`: markets, with each market's 2026 test cell, its group in each arm, and its rollout group.
- `fct_media_plan_weekly`: week x region x planned channel. The media plan's budget line beside delivered spend.
