# MMM grade: holdout fit, seed 2026

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 21 of 32 (66%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,148 | 20,311 (2,402 to 143,049) | 230% | 38,302 | 41,430 (2,860 to 283,516) | 3,017 | 913 (miss) | 1,198 | 1,316 |
| paid_search_nonbrand | 3,074 | 4,131 (2,629 to 6,106) | 34% | 11,117 | 7,896 (5,321 to 11,135) | 13,851 | 10,305 | 3,636 | 2,292 |
| meta | 1,488 | 5,065 (2,266 to 9,420) (miss) | 240% | 1,844 | 3,523 (2,108 to 5,540) (miss) | 7,392 | 2,172 (miss) | 2,880 | 462 |
| linkedin | 2,556 | 3,682 (1,027 to 12,837) | 44% | 3,301 | 5,209 (1,719 to 19,790) | 2,504 | 1,738 | 3,358 | 1,965 |
| youtube | 1,547 | 2,035 (1,509 to 2,647) | 32% | 1,639 | 2,300 (1,768 to 2,948) (miss) | 4,525 | 3,439 (miss) | 15,945 | 857 |
| ctv | 2,551 | 2,511 (2,097 to 2,932) | -2% | 3,134 | 3,615 (3,073 to 4,217) | 2,842 | 2,887 | n/a | 1,685 |
| display | 42,257 | 23,421 (2,360 to 153,198) | -45% | 113,390 | 56,162 (5,457 to 355,742) | 257 | 464 | 4,840 | 2,093 |
| affiliates | 1,238 | 4,998 (949 to 23,914) | 304% | 1,997 | 9,412 (1,423 to 58,469) | 3,937 | 975 (miss) | 1,423 | 789 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.43 | 44% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 81% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 40% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 38,325 | 24,013 (19,173 to 28,207) | no |
| incremental_cpa_paid_media | 2,832 | 4,519 (3,712 to 5,434) | no |

Upper funnel through brand search: 90% HDI coverage 6 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.3% (5.5% to 7.1%) | -62% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 3.2% | 15% |
| meta | incremental_deals_via_brand_search | 43 | 9 (0 to 33) (miss) | -79% |
| meta | incremental_deals_total | 7,435 | 2,184 (824 to 3,696) (miss) | -71% |
| meta | cpa_total | 1,479 | 5,036 (2,095 to 9,119) (miss) | 240% |
| meta | marginal_cpa_total | 1,836 | 3,509 (2,102 to 5,492) (miss) | 91% |
| youtube | incremental_deals_via_brand_search | 24 | 7 (0 to 24) | -71% |
| youtube | incremental_deals_total | 4,548 | 3,448 (2,566 to 4,493) (miss) | -24% |
| youtube | cpa_total | 1,539 | 2,030 (1,475 to 2,603) | 32% |
| youtube | marginal_cpa_total | 1,634 | 2,291 (1,774 to 2,948) (miss) | 40% |
| ctv | incremental_deals_via_brand_search | 16 | 13 (0 to 48) | -21% |
| ctv | incremental_deals_total | 2,858 | 2,906 (2,453 to 3,407) | 2% |
| ctv | cpa_total | 2,537 | 2,495 (2,090 to 2,907) | -2% |
| ctv | marginal_cpa_total | 3,124 | 3,578 (3,046 to 4,176) | 15% |

Optimizer plan at the same total spend: model predicts 2,664 deals (1,732 to 3,698); the true world gives 4,560 (outside the HDI).

Proposal memo's recommended moves, extra deals a year:

| Variant | Memo claims (90% range) | True | Error | Covered | Range in memo |
|---|---:|---:|---:|---|---|
| reallocation | 218 (121 to 311) | 867 | -75% | no | yes |
| youtube_ask | 186 (125 to 242) | 657 | -72% | no | no |
