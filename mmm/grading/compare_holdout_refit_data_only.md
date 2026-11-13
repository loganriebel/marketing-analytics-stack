# MMM grade: holdout fit against refit_data_only fit

Same window (2023 to 2025), same answer key. Error is the posterior median against the truth; covered means the 90% HDI holds the truth.

| Channel | CPA err | mCPA err | Deals err | CPA covered | mCPA covered | Deals covered |
|---|---:|---:|---:|---|---|---|
| paid_search_brand | +105% to +94% | -28% to -34% | -51% to -48% | yes to yes | yes to yes | yes to yes |
| paid_search_nonbrand | +7% to +28% | -39% to -25% | -7% to -22% | yes to yes | yes to yes | yes to yes |
| meta | +340% to +224% | +287% to +120% | -77% to -69% | yes to yes | no to no | no to no |
| linkedin | +80% to +142% | +146% to +237% | -45% to -59% | yes to yes | yes to yes | yes to yes |
| youtube | +19% to +21% | +38% to +44% | -16% to -17% | yes to yes | yes to yes | yes to yes |
| ctv | +18% to +20% | +24% to +21% | -16% to -17% | yes to yes | yes to yes | yes to yes |
| display | -73% to -74% | -76% to -76% | +266% to +283% | yes to yes | yes to yes | yes to yes |
| affiliates | +238% to +237% | +411% to +403% | -70% to -70% | yes to yes | yes to yes | no to no |

90% HDI coverage, all 4 metrics x 8 channels: 27 of 32 to 26 of 32.
Median absolute error: CPA 77% to 84%; marginal CPA 57% to 60%; deals 48% to 54%.

| Marginal CPA call | holdout | refit_data_only |
|---|---|---|
| Best next dollar (true: youtube) | youtube (right) | youtube (right) |
| Worst next dollar (true: display) | display (right) | display (right) |
| Marginal CPA rank correlation | 0.69 | 0.83 |
| CPA rank correlation | 0.48 | 0.55 |

| Total paid media | True | holdout (90% HDI) | refit_data_only (90% HDI) |
|---|---:|---:|---:|
| incremental_deals_paid_media | 15,389 | 11,060 (8,515 to 13,937) (miss) | 10,293 (7,850 to 12,715) (miss) |
| incremental_cpa_paid_media | 2,821 | 3,925 (2,987 to 4,916) (miss) | 4,217 (3,357 to 5,409) (miss) |

| Optimizer plan, same total spend | Model (90% HDI) | True | Inside |
|---|---:|---:|---|
| holdout | 654 (363 to 932) | 1,045 | no |
| refit_data_only | 887 (410 to 1,390) | 1,676 | no |
