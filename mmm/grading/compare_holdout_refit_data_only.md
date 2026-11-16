# MMM grade: holdout fit against refit_data_only fit

Same window (2023 to 2025), same answer key. Error is the posterior median against the truth; covered means the 90% HDI holds the truth.

| Channel | CPA err | mCPA err | Deals err | CPA covered | mCPA covered | Deals covered |
|---|---:|---:|---:|---|---|---|
| paid_search_brand | +230% to +199% | +8% to -4% | -70% to -67% | yes to yes | yes to yes | no to no |
| paid_search_nonbrand | +34% to +39% | -29% to -27% | -26% to -28% | yes to yes | yes to yes | yes to yes |
| meta | +240% to +162% | +91% to +45% | -71% to -62% | no to no | no to no | no to no |
| linkedin | +44% to +143% | +58% to +194% | -31% to -59% | yes to yes | yes to yes | yes to no |
| youtube | +32% to +17% | +40% to +27% | -24% to -14% | yes to yes | no to yes | no to yes |
| ctv | -2% to +1% | +15% to +16% | +2% to -1% | yes to yes | yes to yes | yes to yes |
| display | -45% to -46% | -50% to -50% | +80% to +84% | yes to yes | yes to yes | yes to yes |
| affiliates | +304% to +385% | +371% to +536% | -75% to -79% | yes to yes | yes to yes | no to no |

90% HDI coverage, all 4 metrics x 8 channels: 21 of 32 to 21 of 32.
Median absolute error: CPA 44% to 95%; marginal CPA 45% to 36%; deals 50% to 60%.

| Marginal CPA call | holdout | refit_data_only |
|---|---|---|
| Best next dollar (true: youtube) | youtube (right) | youtube (right) |
| Worst next dollar (true: display) | display (right) | display (right) |
| Marginal CPA rank correlation | 0.86 | 0.83 |
| CPA rank correlation | 0.43 | 0.64 |

| Total paid media | True | holdout (90% HDI) | refit_data_only (90% HDI) |
|---|---:|---:|---:|
| incremental_deals_paid_media | 38,325 | 24,013 (19,173 to 28,207) (miss) | 23,877 (19,240 to 27,847) (miss) |
| incremental_cpa_paid_media | 2,832 | 4,519 (3,712 to 5,434) (miss) | 4,545 (3,766 to 5,408) (miss) |

| Optimizer plan, same total spend | Model (90% HDI) | True | Inside |
|---|---:|---:|---|
| holdout | 2,664 (1,732 to 3,698) | 4,560 | no |
| refit_data_only | 3,348 (2,376 to 4,237) | 3,842 | yes |
