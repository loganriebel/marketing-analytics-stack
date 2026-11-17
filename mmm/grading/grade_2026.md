# 2026 grade: the market test and the rollout, seed 2026

Answer key: `truth_2026.json` from the 2027-01-03 data cut, plans `plans/2026_test.yaml`, `plans/2026_rollout.yaml`. True effects are expected, noise-free deals the spend change caused that close inside the window; nobody in the story sees them.

| What | Window | True | Estimate (90% range) | Error | Covered |
|---|---|---:|---:|---:|---|
| Test, grow arm, readout | 2026-02-02 to 2026-05-24 | 346 | 463 (246 to 679) | 117 | yes |
| Test, grow arm, January forecast | 2026-02-02 to 2026-05-24 | 346 | 334 (287 to 382) | -12 | yes |
| Test, cut arm, readout | 2026-02-02 to 2026-05-24 | -119 | -79 (-328 to 170) | 40 | yes |
| Test, cut arm, January forecast | 2026-02-02 to 2026-05-24 | -119 | -190 (-252 to -113) | -71 | yes |
| Rollout, May forecast | 2026-06-01 to 2027-01-03 | 882 | 533 (407 to 661) | -348 | no |
| Rollout, year-end measurement (standing holdout) | 2026-06-01 to 2027-01-03 | 882 | 464 (18 to 911) | -417 | yes |
| Rollout, the model's own view (cross-check) | 2026-06-01 to 2027-01-03 | 882 | 505 (383 to 633) | -377 | no |

All the deals the rollout causes, closing in the window or after: true 925, forecast 543 (403 to 678).
