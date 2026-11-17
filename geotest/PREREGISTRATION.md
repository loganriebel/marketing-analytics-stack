# Pre-registration: market test MT2026Q1

Registered 2026-01-26, before the test starts. Written by `python -m geotest.design` from `geotest/outputs/design.json`; every number below comes from that file. Data: the December 2025 cut (2023-01-02 to 2025-12-22).

## Why this test

Two questions decide the 2026 budget. First, where should the next dollar go? The MMM says YouTube, its lowest cost per extra deal. YouTube runs in flights, so the data show it on and off, but never at the level the model recommends. Second, is the money poured into non-brand search still working? It is the biggest channel and always on, so the data never show life without it, and its spend went from $8,450,000 in 2023 to $21,075,000 in 2025. The test checks both at once.

## Design

- **Dates:** 12 test weeks, 2026-02-02 to 2026-04-26. The measurement window adds 4 weeks for deals to close: 2026-02-02 to 2026-05-24. Readout from the 2026-05-31 data cut.
- **Grow arm (10 markets):** YouTube adds $5,625 a week per unit of market size (target accounts over the market average), on top of plan. Markets: Columbus (CMH), Cincinnati (CVG), Duluth (DLH), Green Bay (GRB), Milwaukee (MKE), Quad Cities (MLI), Madison (MSN), Rockford (RFD), Rochester (RST), Toledo (TOL).
- **Search arm (10 markets):** non-brand search runs at 39% of plan, its 2023 weekly pace. Markets: Chicago (CHI), Cincinnati (CVG), Dayton (DAY), Duluth (DLH), Des Moines (DSM), Fargo (FAR), Green Bay (GRB), Madison (MSN), Peoria (PIA), Toledo (TOL).
- **Cells (a 2x2 factorial):** grow only: CMH, MKE, MLI, RFD, RST; search only: CHI, DAY, DSM, FAR, PIA; grow and search: CVG, DLH, GRB, MSN, TOL; neither: CAK, CID, CLE, FSD, MSP.
- **Assignment:** markets sit in 5 blocks of 4 similar-size markets, and each block gives one market to each cell. Of 4,000 random assignments, 1,940 kept each arm's dose balanced across the other arm's sides (within 15%), and the one whose worst placebo error, over both arms and over 2024 and 2025 windows, was smallest was chosen.
- **Everything else** runs on the 2026 plan: every channel at its end-2025 budget, with its usual flighting and market split. Brand search follows searches, as always.

## Metrics

- **Primary: won deals.** Closed-won deals, all lead sources, counted in their close week (`fct_funnel.won_deals`), summed over each arm's markets and the measurement window.
- **Secondary: cost per deal.** For the grow arm, extra spend (with the brand-search spend that follows the extra searches) per extra deal, against the MMM's YouTube cost per extra deal of $2,291. For the search arm, dollars saved per deal lost. Blended cost per deal in each arm's markets against the rest is reported beside them.

## Analysis

- **Estimator:** ratio difference-in-differences per arm. An arm's markets are compared with the other 10 markets, scaled by their deal ratio over the 52 weeks before the test. The two arms' contrasts form a 2x2 system in each arm's effect per planned dollar, which removes the other arm's effect (`geotest/estimator.py`).
- **Interval:** 90%, from the placebo spread: the estimator run on 89 2024 and 2025 windows where nothing was tested. The standard deviation used is the largest of the 2024 placebo error, the 2025 placebo error and the count-noise floor.
- **Cross-check:** a Bayesian synthetic control (CausalPy) on the same window. It does not decide.
- **Comparison with the model:** the MMM's forecast for each arm, made now from the same posterior the plan came from, with last year's same weeks as the stand-in for 2026 spend.

## Power

| Arm | Placebo error (2024 / 2025 / floor) | Smallest detectable lift | MMM forecast (90% range) | Power |
|---|---:|---:|---:|---:|
| grow | 132 / 115 / 76 | 328 deals | +334 (+287 to +382) | 81% |
| search | 135 / 151 / 89 | 376 deals | -190 (-252 to -113) | 35% |

