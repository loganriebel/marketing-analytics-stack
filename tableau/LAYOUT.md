# Tableau build plan: Fernhook marketing readout

Three dashboards on Tableau Public, built from the five CSVs in `tableau/data/`. Budget: about 3.5 hours.

| Block | Time |
|---|---:|
| Data sources, parameters, shared calcs | 30 min |
| Dashboard 1, weekly performance readout | 90 min |
| Dashboard 2, three views of the same spend | 40 min |
| Dashboard 3, where the next dollar goes | 45 min |
| QA against the check values, publish | 20 min |

All data is synthetic. Regenerate the CSVs with `python -m tableau.export` after `python -m sim` and `dbt build` (see the root README). `pytest` checks that the committed CSVs match a fresh export and that 2025 spend, leads and won deals equal the governed MetricFlow metrics.

## The data

Tableau title-cases names on connect (`cpa_hdi_low` becomes `Cpa Hdi Low`). Formulas below use those names. Rename `Mqls`, `Sqls` and `Cpa` to `MQLs`, `SQLs` and `CPA` if you like; the formulas follow the rename.

Conventions in every file: ISO dates, one row per grain, flags as 1/0, blank where a value does not exist (CPA with no deals, clicks a source does not report). Weeks start on Monday and belong to the year of their Monday, which is the governed week rule.

| File | Grain | Rows | Notes |
|---|---|---:|---|
| `weekly_channel_market.csv` | week x market x lead source | 40,560 | 156 weeks x 20 markets x 13 sources. `fct_channel_weekly` full-joined to `fct_funnel`, so organic, direct, referral and email keep their funnel rows. Unpaid sources have `Spend` 0 and blank platform fields. |
| `controls_weekly_market.csv` | week x market | 3,120 | `fct_controls_weekly`: SDR and AE headcount, email, promo flag, list price index, fleet activity index. |
| `mmm_channel_views.csv` | channel x view | 36 | Cost per deal four ways for the 8 channels the MMM measures, plus a paid-media total row per view (`Grain` = `paid_media_total`). |
| `mmm_response_curves.csv` | channel x spend multiplier | 72 | Posterior-mean deals with 90% HDI at 0 to 3x each channel's actual 2023 to 2025 spend path. |
| `mmm_optimizer_plan.csv` | channel | 9 | Current vs suggested spend at the same total, with the deal change and its HDI. 7 levers, brand search (not a lever), and a total row. |

Field notes:

- **Spend** in the weekly file is paid media in USD, all 9 paid channels including webinars. Unpaid rows are 0.
- **Leads, MQLs, SQLs, Opportunities, Pipeline Amount, Won Deals, Lost Deals** are counted in the week each stage happened, by the lead's last-touch source. Pipeline is opportunity amount in the week the opportunity was created.
- **Impressions** are blank for affiliates and webinars; **Clicks** for CTV and webinars. **Platform Conversions** are each platform's own claim and overlap across platforms.
- **CTV** runs in 8 markets only (Minneapolis-St. Paul, Milwaukee, Madison, Des Moines, Quad Cities, Toledo, Columbus, Cincinnati), in flights. Zero-spend weeks are real.
- **Latitude** comes from `dim_region`. **Longitude** comes from `tableau/metro_centroids.csv`, public coordinates of each market's main city, because the marts carry latitude only.
- **MMM numbers** cover the full 2023-01-02 to 2025-12-22 window. Spend there is the three-year total; divide by 3 for a yearly view.
- **Views** (`View Id`): `crm_last_touch` (won deals credited to the last UTM touch), `platform_reported` (platform conversions times the company lead-to-won rate), `mmm` (posterior median and 90% HDI), `truth` (the answer key).
- **The answer key** (`View Id` = `truth`, `Is Answer Key` = 1, and `True Deal Change` in the plan) comes from the grader's written results in `mmm/grading/`, never from `sim/truth/`. It exists only because the data is synthetic; a real team never has it. Label it that way everywhere it shows.
- **Upper funnel through brand search:** for Meta, YouTube and CTV, `Deals Via Brand Search` and `Cpa Total` add the deals they create through brand searches. The headline `Cpa` is direct, matching the graded table in `docs/mmm/README.md`. The response curves for those three already include the brand-search path (`Curve Basis`), because that is the curve the optimizer moves.

