# marketing-analytics-stack

An example of the stack I run at work: dashboards, Claude on golden tables, MMM for budget asks. All data is synthetic.

**Status:** step 2 of 6. The fake company, its raw data, the dbt golden tables, an [EDA and data validation report](docs/eda/EDA.md), the governed metrics layer, and the Claude eval are built and tested. Tableau and the MMM come next.

## The company

**Fernhook Software** is fictional. It sells fleet-maintenance and work-order software to small fleets (5 to 50 vehicles): local delivery, HVAC and plumbing vans, landscaping crews.

- Sales-assisted motion: inbound lead, SDR call, demo, 14-day trial, close.
- Short cycle: a lead closes in about two weeks; nine in ten close in 6 to 27 days.
- First-year contracts run about $2,800 on average, and it closes about 210 deals a week.
- About $14M a year in paid media across nine channels.
- Sold only in seven Midwest states: Minnesota, Wisconsin, Illinois, Iowa, Ohio, North Dakota, and South Dakota. They split into 20 metro markets in four sales areas.
- About 50 SDRs and 70 AEs.

| Sales area | Markets |
|---|---|
| Illinois and Iowa | Chicago, Rockford, Peoria, Quad Cities, Des Moines, Cedar Rapids |
| Ohio | Cleveland, Columbus, Cincinnati, Dayton, Toledo, Akron |
| Wisconsin | Milwaukee, Madison, Green Bay |
| Upper Midwest | Minneapolis-St. Paul, Rochester, Duluth, Fargo (ND), Sioux Falls (SD) |

**The seasons drive the business.** Fleets shop for software when the season turns: AC switches on in late spring (May and June) and heat switches on in late fall (October and November). The slowest stretch runs from mid-July into September, when crews are busy with AC calls and then coast before heat. Winter after the holidays is soft, and the holidays dip hard. The seasons arrive a little earlier or later by latitude: heat season starts in Fargo and Duluth a few weeks before Cincinnati and Columbus.

## The problem

Fernhook grew on paid search, and its CRM credits every deal to the last UTM touch.

- **The mix drifted to performance.** Budget reviews reward the channels closest to the click: search, retargeting, affiliates. Connected TV, YouTube, and Meta look weak in last touch, so they get cut. Performance took 66% of spend in 2023 and 77% in 2025.
- **Search keeps getting more expensive.** Last-touch search cost per lead rose from $74 in 2023 to $94 in 2025.
- **Growth stalled.** In 2025 spend rose 1% over 2024, and closed-won deals fell 12%. Blended cost per deal rose from about $1,230 to $1,410.
- **Nobody agrees on the numbers.** Every ad platform claims credit for the same deals, so their totals add up to far more than the CRM has. Last touch never credits Connected TV at all.
- **Finance has stopped trusting marketing.** When the CFO asks what a channel returns, the team can show last-touch numbers or platform numbers, and neither holds up.

**The goal:** Use an MMM to give finance one honest number, the overall marketing cost per acquisition (CPA), plus the true CPA of each channel. Then lower it by moving budget between channels at the same total spend.

**The questions the MMM has to answer:**

1. How many deals does each channel add, after controls?
2. What is Fernhook's real marketing cost per deal, overall and by channel?
3. Where should the next dollar go, and what would a budget shift do at the same total?
4. How much of the 2025 drop came from marketing, and how much from the hiring freeze, pricing, and the market?

## Claude on governed metrics

Ad-hoc questions are where trust breaks. Each analyst, or each AI prompt, defines "paid media" or "a 2025 deal" a little differently, and the numbers drift. So every metric is defined once in a MetricFlow semantic layer on top of the golden tables (35 metrics, from spend and leads to CPL, CPA, and ROAS), and Claude reaches the data through a small MCP server that only answers with those definitions.

