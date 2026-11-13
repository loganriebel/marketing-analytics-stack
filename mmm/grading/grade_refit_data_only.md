# MMM grade: refit_data_only fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 26 of 32 (81%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,123 | 11,853 (1,523 to 69,612) | 94% | 37,735 | 25,049 (3,135 to 158,284) | 1,212 | 626 | 1,222 | 1,341 |
| paid_search_nonbrand | 3,068 | 3,913 (2,247 to 6,546) | 28% | 11,116 | 8,290 (4,750 to 13,551) | 5,551 | 4,352 | 3,644 | 2,320 |
| meta | 1,482 | 4,798 (1,433 to 11,222) | 224% | 1,834 | 4,026 (1,864 to 9,171) (miss) | 2,969 | 917 (miss) | 3,022 | 462 |
| linkedin | 2,550 | 6,169 (849 to 31,439) | 142% | 3,294 | 11,092 (1,908 to 61,105) | 1,004 | 415 | 3,492 | 1,971 |
| youtube | 1,542 | 1,860 (1,156 to 2,656) | 21% | 1,637 | 2,365 (1,618 to 3,304) | 1,815 | 1,506 | 14,737 | 868 |
| ctv | 2,516 | 3,023 (2,358 to 3,883) | 20% | 3,096 | 3,740 (2,912 to 4,727) | 1,153 | 959 | n/a | 1,561 |
| display | 42,123 | 10,993 (1,393 to 77,287) | -74% | 113,255 | 27,205 (3,632 to 175,858) | 103 | 396 | 5,172 | 2,157 |
| affiliates | 1,232 | 4,158 (692 to 25,277) | 237% | 1,982 | 9,968 (1,692 to 62,197) | 1,583 | 469 (miss) | 1,430 | 793 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.55 | 84% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 80% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 41% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 15,389 | 10,293 (7,850 to 12,715) | no |
| incremental_cpa_paid_media | 2,821 | 4,217 (3,357 to 5,409) | no |

Upper funnel through brand search: 90% HDI coverage 9 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.1% (5.3% to 6.8%) | -64% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 3.0% | 7% |
| meta | incremental_deals_via_brand_search | 18 | 5 (0 to 16) (miss) | -71% |
| meta | incremental_deals_total | 2,986 | 921 (189 to 1,865) (miss) | -69% |
| meta | cpa_total | 1,473 | 4,779 (1,509 to 11,066) (miss) | 224% |
| meta | marginal_cpa_total | 1,825 | 4,008 (1,801 to 8,964) | 120% |
| youtube | incremental_deals_via_brand_search | 10 | 4 (0 to 12) | -57% |
| youtube | incremental_deals_total | 1,825 | 1,509 (975 to 2,176) | -17% |
| youtube | cpa_total | 1,534 | 1,856 (1,157 to 2,647) | 21% |
| youtube | marginal_cpa_total | 1,632 | 2,356 (1,601 to 3,267) | 44% |
| ctv | incremental_deals_via_brand_search | 6 | 9 (0 to 27) | 42% |
| ctv | incremental_deals_total | 1,159 | 972 (734 to 1,201) | -16% |
| ctv | cpa_total | 2,502 | 2,985 (2,260 to 3,747) | 19% |
| ctv | marginal_cpa_total | 3,086 | 3,682 (2,901 to 4,648) | 19% |

Optimizer plan at the same total spend: model predicts 887 deals (410 to 1,390); the true world gives 1,676 (outside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 218 (121 to 311) | 348 | -37% | no | yes |
| youtube_ask | 186 (125 to 242) | 263 | -29% | no | no |
