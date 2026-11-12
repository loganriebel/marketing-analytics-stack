# marketing-analytics-stack

The public version of the stack I run at work: dashboards, Claude on golden tables, MMM for budget asks. All data is synthetic.

**Status:** step 1 of 6. The fake company, its raw data, and the dbt golden tables are built and tested. Metrics layer, Claude evals, Tableau, and MMM come next.

## The company

**Fernhook Software** is fictional. It sells fleet-maintenance and work-order software to small and mid-size fleets (5 to 200 vehicles): local delivery, HVAC and plumbing vans, landscaping crews.

- Sales-assisted motion: inbound lead, SDR call, demo, 14-day trial, close.
- Short cycle: a lead closes in about two weeks; nine in ten close in 6 to 27 days.
- First-year contracts run about $6,800 on average.
- About $14M a year in paid media across nine channels, sold in 20 regions across North America, Europe, and APAC.
- About 35 SDRs and 45 AEs.

## The problem

Fernhook grew on paid search, and its CRM credits every deal to the last UTM touch.

- **The mix drifted to performance.** Budget reviews reward the channels closest to the click: search, retargeting, affiliates. TV, YouTube, and Meta look weak in last touch, so they get cut. Performance took 69% of spend in 2023 and 79% in 2025.
- **Search keeps getting more expensive.** Last-touch search cost per lead rose from $171 in 2023 to $207 in 2025. Each new dollar buys less.
- **Growth stalled.** 2025 had the biggest budget yet, and closed-won deals fell by more than 10%. Blended cost per deal rose from $2,500 to almost $3,000.
- **Nobody agrees on the numbers.** Every ad platform claims credit for the same deals, so their totals add up to far more than the CRM has. Last touch never credits TV at all.
- **Finance has stopped trusting marketing.** When the CFO asks what a channel returns, the team can show last-touch numbers or platform numbers, and neither holds up.

**The goal:** use an MMM to give finance one honest number, the overall marketing cost per acquisition (CPA), plus the true CPA of each channel. Then lower it by moving budget between channels at the same total spend.

## The model setup

Every table is weekly, by region, for 156 weeks (2023 to 2025).

**Dependent variable:** closed-won deals per region per week (`fct_funnel.won_deals`, summed across sources). New first-year contract value and pipeline sit beside it for revenue and payback views.

**Independent variables:** weekly spend in nine paid channels (`fct_channel_weekly.spend`).

| Channel | Role | What Fernhook buys | Raw export |
|---|---|---|---|
| Paid search, non-brand | Performance | Google ads on category searches like "fleet maintenance software". 65% of search spend. | `ads_google_weekly` |
| Paid search, brand | Performance | Google ads on searches for "Fernhook". 35% of search spend. | `ads_google_weekly` |
| LinkedIn | Performance | Lead-gen form ads to fleet and operations managers. | `ads_linkedin_weekly` |
| Display retargeting | Performance | Programmatic ads that follow past site visitors. | `ads_display_weekly` |
| Affiliates and partners | Performance | Placement and sponsor fees with resellers, fleet consultants, and review sites. | `partners_weekly` |
| Meta | Brand | Prospecting video to small-business owners. | `ads_meta_weekly` |
| YouTube | Brand | Prospecting video. | `ads_google_weekly` |
| TV | Brand | Linear and streaming (CTV) spots in 8 US markets. | `tv_weekly` |
| Webinars | Events | Regional live webinars. | `webinar_events` |

**Controls:** what moves deals besides paid media (`fct_controls_weekly`).

| Control | Why it is in the model | Raw export |
|---|---|---|
| SDR and AE headcount | More SDRs book more calls; more AEs close more trials. A hiring freeze from July 2024 to January 2025 cut both. | `sales_capacity_monthly` |
| Email sends, opens, clicks | Newsletters and nurture emails bring known contacts back. Owned media, so no spend. | `email_weekly` |
| Year-end promo | 15% off annual plans for trials started mid-November to mid-December. Lifts the win rate. | `promo_calendar` |
| List price | Rose 10% in July 2024. Bigger deals, slightly lower win rate. | `promo_calendar` |
| Fleet activity index | Market demand. When fleets are busy, more of them shop for software. | `fleet_activity_index_weekly` |
| Seasonality and trend | Holiday dips, a summer slowdown, and steady organic growth. | the calendar |

Two modeling traps are built in on purpose, because real teams hit them:

- **Brand search spend follows demand.** People search "Fernhook" after they see TV, YouTube, or Meta, and brand search spend rises with them. A naive model will credit brand search for demand other channels created. Regional brand-search pauses act as holdout tests.
- **Affiliate commissions are not media spend.** Commissions are paid per closed deal, so they follow sales instead of causing them. Only placement and sponsor fees enter the model.

## Three views of the same spend

| View | Where it lives | What it gets wrong |
|---|---|---|
| Platform-reported conversions | `ads_*`, `tv_weekly`, `partners_weekly`; `fct_channel_weekly.platform_conversions` | Every platform over-claims. Brand search and display claim buyers who were already coming. |
| CRM last touch | `crm_leads` UTMs; `fct_channel_weekly.sourced_*` | Brand search gets credit for demand TV, YouTube, and Meta created. TV gets nothing. |
| The truth | `sim/truth/truth.json` only | Nothing. It is the answer key, and no dbt model or later agent may read it. |

The true effects are built in: carryover (adstock), diminishing returns (saturation), seasonality, trend, and noise. Non-brand search is past its saturation point. Brand search mostly buys clicks that would have come anyway. Display retargeting has almost no true effect. TV, YouTube, and Meta are underfunded. Lead quality differs by channel, so cheap leads are not always good leads.

## How the spend is set up

Spend has to move a lot, and not in lockstep, or no model can tell the channels apart.

- **Flighting:** TV and YouTube run in on/off flights, Meta and LinkedIn run in bursts with pauses, non-brand search and display are always on.
- **Regions:** each channel is spread unevenly across the 20 regions, and most channels have a few weeks where a region goes dark. Those act like natural geo holdouts. TV runs in only 8 regions, on its own schedule in each.
- **Webinars** are regional events, so their spend lands in one region and one week at a time.
- **Affiliate fees** step up or down at quarterly contract renewals.
- **Budget drift:** non-brand search, display, and affiliates grow each year; TV, YouTube, and Meta shrink. That is the last-touch habit playing out.
- National weekly spend for any two channels correlates at under 0.4.

## Layout

```
sim/             seeded simulator (python -m sim) and the answer key in sim/truth/
data/raw/        CSV exports, one per source system (generated, not committed)
warehouse/       dbt project on DuckDB: staging, intermediate, marts
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
.venv\Scripts\python -m pytest -q
```

The same seed always writes byte-identical files.
