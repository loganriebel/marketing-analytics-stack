# MMM grade: holdout fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 21 of 32 (66%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 5,756 | 13,374 (1,623 to 78,055) | 132% | 35,584 | 28,914 (2,762 to 176,618) | 1,284 | 552 | 1,232 | 1,345 |
| paid_search_nonbrand | 2,067 | 3,736 (1,763 to 6,777) | 81% | 5,074 | 6,198 (3,455 to 11,382) | 6,482 | 3,586 (miss) | 2,461 | 1,719 |
| meta | 1,441 | 5,578 (1,064 to 25,828) | 287% | 1,725 | 6,827 (1,357 to 32,014) | 2,597 | 671 (miss) | 2,832 | 432 |
| linkedin | 2,670 | 5,576 (1,057 to 29,512) | 109% | 3,954 | 12,109 (1,869 to 65,331) | 1,440 | 690 | 3,690 | 1,977 |
| youtube | 1,516 | 2,179 (1,187 to 3,194) | 44% | 1,446 | 2,446 (1,562 to 3,482) (miss) | 1,328 | 924 | 14,918 | 802 |
| ctv | 2,578 | 2,411 (1,949 to 2,979) | -6% | 3,141 | 3,888 (2,919 to 4,982) | 1,161 | 1,241 | n/a | 1,693 |
| display | 37,654 | 5,568 (988 to 28,891) (miss) | -85% | 103,464 | 11,667 (1,731 to 73,732) (miss) | 123 | 833 | 5,138 | 2,027 |
| affiliates | 1,160 | 6,668 (887 to 36,353) | 475% | 1,875 | 16,409 (2,565 to 85,376) (miss) | 1,730 | 301 (miss) | 1,367 | 719 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.00 | 97% | youtube | yes | paid_search_brand | no |
| CRM last touch | 0.14 | 79% | paid_search_brand | no | ctv | no |
| Platform reported | 0.81 | 43% | meta | no | display | yes |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 16,145 | 9,579 (7,185 to 12,204) | no |
| incremental_cpa_paid_media | 2,479 | 4,178 (3,127 to 5,309) | no |

Upper funnel through brand search: 90% HDI coverage 9 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.7% (5.5% to 7.8%) | -60% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 2.9% | 2% |
| meta | incremental_deals_via_brand_search | 19 | 4 (0 to 13) (miss) | -80% |
| meta | incremental_deals_total | 2,615 | 676 (6 to 1,621) (miss) | -74% |
| meta | cpa_total | 1,430 | 5,537 (777 to 24,592) | 287% |
| meta | marginal_cpa_total | 1,715 | 6,750 (1,522 to 30,395) | 293% |
| youtube | incremental_deals_via_brand_search | 10 | 5 (0 to 15) | -55% |
| youtube | incremental_deals_total | 1,338 | 932 (502 to 1,367) | -30% |
| youtube | cpa_total | 1,505 | 2,160 (1,209 to 3,200) | 44% |
| youtube | marginal_cpa_total | 1,440 | 2,428 (1,542 to 3,441) (miss) | 69% |
| ctv | incremental_deals_via_brand_search | 8 | 7 (0 to 23) | -4% |
| ctv | incremental_deals_total | 1,168 | 1,252 (995 to 1,514) | 7% |
| ctv | cpa_total | 2,561 | 2,390 (1,946 to 2,960) | -7% |
| ctv | marginal_cpa_total | 3,130 | 3,838 (2,902 to 4,892) | 23% |

Optimizer plan at the same total spend: model predicts 499 deals (30 to 1,001); the true world gives 582 (inside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 166 (10 to 334) | 194 | -14% | yes | yes |
| youtube_ask | 128 (75 to 172) | 221 | -42% | no | no |