## Data sources and relationships

Three data sources. Extracts are automatic on Tableau Public.

| Data source | Tables | Relationship (keys) | Cardinality |
|---|---|---|---|
| **Weekly** | `weekly_channel_market` (root), `controls_weekly_market` | `Week Start` = `Week Start` and `Region Id` = `Region Id` | many to one, all records match |
| **MMM views** | `mmm_channel_views` | none | |
| **MMM plan** | `mmm_optimizer_plan` (root), `mmm_response_curves` | `Channel Id` = `Channel Id` | one to many, some records match (the total row has no curve) |

On connect:

- Weekly: set `Latitude` and `Longitude` geographic roles. Convert `Is Paid` and `Channel Sort` to dimensions. Alias `Is Paid` 1/0 to Paid/Unpaid. Use the weekly table's `Market`, `State` and `Sales Area`; hide the duplicates from the controls table.
- MMM views: convert `Channel Sort`, `View Order`, `Is Answer Key` to dimensions. Sort `View Name` by `View Order`.
- MMM plan: convert `Channel Sort`, `Is Lever`, `At Bound` to dimensions. Convert `Spend Multiplier` (curves) to a continuous dimension. Use the plan table's `Channel Name` and `Marketing Role`.
- Every source: sort `Channel Name` by `Channel Sort` (field, minimum, ascending), so channels sit in the same order on every sheet.

## Colors

Okabe-Ito based, safe for color-blind readers. Assign `Marketing Role` in each of the three data sources with the same hex values.

| Marketing Role | Hex | Channels |
|---|---|---|
| performance | `#0072B2` | Paid Search Brand, Paid Search Non-Brand, Display Retargeting, Affiliates and Partners |
| brand | `#E69F00` | Meta, YouTube, Connected TV, LinkedIn |
| events | `#CC79A7` | Webinars |
| owned | `#009E73` | Email |
| unpaid | `#999999` | Organic Search, Direct, Referral |

Views, on Dashboard 2 only:

| View | Hex | Mark |
|---|---|---|
| CRM last touch | `#7F7F7F` | filled circle |
| Platform reported | `#CC79A7` | filled circle |
| MMM | `#009E73` | filled circle with 90% HDI line |
| Truth (answer key) | `#000000` | hollow diamond |

Deltas: good `#2E7D32`, bad `#C62828`, neutral `#6B6B6B`. Up is good for leads, won deals and pipeline; down is good for CPL and CPA; spend is neutral. Number format for deltas: `▲0.0%;▼0.0%;0.0%`.

Fonts: Tableau Book and Tableau Semibold render on Public without substitution.

## Parameters (Weekly source)

| Parameter | Type | Values | Default |
|---|---|---|---|
| `p.Report Week` | Date | List, when workbook opens, from `Week Start` | 2025-12-15 |
| `p.Weeks` | Integer | List: 1 = "This week", 4 = "Last 4 weeks", 13 = "Last 13 weeks" | 1 |
| `p.Trend Measure` | String | Spend, Leads, CPL, Won deals, CPA, Pipeline | Won deals |

2025-12-15 is the last full week before Christmas; the 2025-12-22 week runs at reduced holiday spend. The latest weeks also undercount deals, because their leads have not had time to close.

## Shared calcs (Weekly source)

**Period.** One field puts each week in the current period, the prior period, or the same weeks a year earlier. 364 days keeps Mondays aligned.

```
// Days Back
DATEDIFF('day', [Week Start], [p.Report Week])

// Period
IF [Days Back] >= 0 AND [Days Back] < 7 * [p.Weeks] THEN "Current"
ELSEIF [Days Back] >= 7 * [p.Weeks] AND [Days Back] < 14 * [p.Weeks] THEN "Prior"
ELSEIF [Days Back] >= 364 AND [Days Back] < 364 + 7 * [p.Weeks] THEN "Year ago"
END
```

**Period measures.** One pattern, three periods (Cur, Prior, YA). Build Spend, then duplicate.

```
// Spend Cur
SUM(IF [Period] = "Current" THEN [Spend] END)
// Spend Prior
SUM(IF [Period] = "Prior" THEN [Spend] END)
// Spend YA
SUM(IF [Period] = "Year ago" THEN [Spend] END)
```

