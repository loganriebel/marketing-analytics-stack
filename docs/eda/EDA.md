# EDA and data validation

Built by `python -m eda` from the dbt warehouse only: the golden tables plus a few staging views. Nothing here reads the simulator or its answer key, so this is what an analyst at Fernhook would see before an MMM.

## 1. Validation checks

9 of 10 checks pass; notes flag known limits. The dbt tests (`dbt build`) cover row-level rules; these are the checks an analyst reads before trusting the data.

| Check | Result | Status |
|---|---|---|
| Reporting window | 156 weeks, 2023-01-02 to 2025-12-22, 20 regions | Pass |
| fct_channel_weekly is a full grid | 28,080 rows (expected 28,080) | Pass |
| fct_funnel is a full grid | 40,560 rows (expected 40,560) | Pass |
| fct_controls_weekly is a full grid | 3,120 rows (expected 3,120) | Pass |
| Spend matches the platform exports | $113.9M in both; difference $0.00 | Pass |
| No negative values; clicks never exceed impressions | 0 bad rows | Pass |
| Every lead maps to a channel | 0 unmapped of 2,051,367; 19% recorded as direct | Pass |
| Lead to close (won deals) | median 14 days; 80% between 8 and 24 | Pass |
| Censoring at the end of the window | 36% of opportunities from the last 4 weeks are still open; treat the final weeks of deals as incomplete | Note |
| Promo and price calendar loaded | 4 entries | Pass |
| Channels are not collinear | largest correlation 0.78 (Paid Search Non-Brand and LinkedIn); largest VIF 4.1 | Review |

## 2. Outcome and spend over time

![Spend and deals](img/spend_and_deals.png)

| Year | Paid spend | Leads | Closed-won deals | New contract value | Spend per deal |
|---|---|---|---|---|---|
| 2023 | $33.8M | 570,252 | 26,637 | $72.0M | $1,267 |
| 2024 | $37.1M | 597,483 | 27,658 | $78.1M | $1,342 |
| 2025 | $43.1M | 604,780 | 24,886 | $73.8M | $1,731 |

The last few weeks of 2025 are undercounted for deals, because those leads have not had time to close.

## 3. Seasonality

Expected pattern for Midwest service fleets: busy when the season turns (AC switching on in late spring, heat switching on in late fall), a lull from mid-July into September, a soft winter, a deep holiday dip in late December and early January, and a smaller dip at Thanksgiving.

![Seasonality](img/seasonality.png)

| Period | Expected | Leads index (100 = average week) | Holds |
|---|---|---|---|
| Holiday weeks (51, 52, 1) | well below 100 | 73 | Yes |
| Thanksgiving week (47) | below 100 | 98 | Yes |
| Winter after the holidays (weeks 3 to 9) | below 100 | 88 | Yes |
| Spring switchover, AC on (weeks 19 to 25) | above 100 | 111 | Yes |
| Summer lull into early fall (weeks 29 to 37) | below 100 | 94 | Yes |
| Fall switchover, heat on (weeks 40 to 45) | above 100 | 115 | Yes |

6 of 6 expectations hold. The data matches the planning calendar. During the year-end promo (weeks 46 to 50), deals run +7% relative to leads, which is what a discount on annual plans should do.

## 4. How the media was flighted

![Flighting calendar](img/flighting_calendar.png)

![Spend by channel](img/spend_by_channel.png)

| Channel | Weeks on (of 156) | Regions used | Typical run in a region (weeks) | Typical pause (weeks) |
|---|---|---|---|---|
| Paid Search Brand | 156 | 20 | 156 | none |
| Paid Search Non-Brand | 156 | 20 | 156 | none |
| Meta | 156 | 20 | 156 | none |
| LinkedIn | 156 | 20 | 156 | none |
| YouTube | 156 | 20 | 156 | none |
| Connected TV | 103 | 8 | 8 | 15 |
| Display Retargeting | 156 | 20 | 156 | none |
| Affiliates and Partners | 156 | 20 | 156 | none |
| Webinars | 123 | 20 | 1 | 8 |

