# MMM grade: holdout fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 27 of 32 (84%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,123 | 12,557 (1,366 to 85,642) | 105% | 37,735 | 27,198 (3,306 to 192,726) | 1,212 | 591 | 1,222 | 1,341 |
| paid_search_nonbrand | 3,068 | 3,293 (1,860 to 5,409) | 7% | 11,116 | 6,835 (4,094 to 11,336) | 5,551 | 5,171 | 3,644 | 2,320 |
| meta | 1,482 | 6,522 (1,091 to 26,506) | 340% | 1,834 | 7,099 (1,863 to 31,721) (miss) | 2,969 | 675 (miss) | 3,022 | 462 |
| linkedin | 2,550 | 4,600 (798 to 26,806) | 80% | 3,294 | 8,093 (1,802 to 47,872) | 1,004 | 556 | 3,492 | 1,971 |
| youtube | 1,542 | 1,829 (1,182 to 2,573) | 19% | 1,637 | 2,265 (1,580 to 3,093) | 1,815 | 1,531 | 14,737 | 868 |
| ctv | 2,516 | 2,979 (2,235 to 3,841) | 18% | 3,096 | 3,850 (2,949 to 4,897) | 1,153 | 973 | n/a | 1,561 |
| display | 42,123 | 11,515 (1,232 to 77,976) | -73% | 113,255 | 27,517 (3,359 to 182,094) | 103 | 378 | 5,172 | 2,157 |
| affiliates | 1,232 | 4,161 (565 to 22,418) | 238% | 1,982 | 10,134 (1,639 to 53,687) | 1,583 | 469 (miss) | 1,430 | 793 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.48 | 77% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 80% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 41% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 15,389 | 11,060 (8,515 to 13,937) | no |
| incremental_cpa_paid_media | 2,821 | 3,925 (2,987 to 4,916) | no |

Upper funnel through brand search: 90% HDI coverage 10 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 5.9% (5.1% to 6.7%) | -65% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 2.8% | 1% |
| meta | incremental_deals_via_brand_search | 18 | 4 (0 to 13) (miss) | -76% |
| meta | incremental_deals_total | 2,986 | 680 (10 to 1,572) (miss) | -77% |
| meta | cpa_total | 1,473 | 6,469 (1,090 to 25,293) | 339% |
| meta | marginal_cpa_total | 1,825 | 7,038 (1,555 to 30,150) | 286% |
| youtube | incremental_deals_via_brand_search | 10 | 4 (0 to 12) | -59% |
| youtube | incremental_deals_total | 1,825 | 1,534 (967 to 2,094) | -16% |
| youtube | cpa_total | 1,534 | 1,826 (1,182 to 2,568) | 19% |
| youtube | marginal_cpa_total | 1,632 | 2,253 (1,609 to 3,098) | 38% |
| ctv | incremental_deals_via_brand_search | 6 | 8 (0 to 25) | 27% |
| ctv | incremental_deals_total | 1,159 | 983 (720 to 1,243) | -15% |
| ctv | cpa_total | 2,502 | 2,951 (2,229 to 3,789) | 18% |
| ctv | marginal_cpa_total | 3,086 | 3,797 (2,889 to 4,778) | 23% |

Optimizer plan at the same total spend: model predicts 654 deals (363 to 932); the true world gives 1,045 (outside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 218 (121 to 311) | 348 | -37% | no | yes |
| youtube_ask | 186 (125 to 242) | 263 | -29% | no | no |