| Base field | Cur, Prior, YA names |
|---|---|
| `[Spend]` | Spend Cur, Spend Prior, Spend YA |
| `[Leads]` | Leads Cur, Leads Prior, Leads YA |
| `[Won Deals]` | Won Cur, Won Prior, Won YA |
| `[Pipeline Amount]` | Pipeline Cur, Pipeline Prior, Pipeline YA |
| `[Mqls]`, `[Sqls]`, `[Opportunities]`, `[Lost Deals]` | MQLs Cur, SQLs Cur, Opps Cur, Lost Cur (and YA for the funnel rates) |

**Ratios.** Without a channel filter these are blended: all paid spend over all leads or deals, including unpaid sources. That is the governed definition of `cost_per_lead` and `cost_per_acquisition`. Filtered to a channel they become last-touch CPL and CPA.

```
// CPL Cur            (and CPL Prior, CPL YA)
[Spend Cur] / [Leads Cur]
// CPA Cur            (and CPA Prior, CPA YA)
[Spend Cur] / [Won Cur]
```

**Deltas.** Six KPIs x two comparisons.

```
// Spend vs Prior     (same for Leads, CPL, Won, CPA, Pipeline)
[Spend Cur] / [Spend Prior] - 1
// Spend vs YA
[Spend Cur] / [Spend YA] - 1
```

A text mark takes one color, so each colored delta splits into a good and a bad field, and only one is ever non-null. Color them statically in the text editor. Spend stays neutral.

```
// CPA vs Prior Good   (CPL the same)
IF [CPA vs Prior] < 0 THEN [CPA vs Prior] END
// CPA vs Prior Bad
IF [CPA vs Prior] > 0 THEN [CPA vs Prior] END
// Won vs Prior Good   (Leads and Pipeline the same: up is good)
IF [Won vs Prior] > 0 THEN [Won vs Prior] END
// Won vs Prior Bad
IF [Won vs Prior] < 0 THEN [Won vs Prior] END
```

Repeat for the vs YA deltas.

**Dashboard filters** for every Weekly sheet: `Sales Area`, `Marketing Role`, `Channel Name` (multi-select), and `Market` through the map action. Apply to all sheets using this data source.

## Dashboard 1: weekly performance readout

Title: "Fernhook weekly readout". Subtitle, computed: `"Week of " + STR([p.Report Week])`, plus the period length. Fixed size 1400 x 1000.

Layout, top to bottom: KPI tiles across the top; channel table (left, 60%) beside the map (right); trend line with the capacity strip under it (left) beside the funnel (right); the "what to test next" note across the bottom.

### 1.1 KPI tiles (6 sheets, or one sheet per tile from a template)

- **Feeds:** Weekly.
- **Build:** one sheet per KPI: Spend, Leads, CPL, Won deals, CPA, Pipeline. Text mark. Line 1: `[X Cur]` large. Line 2: `[X vs Prior Good]`, `[X vs Prior Bad]`, then the same pair for vs YA, with the delta format, good fields in green and bad in red. Spend shows plain `[Spend vs Prior]` and `[Spend vs YA]` in neutral gray.
- **Calcs:** the period measures, ratios and deltas above. Label line 2 "vs prior week" when `p.Weeks` = 1 and "vs prior period" otherwise:
  ```
  // Prior Label
  IF [p.Weeks] = 1 THEN "vs prior week" ELSE "vs prior " + STR([p.Weeks]) + " weeks" END
  ```
- **Filters:** none of their own. The dashboard filters apply.
- **Tooltip:** prior and year-ago values in full.

### 1.2 Channel table

- **Feeds:** Weekly.
- **Build:** Rows `Marketing Role`, `Channel Name` (sorted by `Channel Sort`). Columns `Measure Names`. Mark: Square; `Measure Values` on Label; `Marketing Role` on Color at 25% opacity, so each row is tinted by role. Subtotals by role, grand total on. Measures: Spend Cur, Share of Spend, Leads Cur, Table CPL, Won Cur, Table CPA, Pipeline Cur, Won vs YA.
- **Calcs:**
  ```
  // Share of Spend   (table calc, compute using Channel Name)
  [Spend Cur] / TOTAL([Spend Cur])
  // Table CPL        (blank for unpaid sources and channels with no leads)
  IF [Spend Cur] > 0 AND [Leads Cur] > 0 THEN [Spend Cur] / [Leads Cur] END
  // Table CPA
  IF [Spend Cur] > 0 AND [Won Cur] > 0 THEN [Spend Cur] / [Won Cur] END
  ```