Media plan changes logged between annual plans:

| Date | Channel | Change | Reason |
|---|---|---|---|
| 2023-04-03 | Connected TV | +15% | Q1 review: CTV test expands, YouTube trimmed |
| 2023-04-03 | Paid Search Non-Brand | +7% | Q1 review: CTV test expands, YouTube trimmed |
| 2023-04-03 | YouTube | -22% | Q1 review: CTV test expands, YouTube trimmed |
| 2023-10-02 | Display Retargeting | +18% | Q4 plan: more retargeting for year-end |
| 2023-10-02 | Meta | -12% | Q4 plan: more retargeting for year-end |
| 2024-04-01 | Affiliates and Partners | +21% | Attribution review: video and CTV show few last-touch leads |
| 2024-04-01 | Connected TV | -34% | Attribution review: video and CTV show few last-touch leads |
| 2024-04-01 | Paid Search Non-Brand | +12% | Attribution review: video and CTV show few last-touch leads |
| 2024-04-01 | YouTube | -31% | Attribution review: video and CTV show few last-touch leads |
| 2024-08-05 | LinkedIn | -19% | Hiring freeze: brand programs trimmed, search protected |
| 2024-08-05 | Meta | -17% | Hiring freeze: brand programs trimmed, search protected |
| 2024-08-05 | Paid Search Non-Brand | +10% | Hiring freeze: brand programs trimmed, search protected |
| 2024-11-04 | Affiliates and Partners | -24% | Two reseller contracts end |
| 2025-02-03 | Display Retargeting | +13% | New fiscal year: more for what last touch rewards |
| 2025-02-03 | LinkedIn | -15% | New fiscal year: more for what last touch rewards |
| 2025-02-03 | Paid Search Non-Brand | +20% | New fiscal year: more for what last touch rewards |
| 2025-06-02 | Meta | +23% | Meta retest after a new creative agency |
| 2025-06-02 | YouTube | -14% | Meta retest after a new creative agency |

## 5. Spend mix

![Mix by year](img/mix_by_year.png)

| Year | Performance | Brand | Events |
|---|---|---|---|
| 2023 | 57% | 38% | 5% |
| 2024 | 67% | 29% | 5% |
| 2025 | 76% | 19% | 4% |

## 6. Reporting sources disagree

![Claims vs CRM](img/claims_vs_crm.png)

Platforms claim 1,995,724 conversions in total; the CRM credits 1,008,114 leads to paid channels. Connected TV gets 0 last-touch leads because nobody clicks a TV ad. Neither source measures what a channel adds; that is the MMM's job.

## 7. Controls

![Controls](img/controls.png)

- **Sales headcount** grows each Q1 hiring wave, then falls through the July 2024 to January 2025 freeze.
- **Email** volume grows with the list, with blasts in promo weeks.
- **Fleet activity index** moves a few points either way; it is the market-demand control.
- **Promo and price:** year-end discount weeks are flagged each year; list price rose 10% in July 2024 (index 1.10 after).

## 8. Channel by channel

What the data shows about how each channel was bought and reported. These are observations, not effects.

### Paid Search Brand

*Performance channel.* Bids on every search for Fernhook, always on in every market. Spend follows how many people search the brand, and Meta, YouTube and CTV ads drive some of those searches.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $6.0M, 2024: $6.2M, 2025: $6.4M. Highest in Q2, lowest in Q1; the biggest week was 1.3 times a typical on-week. The top 5 regions take 51% of its spend and hold 51% of target accounts.
- **Plan changes:** none between annual plans.
- **Reporting:** the platform claims 315,639 conversions; the CRM credits 337,384 last-touch leads (0.9 times). Last-touch cost per lead: 2023: $52, 2024: $54, 2025: $59.
- **What to watch in the MMM:** its weekly spend tracks total leads closely (correlation 0.91). Spend that follows demand can look like it causes demand, and Meta, YouTube and CTV create some of the searches it pays for. It never pauses, so no test separates what it adds from the demand it follows.

### Paid Search Non-Brand

