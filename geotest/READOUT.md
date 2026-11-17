# Readout: market test MT2026Q1

Written by `python -m geotest.readout` from `geotest/outputs/readout.json`; every number below comes from that file. Data: the 2026-05-31 cut, weeks 2023-01-02 to 2026-05-25. Method, markets, windows and rules: [PREREGISTRATION.md](PREREGISTRATION.md), unchanged.

## Results

| Arm | Measured lift, deals (90% interval) | MMM forecast (90% range) | Power at forecast |
|---|---:|---:|---:|
| grow: YouTube | +463 (+246 to +679) | +334 (+287 to +382) | 81% |
| search: non-brand search at 39% of plan | -79 (-328 to +170) | -190 (-252 to -113) | 35% |

Deals in the window, 2026-02-02 to 2026-05-24: the grow markets closed 3,741, and the other markets scaled by their pre-test ratio point to 3,271. The search markets closed 4,046 against 4,158. The 2x2 solve then takes out each arm's effect on the other.

## Decision rules, as registered

1. **YouTube works.** The grow arm's 90% interval, +246 to +679, is above zero.
2. **Against the model.** Grow arm: the interval holds the forecast (+334), so the lift agrees with the model. Search arm: the interval holds the forecast (-190), so the cost of pulling non-brand search back agrees with the model.
   The search arm's drop is not clear: its interval, -328 to +170, reaches zero. This arm had 35% power at the forecast and was registered as a guardrail, so this is not evidence that non-brand search does nothing. The test can only rule out a loss larger than 328 deals over the window.
3. **The model learns.** Both arms enter the MMM as lift tests: YouTube from the grow arm, non-brand search from the search arm (rows below). The refit and its grade are in [docs/mmm/README.md](../docs/mmm/README.md#the-2026-market-test-and-the-refit).
4. **Guardrail.** Not tripped. The search arm did not show non-brand search worth more than modeled, and YouTube showed a lift.
5. **Validity: the readout stands.** Realized spend change against plan: grow $524,869 against $568,421 (-8%); search -$1,506,568 against -$1,624,941 (-7%); the limit is 20%. The plan file puts every market in its registered cell, every grow market shows the add, and the search arm shows the cut (step 0.42 against a line of 0.62).

**Rule 5, as registered** (design.json `compliance`, applied unchanged):

- Spend change: the ratio difference-in-differences on the moved channel's spend over the test weeks. Its error on earlier windows is 27% of YouTube spend and 11% of non-brand search spend. The plan's dollars: the grow add is $5,625 a week per size unit; the search change is observed spend over the multiplier, minus observed spend.
- Plan file: `plans/2026_test.yaml`, the plan that drove 2026 spend, must match the registered arms and dates (it does).
- YouTube add: the add runs every test week, so a market shows it when its lowest weekly YouTube spend per size unit over the test weeks is at least $2,812.
- Non-brand search cut: a step test at the test start. Spend in the 9 test weeks of the test's quarter is compared with the 4 weeks of that quarter before the test, against the same step in the markets outside the arm. The arm, its markets summed, shows the cut when its step is nearer, in logs, to 0.39 than to 1 (the line is 0.62); one noise unit is 0.15 in logs. Each market gets the same test on its own (one noise unit 0.21, from 12 earlier quarters).
- Void if an arm's spend misses its plan by more than the limit, the plan file does not match, an assigned grow market does not show the add, or the search arm does not show the cut. A search market whose own step misses, or a market outside an arm whose spend shows the move (drift), is named, and the lifts are recomputed without it (exploratory). Neither voids the readout.

## Cost per deal (secondary)

- **Grow arm:** $568,421 of YouTube plus $74,227 of brand search that followed the extra searches, $642,648 in all: $1,389 per extra deal ($946 to $2,616). The MMM's cost per extra deal for YouTube was $2,291.
- **Search arm:** $1,624,941 saved, $20,479 per deal lost (range unbounded: the interval reaches zero). The MMM's cost per extra deal for non-brand search was $7,896.
- **Blended cost per deal in the window:** grow markets $1,601 against $1,520 in the rest; search markets $1,455 against $1,658.

## Cross-check: Bayesian synthetic control (does not decide)

- **Grow arm:** +566 deals (+464 to +680), pre-test fit R² 0.54; 59% of the donor weight sits on the other arm's markets.
- **Search arm:** -161 deals (-316 to +11), pre-test fit R² 0.39; 63% of the donor weight sits on the other arm's markets.
- Each arm's donors include markets of the other arm, so this check does not take out the other arm's effect the way the registered 2x2 estimator does.
- One market's weekly deals are noisy, so a weighted mix of single markets tracks an arm only loosely before the test (low R²). The registered estimator sums whole windows, which averages that noise out.

## Exploratory (does not decide)

- **Search doses from 2026 spend:** grow +452, search -80. The registered doses use last year's same weeks.
- **Placebo mean removed:** the placebo windows erred by +27 (grow) and +4 (search) on average. Taking that out gives grow +436 and search -84.

## Into the MMM

Each arm becomes one `add_lift_test_measurements` row, in dollars and deals per week per size unit (market value / size index), the MMM's own units. delta_y = lift in window / (test weeks x window share x size units); the window share is the pre-test MMM forecast's in-window lift over its total lift.

| Arm | Channel | x | delta_x | delta_y | sigma | Window share |
|---|---|---:|---:|---:|---:|---:|
| grow | youtube | 2,904 | +5,625 | +4.670 | 1.331 | 0.980 |
| cut | paid_search_nonbrand | 21,741 | -13,262 | -0.654 | 1.247 | 0.990 |