- **Filters:** dashboard filters. `Channel Name` filter excludes nothing by default; unpaid rows show leads and deals with blank CPL and CPA.
- **Color:** role tint as above.
- **Note:** grand total CPL and CPA equal the blended KPI tiles.

### 1.3 Trend line

- **Feeds:** Weekly.
- **Build:** Columns `Week Start` (exact date, continuous). Rows `Trend Value` and `Trend Last Year`, dual axis, synchronized. This year solid `#333333`, last year dashed `#999999`. Reference band from `MIN([Period Start])` to `p.Report Week`.
- **Calcs:**
  ```
  // Period Start
  [p.Report Week] - 7 * ([p.Weeks] - 1)
  // Trend Value
  CASE [p.Trend Measure]
    WHEN "Spend" THEN SUM([Spend])
    WHEN "Leads" THEN SUM([Leads])
    WHEN "CPL" THEN SUM([Spend]) / SUM([Leads])
    WHEN "Won deals" THEN SUM([Won Deals])
    WHEN "CPA" THEN SUM([Spend]) / SUM([Won Deals])
    WHEN "Pipeline" THEN SUM([Pipeline Amount])
  END
  // Trend Last Year  (table calc along Week Start; every week is present, so -52 is 364 days)
  LOOKUP([Trend Value], -52)
  // Trend Window     (table calc filter, keep True; leaves the prior year in the partition)
  LOOKUP(MIN([Week Start]), 0) > [p.Report Week] - 364
  AND LOOKUP(MIN([Week Start]), 0) <= [p.Report Week]
  ```
- **Filters:** `Trend Window` = True, plus dashboard filters. Do not filter `Week Start` as a dimension; that removes the prior year from `LOOKUP`.
- **Color:** neutral. With a role or channel filter active the line follows it.

### 1.4 Capacity and promo strip (under the trend)

- **Feeds:** Weekly, controls table through the relationship.
- **Build:** Columns `Week Start` (same window). Rows `SUM([Sdr Headcount])` and `SUM([Ae Headcount])` as lines, plus `Promo Week` as a light gray bar on a hidden dual axis. Height about 90 px.
- **Calcs:**
  ```
  // Promo Week
  MAX([Is Discount Promo])
  ```
- **Filters:** `Trend Window`, `Sales Area`, `Market`. It explains the 2025 dip: the hiring freeze ran July 2024 to January 2025.
- **Color:** SDR `#56B4E9`, AE `#0072B2`, promo `#E0E0E0`.

### 1.5 Market map

- **Feeds:** Weekly.
- **Build:** `AVG([Longitude])` on Columns, `AVG([Latitude])` on Rows. Detail `Market`, `Region Id`. Size `Won Cur`. Color `Won vs YA`, diverging orange-blue centered on 0, range ±30%. Label `Market` for the six largest. Background: Tableau Light, Midwest extent.
- **Calcs:**
  ```
  // Deals per 1k Accounts   (tooltip)
  [Won Cur] / MIN([Target Accounts]) * 1000
  // Market CPA             (tooltip)
  [Spend Cur] / [Won Cur]
  // CTV Market             (tooltip; FIXED, so a channel filter does not change it)
  {FIXED [Region Id] : SUM(IF [Channel Id] = "ctv" THEN [Spend] END)} > 0
  ```
- **Filters:** dashboard filters. Dashboard action: select on the map filters the table, trend, strip and funnel by `Market`.
- **Tooltip:** market, state, sales area, spend, leads, won deals, CPA, deals per 1k accounts, and "CTV test market" when `CTV Market` is true.

### 1.6 Funnel conversion (2 sheets)

