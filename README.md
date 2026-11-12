# marketing-analytics-stack

The public version of the stack I run at work: dashboards, Claude on golden tables, MMM for budget asks. All data is synthetic.

**Status:** step 1 of 6. The fake company, its raw data, and the dbt golden tables are built and tested. Metrics layer, Claude evals, Tableau, and MMM come next.

## The company

**Fernhook Software** is fictional. It sells fleet-maintenance and work-order software to small and mid-size fleets (5 to 200 vehicles): local delivery, HVAC and plumbing vans, landscaping crews.

- Sales-assisted motion: inbound lead, SDR call, demo, 14-day trial, close.
- Short cycle: a lead closes in about two weeks; nine in ten close in 6 to 27 days.
- First-year contracts run about $6,500 on average.
- About $12M a year in paid media across six channels and 20 sales regions in North America, Europe, and APAC.

## The problem

Fernhook grew on paid search, and its CRM credits every deal to the last UTM touch.

- Every budget review rewards search and display retargeting, because they sit closest to the conversion.
- YouTube and Meta look weak in last touch, so their budgets get cut each year.
- Performance channels took 70% of spend in 2023 and 76% by 2025. Brand fell from 22% to 19%.
- Each ad platform claims credit for the same deals, so their totals add up to far more leads than the CRM has.
- When the CFO asks what marketing returns, the team can only show last-touch numbers or platform numbers, and finance trusts neither.

The questions this repo answers: what does each channel really return, where should the next dollar go, and how do you prove it to finance?

## Three views of the same spend

| View | Where it lives | What it gets wrong |
|---|---|---|
| Platform-reported conversions | `ads_*` exports, `fct_channel_weekly.platform_conversions` | Every platform over-claims. Display claims credit for buyers who were already coming. |
| CRM last touch | `crm_leads` UTMs, `fct_channel_weekly.sourced_*` | Search gets credit for brand searches that YouTube and Meta caused. |
| The truth | `sim/truth/truth.json` only | Nothing. It is the answer key, and no dbt model or later agent may read it. |

The true effects are built in: carryover (adstock), diminishing returns (saturation), seasonality, trend, and noise. Search is past its saturation point. Display retargeting has almost no true effect. YouTube and Meta are underfunded. Lead quality differs by channel, so cheap leads are not always good leads.

## How the spend is set up

Spend has to move a lot, and not in lockstep, or no model can tell the channels apart.

- **Flighting:** YouTube runs in on/off flights, Meta and LinkedIn run in bursts with pauses, search and display are always on.
- **Regions:** each channel is spread unevenly across the 20 regions, and each region has a few weeks where a channel goes dark. Those act like natural geo holdouts.
- **Webinars** are regional events, so their spend lands in one region and one week at a time.
- **Budget drift:** search and display grow each year, YouTube and Meta shrink. That is the last-touch habit playing out.
- National weekly spend for any two channels correlates at under 0.3.

## Layout

```
sim/             seeded simulator (python -m sim) and the answer key in sim/truth/
data/raw/        CSV exports, one per source system (generated, not committed)
warehouse/       dbt project on DuckDB: staging, intermediate, marts
tests/           pytest: determinism, no truth leak, sim shape
```

Golden tables: `fct_channel_weekly` (week x region x paid channel), `fct_funnel` (week x region x lead source, each stage counted in the week it happened), `dim_channel`.

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
