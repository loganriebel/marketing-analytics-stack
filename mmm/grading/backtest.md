# Rolling-origin backtest

The unchanged MMM refit 4 times, each fold trained from 2023-01-02 through its cutoff and predicting the next 13 weeks it never saw, from their actual spend and controls. Written by `python -m mmm.backtest` from `mmm/outputs/backtest.json`. Reading: [docs/mmm/README.md](../../docs/mmm/README.md#backtest).

## National weekly deals, holdout

| Fold | Trained through (weeks) | Predicts | Gates | MAPE | WAPE | MAE | Bias | MPE | In 90% interval | R² |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 2024-12-30 (105) | 2025-01-06 to 2025-03-31 | pass | 3.5% | 3.5% | 14.8 | -3.3 | -0.5% | 13 of 13 | 0.83 |
| 2 | 2025-03-31 (118) | 2025-04-07 to 2025-06-30 | pass | 3.9% | 3.9% | 20.3 | +9.5 | 2.0% | 13 of 13 | 0.49 |
| 3 | 2025-06-30 (131) | 2025-07-07 to 2025-09-29 | pass | 3.6% | 3.5% | 16.5 | +3.1 | 0.8% | 12 of 13 | 0.35 |
| 4 | 2025-09-22 (143) | 2025-09-29 to 2025-12-22 | pass | 5.2% | 5.3% | 28.9 | -23.8 | -4.2% | 11 of 13 | -0.89 |
| Pooled | | 52 fold-weeks (51 distinct) | 4 of 4 pass | 4.0% | 4.1% | 20.1 | -3.6 | -0.5% | 49 of 52 | 0.83 |

## NRMSE, holdout against training

| Fold | Holdout RMSE / mean | Training RMSE / mean | Ratio | Holdout RMSE / range | Training RMSE / range | Ratio |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 4.5% | 4.8% | 0.95 | 12.7% | 7.1% | 1.80 |
| 2 | 4.3% | 4.8% | 0.90 | 23.4% | 6.9% | 3.38 |
| 3 | 4.5% | 4.7% | 0.96 | 21.7% | 6.9% | 3.15 |
| 4 | 6.4% | 4.7% | 1.36 | 53.5% | 6.8% | 7.84 |
| Pooled | 5.1% | 4.7% | 1.09 | 10.4% | 6.9% | 1.49 |

## Market-weeks: small weeks inflate MAPE

| Fold | Training MAPE | Training WAPE | Holdout MAPE | Holdout WAPE | Smaller half of markets: MAPE / WAPE | Larger half: MAPE / WAPE | In 90% interval |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 21.0% | 15.0% | 27.5% | 17.1% | 34.4% / 24.1% | 20.6% / 14.5% | 95.0% |
| 2 | 21.8% | 15.2% | 21.0% | 16.0% | 25.4% / 22.1% | 16.6% / 13.9% | 87.7% |
| 3 | 21.6% | 15.2% | 23.5% | 16.4% | 30.6% / 25.0% | 16.4% / 13.2% | 91.2% |
| 4 | 21.8% | 15.3% | 19.8% | 16.9% | 21.8% / 20.4% | 17.8% / 15.7% | 87.3% |
| Pooled |  |  | 23.0% | 16.6% | 28.0% / 22.8% | 17.9% / 14.4% | 90.3% |

The smaller half of markets close 13.0 deals a week on average in the holdouts, the larger half 35.8.

## Definitions

- **error:** predicted minus observed, so a negative bias or MPE means the model ran low
- **predicted:** holdout: posterior predictive mean; training: posterior mean of the fitted line, as in diagnostics fit_stats
- **mape:** mean of |error| / observed, leaving out cells with zero deals
- **wape:** sum of |error| / sum of observed
- **mae:** mean |error|, in deals
- **bias:** mean error, in deals per week (per market-week for market-week rows)
- **bias_pct:** sum of error / sum of observed
- **mpe:** mean of error / observed
- **coverage_90:** share inside the 90% posterior predictive interval (5th to 95th percentile)
- **nrmse_mean:** RMSE / mean observed
- **nrmse_range:** RMSE / (max - min observed), over the same weeks
- **holdout_over_training_nrmse:** holdout NRMSE / the same fold's training NRMSE; above 1 means the fit does worse on weeks it did not train on
- **pooled:** every fold's holdout weeks together; training NRMSE is the mean over folds
