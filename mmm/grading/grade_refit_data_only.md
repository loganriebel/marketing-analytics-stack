# MMM grade: refit_data_only fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 21 of 32 (66%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,148 | 18,356 (2,148 to 119,777) | 199% | 38,302 | 36,740 (1,987 to 264,012) | 3,017 | 1,011 (miss) | 1,198 | 1,316 |
| paid_search_nonbrand | 3,074 | 4,264 (2,683 to 6,028) | 39% | 11,117 | 8,160 (5,830 to 11,434) | 13,851 | 9,985 | 3,636 | 2,292 |
| meta | 1,488 | 3,903 (2,159 to 6,398) (miss) | 162% | 1,844 | 2,668 (1,867 to 3,700) (miss) | 7,392 | 2,819 (miss) | 2,880 | 462 |
| linkedin | 2,556 | 6,223 (1,370 to 30,767) | 143% | 3,301 | 9,695 (2,151 to 54,435) | 2,504 | 1,028 (miss) | 3,358 | 1,965 |
| youtube | 1,547 | 1,808 (1,288 to 2,429) | 17% | 1,639 | 2,076 (1,572 to 2,695) | 4,525 | 3,871 | 15,945 | 857 |
| ctv | 2,551 | 2,566 (2,158 to 2,997) | 1% | 3,134 | 3,646 (3,065 to 4,241) | 2,842 | 2,825 | n/a | 1,685 |
| display | 42,257 | 23,015 (1,900 to 165,117) | -46% | 113,390 | 56,565 (5,155 to 378,849) | 257 | 473 | 4,840 | 2,093 |
| affiliates | 1,238 | 5,999 (894 to 31,062) | 385% | 1,997 | 12,703 (1,646 to 77,600) | 3,937 | 813 (miss) | 1,423 | 789 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.64 | 95% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 81% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 40% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 38,325 | 23,877 (19,240 to 27,847) | no |
| incremental_cpa_paid_media | 2,832 | 4,545 (3,766 to 5,408) | no |

Upper funnel through brand search: 90% HDI coverage 8 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.2% (5.5% to 6.9%) | -63% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 3.3% | 18% |
| meta | incremental_deals_via_brand_search | 43 | 10 (0 to 38) (miss) | -76% |
| meta | incremental_deals_total | 7,435 | 2,841 (1,530 to 4,502) (miss) | -62% |
| meta | cpa_total | 1,479 | 3,872 (2,215 to 6,403) (miss) | 162% |
| meta | marginal_cpa_total | 1,836 | 2,659 (1,866 to 3,678) (miss) | 45% |
| youtube | incremental_deals_via_brand_search | 24 | 7 (0 to 29) | -69% |
| youtube | incremental_deals_total | 4,548 | 3,888 (2,649 to 5,045) | -15% |
| youtube | cpa_total | 1,539 | 1,800 (1,266 to 2,400) | 17% |
| youtube | marginal_cpa_total | 1,634 | 2,066 (1,569 to 2,687) | 26% |
| ctv | incremental_deals_via_brand_search | 16 | 15 (0 to 59) | -8% |
| ctv | incremental_deals_total | 2,858 | 2,850 (2,386 to 3,291) | -0% |
| ctv | cpa_total | 2,537 | 2,544 (2,149 to 2,973) | 0% |
| ctv | marginal_cpa_total | 3,124 | 3,599 (3,065 to 4,220) | 15% |

Optimizer plan at the same total spend: model predicts 3,348 deals (2,376 to 4,237); the true world gives 3,842 (inside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 888 (577 to 1,233) | 1,520 | -42% | no | yes |
| youtube_ask | 454 (318 to 571) | 657 | -31% | no | no |
