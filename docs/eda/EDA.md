# EDA and data validation

Built by `python -m eda` from the dbt warehouse only: the golden tables plus a few staging views. Nothing here reads the simulator or its answer key, so this is what an analyst at Fernhook would see before an MMM.

## 1. Validation checks

10 of 10 checks pass; notes flag known limits. The dbt tests (`dbt build`) cover row-level rules; these are the checks an analyst reads before trusting the data.

| Check | Result | Status |
|---|---|---|
| Reporting window | 156 weeks, 2023-01-02 to 2025-12-22, 20 regions | Pass |
| fct_channel_weekly is a full grid | 28,080 rows (expected 28,080) | Pass |
| fct_funnel is a full grid | 40,560 rows (expected 40,560) | Pass |
| fct_controls_weekly is a full grid | 3,120 rows (expected 3,120) | Pass |
| Spend matches the platform exports | $41.8M in both; difference $0.00 | Pass |
| No negative values; clicks never exceed impressions | 0 bad rows | Pass |
| Every lead maps to a channel | 0 unmapped of 828,558; 19% recorded as direct | Pass |
| Lead to close (won deals) | median 14 days; 80% between 8 and 24 | Pass |
| Censoring at the end of the window | 39% of opportunities from the last 4 weeks are still open; treat the final weeks of deals as incomplete | Note |
| Promo and price calendar loaded | 4 entries | Pass |
| Channels are not collinear | largest correlation 0.54 (Display Retargeting and Affiliates and Partners); largest VIF 1.8 | Pass |

## 2. Outcome and spend over time

![Spend and deals](img/spend_and_deals.png)

| Year | Paid spend | Leads | Closed-won deals | New contract value | Spend per deal |
|---|---|---|---|---|---|
| 2023 | $14.6M | 246,845 | 11,287 | $30.4M | $1,292 |
| 2024 | $13.3M | 232,223 | 11,336 | $32.0M | $1,177 |
| 2025 | $13.9M | 233,889 | 10,445 | $30.9M | $1,331 |

The last few weeks of 2025 are undercounted for deals, because those leads have not had time to close.

## 3. Seasonality

Expected pattern for fleet software: a deep holiday dip in late December and early January, a smaller dip at Thanksgiving, a softer July and August, and strength in Q1 and the fall when operators plan for the next season.

![Seasonality](img/seasonality.png)

| Period | Expected | Leads index (100 = average week) | Holds |
|---|---|---|---|
| Holiday weeks (51, 52, 1) | well below 100 | 77 | Yes |
| Thanksgiving week (47) | below 100 | 90 | Yes |
| Summer (weeks 27 to 34) | below 100 | 101 | No |
| Q1 after the holidays (weeks 3 to 13) | above 100 | 109 | Yes |
| Fall (weeks 36 to 45) | above 100 | 95 | No |

3 of 5 expectations hold. Not seen: summer, fall. The MMM should learn seasonality from the data rather than impose the planning calendar. During the year-end promo (weeks 46 to 50), deals run +11% relative to leads, which is what a discount on annual plans should do.

## 4. How the media was flighted

![Flighting calendar](img/flighting_calendar.png)

![Spend by channel](img/spend_by_channel.png)

| Channel | Weeks on (of 156) | Regions used | Typical run in a region (weeks) | Typical pause (weeks) |
|---|---|---|---|---|
| Paid Search Brand | 156 | 20 | 154 | 6 |
| Paid Search Non-Brand | 156 | 20 | 122 | 6 |
| Meta | 142 | 20 | 21 | 4 |
| LinkedIn | 148 | 20 | 43 | 4 |
| YouTube | 90 | 20 | 5 | 5 |
| Connected TV | 155 | 8 | 5 | 7 |
| Display Retargeting | 156 | 20 | 67 | 8 |
| Affiliates and Partners | 156 | 20 | 156 | 10 |
| Webinars | 112 | 19 | 1 | 10 |

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
| 2024-08-05 | LinkedIn | -19% | Cost cut during the hiring freeze |
| 2024-08-05 | Meta | -17% | Cost cut during the hiring freeze |
| 2024-11-04 | Affiliates and Partners | -24% | Two reseller contracts end |
| 2025-02-03 | Display Retargeting | +13% | New fiscal year: more for what last touch rewards |
| 2025-02-03 | Paid Search Non-Brand | +9% | New fiscal year: more for what last touch rewards |
| 2025-06-02 | Meta | +23% | Meta retest after a new creative agency |
| 2025-06-02 | YouTube | -14% | Meta retest after a new creative agency |

## 5. Spend mix

![Mix by year](img/mix_by_year.png)

| Year | Performance | Brand | Events |
|---|---|---|---|
| 2023 | 67% | 28% | 5% |
| 2024 | 76% | 20% | 5% |
| 2025 | 80% | 16% | 4% |

## 6. Reporting sources disagree

![Claims vs CRM](img/claims_vs_crm.png)

Platforms claim 755,152 conversions in total; the CRM credits 401,887 leads to paid channels. Connected TV gets 0 last-touch leads because nobody clicks a TV ad. Neither source measures what a channel adds; that is the MMM's job.