*Performance channel.* Always on in every market. Budgets lean into busy seasons and are re-split across markets every quarter.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $8.4M, 2024: $13.0M, 2025: $21.1M. Highest in Q2, lowest in Q1; the biggest week was 2.2 times a typical on-week. The top 5 regions take 57% of its spend and hold 50% of target accounts.
- **Plan changes:** Apr 2023 +7% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 +12% (Attribution review: video and CTV show few last-touch leads); Aug 2024 +10% (Hiring freeze: brand programs trimmed, search protected); Feb 2025 +20% (New fiscal year: more for what last touch rewards).
- **Reporting:** the platform claims 415,847 conversions; the CRM credits 282,605 last-touch leads (1.5 times). Last-touch cost per lead: 2023: $117, 2024: $136, 2025: $184.
- **What to watch in the MMM:** always on and seasonal (correlation with total leads 0.41), so most of its signal comes from quarterly market re-splits and plan changes, not from week-to-week swings.

### Meta

*Brand channel.* Always-on prospecting that pushes before and into the spring and fall busy seasons and eases off in slow weeks. Each market's timing differs.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $4.0M, 2024: $3.6M, 2025: $3.4M. Highest in Q4, lowest in Q1; the biggest week was 3.0 times a typical on-week. The top 5 regions take 47% of its spend and hold 47% of target accounts.
- **Plan changes:** Oct 2023 -12% (Q4 plan: more retargeting for year-end); Aug 2024 -17% (Hiring freeze: brand programs trimmed, search protected); Jun 2025 +23% (Meta retest after a new creative agency).
- **Reporting:** the platform claims 533,541 conversions; the CRM credits 147,408 last-touch leads (3.6 times). Last-touch cost per lead: 2023: $76, 2024: $74, 2025: $73.
- **What to watch in the MMM:** pushes land on the busy seasons, so spend rises when demand does. Each market's push comes on its own week and at its own size, and that is the contrast to learn from; the June 2025 retest adds a late step up.

### LinkedIn

*Brand channel.* Lead-gen forms, always on. Market budgets are re-split every quarter.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $3.1M, 2024: $2.1M, 2025: $1.3M. Highest in Q1, lowest in Q3; the biggest week was 1.8 times a typical on-week. The top 5 regions take 66% of its spend and hold 51% of target accounts.
- **Plan changes:** Aug 2024 -19% (Hiring freeze: brand programs trimmed, search protected); Feb 2025 -15% (New fiscal year: more for what last touch rewards).
- **Reporting:** the platform claims 72,896 conversions; the CRM credits 35,026 last-touch leads (2.1 times). Last-touch cost per lead: 2023: $197, 2024: $177, 2025: $163.
- **What to watch in the MMM:** always on with no pauses, so its signal comes from quarterly market re-splits and plan changes.

### YouTube

*Brand channel.* National flights that run several weeks ahead of each busy season, with a low level in between. Each flight targets about three in four markets.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $2.5M, 2024: $2.4M, 2025: $2.1M. Highest in Q3, lowest in Q4; the biggest week was 12.3 times a typical on-week. The top 5 regions take 50% of its spend and hold 50% of target accounts.
- **Plan changes:** Apr 2023 -22% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 -31% (Attribution review: video and CTV show few last-touch leads); Jun 2025 -14% (Meta retest after a new creative agency).
- **Reporting:** the platform claims 182,895 conversions; the CRM credits 9,658 last-touch leads (18.9 times). Last-touch cost per lead: 2023: $726, 2024: $714, 2025: $736.
- **What to watch in the MMM:** flights are national and run ahead of each busy season, so they line up with the run-up in demand; long carryover means effects can land in the busy weeks after a flight ends.

### Connected TV

*Brand channel.* A market test in 8 markets. Each runs its own flight ahead of each busy season and goes dark between flights.

