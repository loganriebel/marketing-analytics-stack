# MMM grade: holdout

90% HDI coverage: 21 of 36 (58%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 5,756 | 15,226 (2,555 to 89,691) | 165% | 35,601 | 21,893 (1,391 to 139,636) | 1,270 | 480 | 1,166 | 1,301 |
| paid_search_nonbrand | 2,067 | 3,497 (2,019 to 5,455) | 69% | 5,003 | 3,426 (2,268 to 5,227) | 6,169 | 3,646 (miss) | 2,464 | 1,733 |
| meta | 1,441 | 2,706 (1,454 to 4,447) (miss) | 88% | 1,841 | 2,358 (1,546 to 3,441) | 2,812 | 1,497 (miss) | 2,730 | 438 |
| linkedin | 2,670 | 9,240 (1,728 to 47,913) | 246% | 4,350 | 13,068 (2,230 to 85,280) | 1,585 | 458 (miss) | 3,557 | 2,030 |
| youtube | 1,516 | 1,654 (989 to 2,458) | 9% | 1,296 | 1,961 (1,139 to 3,226) | 1,009 | 925 | 15,303 | 1,006 |
| ctv | 2,578 | 4,961 (2,632 to 8,247) (miss) | 92% | 2,477 | 5,287 (2,882 to 9,234) (miss) | 1,297 | 674 (miss) | n/a | 1,768 |
| display | 37,654 | 10,197 (1,834 to 51,996) | -73% | 102,842 | 16,242 (2,419 to 93,670) (miss) | 121 | 445 | 4,677 | 2,001 |
| affiliates | 1,160 | 3,662 (734 to 18,342) | 216% | 1,960 | 5,877 (866 to 32,134) | 1,915 | 607 (miss) | 1,348 | 726 |
| webinars | 1,202 | 1,108 (966 to 1,271) | -8% | 2,184 | 1,612 (1,342 to 1,914) (miss) | 1,544 | 1,675 | 1,268 | 941 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.80 | 88% | webinars | no | paid_search_brand | no |
| CRM last touch | 0.27 | 56% | paid_search_brand | no | ctv | no |
| Platform reported | 0.82 | 34% | meta | no | linkedin | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 17,722 | 10,993 (8,941 to 13,205) | no |
| incremental_cpa_paid_media | 2,361 | 3,806 (3,099 to 4,595) | no |

Optimizer plan at the same total spend: model predicts 2,075 deals (1,031 to 3,063); the true world gives 1,230 (inside the HDI).