- **Feeds:** Weekly.
- **Counts:** Rows `Measure Names` (Leads Cur, MQLs Cur, SQLs Cur, Opps Cur, Won Cur, in that order). Columns `Measure Values`, bar. Label values. Color `#9E9E9E`, with Won Cur `#333333`. Role colors stay off this sheet, since stages are not channels.
- **Rates:** a text sheet under it with four rates and their year-over-year change in points. These are same-period ratios, because each stage is counted in its own week; they are not cohort rates. Same definitions as the governed `mql_rate`, `sql_rate`, `opportunity_rate` and `win_rate`.
  ```
  // MQL Rate Cur
  [MQLs Cur] / [Leads Cur]
  // SQL Rate Cur
  [SQLs Cur] / [MQLs Cur]
  // Opp Rate Cur
  [Opps Cur] / [SQLs Cur]
  // Win Rate Cur
  [Won Cur] / ([Won Cur] + [Lost Cur])
  // Win Rate YoY pts      (same for the other three)
  ([Win Rate Cur] - [Won YA] / ([Won YA] + [Lost YA])) * 100
  ```
- **Filters:** dashboard filters. Filter to a channel to see its last-touch funnel.

### 1.7 What to test next (text object)

Static text, rewritten each week. Starting draft, grounded in the MMM's uncertainty rather than the answer key:

> **What to test next**
>
> 1. **Non-brand search budget test.** It is half of paid spend, always on, and went from $3.4M in 2023 to $8.4M in 2025, so the MMM can only bound its cost per extra deal between $4.1k and $11.3k. Run 10 matched markets at its 2023 pace for 12 weeks from February, and read deals against the other 10 (the pre-registered test in `geotest/PREREGISTRATION.md`).
> 2. **YouTube heavy-up.** The MMM's cheapest next dollar ($2.3k per extra deal), but it has never run at the level the model recommends. Push it in a crossing 10 markets in the same test.
> 3. **Refit with both reads as lift tests.** On the development seed, planned tests put brand search on target; without them it came out 54% low.

## Dashboard 2: three views of the same spend

Title: "Three views of the same spend". Subtitle: "Cost per closed-won deal by channel, 2023 to 2025. The black diamond is the answer key, which exists only because Fernhook is synthetic." Fixed size 1400 x 900.

Layout: scorecard across the top; dot plot (left, 65%) beside the error table (right). Caption at the bottom.

**Parameter and filter, shared by the sheets:**

```
// p.Show Answer Key   (Boolean, default True)
// Show View          (filter, keep True, on every sheet)
[p.Show Answer Key] OR [View Id] != "truth"
```

Turning it off shows what a real team has: three views that disagree.

### 2.1 Scorecard

- **Feeds:** MMM views.
- **Build:** Columns `View Name` (sorted by `View Order`). Rows `Measure Names`: `MIN([Cpa])` (paid-media CPA), `MIN([Cpa Rank Corr Vs Truth])`, `MIN([Median Abs Cpa Error Pct])` (already in percent units), `Best Pick Label`. Text mark, colored by `View Name`. Tooltip on the MMM column: `Cpa Hdi Low` to `Cpa Hdi High`.
- **Calcs:**
  ```
  // Best Pick Label   (an aggregate string, so it can sit in Measure Values)
  IF MIN([View Id]) = "truth" THEN MIN([Best Next Dollar])
  ELSEIF MIN([Best Next Dollar Right]) = 1 THEN MIN([Best Next Dollar]) + " ✓"
  ELSE MIN([Best Next Dollar]) + " ✗"
  END
  ```
- **Filters:** `Grain` = paid_media_total, `Show View`.

### 2.2 Dot plot: CPA by channel four ways

- **Feeds:** MMM views.
- **Build:** Rows `Marketing Role`, `Channel Name`. Columns `Cpa` and `Measure Values` (`Cpa Hdi Low`, `Cpa Hdi High`), dual axis, synchronized, both log scale, fixed range 300 to 100,000.
  - Marks 1 (`Cpa`): Shape and Color by `View Name` (see Colors), size about 9. Detail `View Id`.
  - Marks 2 (interval): Line, `Measure Names` on Path, color `#009E73`, size 2. Only MMM rows carry an HDI, so only they draw.
- **Calcs:** none beyond the filter.
- **Filters:** `Grain` = channel, `Show View`.
- **Color by role:** the `Marketing Role` row header carries the role; add a thin sheet left of it with `MIN(1)` as a Square colored by `Marketing Role` and headers hidden, or tint the row-header pane.
- **Annotation:** on Connected TV, "CRM last touch: no deals credited, no CPA". The CRM row has blank CPA, so it draws nothing.
- **Tooltip:** `View Name`, `Deals`, `Cpa`, HDI for MMM, `Deals Via Brand Search` and `Cpa Total` where present, and `Note`.

