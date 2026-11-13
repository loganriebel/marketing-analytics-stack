# MMM grade: refit fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 24 of 32 (75%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,123 | 11,975 (1,900 to 61,897) | 96% | 37,735 | 26,033 (2,545 to 149,045) | 1,212 | 620 | 1,222 | 1,341 |
| paid_search_nonbrand | 3,068 | 4,146 (2,246 to 7,008) | 35% | 11,116 | 8,889 (5,172 to 15,099) | 5,551 | 4,107 | 3,644 | 2,320 |
| meta | 1,482 | 4,824 (1,586 to 11,719) (miss) | 225% | 1,834 | 3,967 (1,830 to 9,111) | 2,969 | 912 (miss) | 3,022 | 462 |
| linkedin | 2,550 | 6,284 (841 to 33,204) | 146% | 3,294 | 11,640 (1,773 to 67,442) | 1,004 | 407 | 3,492 | 1,971 |
| youtube | 1,542 | 1,881 (1,162 to 2,625) | 22% | 1,637 | 2,330 (1,654 to 3,212) (miss) | 1,815 | 1,488 | 14,737 | 868 |
| ctv | 2,516 | 3,013 (2,241 to 3,717) | 20% | 3,096 | 3,735 (2,969 to 4,761) | 1,153 | 962 | n/a | 1,561 |
| display | 42,123 | 11,474 (1,555 to 67,196) | -73% | 113,255 | 27,235 (3,243 to 173,896) | 103 | 379 | 5,172 | 2,157 |
| affiliates | 1,232 | 3,954 (673 to 19,918) | 221% | 1,982 | 9,317 (1,982 to 49,202) (miss) | 1,583 | 493 (miss) | 1,430 | 793 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.67 | 84% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 80% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 41% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 15,389 | 10,016 (7,626 to 12,647) | no |
| incremental_cpa_paid_media | 2,821 | 4,334 (3,300 to 5,499) | no |

Upper funnel through brand search: 90% HDI coverage 10 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.1% (5.3% to 6.8%) | -64% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 3.0% | 6% |
| meta | incremental_deals_via_brand_search | 18 | 5 (0 to 16) (miss) | -71% |
| meta | incremental_deals_total | 2,986 | 920 (174 to 1,819) (miss) | -69% |
| meta | cpa_total | 1,473 | 4,780 (1,361 to 11,277) | 224% |
| meta | marginal_cpa_total | 1,825 | 3,934 (1,823 to 9,009) | 115% |
| youtube | incremental_deals_via_brand_search | 10 | 4 (0 to 13) | -59% |
| youtube | incremental_deals_total | 1,825 | 1,493 (926 to 2,075) | -18% |
| youtube | cpa_total | 1,534 | 1,876 (1,160 to 2,607) | 22% |
| youtube | marginal_cpa_total | 1,632 | 2,320 (1,630 to 3,170) | 42% |
| ctv | incremental_deals_via_brand_search | 6 | 9 (0 to 27) | 37% |
| ctv | incremental_deals_total | 1,159 | 973 (749 to 1,218) | -16% |
| ctv | cpa_total | 2,502 | 2,981 (2,237 to 3,680) | 19% |
| ctv | marginal_cpa_total | 3,086 | 3,675 (2,939 to 4,671) | 19% |

Optimizer plan at the same total spend: model predicts 925 deals (425 to 1,415); the true world gives 1,779 (outside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 218 (121 to 311) | 348 | -37% | no | yes |
| youtube_ask | 186 (125 to 242) | 263 | -29% | no | no |
