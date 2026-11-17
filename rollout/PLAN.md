# Rollout plan and holdout registration: RO2026H2

Approved 2026-05-29, before the rollout starts. Written by `python -m rollout.plan` from `rollout/outputs/plan.json`; every number below comes from that file. Data: the May 2026 cut (2023-01-02 to 2026-05-25) and the refit MMM.

## Why this plan

The spring test's rule 3 says the rollout follows the refit model, not the test plan. Rule 4's guardrails did not trip: YouTube showed a lift, and pulling non-brand search back did not cost more than modeled. So the refit model's budget optimizer sets the plan, inside the same -50% to +50% limits on every channel. The model has never seen a channel moved further, so the plan does not move one further.

## The optimizer's flag

The refit optimizer's solver stopped with `converged: false` ("Positive directional derivative for linesearch"), with 4 of its 7 channels at a limit. That flag was a false alarm. Rebuilt from the saved posterior, the same curves give the same plan (3,363 extra deals over 2023 to 2025), and the plan meets the optimum's conditions (`mmm.optimize.optimality`):

- The 3 channels inside their limits (non-brand search at 0.88x, LinkedIn at 0.87x, affiliates at 0.70x) each earn 0.137 extra deals per extra $1,000, so no move between them adds deals.
- The channels at the cap earn more (Meta 0.365, YouTube 0.391, connected TV 0.210), and the channel at the floor earns less (display retargeting 0.046). They would move further if the limits allowed.
- An exact solver (`mmm.optimize.solve_exact`) finds the same plan: 3,363 extra deals.

The limits bind for 4 channels. That is a choice, not a failure: past them the model is guessing.

## The plan

The refit plan's multipliers were set on 2023 to 2025 spend. 2026 runs on 2025's mix, heavier on non-brand search, so the same multipliers would spend $842,410 less over the rollout weeks and forecast 429 extra deals. So the same objective, posterior and limits are solved again on the rollout's own weeks and markets, at the same total, with last year's same weeks (2025-06-02 to 2025-12-29) as the stand-in for 2026 spend:

| Channel | Move | Spend now (stand-in weeks) | Change | Extra deals in the window |
|---|---:|---:|---:|---:|
| non-brand search | 0.88x (-12%) | $9,778,992 | -$1,137,297 | -66 |
| Meta | 1.50x (+50%) | $1,624,592 | $812,296 | +289 |
| LinkedIn | 1.50x (+50%) | $507,262 | $253,631 | +40 |
| YouTube | 1.50x (+50%) | $917,332 | $458,666 | +174 |
| connected TV | 1.50x (+50%) | $461,213 | $230,607 | +91 |
| display retargeting | 0.50x (-50%) | $1,904,196 | -$952,098 | -25 |
| affiliates | 1.50x (+50%) | $669,366 | $334,683 | +30 |

- **Dates:** the 31 weeks from 2026-06-01 through the week of 2026-12-28.
- **Markets:** the 15 rollout markets. Brand search is not a lever; it follows searches, and the plan's upper-funnel moves add about $64,435 of it.
- **Net spend change:** $487 (rounding the multipliers).
- **Check:** the solved plan meets the optimum's conditions (yes).
- **Why it differs from the refit plan:** in 2025's mix LinkedIn and affiliates had been cut back, so their next dollar is cheaper than on the 2023 to 2025 average, and the model now grows them.

## Forecast

In the 15 rollout markets, the refit model expects +533 extra deals closing inside the rollout weeks (90% range +407 to +661), and +543 (+403 to +678) counting deals that close after the year ends. The always-on channels never pause, so the model is likely to under-credit paid media, and the forecast may run low.

## How we'll know: the holdout readout, registered now

- **Holdout:** CAK, CID, CLE, FSD, MSP stay on the old plan all year. They are the spring test's "neither" cell, untouched by either arm, and hold 27% of deals.
- **Metric:** won deals, all sources, by close week, summed over the 31 rollout weeks (2026-06-01 to 2027-01-03).
- **Estimator:** the spring test's ratio difference-in-differences with one arm: rollout-market deals minus holdout deals scaled by their ratio in the 52 weeks before the spring test (2025-02-03 to 2026-01-26), so the test's own effect cannot leak in.
- **Interval:** 90%, from 62 placebo windows with the same shape on weeks before the spring test (2024-04-29 to 2025-06-30 starts). Placebo error 271 (2024 starts) / 269 (2025 starts), count-noise floor 203; the sd used is 271 deals.
- **Power:** the smallest lift it can reliably see is 675 deals. At the forecast it has **63% power**. A "not clear" result is the likely read even if the plan works as forecast.
- **Readout:** from the 2027-01-03 data cut.

**Rules:**

1. The rollout works if the holdout readout's 90% interval is above zero.
2. Against the model: the rollout beats the May forecast if the interval lies above it, falls short if it lies below, and agrees otherwise.
3. If the interval reaches zero, the result is not clear. At 63% power that is the likely read even if the forecast is right, so it is not evidence that the plan failed. A clear drop (the whole interval below zero) would be.
4. The model's own counterfactual, the refit MMM scoring the realized 2026 spend with and without the rollout's moves, is shown beside the readout as a cross-check. It decides nothing.
5. Validity: the plan file assigns the registered markets, moves and dates. For every moved channel, the rollout markets' delivered spend over the rollout weeks sits nearer, in logs, to the new plan's budget line than to the old one, and the holdout markets' sits nearer to the old line than to the new. Otherwise the readout is void. A single market that misses is named, never void.

**Dry run of the move check** (rule 5), on the media plan's weeks before the rollout (2025-12-29 to 2026-05-25):

| Channel | Move | Line | Delivered / planned, spend followed the plan | Same, if the rollout had not run |
|---|---:|---:|---:|---:|
| non-brand search | 0.88x | 1.064 | 0.973 (shows) | 1.101 (misses) |
| Meta | 1.50x | 0.816 | 0.950 (shows) | 0.633 (misses) |
| LinkedIn | 1.50x | 0.816 | 0.980 (shows) | 0.653 (misses) |
| YouTube | 1.50x | 0.816 | 0.994 (shows) | 0.663 (misses) |
| connected TV | 1.50x | 0.816 | 0.999 (shows) | 0.666 (misses) |
| display retargeting | 0.50x | 1.414 | 1.101 (shows) | 2.202 (misses) |
| affiliates | 1.50x | 0.816 | 0.995 (shows) | 0.663 (misses) |

- **Spend followed the plan:** the check passes; 0 market-channel cells would be named.
- **The rollout had not run:** the check fails, so it can see every move, including the smallest one, the non-brand search trim.
