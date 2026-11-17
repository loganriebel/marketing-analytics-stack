# Results: the 2026 rollout (RO2026H2)

Written by `python -m rollout.results` from `rollout/outputs/results.json`; every number below comes from that file. Data: the 2027-01-03 cut, weeks 2023-01-02 to 2026-12-28. Method, markets, window and rules: [PLAN.md](PLAN.md), registered in May, unchanged.

## The readout

| What | Extra deals in the rollout markets, 2026-06-01 to 2027-01-03 |
|---|---:|
| Measured: 15 rollout markets against the 5 holdout markets (90% interval) | +464 (+18 to +911) |
| May forecast, refit MMM (90% range) | +533 (+407 to +661) |

The rollout markets closed 13,128 deals in the window. The holdout markets closed 4,650, and scaled by their ratio before the spring test they point to 12,664.

## The rules, as registered

1. **Does the rollout work?** Yes: the interval is above zero.
2. **Against the forecast:** the readout agrees with the forecast (+533).
3. **Clear.** The interval does not reach zero, though the holdout had only 63% power at the forecast.
4. **Cross-check (decides nothing):** the refit MMM, scoring the realized 2026 spend with and without the rollout's moves, puts the gain at +505 (+383 to +633) in the same markets and weeks.
5. **Validity: the readout stands.** The plan file matches the registration. Every moved channel's delivered spend sits nearer to its new budget line than to the old one in the rollout markets, with the holdout on the old line; no market missed.

## The year

| | 2025 | 2026 | Change |
|---|---:|---:|---:|
| Won deals | 25,318 | 28,054 | +10.8% |
| Paid spend | $43,535,140 | $42,772,953 | -1.8% |
| Cost per deal | $1,720 | $1,525 | -11.3% |

Weeks by their Monday: 52 in 2025 and 52 in 2026. Paid spend counts all 9 paid channels. These totals hold everything that moved in 2026: the spring test, the rollout, sales headcount, the market and the season. They do not measure the rollout; the holdout does.

## Cost (secondary)

- **Brand search that followed the extra searches:** $91,493 in the rollout markets, by the ratio method.
- **Blended cost per deal in the window:** rollout markets $1,490, holdout markets $1,436.

## Delivered against the media plan, rollout weeks

| Channel | Move | Rollout markets: delivered / new line | Line | Holdout: delivered / old line |
|---|---:|---:|---:|---:|
| paid_search_nonbrand | x0.88 | 1.003 | 1.064 | 1.004 |
| meta | x1.50 | 0.995 | 0.816 | 0.993 |
| linkedin | x1.50 | 1.014 | 0.816 | 1.014 |
| youtube | x1.50 | 0.970 | 0.816 | 0.971 |
| ctv | x1.50 | 0.990 | 0.816 | 0.999 |
| display | x0.50 | 1.010 | 1.414 | 1.010 |
| affiliates | x1.50 | 1.016 | 0.816 | 1.016 |

A move shows when delivered over planned sits nearer, in logs, to 1 than to the old line over the new one (the line is halfway, in logs).

## Exploratory (does not decide)

- **Placebo mean removed:** the placebo windows erred by +97 on average; taking that out gives +367.