## 7. Controls

![Controls](img/controls.png)

- **Sales headcount** grows each Q1 hiring wave, then falls through the July 2024 to January 2025 freeze.
- **Email** volume grows with the list, with blasts in promo weeks.
- **Fleet activity index** moves a few points either way; it is the market-demand control.
- **Promo and price:** year-end discount weeks are flagged each year; list price rose 10% in July 2024 (index 1.10 after).

## 8. Channel by channel

What the data shows about how each channel was bought and reported. These are observations, not effects.

### Paid Search Brand

*Performance channel.* Bids on searches for Fernhook. Spend follows how many people search the brand, with occasional regional pauses.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on within each region, apart from 6 regional pauses of about 6 weeks.
- **Spend:** 2023: $2.4M, 2024: $2.4M, 2025: $2.5M. Highest in Q1, lowest in Q4; the biggest week was 1.3 times a typical on-week. The top 5 regions take 43% of its spend and hold 41% of target accounts.
- **Plan changes:** none between annual plans.
- **Reporting:** the platform claims 121,121 conversions; the CRM credits 133,689 last-touch leads (0.9 times). Last-touch cost per lead: 2023: $50, 2024: $56, 2025: $59.
- **What to watch in the MMM:** its weekly spend tracks total leads closely (correlation 0.78). Spend that follows demand can look like it causes demand. The regional pauses are the cleanest evidence of what it adds.

### Paid Search Non-Brand

*Performance channel.* Always on. Budgets lean into busy seasons, and the team runs regional budget tests and pauses.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on within each region, apart from 9 regional pauses of about 6 weeks.
- **Spend:** 2023: $3.6M, 2024: $4.1M, 2025: $5.1M. Highest in Q2, lowest in Q4; the biggest week was 1.7 times a typical on-week. The top 5 regions take 46% of its spend and hold 38% of target accounts.
- **Plan changes:** Apr 2023 +7% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 +12% (Attribution review: video and CTV show few last-touch leads); Feb 2025 +9% (New fiscal year: more for what last touch rewards).
- **Reporting:** the platform claims 158,662 conversions; the CRM credits 107,813 last-touch leads (1.5 times). Last-touch cost per lead: 2023: $108, 2024: $112, 2025: $133.
- **What to watch in the MMM:** always on and seasonal (correlation with total leads 0.28), so most of its signal comes from the regional budget tests and pauses, not from week-to-week swings.

### Meta

*Brand channel.* Always-on prospecting with multi-week pushes and short pauses between creative rounds.

- **When it ran:** On 142 of 156 weeks nationally; used in 20 of 20 regions, with about 19 active in a typical on-week. Within a region it typically runs 21 weeks on, then pauses for 4 weeks (95 regional pauses in all).
- **Spend:** 2023: $1.9M, 2024: $1.0M, 2025: $1.1M. Highest in Q1, lowest in Q4; the biggest week was 2.8 times a typical on-week. The top 5 regions take 47% of its spend and hold 32% of target accounts.
- **Plan changes:** Oct 2023 -12% (Q4 plan: more retargeting for year-end); Aug 2024 -17% (Cost cut during the hiring freeze); Jun 2025 +23% (Meta retest after a new creative agency).
- **Reporting:** the platform claims 199,379 conversions; the CRM credits 57,360 last-touch leads (3.5 times). Last-touch cost per lead: 2023: $78, 2024: $64, 2025: $66.
- **What to watch in the MMM:** short pauses and multi-week pushes give clean on/off contrasts; the June 2025 retest adds a late step up.

### LinkedIn

*Performance channel.* Lead-gen forms run always on, with pushes and short regional pauses.

- **When it ran:** On 148 of 156 weeks nationally; used in 20 of 20 regions, with about 19 active in a typical on-week. Always on within each region, apart from 49 regional pauses of about 4 weeks.
- **Spend:** 2023: $1.8M, 2024: $1.4M, 2025: $1.0M. Highest in Q2, lowest in Q3; the biggest week was 2.9 times a typical on-week. The top 5 regions take 47% of its spend and hold 40% of target accounts.
- **Plan changes:** Aug 2024 -19% (Cost cut during the hiring freeze).
- **Reporting:** the platform claims 44,962 conversions; the CRM credits 22,005 last-touch leads (2.0 times). Last-touch cost per lead: 2023: $205, 2024: $191, 2025: $174.
- **What to watch in the MMM:** 49 short regional pauses give clean on/off contrasts, and spend fell each year, so the later years carry less signal.

### YouTube

*Brand channel.* Bought in national flights of four to eight weeks. Each flight targets about three in four regions.

- **When it ran:** On 90 of 156 weeks nationally; used in 20 of 20 regions, with about 14 active in a typical on-week. Within a region it typically runs 5 weeks on, then pauses for 5 weeks (216 regional pauses in all).
- **Spend:** 2023: $0.6M, 2024: $0.6M, 2025: $0.3M. Highest in Q1, lowest in Q4; the biggest week was 2.3 times a typical on-week. The top 5 regions take 42% of its spend and hold 39% of target accounts.
- **Plan changes:** Apr 2023 -22% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 -31% (Attribution review: video and CTV show few last-touch leads); Jun 2025 -14% (Meta retest after a new creative agency).
- **Reporting:** the platform claims 32,812 conversions; the CRM credits 2,097 last-touch leads (15.6 times). Last-touch cost per lead: 2023: $706, 2024: $752, 2025: $735.
- **What to watch in the MMM:** flights are national, so on/off weeks line up with seasonality and other channels; long carryover means effects can show up in off-weeks.