### 2.3 Error table: how far each view is from the answer key

- **Feeds:** MMM views.
- **Build:** Rows `Channel Name`. Columns `View Name`. Mark: Square. Color `Log Error`, diverging, centered on 0, range -1 to 1 (10x low to 10x high). Label `Times Off`.
- **Calcs:**
  ```
  // Truth CPA
  {FIXED [Channel Id] : MIN(IF [View Id] = "truth" THEN [Cpa] END)}
  // CPA Ratio
  MIN([Cpa]) / MIN([Truth CPA])
  // Log Error
  LOG([CPA Ratio])
  // Times Off
  IF ISNULL([CPA Ratio]) THEN "no CPA"
  ELSEIF [CPA Ratio] >= 1 THEN STR(ROUND([CPA Ratio], 1)) + "x high"
  ELSE STR(ROUND(1 / [CPA Ratio], 1)) + "x low"
  END
  ```
- **Filters:** `Grain` = channel, `View Id` != truth. Hide this sheet when `p.Show Answer Key` is False (dynamic zone visibility on the parameter).
- **Color:** diverging, not role. Role stays on the dot plot's header.

**Caption (draft):** "No view gets both the level and the ranking right. Platform-reported ranks closest (0.79) but claims more than twice the deals. Last touch lands near the true total but splits it badly (0.10) and gives CTV nothing. The MMM ranks better than last touch (0.48), picks the right best and worst next dollar (YouTube and display), and lands non-brand search's average cost within 7%, but still gives paid media too little credit."

## Dashboard 3: where the next dollar goes

Title: "Where the next dollar goes". Subtitle: "MMM response curves and a reallocation at the same total spend, 2023 to 2025 spend paths." Fixed size 1400 x 1000.

Layout: plan BANs across the top; response curves as small multiples (full width); next-dollar ranking (left) beside the optimizer shift (right).

### 3.1 Plan BANs

- **Feeds:** MMM plan.
- **Build:** text, from the total row: deal change mean, its 90% HDI, `Prob Gain Positive`, `True Deal Change` (labeled "answer key"), and `Brand Search Spend Change`.
- **Filters:** `Grain` = total.

### 3.2 Response curves (small multiples)

- **Feeds:** MMM plan (curves table, plan table through `Channel Id`).
- **Build:** Columns `Channel Name` then `Spend Multiplier` (continuous dimension, 0 to 3). Rows `Measure Values` (`Deals Hdi Low`, `HDI Width`) as stacked Area, dual axis with `SUM([Deals Mean])` as Line. Synchronize. Y axis: independent range per column. Area colored by `Measure Names`: the low area transparent, the width area `#D9D9D9`. The line is colored by `Marketing Role`.
  - Reference band, per pane, from 0.5 to 1.5: the optimizer's bounds.
  - Reference lines, per pane: at 1 ("today") and at `MIN([Multiplier])` from the plan table ("plan").
- **Calcs:**
  ```
  // HDI Width
  [Deals Hdi High] - [Deals Hdi Low]
  // Curve Marginal CPA   (tooltip; table calc along Spend Multiplier)
  (SUM([Spend]) - LOOKUP(SUM([Spend]), -1)) / (SUM([Deals Mean]) - LOOKUP(SUM([Deals Mean]), -1))
  ```
- **Filters:** none. Brand search shows its curve and a "not a lever" label (`Is Lever` = 0).
- **Color:** `Marketing Role`.
- **Tooltip:** spend in $M, deals with HDI, `Curve Basis`, curve marginal CPA.

### 3.3 Next-dollar ranking

- **Feeds:** MMM views.
- **Build:** Rows `Channel Name`, sorted by MMM marginal CPA ascending. Columns `Marginal Cpa` and `Measure Values` (`Marginal Cpa Hdi Low`, `Marginal Cpa Hdi High`), dual axis, log scale. MMM dot colored by `Marketing Role`; HDI as a line with `Measure Names` on Path; answer key as a black hollow diamond.
- **Calcs:**
  ```
  // MMM Marginal Sort
  {FIXED [Channel Id] : MIN(IF [View Id] = "mmm" THEN [Marginal Cpa] END)}
  ```
