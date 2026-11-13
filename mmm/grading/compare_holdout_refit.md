# MMM grade: holdout fit against refit fit

Same window (2023 to 2025), same answer key. Error is the posterior median against the truth; covered means the 90% HDI holds the truth.

| Channel | CPA err | mCPA err | Deals err | CPA covered | mCPA covered | Deals covered |
|---|---:|---:|---:|---|---|---|
| paid_search_brand | +105% to +96% | -28% to -31% | -51% to -49% | yes to yes | yes to yes | yes to yes |
| paid_search_nonbrand | +7% to +35% | -39% to -20% | -7% to -26% | yes to yes | yes to yes | yes to yes |
| meta | +340% to +225% | +287% to +116% | -77% to -69% | yes to no | no to yes | no to no |
| linkedin | +80% to +146% | +146% to +253% | -45% to -59% | yes to yes | yes to yes | yes to yes |
| youtube | +19% to +22% | +38% to +42% | -16% to -18% | yes to yes | yes to no | yes to yes |
| ctv | +18% to +20% | +24% to +21% | -16% to -17% | yes to yes | yes to yes | yes to yes |
| display | -73% to -73% | -76% to -76% | +266% to +267% | yes to yes | yes to yes | yes to yes |
| affiliates | +238% to +221% | +411% to +370% | -70% to -69% | yes to yes | yes to no | no to no |

90% HDI coverage, all 4 metrics x 8 channels: 27 of 32 to 24 of 32.
Median absolute error: CPA 77% to 84%; marginal CPA 57% to 59%; deals 48% to 54%.

| Marginal CPA call | holdout | refit |
|---|---|---|
| Best next dollar (true: youtube) | youtube (right) | youtube (right) |
| Worst next dollar (true: display) | display (right) | display (right) |
| Marginal CPA rank correlation | 0.69 | 0.83 |
| CPA rank correlation | 0.48 | 0.67 |

| Total paid media | True | holdout (90% HDI) | refit (90% HDI) |
|---|---:|---:|---:|
| incremental_deals_paid_media | 15,389 | 11,060 (8,515 to 13,937) (miss) | 10,016 (7,626 to 12,647) (miss) |
| incremental_cpa_paid_media | 2,821 | 3,925 (2,987 to 4,916) (miss) | 4,334 (3,300 to 5,499) (miss) |

| Optimizer plan, same total spend | Model (90% HDI) | True | Inside |
|---|---:|---:|---|
| holdout | 654 (363 to 932) | 1,045 | no |
| refit | 925 (425 to 1,415) | 1,779 | no |