- **When it ran:** On 103 of 156 weeks nationally; used in 8 of 20 regions, with about 4 active in a typical on-week. Within a region it typically runs 8 weeks on, then pauses for 15 weeks (40 regional pauses in all).
- **Spend:** 2023: $3.3M, 2024: $2.5M, 2025: $1.5M. Highest in Q2, lowest in Q1; the biggest week was 2.8 times a typical on-week. The top 5 regions take 83% of its spend and hold 36% of target accounts.
- **Plan changes:** Apr 2023 +15% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 -34% (Attribution review: video and CTV show few last-touch leads).
- **Reporting:** the platform claims 96,309 conversions; the CRM credits 0 last-touch leads (with no CRM credit to compare against). Last-touch cost per lead: not defined (no CRM credit).
- **What to watch in the MMM:** runs in only 8 regions. The other 12 regions are a natural comparison group, and each test market times its own flights.

### Display Retargeting

*Performance channel.* Always-on retargeting of past site visitors. Market budgets are re-split every quarter.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $3.3M, 2024: $3.6M, 2025: $4.0M. Highest in Q1, lowest in Q2; the biggest week was 2.3 times a typical on-week. The top 5 regions take 55% of its spend and hold 47% of target accounts.
- **Plan changes:** Oct 2023 +18% (Q4 plan: more retargeting for year-end); Feb 2025 +13% (New fiscal year: more for what last touch rewards).
- **Reporting:** the platform claims 116,332 conversions; the CRM credits 54,794 last-touch leads (2.1 times). Last-touch cost per lead: 2023: $177, 2024: $198, 2025: $221.
- **What to watch in the MMM:** always on and retargets people who already visited, so it overlaps with demand from every other channel.

### Affiliates and Partners

*Performance channel.* Placement and sponsor fees with local resellers and fleet consultants, set when each market's contracts renew every quarter. Commissions are booked as cost of sale.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on in every region it uses.
- **Spend:** 2023: $1.5M, 2024: $1.9M, 2025: $1.5M. Highest in Q2, lowest in Q4; the biggest week was 1.4 times a typical on-week. The top 5 regions take 58% of its spend and hold 43% of target accounts.
- **Plan changes:** Apr 2024 +21% (Attribution review: video and CTV show few last-touch leads); Nov 2024 -24% (Two reseller contracts end).
- **Reporting:** the platform claims 138,297 conversions; the CRM credits 60,698 last-touch leads (2.3 times). Last-touch cost per lead: 2023: $78, 2024: $86, 2025: $76.
- **What to watch in the MMM:** fees change only when each market's contracts renew, so there are few distinct spend levels to learn from, and the top 5 regions take 58% of spend against 43% of accounts.

### Webinars

*Events channel.* Regional live events. Cost lands in the week of each event.

- **When it ran:** On 123 of 156 weeks nationally; used in 20 of 20 regions, with about 2 active in a typical on-week. Spend comes in single weeks; a region typically goes 8 weeks between them.
- **Spend:** 2023: $1.8M, 2024: $1.8M, 2025: $1.9M. Highest in Q1, lowest in Q4; the biggest week was 3.1 times a typical on-week. The top 5 regions take 56% of its spend and hold 51% of target accounts.
- **Plan changes:** none between annual plans.
- **Reporting:** the platform claims 123,967 conversions; the CRM credits 80,541 last-touch leads (1.5 times). Last-touch cost per lead: 2023: $70, 2024: $67, 2025: $65.
- **What to watch in the MMM:** spend lands in one region and one week at a time, a strong natural experiment.

## 9. Strongest spend correlations

| Channel A | Channel B | Correlation |
|---|---|---|
| Paid Search Non-Brand | LinkedIn | -0.78 |
| Paid Search Brand | Connected TV | 0.58 |
| Paid Search Brand | Meta | 0.53 |
| Meta | Connected TV | 0.52 |
| Paid Search Non-Brand | Display Retargeting | 0.40 |

Variance inflation (VIF) of national weekly spend: Paid Search Non-Brand 4.1, LinkedIn 3.1, Paid Search Brand 3.0, Connected TV 2.3, Meta 1.8, Display Retargeting 1.3, YouTube 1.1, Affiliates and Partners 1.1, Webinars 1.1.