- The grow step is the smallest on a $625 grid whose forecast clears the bar at 80% power. It adds $568,421 over the test; the MMM expects 334 extra deals in the window, $1,704 each. Averaged over the forecast's own uncertainty, the chance of a clear result is 81%.
- The search arm saves $1,701,092. At the forecast it has 35% power; it reaches 80% if pulling search back costs 2.0 times what the model expects. It is a guardrail: it catches search being worth much more than modeled.
- Net, the test spends $-1,132,671 against plan (negative means it saves money).
- Placebo false-positive rate at the 90% edge: 1%. A calibrated bar would give 5%; this one is lower because it uses the largest of the three errors.
- Duration: 8 weeks gives the grow arm 62% power. 12 weeks is the shortest that clears 80% (81%). 16 weeks reaches 92%, but runs past the spring busy season into the readout.

| Test weeks | Grow: bar / forecast / power | Search: bar / forecast / power |
|---:|---:|---:|
| 8 | 317 / 250 / 62% | 351 / -124 / 22% |
| 12 | 328 / 334 / 81% | 376 / -190 / 35% |
| 16 | 369 / 454 / 92% | 401 / -253 / 47% |

## Decision rules

1. **YouTube works** if the grow arm's 90% interval is above zero.
2. **Against the model:** the grow lift beats the forecast if its 90% interval lies above the forecast (334), falls short if it lies below, and agrees otherwise. Pulling non-brand search back costs more than modeled if the search arm's 90% interval lies below the forecast (-190), and less if it lies above.
3. **Either way, the model learns:** each arm moved 1 channel, so each enters the MMM as a lift test (`add_lift_test_measurements`): YouTube for the grow arm, non-brand search for the search arm. The MMM is refit on data through the readout and the optimizer runs again. The rollout follows the refit model, not this plan.
4. **Guardrail:** if pulling non-brand search back costs more than modeled (rule 2), the rollout does not cut it below today's spend. If YouTube shows no lift (rule 1 fails), the rollout does not grow it.
5. **Validity, the market-compliance check.** Set now, before the test, and applied as written (`compliance` in the design file, `geotest/compliance.py`). It reads spend only and never moves a lift.
   - **Spend:** each arm's realized spend change, by the same ratio difference-in-differences on the moved channel's spend over the 12 test weeks, lands within 20% of its plan. The grow plan is $5,625 a week per size unit; the search plan is observed spend over the multiplier, minus observed spend.
   - **Plan file:** `plans/2026_test.yaml`, the plan that drives 2026 spend, assigns these markets, moves and dates.
   - **Moves:** the spend shows every move. YouTube, for each grow market: its lowest weekly YouTube spend per size unit over the test weeks is at least $2,812, half the add (the add runs every test week; a median would not do, because national flights lift every market's median in season). Non-brand search, for the arm as a whole: the arm's summed spend in the test weeks of the test's quarter, over its spend in that quarter's weeks before the test, and against the same step in the markets outside the arm, is nearer in logs to 0.39 than to 1 (the line is 0.62). Budgets for always-on channels are re-split across markets every quarter, so the step stays inside one quarter. Each search market gets the same test on its own.
   - **Void** if the spend change misses, the plan file does not match, a grow market does not show the add, or the search arm does not show the cut.
   - **Named, never void:** a search market whose own step misses the line, and a market outside an arm whose spend shows that arm's move (drift). The readout names each one and recomputes the lifts without it, as exploratory. Neither changes the registered lift. Deciding the cut for the arm rather than market by market was Logan's call, made before the test, from the dry run below.
   - **Dry run** on last year's same weeks (from 2025-02-03), when nothing was tested: the YouTube check flags no market (highest lowest week $985 against $2,812; over all 110 earlier 12-week windows, at most $1,772); the step test flags FAR. One noise unit of a market's step, from 8 earlier quarters, is 0.21 in logs, and of the arm's step 0.17. At that noise, the arm misses the line by chance 0.2% of the time. Decided market by market, one of the 10 would miss 11% of the time; a market outside the arm crosses the line 1.1% of the time.