- **Filters:** `Grain` = channel, `View Id` in (mmm, truth), `Show View` from Dashboard 2 if you reuse the parameter.

### 3.4 Optimizer shift (2 sheets, shared row order)

- **Feeds:** MMM plan.
- **Spend shift:** Rows `Channel Name`. Columns `Spend Change` in $M, diverging bars colored by `Bar Color`. Label `Change Label`; brand search adds "follows searches, not a lever".
- **Deal change:** same rows. Columns `Deal Change Mean` (circle, role color) dual with `Measure Values` (`Deal Change Hdi Low`, `Deal Change Hdi High`) as a line on Path, plus `True Deal Change` as a black hollow diamond. Zero line.
- **Calcs:**
  ```
  // Change Label
  IIF([Multiplier] >= 1, "+", "") + STR(ROUND(([Multiplier] - 1) * 100)) + "%"
  + IIF([At Bound] = 1, " (cap)", "")
  // Bar Color   (role colors, plus "not a lever" = #BDBDBD)
  IF [Is Lever] = 0 THEN "not a lever" ELSE [Marketing Role] END
  // Spend Change per Year   (tooltip)
  [Spend Change] / 3
  ```
- **Filters:** `Grain` = channel.

**Caption (draft):** "At the same total spend, the plan moves money from display, affiliates, LinkedIn and a little non-brand search to YouTube, CTV and Meta. The MMM expects +654 deals (90% HDI 363 to 932); the answer key gives +1,045. YouTube, CTV and display sit at the ±50% bound, so the plan goes as far as the bounds allow, not as far as the curves would."

## Check values

With the defaults (report week 2025-12-15, 1 week, no filters):

| KPI | Current | vs prior week | vs year ago |
|---|---:|---:|---:|
| Spend | $274,153 | -18.3% | +19.9% |
| Leads | 3,992 | -8.7% | -1.4% |
| CPL | $68.68 | -10.5% | +21.6% |
| Won deals | 233 | +14.8% | +18.3% |
| CPA | $1,177 | -28.8% | +1.3% |
| Pipeline | $1,638,570 | -2.0% | +0.9% |

With `p.Weeks` = 4: spend $1,253,829, leads 17,893, won deals 877, CPA $1,430.

Funnel, same week: MQL rate 53.5%, SQL rate 38.6%, opportunity rate 70.4%, win rate 34.7%. Channel table: Paid Search Non-Brand $147,779 spend, CPL $159.59; Chicago has the most won deals (49).

Full years: 2025 spend $17,230,000, leads 244,894, won deals 9,713 (the governed metrics give the same). 2024: $14,850,000, 242,658, 11,008.

Dashboard 2, paid-media CPA: CRM $2,832, platform $1,305, MMM $3,925 ($2,987 to $4,916), answer key $2,821. Rank correlation: CRM 0.10, platform 0.79, MMM 0.48.

Dashboard 3: plan +654 deals mean (median 667, HDI 363 to 932), P(gain) 99.95%, answer key +1,045. YouTube and CTV +50% (cap), Meta +7%, non-brand -3%, LinkedIn -6%, display -50% (cap), affiliates -20%. Brand search +$188,623.

## Publish to Tableau Public

1. Build in Tableau Public (desktop, free). It connects to text files; the workbook stores the data as an extract.
2. Hide every worksheet (each dashboard tab, Hide All Sheets). Dashboard order: 1, 2, 3.
3. Open Dashboard 2 last before saving. Public lands on the sheet that was open at save time and uses it for the thumbnail, and the four-way comparison is the strongest first view.
4. File, Save to Tableau Public As. Name: "Fernhook marketing readout (synthetic)".
5. On the published page, Edit Details:
   - Description: "Fictional company, fully synthetic data. Weekly readout, three views of channel CPA against an answer key, and MMM budget curves. Code and data: github.com/loganriebel/marketing-analytics-stack."
   - Turn on Show Sheets as Tabs and Allow Access (download), since the data is synthetic.
   - Check Show Viz on Profile.
6. Open it on a phone. If the fixed layout is unreadable, add a phone device layout with the KPI tiles, the channel table and the dot plot only.
7. To refresh: re-run `python -m tableau.export`, then Data, Refresh All Extracts, and save to Tableau Public under the same name to overwrite. Public cannot refresh from local files on a schedule.
