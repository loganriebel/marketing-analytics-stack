# Pre-registration: market test MT2026Q1

Registered 2026-01-26, before the test starts. Written by `python -m geotest.design` from `geotest/outputs/design.json`; every number below comes from that file. Data: the December 2025 cut (2023-01-02 to 2025-12-22).

## Why this test

Two questions decide the 2026 budget. First, where should the next dollar go? The MMM says YouTube, its lowest cost per extra deal. YouTube runs in flights, so the data show it on and off, but never at the level the model recommends. Second, is the money poured into non-brand search still working? It is the biggest channel and always on, so the data never show life without it, and its spend went from $3,380,000 in 2023 to $8,430,000 in 2025. The test checks both at once.

## Design

- **Dates:** 12 test weeks, 2026-02-02 to 2026-04-26. The measurement window adds 4 weeks for deals to close: 2026-02-02 to 2026-05-24. Readout from the 2026-05-31 data cut.
- **Grow arm (10 markets):** YouTube adds $2,500 a week per unit of market size (target accounts over the market average), on top of plan. Markets: Akron (CAK), Cedar Rapids (CID), Columbus (CMH), Cincinnati (CVG), Sioux Falls (FSD), Milwaukee (MKE), Quad Cities (MLI), Madison (MSN), Rockford (RFD), Rochester (RST).
- **Search arm (10 markets):** non-brand search runs at 39% of plan, its 2023 weekly pace. Markets: Cedar Rapids (CID), Cleveland (CLE), Cincinnati (CVG), Fargo (FAR), Milwaukee (MKE), Quad Cities (MLI), Minneapolis-St. Paul (MSP), Peoria (PIA), Rochester (RST), Toledo (TOL).
- **Cells (a 2x2 factorial):** grow only: CAK, CMH, FSD, MSN, RFD; search only: CLE, FAR, MSP, PIA, TOL; grow and search: CID, CVG, MKE, MLI, RST; neither: CHI, DAY, DLH, DSM, GRB.
- **Assignment:** markets sit in 5 blocks of 4 similar-size markets, and each block gives one market to each cell. Of 4,000 random assignments, 1,942 kept each arm's dose balanced across the other arm's sides (within 15%), and the one whose worst placebo error, over both arms and over 2024 and 2025 windows, was smallest was chosen.
- **Everything else** runs on the 2026 plan: every channel at its end-2025 budget, with its usual flighting and market split. Brand search follows searches, as always.

## Metrics

- **Primary: won deals.** Closed-won deals, all lead sources, counted in their close week (`fct_funnel.won_deals`), summed over each arm's markets and the measurement window.
- **Secondary: cost per deal.** For the grow arm, extra spend (with the brand-search spend that follows the extra searches) per extra deal, against the MMM's YouTube cost per extra deal of $2,253. For the search arm, dollars saved per deal lost. Blended cost per deal in each arm's markets against the rest is reported beside them.

## Analysis

- **Estimator:** ratio difference-in-differences per arm. An arm's markets are compared with the other 10 markets, scaled by their deal ratio over the 52 weeks before the test. The two arms' contrasts form a 2x2 system in each arm's effect per planned dollar, which removes the other arm's effect (`geotest/estimator.py`).
- **Interval:** 90%, from the placebo spread: the estimator run on 89 2024 and 2025 windows where nothing was tested. The standard deviation used is the largest of the 2024 placebo error, the 2025 placebo error and the count-noise floor.
- **Cross-check:** a Bayesian synthetic control (CausalPy) on the same window. It does not decide.
- **Comparison with the model:** the MMM's forecast for each arm, made now from the same posterior the plan came from, with last year's same weeks as the stand-in for 2026 spend.

## Power

| Arm | Placebo error (2024 / 2025 / floor) | Smallest detectable lift | MMM forecast (90% range) | Power |
|---|---:|---:|---:|---:|
| grow | 38 / 37 / 47 | 118 deals | +119 (+88 to +154) | 81% |
| search | 39 / 30 / 54 | 135 deals | -83 (-120 to -41) | 45% |

- The grow step is the smallest on a $250 grid whose forecast clears the bar at 80% power. It adds $252,632 over the test; the MMM expects 119 extra deals in the window, $2,123 each. Averaged over the forecast's own uncertainty, the chance of a clear result is 79%.
- The search arm saves $594,201. At the forecast it has 45% power; it reaches 80% if pulling search back costs 1.6 times what the model expects. It is a guardrail: it catches search being worth much more than modeled.
- Net, the test spends $-341,570 against plan (negative means it saves money).
- Placebo false-positive rate at the 90% edge: 2%. A calibrated bar would give 5%; this one is lower because it uses the largest of the three errors.
- Duration: 8 weeks gives the grow arm 72% power. 12 weeks is the shortest that clears 80% (81%). 16 weeks reaches 91%, but runs past the spring busy season into the readout.

| Test weeks | Grow: bar / forecast / power | Search: bar / forecast / power |
|---:|---:|---:|
| 8 | 102 / 91 / 72% | 117 / -53 / 31% |
| 12 | 118 / 119 / 81% | 135 / -83 / 45% |
| 16 | 132 / 158 / 91% | 151 / -112 / 58% |

## Decision rules

1. **YouTube works** if the grow arm's 90% interval is above zero.
2. **Against the model:** the grow lift beats the forecast if its 90% interval lies above the forecast (119), falls short if it lies below, and agrees otherwise. Pulling non-brand search back costs more than modeled if the search arm's 90% interval lies below the forecast (-83), and less if it lies above.
3. **Either way, the model learns:** each arm moved 1 channel, so each enters the MMM as a lift test (`add_lift_test_measurements`): YouTube for the grow arm, non-brand search for the search arm. The MMM is refit on data through the readout and the optimizer runs again. The rollout follows the refit model, not this plan.
4. **Guardrail:** if pulling non-brand search back costs more than modeled (rule 2), the rollout does not cut it below today's spend. If YouTube shows no lift (rule 1 fails), the rollout does not grow it.
5. **Validity:** the readout is void if an arm's realized spend change misses its plan by more than 20%, or if a market leaves its cell.
