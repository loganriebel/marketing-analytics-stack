# MMM grade: holdout fit against refit fit

Same window (2023 to 2025), same answer key. Error is the posterior median against the truth; covered means the 90% HDI holds the truth.

| Channel | CPA err | mCPA err | Deals err | CPA covered | mCPA covered | Deals covered |
|---|---:|---:|---:|---|---|---|
| paid_search_brand | +230% to +202% | +8% to -0% | -70% to -67% | yes to yes | yes to yes | no to no |
| paid_search_nonbrand | +34% to +43% | -29% to -24% | -26% to -30% | yes to yes | yes to yes | yes to no |
| meta | +240% to +154% | +91% to +43% | -71% to -61% | no to no | no to yes | no to no |
| linkedin | +44% to +151% | +58% to +188% | -31% to -60% | yes to yes | yes to yes | yes to no |
| youtube | +32% to +20% | +40% to +28% | -24% to -17% | yes to yes | no to yes | no to yes |
| ctv | -2% to +0% | +15% to +17% | +2% to -0% | yes to yes | yes to no | yes to yes |
| display | -45% to -47% | -50% to -53% | +80% to +88% | yes to yes | yes to yes | yes to yes |
| affiliates | +304% to +375% | +371% to +499% | -75% to -79% | yes to yes | yes to yes | no to no |

90% HDI coverage, all 4 metrics x 8 channels: 21 of 32 to 20 of 32.
Median absolute error: CPA 44% to 99%; marginal CPA 45% to 35%; deals 50% to 60%.

| Marginal CPA call | holdout | refit |
|---|---|---|
| Best next dollar (true: youtube) | youtube (right) | youtube (right) |
| Worst next dollar (true: display) | display (right) | display (right) |
| Marginal CPA rank correlation | 0.86 | 0.83 |
| CPA rank correlation | 0.43 | 0.64 |

| Total paid media | True | holdout (90% HDI) | refit (90% HDI) |
|---|---:|---:|---:|
| incremental_deals_paid_media | 38,325 | 24,013 (19,173 to 28,207) (miss) | 23,482 (19,749 to 27,810) (miss) |
| incremental_cpa_paid_media | 2,832 | 4,519 (3,712 to 5,434) (miss) | 4,622 (3,902 to 5,495) (miss) |

| Optimizer plan, same total spend | Model (90% HDI) | True | Inside |
|---|---:|---:|---|
| holdout | 2,664 (1,732 to 3,698) | 4,560 | no |
| refit | 3,363 (2,422 to 4,243) | 3,954 | yes |
