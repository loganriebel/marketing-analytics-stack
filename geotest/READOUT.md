# Readout: market test MT2026Q1

Written by `python -m geotest.readout` from `geotest/outputs/readout.json`; every number below comes from that file. Data: the 2026-05-31 cut, weeks 2023-01-02 to 2026-05-25. Method, markets, windows and rules: [PREREGISTRATION.md](PREREGISTRATION.md), unchanged.

## Results

| Arm | Measured lift, deals (90% interval) | MMM forecast (90% range) | Power at forecast |
|---|---:|---:|---:|
| grow: YouTube | +130 (+52 to +208) | +119 (+88 to +154) | 81% |
| search: non-brand search at 39% of plan | -37 (-127 to +52) | -83 (-120 to -41) | 45% |

Deals in the window, 2026-02-02 to 2026-05-24: the grow markets closed 1,461, and the other markets scaled by their pre-test ratio point to 1,335. The search markets closed 1,609 against 1,639. The 2x2 solve then takes out each arm's effect on the other.

## Decision rules, as registered

1. **YouTube works.** The grow arm's 90% interval, +52 to +208, is above zero.
2. **Against the model.** Grow arm: the interval holds the forecast (+119), so the lift agrees with the model. Search arm: the interval holds the forecast (-83), so the cost of pulling non-brand search back agrees with the model.
   The search arm's drop is not clear: its interval, -127 to +52, reaches zero. This arm had 45% power at the forecast and was registered as a guardrail, so this is not evidence that non-brand search does nothing. The test can only rule out a loss larger than 127 deals over the window.
3. **The model learns.** Both arms enter the MMM as lift tests: YouTube from the grow arm, non-brand search from the search arm (rows below). The refit and its grade are in [docs/mmm/README.md](../docs/mmm/README.md#the-2026-market-test-and-the-refit).
4. **Guardrail.** Not tripped. The search arm did not show non-brand search worth more than modeled, and YouTube showed a lift.
5. **Validity: the readout stands.** Realized spend change against plan: grow $218,314 against $252,632 (-14%); search -$581,630 against -$537,107 (+8%); the limit is 20%. The plan file puts every market in its registered cell, and the spend data show every assigned move.
   Drift: Duluth (DLH), outside the search arm, also ran less non-brand search during the test than its own pace before it (step 0.60, against a line of 0.62; -2.3 noise units from no move and +1.9 from the cut). The plan gives it no move. Without it, grow reads +144 and search -17, and no decision changes.

**How rule 5 was checked.** The registration named no method, so these were set on spend only.

- Spend change: the same ratio difference-in-differences on the moved channel's spend over the test weeks. Its error on earlier windows is 47% of YouTube spend and 14% of non-brand search spend, so the YouTube check is rough. The plan's dollars: the grow add is $2,500 a week per size unit; the search change is observed spend over the multiplier, minus observed spend.
- Cells: `plans/2026_test.yaml`, the plan that drove 2026 spend, must match the registered arms and dates (it does), and every assigned move must show in the spend.
- YouTube add: a market shows it when its median weekly YouTube spend per size unit is at least $1,250.
- Non-brand search cut: a step test at the test start. Budgets for always-on channels are re-split across markets every quarter, so each market's spend in the 9 test weeks of the test's quarter is compared with its 4 weeks of that quarter before the test, against the same step in the markets outside the arm. A market shows the cut when its step is nearer, in logs, to 0.39 than to 1 (the line is 0.62). One noise unit, from the same layout in 12 earlier quarters, is 0.22 in logs.
- A market outside an arm whose spend looks moved has drifted, not left its cell. It is named, and the lifts are recomputed without it.
- **Disclosure.** The cells check was first set as each market's test-week non-brand search spend against its 52-week pre-test share, with any mismatch voiding the readout. It flagged Duluth (DLH) and Madison (MSN), outside the arm, whose budgets fell at quarterly re-splits before the test began. The checks above replaced it after the lifts were computed. They decide validity only, never a lift.

## Cost per deal (secondary)

- **Grow arm:** $252,632 of YouTube plus $22,652 of brand search that followed the extra searches, $275,284 in all: $2,116 per extra deal ($1,323 to $5,271). The MMM's cost per extra deal for YouTube was $2,253.
- **Search arm:** $537,107 saved, $14,343 per deal lost (range unbounded: the interval reaches zero). The MMM's cost per extra deal for non-brand search was $6,835.
- **Blended cost per deal in the window:** grow markets $1,608 against $1,574 in the rest; search markets $1,365 against $1,805.

## Cross-check: Bayesian synthetic control (does not decide)

- **Grow arm:** +126 deals (+74 to +180), pre-test fit R² 0.23; 54% of the donor weight sits on the other arm's markets.
- **Search arm:** -7 deals (-77 to +56), pre-test fit R² 0.02; 59% of the donor weight sits on the other arm's markets.
- Each arm's donors include markets of the other arm, so this check does not take out the other arm's effect the way the registered 2x2 estimator does.
- One market's weekly deals are noisy, so a weighted mix of single markets tracks an arm only loosely before the test (low R²). The registered estimator sums whole windows, which averages that noise out.

## Exploratory (does not decide)

- **Search doses from 2026 spend:** grow +130, search -37. The registered doses use last year's same weeks.
- **Placebo mean removed:** the placebo windows erred by +17 (grow) and -2 (search) on average. Taking that out gives grow +113 and search -35.

## Into the MMM

Each arm becomes one `add_lift_test_measurements` row, in dollars and deals per week per size unit (market value / size index), the MMM's own units. delta_y = lift in window / (test weeks x window share x size units); the window share is the pre-test MMM forecast's in-window lift over its total lift.

| Arm | Channel | x | delta_x | delta_y | sigma | Window share |
|---|---|---:|---:|---:|---:|---:|
| grow | youtube | 1,078 | +2,500 | +1.430 | 0.520 | 0.900 |
| cut | paid_search_nonbrand | 7,495 | -4,572 | -0.321 | 0.465 | 0.993 |