To test it, headless Claude answered 50 ad-hoc questions twice: once through the governed MCP server, and once with read-only SQL on the raw source tables. 42 questions have an answer computed in plain SQL; 8 should be refused (churn, NPS, true incremental CTV cost, a channel Fernhook doesn't buy).

| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost |
|---|---|---|---|---|---|
| Claude + governed metrics (MCP) | 42/42 (100%) | 8/8 | 0 | 50/50 | $3.23 |
| Claude + raw tables (SQL) | 22/42 (52%) | 8/8 | 3 | 30/50 | $4.98 |

Model `claude-sonnet-5-5`, one pass per arm, same instructions, built-in tools off. Per-question results: [evals/RESULTS.md](evals/RESULTS.md).

Why the raw arm missed: it had to invent definitions. It left partner fees and webinars out of "paid media", grouped search and YouTube as "Google", counted deals by calendar close date instead of the house week rule, and could not answer share-of-spend questions without channel roles. Every one of those is a definition the semantic layer settles once.

## The model setup

Every table is weekly, by region, for 156 weeks (2023 to 2025).

**Dependent variable:** closed-won deals per region per week (`fct_funnel.won_deals`, summed across sources). New first-year contract value and pipeline sit beside it for revenue and payback views.

**Independent variables:** weekly spend in nine paid channels (`fct_channel_weekly.spend`).

| Channel | Role | What Fernhook buys | Raw export |
|---|---|---|---|
| Paid search, non-brand | Performance | Google ads on category searches like "fleet maintenance software". About 65% of search spend. | `ads_google_weekly` |
| Paid search, brand | Performance | Google ads on searches for "Fernhook". About 35% of search spend, planned against non-brand. | `ads_google_weekly` |
| LinkedIn | Performance | Lead-gen form ads to fleet and operations managers. | `ads_linkedin_weekly` |
| Display retargeting | Performance | Programmatic ads that follow past site visitors. | `ads_display_weekly` |
| Affiliates and partners | Performance | Placement and sponsor fees with resellers, fleet consultants, and review sites. | `partners_weekly` |
| Meta | Brand | Prospecting video to small-business owners. | `ads_meta_weekly` |
| YouTube | Brand | Prospecting video. | `ads_google_weekly` |
| Connected TV (CTV) | Brand | Streaming TV ads, run as a test in 8 of the 20 markets. Cheaper to start and geo-target than broadcast TV. | `ctv_weekly` |
| Webinars | Events | Regional live webinars. | `webinar_events` |

**Controls:** what moves deals besides paid media (`fct_controls_weekly`).

| Control | Why it is in the model | Raw export |
|---|---|---|
| SDR and AE headcount | More SDRs book more calls; more AEs close more trials. A hiring freeze from July 2024 to January 2025 cut both. | `sales_capacity_monthly` |
| Email sends, opens, clicks | Newsletters and nurture emails bring known contacts back. Owned media, so no spend. | `email_weekly` |
| Year-end promo | 15% off annual plans for trials started mid-November to mid-December. Lifts the win rate. | `promo_calendar` |
| List price | Rose 10% in July 2024. Bigger deals, slightly lower win rate. | `promo_calendar` |
| Fleet activity index | Market demand. When fleets are busy, more of them shop for software. | `fleet_activity_index_weekly` |
| Seasonality and trend | Busy at the spring and fall switchovers, a lull from mid-July into September, a soft winter, holiday dips, and steady organic growth. Timing shifts a little by latitude. | the calendar; `dim_region.latitude` |

Three modeling traps are built in on purpose, because real teams hit them:

- **Brand search spend follows demand.** Brand search spend rises and falls with how many people search "Fernhook", and other channels drive some of those searches. A naive model cannot tell whether brand search causes deals or just follows them. Planned regional brand tests act as holdouts: twice a year a few markets pause brand search for 4 to 6 weeks.
- **Brand pushes are timed to demand.** Meta, YouTube, and CTV push before and into the busy seasons, the same weeks fleets shop anyway. A model without seasonality will mix up the season and the media. Each market's push lands on its own week and at its own size, and the size changes from season to season, so a model with market-level seasonality can still tell them apart.
- **Affiliate commissions are not media spend.** Commissions are paid per closed deal, so they follow sales instead of causing them. Only placement and sponsor fees enter the model.

## Three views of the same spend

| View | Where it lives | What it gets wrong |
|---|---|---|
| Platform-reported conversions | `ads_*`, `ctv_weekly`, `partners_weekly`; `fct_channel_weekly.platform_conversions` | Each platform counts conversions it touched, not ones it caused, so their totals overlap. |
| CRM last touch | `crm_leads` UTMs; `fct_channel_weekly.sourced_*` | It credits the final click. Channels people watch but rarely click, like CTV and YouTube, get little; brand search gets a lot. |
| The truth | `sim/truth/truth.json` only | Nothing. It is the answer key, and no dbt model or later agent may read it. |

The true effects are built in: carryover (adstock), diminishing returns (saturation), lead quality that differs by channel, seasonality, trend, and noise. Each run draws every true parameter from a realistic range, so nothing in the answer key is typed into the code. The simulator holds the ranges; the drawn values live only in `truth.json`, and the MMM step is graded against them.

## How the spend is set up

Spend has to move a lot, and not in lockstep, or no model can tell the channels apart.

- **Performance channels are always on.** Brand search, non-brand search, LinkedIn, display, and affiliates run every week in every market. They pause only in planned tests.
- **Brand channels follow the season.** YouTube runs national flights several weeks ahead of each busy season, and each flight skips about one market in four. Meta is always on and pushes closer to the season and into it. CTV runs its own flight in each test market. All three ease off in the slow weeks.
- **Pushes are not in lockstep.** Each market's Meta and CTV push starts on its own week and runs at its own size, and each season's push gets its own budget.
- **Markets:** each channel is spread unevenly across the 20 markets, and always-on budgets are re-split across markets every quarter. CTV runs in only 8 markets.
- **Planned regional tests:** twice a year a few markets pause brand search for 4 to 6 weeks. Non-brand search runs its own tests twice a year: 2 markets pause and 2 get extra budget for 6 to 8 weeks. Markets take turns.
- **Webinars** are regional events, so their spend lands in one market and one week at a time.
- **Affiliate fees** step up or down when each market's partner contracts renew every quarter.
- **Budget history:** each January plan moves in a step, and the team made seven changes between plans. Examples: an attribution review in April 2024 cut YouTube and CTV, a cost cut in August 2024 trimmed LinkedIn, Meta, and display, and Meta got a retest in June 2025.
- National weekly spend for any two channels correlates at under 0.6.

## Quality control

The daily quality control runs in a separate workflow, not in this repo. It works like this:

1. **Scripts run every day.** They build the pipeline and check the output for errors, anomalies, and missing data.
2. **An agent reads the results.** When a check fails, an AI agent reviews the output and opens a GitHub issue with a short synopsis of what is wrong and the likely causes.
3. **A person investigates.** Someone on the team reviews the issue, digs into the cause, and fixes it.

In this repo the same kinds of checks run on demand: the dbt tests in `dbt build`, the validation checks in the [EDA report](docs/eda/EDA.md), and `pytest`.

## Layout

```
sim/             seeded simulator (python -m sim) and the answer key in sim/truth/
data/raw/        CSV exports, one per source system (generated, not committed)
warehouse/       dbt project on DuckDB: staging, intermediate, marts, semantic layer
servers/         MCP servers: governed metrics, and raw SQL for the eval baseline
evals/           50-question eval set, runner, scorer, results
eda/             EDA and validation report (python -m eda), reads the warehouse only
docs/eda/        the generated report and charts
tests/           pytest: determinism, no truth leak, scenario guards
```

Golden tables:

- `fct_channel_weekly`: week x region x paid channel. Spend, delivery, platform claims, last-touch leads and pipeline.
- `fct_funnel`: week x region x lead source. Leads, MQLs, SQLs, opportunities, pipeline, won deals, revenue. Each stage is counted in the week it happened.
- `fct_controls_weekly`: week x region. Headcount, email, promo and price flags, fleet activity index.
- `dim_channel`: channel names, groups, and roles.

## Run it

Windows, Python 3.10 or newer, from the repo root:

```bash
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m sim
.venv\Scripts\dbt build --project-dir warehouse --profiles-dir warehouse
.venv\Scripts\python -m eda
.venv\Scripts\python -m evals.run --arm both
.venv\Scripts\python -m evals.score
.venv\Scripts\python -m pytest -q
```

The same seed always writes byte-identical files. The eval needs the Claude CLI signed in (`claude auth login`); it saves each answer as it lands and resumes if cut off.
