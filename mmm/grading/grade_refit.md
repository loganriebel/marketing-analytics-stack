# MMM grade: refit fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 20 of 32 (62%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,148 | 18,581 (2,577 to 121,661) | 202% | 38,302 | 38,229 (2,982 to 255,812) | 3,017 | 998 (miss) | 1,198 | 1,316 |
| paid_search_nonbrand | 3,074 | 4,409 (2,911 to 6,140) | 43% | 11,117 | 8,459 (6,108 to 11,737) | 13,851 | 9,657 (miss) | 3,636 | 2,292 |
| meta | 1,488 | 3,774 (1,979 to 6,025) (miss) | 154% | 1,844 | 2,633 (1,802 to 3,629) | 7,392 | 2,915 (miss) | 2,880 | 462 |
| linkedin | 2,556 | 6,414 (1,390 to 31,587) | 151% | 3,301 | 9,508 (1,929 to 54,461) | 2,504 | 998 (miss) | 3,358 | 1,965 |
| youtube | 1,547 | 1,856 (1,374 to 2,460) | 20% | 1,639 | 2,092 (1,614 to 2,692) | 4,525 | 3,771 | 15,945 | 857 |
| ctv | 2,551 | 2,560 (2,161 to 2,989) | 0% | 3,134 | 3,666 (3,148 to 4,274) (miss) | 2,842 | 2,832 | n/a | 1,685 |
| display | 42,257 | 22,457 (2,216 to 135,605) | -47% | 113,390 | 53,164 (6,023 to 317,637) | 257 | 484 | 4,840 | 2,093 |
| affiliates | 1,238 | 5,879 (1,028 to 29,732) | 375% | 1,997 | 11,964 (1,842 to 75,268) | 3,937 | 829 (miss) | 1,423 | 789 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.64 | 99% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 81% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 40% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 38,325 | 23,482 (19,749 to 27,810) | no |
| incremental_cpa_paid_media | 2,832 | 4,622 (3,902 to 5,495) | no |

Upper funnel through brand search: 90% HDI coverage 9 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.2% (5.5% to 6.9%) | -63% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 3.1% | 14% |
| meta | incremental_deals_via_brand_search | 43 | 10 (0 to 38) (miss) | -77% |
| meta | incremental_deals_total | 7,435 | 2,929 (1,457 to 4,428) (miss) | -61% |
| meta | cpa_total | 1,479 | 3,756 (2,036 to 6,013) (miss) | 154% |
| meta | marginal_cpa_total | 1,836 | 2,625 (1,803 to 3,617) | 43% |
| youtube | incremental_deals_via_brand_search | 24 | 7 (0 to 27) | -70% |
| youtube | incremental_deals_total | 4,548 | 3,780 (2,841 to 5,099) | -17% |
| youtube | cpa_total | 1,539 | 1,852 (1,361 to 2,446) | 20% |
| youtube | marginal_cpa_total | 1,634 | 2,087 (1,591 to 2,659) | 28% |
| ctv | incremental_deals_via_brand_search | 16 | 14 (0 to 57) | -12% |
| ctv | incremental_deals_total | 2,858 | 2,857 (2,399 to 3,304) | -0% |
| ctv | cpa_total | 2,537 | 2,538 (2,156 to 2,966) | 0% |
| ctv | marginal_cpa_total | 3,124 | 3,630 (3,092 to 4,186) | 16% |

Optimizer plan at the same total spend: model predicts 3,363 deals (2,422 to 4,243); the true world gives 3,954 (inside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 888 (577 to 1,233) | 1,520 | -42% | no | yes |
| youtube_ask | 454 (318 to 571) | 657 | -31% | no | no |
