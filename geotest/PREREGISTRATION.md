# Pre-registration: market test MT2026Q1

Registered 2026-01-26, before the test starts. Written by `python -m geotest.design` from `geotest/outputs/design.json`; every number below comes from that file. Data: the December 2025 cut (2023-01-02 to 2025-12-22).

## Why this test

The MMM recommends one move with two halves: put the next dollar into YouTube, its lowest cost per extra deal, and cut LinkedIn, display retargeting and affiliates, which it rates worst. YouTube runs in flights, so the data show it on and off. The cut channels are always on, so the data never show life without them, and their numbers rest on the model's assumptions. The test checks both halves at once.

## Design

- **Dates:** 12 test weeks, 2026-02-02 to 2026-04-26. The measurement window adds 4 weeks for deals to close: 2026-02-02 to 2026-05-24. Readout from the 2026-05-31 data cut.
- **Grow arm (10 markets):** YouTube adds $4,500 a week per unit of market size (target accounts over the market average), on top of plan. Markets: Akron (CAK), Cedar Rapids (CID), Columbus (CMH), Dayton (DAY), Duluth (DLH), Des Moines (DSM), Milwaukee (MKE), Minneapolis-St. Paul (MSP), Peoria (PIA), Rochester (RST).
- **Cut arm (10 markets):** LinkedIn, display retargeting and affiliates go dark. Markets: Cleveland (CLE), Cincinnati (CVG), Dayton (DAY), Des Moines (DSM), Sioux Falls (FSD), Minneapolis-St. Paul (MSP), Peoria (PIA), Rockford (RFD), Rochester (RST), Toledo (TOL).
- **Cells (a 2x2 factorial):** grow only: CAK, CID, CMH, DLH, MKE; cut only: CLE, CVG, FSD, RFD, TOL; grow and cut: DAY, DSM, MSP, PIA, RST; neither: CHI, FAR, GRB, MLI, MSN.
- **Assignment:** markets sit in 5 blocks of 4 similar-size markets, and each block gives one market to each cell. Of 4,000 random assignments, 2,177 kept each arm's dose balanced across the other arm's sides (within 15%), and the one with the smallest placebo error on 2024 windows was chosen.
- **Everything else** runs on the 2026 plan: every channel at its end-2025 budget, with its usual flighting and market split. Brand search follows searches, as always.

## Metrics

- **Primary: won deals.** Closed-won deals, all lead sources, counted in their close week (`fct_funnel.won_deals`), summed over each arm's markets and the measurement window.
- **Secondary: cost per deal.** For the grow arm, extra spend (with the brand-search spend that follows the extra searches) per extra deal, against the MMM's YouTube cost per extra deal of $2,428. For the cut arm, dollars saved per deal lost. Blended cost per deal in each arm's markets against the rest is reported beside them.

## Analysis

- **Estimator:** ratio difference-in-differences per arm. An arm's markets are compared with the other 10 markets, scaled by their deal ratio over the 52 weeks before the test. The two arms' contrasts form a 2x2 system in each arm's effect per planned dollar, which removes the other arm's effect (`geotest/estimator.py`).
- **Interval:** 90%, from the placebo spread: the estimator run on 89 2024 and 2025 windows where nothing was tested. The standard deviation used is the largest of the 2024 placebo error, the 2025 placebo error and the count-noise floor.
- **Cross-check:** a Bayesian synthetic control (CausalPy) on the same window. It does not decide.
- **Comparison with the model:** the MMM's forecast for each arm, made now from the same posterior the plan came from, with last year's same weeks as the stand-in for 2026 spend.

## Power

| Arm | Placebo error (2024 / 2025 / floor) | Smallest detectable lift | MMM forecast (90% range) | Power |
|---|---:|---:|---:|---:|
| grow | 40 / 49 / 51 | 126 deals | +128 (+77 to +176) | 81% |
| cut | 45 / 77 / 52 | 193 deals | -71 (-122 to -22) | 23% |

- The grow step is the smallest on a $250 grid whose forecast clears the bar at 80% power. It adds $500,211 over the test; the MMM expects 128 extra deals in the window, $3,914 each. Averaged over the forecast's own uncertainty, the chance of a clear result is 77%.
- The cut arm saves $403,406. At the forecast it has 23% power; it reaches 80% if the cuts cost 2.7 times what the model expects. It is a guardrail: it catches the cuts costing much more than modeled.
- Placebo false-positive rate at the 90% edge: 1%. A calibrated bar would give 5%; this one is lower because it uses the largest of the three errors.
- Duration: 8 weeks falls short of 80% power for the grow arm; 16 weeks adds little power for a third more spend. 12 weeks is the shortest test that clears the bar.

| Test weeks | Grow: bar / forecast / power | Cut: bar / forecast / power |
|---:|---:|---:|
| 8 | 110 / 98 / 72% | 150 / -44 / 18% |
| 12 | 126 / 128 / 81% | 193 / -71 / 23% |
| 16 | 160 / 168 / 83% | 239 / -97 / 26% |

## Decision rules

1. **YouTube works** if the grow arm's 90% interval is above zero.
2. **Against the model:** the grow lift beats the forecast if its 90% interval lies above the forecast (128), falls short if it lies below, and agrees otherwise. The cuts cost more than modeled if the cut arm's 90% interval lies below the forecast (-71).
3. **Either way, the model learns:** the grow arm enters the MMM as a YouTube lift test (`add_lift_test_measurements`). The cut arm moved 3 channels at once, so it enters as one lift measurement on their sum, built the same way. The MMM is refit on data through the readout and the optimizer runs again. The rollout follows the refit model, not this plan.
4. **Guardrail:** if the cuts cost more than modeled (rule 2), no cut channel falls below today's spend in the rollout. If YouTube shows no lift (rule 1 fails), the rollout does not grow it.
5. **Validity:** the readout is void if an arm's realized spend change misses its plan by more than 20%, or if a market leaves its cell.