### Connected TV

*Brand channel.* A market test in 8 US regions. Each market runs its own on/off flights, so markets rotate.

- **When it ran:** On 155 of 156 weeks nationally; used in 8 of 20 regions, with about 3 active in a typical on-week. Within a region it typically runs 5 weeks on, then pauses for 7 weeks (101 regional pauses in all).
- **Spend:** 2023: $1.6M, 2024: $1.0M, 2025: $0.8M. Highest in Q3, lowest in Q1; the biggest week was 3.1 times a typical on-week. The top 5 regions take 71% of its spend and hold 37% of target accounts.
- **Plan changes:** Apr 2023 +15% (Q1 review: CTV test expands, YouTube trimmed); Apr 2024 -34% (Attribution review: video and CTV show few last-touch leads).
- **Reporting:** the platform claims 40,772 conversions; the CRM credits 0 last-touch leads (with no CRM credit to compare against). Last-touch cost per lead: not defined (no CRM credit).
- **What to watch in the MMM:** runs in only 8 regions. The other 12 regions are a natural comparison group, and rotating market flights add contrast.

### Display Retargeting

*Performance channel.* Always-on retargeting of past site visitors, with regional pauses.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 19 active in a typical on-week. Always on within each region, apart from 17 regional pauses of about 8 weeks.
- **Spend:** 2023: $1.2M, 2024: $1.5M, 2025: $1.8M. Highest in Q3, lowest in Q1; the biggest week was 3.1 times a typical on-week. The top 5 regions take 47% of its spend and hold 35% of target accounts.
- **Plan changes:** Oct 2023 +18% (Q4 plan: more retargeting for year-end); Feb 2025 +13% (New fiscal year: more for what last touch rewards).
- **Reporting:** the platform claims 48,931 conversions; the CRM credits 22,767 last-touch leads (2.1 times). Last-touch cost per lead: 2023: $161, 2024: $202, 2025: $236.
- **What to watch in the MMM:** always on and retargets people who already visited, so it overlaps with demand from every other channel.

### Affiliates and Partners

*Performance channel.* Placement and sponsor fees set at quarterly contract renewals. Commissions are booked as cost of sale.

- **When it ran:** On every week of the window; used in 20 of 20 regions, with about 20 active in a typical on-week. Always on within each region, apart from 3 regional pauses of about 10 weeks.
- **Spend:** 2023: $0.7M, 2024: $0.7M, 2025: $0.8M. Highest in Q1, lowest in Q4; the biggest week was 1.7 times a typical on-week. The top 5 regions take 48% of its spend and hold 27% of target accounts.
- **Plan changes:** Apr 2024 +21% (Attribution review: video and CTV show few last-touch leads); Nov 2024 -24% (Two reseller contracts end).
- **Reporting:** the platform claims 65,985 conversions; the CRM credits 28,826 last-touch leads (2.3 times). Last-touch cost per lead: 2023: $78, 2024: $76, 2025: $77.
- **What to watch in the MMM:** fees change only at contract renewals, so there are few distinct spend levels to learn from, and the top 5 regions take 48% of spend against 27% of accounts.

### Webinars

*Events channel.* Regional live events. Cost lands in the week of each event.

- **When it ran:** On 112 of 156 weeks nationally; used in 19 of 20 regions, with about 2 active in a typical on-week. Spend comes in single weeks; a region typically goes 10 weeks between them.
- **Spend:** 2023: $0.7M, 2024: $0.6M, 2025: $0.5M. Highest in Q3, lowest in Q1; the biggest week was 3.6 times a typical on-week. The top 5 regions take 42% of its spend and hold 37% of target accounts.
- **Plan changes:** none between annual plans.
- **Reporting:** the platform claims 42,528 conversions; the CRM credits 27,330 last-touch leads (1.6 times). Last-touch cost per lead: 2023: $66, 2024: $67, 2025: $72.
- **What to watch in the MMM:** spend lands in one region and one week at a time, a strong natural experiment.

## 9. Strongest spend correlations

| Channel A | Channel B | Correlation |
|---|---|---|
| Display Retargeting | Affiliates and Partners | 0.54 |
| Paid Search Non-Brand | Connected TV | -0.39 |
| Paid Search Brand | Paid Search Non-Brand | 0.39 |
| Paid Search Brand | Meta | 0.35 |
| Paid Search Non-Brand | Display Retargeting | 0.33 |

Variance inflation (VIF) of national weekly spend: Paid Search Non-Brand 1.8, Display Retargeting 1.8, Paid Search Brand 1.7, Affiliates and Partners 1.7, Connected TV 1.4, Meta 1.3, LinkedIn 1.3, YouTube 1.2, Webinars 1.0.
