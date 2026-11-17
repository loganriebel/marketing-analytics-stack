# Step 4: the MMM

A Bayesian geo MMM for Fernhook on [PyMC-Marketing](https://www.pymc-marketing.io/), fit on the golden marts, with brand search modeled as a mediator of the upper funnel, and graded once against the hidden answer key.

**Final fit (the 2.5x world: Fernhook at 2.5 times its first size with the same unit economics, budgets drifting from brand to non-brand search; last 13 weeks held out): it passes every health gate and tracks weekly deals more closely than before (national weekly R² 0.88, up from 0.76), because count luck is a smaller share of each week. Its ranges are tighter, so they miss the truth more often, and it gives paid media 37% too little credit.**

- **Health:** max r-hat 1.002, min bulk ESS 1,062, 4 divergences in 8,000 draws. The brand-search stage passes its own gates.
- **Prediction:** holdout weekly error 5.2%, 87% of holdout market-weeks inside the 90% interval. Residuals show no pattern.
- **Scale:** paid media drives 24,013 deals in the model (90% HDI 19,173 to 28,207) against 38,325 in truth. The 90% HDIs cover the truth 21 of 32 times.
- **Ranking:** CPA rank correlation with the truth is 0.43. Platform-reported numbers rank better (0.79); CRM last touch worse (0.10).
- **What it gets right:** YouTube as the best next dollar and display as the worst; CTV's average cost per deal (2% off) and its deals.
- **What it misses:** non-brand search's next dollar costs $11,117 in truth and $7,896 in the model, so the model still understates how saturated search is, and its average cost comes out 34% high. Meta comes out 71% low and affiliates 75% low.
- **The budget shift:** at the same spend the plan gains 4,560 true deals, above the model's 90% HDI (1,732 to 3,698).
- **The lesson:** more volume buys a sharper fit, not a truer split. Non-brand search's spend ramp still lines up with time, so the model separates them on average cost, not on the margin. Only a test that moves search can show what the extra dollars buy.

## Run it

Windows, Python 3.11, from the repo root, after `python -m sim` and `dbt build` (see the root README):

```bash
py -3.11 -m venv .venv-mmm
.venv-mmm\Scripts\python -m pip install -r requirements-mmm.txt
.venv-mmm\Scripts\python -m mmm
.venv-mmm\Scripts\python -m mmm.grade
.venv-mmm\Scripts\python -m pytest tests/test_mmm_smoke.py tests/test_mmm_no_truth_leak.py tests/test_mmm_market_lifts.py -q
```

- `python -m mmm` fits stage 2 (the MMM) with the last 13 weeks held out, checks its gates, fits stage 1 (brand-search demand), checks its gates, and writes `mmm/outputs/` only when they pass. About 10 minutes. `--holdout 0` fits the full window.
- `python -m mmm --report-only` re-scores the saved posterior in `mmm/fits/` (gitignored, about 2.8 GB) without sampling the MMM again.
- The MMM has its own environment, so PyMC never moves the pinned warehouse stack. `nutpie` compiles through numba, and PyTensor runs in numba mode, so Windows needs no C compiler. Without numba mode, PyMC-Marketing's post-sampling pass took 58 minutes in pure Python.
- The smoke test fits 2 markets for 100 weeks, both stages, in about a minute. It skips in the main `.venv`.

**Development worlds.** Model changes are tested on another simulator seed, never on the graded one. Each seed draws its own true parameters.

```bash
.venv\Scripts\python -m sim --seed 2 --raw-dir data/dev/seed2/data/raw --truth-path data/dev/seed2/truth.json
```

Then run `dbt build` from `data/dev/seed2` with `--project-dir` and `--profiles-dir` pointing at `warehouse/`, and point the MMM at it with `MMM_WAREHOUSE`, `MMM_OUTPUT_DIR` and `MMM_FIT_DIR`. `mmm.grade` takes `--truth` and `--grade-dir`. `data/dev/` is gitignored.

## Data

The model reads marts and nothing else. It never touches `data/raw/` or `sim/`, and never queries staging or intermediate rows: those are dbt views over the raw CSVs. Tests enforce all three.

| Piece | Source | Notes |
|---|---|---|
| KPI | `fct_funnel.won_deals`, summed over lead sources | Market x week, counted in the close week. |
| Media | `fct_channel_weekly.spend`, 8 bought channels | CTV runs in 8 of 20 markets. |
| Webinars | `fct_channel_weekly.spend` | An events program, so a control, not media. |
| Controls | `fct_controls_weekly` | Headcount, email, promo, price, fleet activity index. |
| Market size and latitude | `dim_region` | Size index = target accounts / market mean. |
| Channel roles | `dim_channel.marketing_role` | Sets the curve-shape prior. |

**Affiliate spend is placement fees only**, checked from marts and metadata: the `stg_partners` view's SQL takes `partner_fees` as spend and no commission column, the intermediate media model reads that view, `dim_channel` says commissions are booked as cost of sale, and week-to-week changes in affiliate spend do not track affiliate-sourced wins (correlation under 0.3 is required).

## Model

Two stages. Stage 2 is PyMC-Marketing's multidimensional `MMM` with `dims=("geo",)`: 20 markets x 143 training weeks. Stage 1 is a small PyMC model of brand-search spend. Each is one joint model across markets, not one model per market.

### Stage 2: deals

For market $g$ and week $t$, with $s_g$ the size index:

```math
y_{g,t} = \frac{\text{deals}_{g,t}}{s_g\,Y},
\qquad
x_{g,t,c} = \frac{\text{spend}_{g,t,c}}{s_g\,X_c},
\qquad
y_{g,t} \sim \mathcal{N}\!\left(\mu_{g,t},\ \sigma_g\right)
```

$Y$ and $X_c$ are the largest training values of deals and of channel $c$'s spend per size unit.

```math
\mu_{g,t} = b_g
 + \sum_{c=1}^{8} \beta_c\,\frac{a_{g,t,c}^{\,s_c}}{a_{g,t,c}^{\,s_c} + \kappa_c^{\,s_c}}
 + \sum_{j} \gamma_j\, z_{j,g,t}
 + \sum_{m=1}^{3} \Big[\lambda_m \sin(2\pi m\,d_t) + \rho_m \cos(2\pi m\,d_t)\Big]
```

$d_t$ is the day of year over 365.25. Among the controls $z$ are six latitude terms, $\ell_g \sin(2\pi m\,d_t)$ and $\ell_g \cos(2\pi m\,d_t)$ with $\ell_g$ the standardized latitude, so the shared season can arrive earlier or later by market.

Adstock, with lead-side carryover $\alpha_c$ and the fixed lead-to-close kernel $k$:

```math
a_{g,t,c} = \sum_{l=0}^{11} w_c(l)\, x_{g,t-l,c},
\qquad
w_c(l) = \sum_{j=0}^{4} k_j\, \frac{\alpha_c^{\,l-j}}{\sum_{i=0}^{7}\alpha_c^{\,i}}\ \mathbb{1}[0 \le l-j \le 7],
\qquad
k = (0.025,\ 0.291,\ 0.409,\ 0.210,\ 0.065)
```

The weights sum to 1, so carryover moves when a dollar's effect lands, not how big it is. With $\alpha = 0.4$ a dollar's effect lands 2% in week 0, 18% in week 1, 32% in week 2, 25% in week 3, 14% in week 4 and 9% later.

### Stage 1: brand-search demand

Brand search is always on, so its spend follows searches. Stage 1 splits brand-search spend $q$ (per size unit, on stage 2's scale) into baseline search demand and searches the upper funnel creates:

```math
q_{g,t} \sim \mathcal{N}\!\Big(b^{q}_g + \sum_k \gamma^{q}_k\, z^{q}_{k,g,t} + \sum_{u \in \{\text{Meta, YouTube, CTV}\}} \theta_u\, A_{g,t,u},\ \sigma^{q}_g\Big),
\qquad
A_{g,t,u} = \sum_{l=0}^{7} \frac{\delta_u^{\,l}}{\sum_i \delta_u^{\,i}}\, x_{g,t-l,u}
```

$z^q$ holds lead-side search drivers: the shared season, its latitude shift, trend, the fleet activity index and holiday lead weeks. $\theta_u \ge 0$ is brand-search spend created per unit of channel $u$'s carryover $A$, with its own search carryover $\delta_u$ (a search is not a deal, so no close delay).

### Mediation: deals the upper funnel creates through brand search

With $H_b$ stage 2's brand-search curve (adstock, Hill, $\beta_b$), and channel $u$'s path scaled by $m$:

```math
\text{via}_u(m) = H_b\big(q + (m-1)\,\theta_u A_u\big) - H_b(q),
\qquad
\text{deals via brand search}_u = -\,\text{via}_u(0)
```

Total deals = direct + via brand search. Total CPA and total marginal CPA (central difference, 0.99 to 1.01) follow, along with a total response curve. Stage 1 and stage 2 draws are paired at random, which treats their uncertainty as independent.

| Symbol | Meaning | Count |
|---|---|---|
| $b_g$, $\sigma_g$ | Market intercept and noise | 20 each |
| $\beta_c$, $\kappa_c$, $s_c$, $\alpha_c$ | Channel effect size, half-saturation, curve shape, carryover | 8 each |
| $\gamma_j$ | Controls, shared by markets | 18 |
| $\lambda_m$, $\rho_m$ | Shared yearly season | 6 |
| Stage 1 | Intercepts, noise, 15 drivers, 3 $\theta$, 3 $\delta$ | 61 |

Stage 2 has 96 parameters for 2,860 market-weeks. Every one is summarized in `mmm/outputs/parameters_<fit>.csv`.

### Design choices

**Population scaling.** Deals and spend are divided by each market's size index before the model sees them, the way Meridian scales by population. One set of channel parameters then serves every market.

**Adstock = lead-side carryover, then the close delay.** Won deals land one to four weeks after the lead. A custom `LaggedGeometricAdstock` convolves a normalized geometric kernel (one $\alpha$ per channel) with a fixed lead-to-close kernel from the README's sales-cycle facts (a gamma lag with 5th and 95th percentiles at 6 and 27 days). It costs no extra parameters.

**Hill saturation, made safe at zero.** The stock `HillSaturation` has a NaN gradient for its slope at exactly zero input (`d(x^s)/ds = x^s log x`), and CTV is zero in 12 markets: every draw diverged until the input was floored at 1e-12 (`ZeroSafeHillSaturation`).

**Curve shape by role.** Performance channels harvest intent that already exists, so their first dollar is their best: slope prior median 0.9 (90% 0.55 to 1.47). Brand channels can need a threshold of reach: median 1.5 (0.84 to 2.66). The role comes from `dim_channel`; LinkedIn is a brand channel there since the rebuild.

**One season, shifted by latitude.** Seasons arrive earlier in Fargo than in Cincinnati, and brand channels push into them. Free per-market season curves (60 terms) failed the r-hat and ESS gates on the dev seed. A shared curve plus latitude x each Fourier term (6 terms) passes. The latitude terms come out near zero on the graded seed.

**Priors.**

| Parameter | Prior | Why |
|---|---|---|
| $\alpha$ (carryover) | Beta(2, 3) | Mean 0.4 per week, wide. |
| Hill slope | LogNormal by role (above) | Concave for performance, S allowed for brand. |
| Hill $\kappa$ | LogNormal at the channel's median on-week level, sd 0.7 | Half-saturation near where the channel runs. |
| Hill $\beta$ | HalfNormal, median from spend share of 40% of deals | Equal ROI by default; mass near zero lets a dud stay a dud. |
| Brand search $\beta$ | Same, at half scale | Skeptical: its spend follows demand. |
| Stage 1 $\theta_u$ | HalfNormal, scale so the upper funnel could explain half of brand-search spend | Wide. |

**Controls.** Everything that acts on leads shows up in won deals after the lead-to-close delay, so these get the same fixed kernel: SDR and AE coverage (headcount per 1k accounts), email sends, log fleet activity index, the year-end promo, the July 2024 price increase and webinar cost. A linear trend, close-week dummies for weeks 52, 1, 2 and 3, and the latitude terms complete the baseline. On the graded seed, SDR and AE coverage, the fleet index and webinars carry clear positive effects; the price increase and the trend come out negative; the promo leans positive (87% of draws above zero) and email sits near zero.

**Lift tests.** `mmm/lift_tests.py` turns any channel's planned regional pauses into a pooled lift test through `add_lift_test_measurements`: the deal deficit over the pause plus carryover, against the market's share of the other markets, with placebo windows for sigma. PyMC-Marketing compares absolute lifts, so pauses are pooled per channel, and a pooled test with the wrong sign enters as a zero drop. The current world has no pauses, so no pause test enters the fit. The 2026 market test's two arms enter the refit as lift tests (`--market-tests`, see [the refit](#the-refit)).

## Health gates

No number is reported unless every gate passes (`mmm/config.py`). The gates read `az.rhat` and `az.ess` directly; `az.summary` rounds r-hat to two decimals, which once turned 1.0095 into a failing 1.01.

| Gate | Threshold | Final fit | Pass |
|---|---|---|---|
| r-hat, every sampled parameter | below 1.01 | 1.002 (display $\beta$) | yes |
| Bulk ESS | at least 400 | 1,062 (brand search $\beta$) | yes |
| Tail ESS | at least 400 | 667 | yes |
| Divergences | at most 0.1% | 4 of 8,000 | yes |
| Posterior predictive: market-weeks inside the 90% interval | 85% to 97% | 91.3% | yes |
| Holdout: national weekly MAPE | at most 10% | 5.2% | yes |
| Holdout: market-weeks inside the 90% interval | 80% to 98% | 86.9% | yes |
| Stage 1: r-hat, bulk ESS, divergences | same | 1.004, 10,880, 0 | yes |

## Fit statistics

Reported in `diagnostics_<fit>.json` (`mmm/validation.py`). They describe the fit; they are not gates.

| | Train market-week | Train national week | Holdout market-week | Holdout national week |
|---|---:|---:|---:|---:|
| Rows | 2,860 | 143 | 260 | 13 |
| Mean observed | 25.2 | 504.2 | 27.3 | 545.2 |
| MSE | 26.3 | 561.3 | 39.3 | 1,201.4 |
| RMSE | 5.13 | 23.7 | 6.27 | 34.7 |
| MAE | 3.87 | 19.0 | 4.62 | 28.8 |
| MAPE | 22% | 3.8% | 20% | 5.2% |
| R² | 0.94 | 0.88 | 0.91 | -0.87 |
| Bias (predicted - observed) | -0.01 | -0.10 | -1.18 | -23.6 |

- **The misses are count noise.** A market-week averaging 25.2 deals has a noise floor of about 5.0 (its square root), and RMSE sits near it. Market-week MAPE is high only because small markets close few deals a week. The holdout's national R² is negative because 13 weeks barely vary; its MAPE is 5.2%.
- **PSIS-LOO:** elpd 2,519 (se 41), p_loo 76 against 96 parameters; no Pareto k above 0.7 (max 0.43).
- **Residuals:** national lag-1 autocorrelation -0.06, Durbin-Watson 2.05, Ljung-Box p = 0.68. By market: median lag-1 0.02, median Durbin-Watson 1.94, 2 of 20 markets with Ljung-Box p below 0.05.
- **Residual vs spend:** every channel's correlation is within ±0.03.
- **Stage 1:** R² 0.61 in training and 0.68 in the holdout, holdout national weekly MAPE 5.1%.

There is no ANOVA table. F-tests split variance for least squares with fixed effects; here each effect has a full posterior, so the 90% HDI and the share of draws above zero (in the parameter table) answer the same question.

## Outputs

`mmm/outputs/` is what step 5's memo grounding check reads. Every estimate has a posterior mean, median and 90% HDI from 2,000 posterior draws.

| File | What |
|---|---|
| `channels.json`, `channels.csv` | Per channel: spend, incremental deals, CPA, marginal CPA, ROI. For Meta, YouTube and CTV also deals via brand search, total deals, total CPA and total marginal CPA. For brand search, its deals split into upper-funnel-created and other searches. Paid-media totals. |
| `response_curves.csv` | Direct incremental deals at spend multipliers 0 to 3 of the actual path. |
| `response_curves_total.csv` | Meta, YouTube and CTV: direct plus via brand search. |
| `contributions_weekly.csv` | National weekly incremental deals by channel. |
| `optimizer.json` | Reallocation at the same spend, with the deal change and its HDI. |
| `baselines.json` | CRM last-touch and platform-reported deals and CPA, from the marts. |
| `diagnostics_<fit>.json` | Gates, sampler diagnostics, PPC and holdout checks, fit statistics, stage 1 diagnostics, affiliate check. |
| `parameters_<fit>.csv` | Posterior summary of every stage 2 parameter. |

Estimand definitions match the scenario's:

- **Incremental deals:** expected deals caused by the channel's in-window spend, counting deals that close after the window (carryover runs 12 weeks past the last week).
- **CPA:** in-window spend / incremental deals. **Marginal CPA:** extra spend per extra deal when the whole in-window path is scaled by 1%.
- **Via brand search, total, total CPA, total marginal CPA:** as in the mediation section above. Brand search's own incremental deals are given its actual spend path, which already holds the searches the upper funnel created.
- **ROI:** incremental first-year revenue / spend, valuing each deal at its market's average won-deal revenue.

Stage 2's numbers come from a numpy copy of its media path (`mmm/estimands.py`). The smoke test checks it against PyMC-Marketing's own `channel_contribution` to 1e-8.

**Optimizer** (`mmm/optimize.py`): one multiplier per channel on its actual weekly path, bounded to 0.5 to 1.5, same total spend, maximizing posterior-mean deals. Brand search is not a lever: it is always on and its spend follows searches. Upper-funnel curves include their deals via brand search, and the plan reports the brand-search spend those searches add (about $626,000 for the final plan). SLSQP stops with "positive directional derivative" with most channels at a bound; the budget holds exactly.

## Grading

`mmm/grade.py` is the only module that reads an answer key. It writes to `mmm/grading/`, never to `mmm/outputs/`. It scores 90% HDI coverage and percent error (posterior median) per channel, CPA rank agreement, the best and worst marginal-CPA picks, the same for CRM last touch and platform-reported (which rank the next dollar by average CPA), the mediation estimands, and the optimizer's plan run through the true, noise-free response curves (total curves for upper-funnel moves).

Webinars are a control in the MMM, so the 8 media channels are graded. 90% HDI coverage: 21 of 32 (66%). Point estimates are posterior medians. Full table: [`mmm/grading/grade_holdout.md`](../../mmm/grading/grade_holdout.md).

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals |
|---|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,148 | 20,311 (2,402 to 143,049) | 230% | 38,302 | 41,430 (2,860 to 283,516) | 3,017 | 913 (miss) |
| paid_search_nonbrand | 3,074 | 4,131 (2,629 to 6,106) | 34% | 11,117 | 7,896 (5,321 to 11,135) | 13,851 | 10,305 |
| meta | 1,488 | 5,065 (2,266 to 9,420) (miss) | 240% | 1,844 | 3,523 (2,108 to 5,540) (miss) | 7,392 | 2,172 (miss) |
| linkedin | 2,556 | 3,682 (1,027 to 12,837) | 44% | 3,301 | 5,209 (1,719 to 19,790) | 2,504 | 1,738 |
| youtube | 1,547 | 2,035 (1,509 to 2,647) | 32% | 1,639 | 2,300 (1,768 to 2,948) (miss) | 4,525 | 3,439 (miss) |
| ctv | 2,551 | 2,511 (2,097 to 2,932) | -2% | 3,134 | 3,615 (3,073 to 4,217) | 2,842 | 2,887 |
| display | 42,257 | 23,421 (2,360 to 153,198) | -45% | 113,390 | 56,162 (5,457 to 355,742) | 257 | 464 |
| affiliates | 1,238 | 4,998 (949 to 23,914) | 304% | 1,997 | 9,412 (1,423 to 58,469) | 3,937 | 975 (miss) |

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.43 | 44% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 81% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 40% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 38,325 | 24,013 (19,173 to 28,207) | no |
| incremental_cpa_paid_media | 2,832 | 4,519 (3,712 to 5,434) | no |

Upper funnel through brand search: 90% HDI coverage 6 of 12. The upper funnel's share of brand-search deals comes out 3.2% against 2.8% true; stage 1 sees it creating 6.3% of brand searches against 16.7% true.

Optimizer plan at the same total spend: the model predicts 2,664 deals (1,732 to 3,698); the true world gives 4,560, above the HDI.

**Reading it.**

- **Prediction is not attribution.** Every fit statistic is healthy, and sharper than at 1x, while paid media is 37% low.
- **Average is not margin.** Non-brand search's next dollar costs $11,117 in truth against $7,896 in the model, and its average cost comes out 34% high. The search ramp lines up with time, so the model cannot tell how fast search saturated. The memo's market test pulls search back to its 2023 pace for exactly this reason.
- **Flighted channels are measured; always-on channels are not.** CTV lands within 2% and YouTube within about a third. Meta pushes into the busy seasons and the season curve absorbs most of it (71% low). Affiliates come out 75% low.
- **Tighter ranges, more misses.** With 2.5 times the deals the posteriors narrow, but the biases stay, so coverage falls from 27 to 21 of 32.
- **The budget move still works, and better than modeled.** Growing Meta, YouTube, CTV and LinkedIn and cutting display, affiliates and some non-brand search gains 4,560 true deals against the model's 2,664.

## How the model got here

Each change was tested on a development seed and kept only if it held there. The graded seed was fit once with the final model.

| World | Fit | Change | Paid media deals, model vs truth | Kept |
|---|---|---|---|---|
| 20 global regions, random dark weeks | First fit, seed 2026 | Baseline (webinars as media) | 10,993 vs 17,722 (-38%) | replaced |
| same, dev seed 2 | v1 | Webinars become a control | 13,164 vs 18,304 (-28%) | yes |
| same | v2 | Curve shape by role, target accept 0.95 | 13,189 (-28%); marginal CPA error 42% to 35% | yes |
| same | v3 | LogNormal effect-size prior | 13,407 (-27%); display 2.5x over; divergence gate fails | no |
| same | (no fit) | Dark-week lift tests for every steady channel | Pooled sigma 0.75 to 2.4, three wrong-signed | no |
| Midwest, planned search tests, dev seed 2 | mw1 | Free per-market season curves | 12,416 vs 18,030 (-31%); r-hat and ESS gates fail | no |
| same | mw2 | One season shifted by latitude; brand and non-brand pause tests | 12,547 (-30%); brand search on target | yes |
| Midwest, always-on search, dev seed 2 | m1 | Brand-search mediation (stage 1) | 9,347 vs 17,797 (-47%) | yes |
| same, seed 2026 | final | 2,000 draws per chain for tail ESS | 9,579 vs 16,145 (-41%) | replaced |
| Rebuilt: budgets drift to search, seed 2026 | refit | Same model; LinkedIn's role prior is now brand | 11,060 vs 15,389 (-28%) | replaced |
| Scaled 2.5x, same unit economics, seed 2026 | refit | Same model | 24,013 vs 38,325 (-37%) | graded |

**Disclosures.** The first seed-2026 grade (old world) was seen before the dev-seed work began, and it suggested the curve-shape hypothesis. While checking the new answer key's field names, some seed-2026 true values were printed: Meta's, YouTube's and CTV's direct and via-brand-search deals, and the paid-media summary. No model change followed. The only change after that was more draws, made because the final fit failed the tail ESS gate.

**Rebuild (step 6).** At Logan's direction the 2023 to 2025 world was rebuilt so budgets drift from brand to non-brand search (60/40 to 80/20) and search saturates. The same model was refit once on the new seed-2026 world; no model change was made. `python -m sim` prints each channel's true average CPA when it writes the world, so those 9 numbers were seen when the world was generated; the test design and memo use none of them.

**Scale-up (step 6).** Also at Logan's direction, every volume in the world was then scaled 2.5x with the same unit economics, so less of each week is count luck. Before any fit, a world check compared every channel's true average and marginal CPA with the old world's (all within 1.5%) and confirmed spend is exactly 2.5x. The same model was refit once, unchanged.

The scenario changed twice during step 4, at Logan's direction: the business now sells only in seven Midwest states, and paid search is always on with the upper funnel creating brand searches. The original plan to turn brand-search pauses into lift tests still exists in code, but the current world has no pauses.

## The 2026 market test and the refit

Chapters 4 to 6 of the story: run the test, read it out, teach the model.

### The readout (May 2026)

The sim ran the world from January to May 2026 on the pre-registered plan (`plans/2026_test.yaml`). From February 2 to April 26, ten markets bought extra YouTube and a crossing ten ran non-brand search at 39% of plan. The true world decided what happened; nothing was typed in. The readout ([`geotest/READOUT.md`](../../geotest/READOUT.md), from `geotest/outputs/readout.json`) uses only the method, markets, windows and rules written down in January, on data through the May 31 snapshot.

| Arm | Measured, extra deals in the window (90% interval) | MMM forecast in January (90% range) | Power |
|---|---:|---:|---:|
| YouTube up $5,625 a week per size unit | +463 (+246 to +679) | +334 (+287 to +382) | 81% |
| Non-brand search at 39% of plan | -79 (-328 to +170) | -190 (-252 to -113) | 35% |

- **YouTube works.** Its whole interval is above zero. Each extra deal cost $1,389, counting the brand search the extra searches pulled in. The model said $2,291.
- **The search cut showed no clear drop.** That arm had 35% power and was set up as a guardrail, so this does not mean search does nothing. It rules out a big hidden loss (more than 328 deals over the window), not a small one. Pulling search back saved $1,624,941.
- **Both arms agree with the model's forecast,** so neither guardrail trips, and the rollout follows the refit model (rule 3).
- **The cross-check agrees in direction.** A Bayesian synthetic control (CausalPy, `geotest/outputs/synthetic_control.json`) reads +566 (+464 to +680) and -161 (-316 to +11). It does not decide.
- **The readout stands, with no call to make.** The market-compliance check was registered with the design, before the test ran: spend moved as planned (YouTube 8% under its planned dollars, search 7% under, inside the 20% limit), every YouTube market shows the add in every test week, and the search arm shows the cut (step 0.42 against a line of 0.62). No market drifted or missed. The one judgment in the check, deciding the search cut for the arm as a whole rather than market by market, was Logan's, made from a dry run on 2025 weeks before the test.
- **More volume, same power problem for search.** At 2.5 times the deals, count luck shrank, but the placebo error comes from market-week swings that scale with the business, so the search arm's power fell from 45% to 35%.

### The refit

Both arms entered the MMM as lift tests through `add_lift_test_measurements`: YouTube from the grow arm, non-brand search from the search arm. PyMC-Marketing compares a lift with a steady weekly effect on the response curve, so the readout turns each window lift into extra deals per week per size unit (`mmm_lift_tests` in `readout.json`). The model, priors and gates did not change. The fit reads the May 31 cut and holds out the last 13 weeks as every fit does, so it trains through February 23 and the holdout is most of the test. Its estimands, optimizer and baselines are scored on 2023 to 2025, so the grade compares like with like ([`mmm/grading/compare_holdout_refit.md`](../../mmm/grading/compare_holdout_refit.md)).

**Health:** every gate passes. Max r-hat 1.004, min bulk ESS 1,248, min tail ESS 1,315, 2 divergences in 8,000. Holdout weekly error 3.7% and 92% of holdout market-weeks inside the 90% interval, on weeks with the test's spend in them. Stage 1 passes its own gates.

| Channel | CPA error, before to after | Next-dollar CPA error | 90% HDI covers true CPA / next-dollar CPA / deals |
|---|---:|---:|---|
| paid_search_brand | +230% to +202% | +8% to -0% | yes / yes / no, unchanged |
| paid_search_nonbrand | +34% to +43% | -29% to -24% | deals lost |
| meta | +240% to +154% | +91% to +43% | next dollar gained, CPA and deals still no |
| linkedin | +44% to +151% | +58% to +188% | deals lost |
| youtube | +32% to +20% | +40% to +28% | next dollar and deals gained |
| ctv | -2% to +0% | +15% to +17% | next dollar lost |
| display | -45% to -47% | -50% to -53% | yes / yes / yes, unchanged |
| affiliates | +304% to +375% | +371% to +499% | yes / yes / no, unchanged |

| | Before (December cut) | After the test | True |
|---|---:|---:|---:|
| Best next dollar | YouTube (right) | YouTube (right) | YouTube |
| Worst next dollar | display (right) | display (right) | display |
| Next-dollar CPA rank correlation | 0.86 | 0.83 | |
| CPA rank correlation | 0.43 | 0.64 | |
| Non-brand search next-dollar CPA | $7,896 | $8,459 | $11,117 |
| Paid media deals (90% HDI) | 24,013 (19,173 to 28,207) | 23,482 (19,749 to 27,810) | 38,325 |
| 90% HDI coverage | 21 of 32 | 20 of 32 | |
| Optimizer plan: model (90% HDI) | +2,664 (1,732 to 3,698) | +3,363 (2,422 to 4,243) | |
| Optimizer plan: true gain | +4,560 | +3,954 | |

**Reading it.**

- **Better calibrated, not better aimed.** The refit's plan predicts its own result: +3,363 deals modeled (2,422 to 4,243) against +3,954 true, inside its range. The December plan promised +2,664 and delivered +4,560.
- **A weaker plan.** The refit keeps Meta, YouTube and CTV at the 150% cap and display at the floor, trims non-brand search to 89% and affiliates to 70%, and now trims LinkedIn to 87% (the December plan pushed it to 126%). LinkedIn's next dollar comes out almost three times its true cost, so the plan cuts a channel that works, and the true gain falls from 4,560 to 3,954.
- **Better ranking on average cost.** CPA rank correlation rises from 0.43 to 0.64, and YouTube's next dollar moves toward the truth (error +40% to +28%). Non-brand search's next dollar moves from $7,896 toward the true $11,117.
- **No better on scale.** Paid media stays near 23,500 deals against 38,325 true. Non-brand search loses more credit (9,657 deals against 13,851 true). Coverage slips from 21 to 20 of 32.

**Exploratory: how much came from the test itself?** A second refit on the same cut, with no lift tests (`mmm/outputs/refit_data_only/`, [`compare_holdout_refit_data_only.md`](../../mmm/grading/compare_holdout_refit_data_only.md)), passes every gate too. It still trains on the test's first four weeks, so it is "more data", not "no test".

| | Before | More data, no lift tests | More data plus lift tests | True |
|---|---:|---:|---:|---:|
| Next-dollar CPA rank correlation | 0.86 | 0.83 | 0.83 | |
| CPA rank correlation | 0.43 | 0.64 | 0.64 | |
| Non-brand search next-dollar CPA | $7,896 | $8,160 | $8,459 | $11,117 |
| Non-brand search deals | 10,305 | 9,985 | 9,657 | 13,851 |
| Paid media deals | 24,013 | 23,877 | 23,482 | 38,325 |
| 90% HDI coverage | 21 of 32 | 21 of 32 | 20 of 32 | |
| Optimizer plan: true gain | +4,560 | +3,842 | +3,954 | |

- **Most of the change came from five more months of data.** The December fit trained through September 2025; the refits train through February 2026. Those weeks alone lift the average-cost ranking and pull the plan's promise in line with what it delivers.
- **The lift tests add a nudge.** They move search's next dollar about $300 closer to the truth and add about 110 true deals to the plan. They also take a little more credit from search and cost one covered interval.
- **Why it is small:** the search arm had 35% power, so its lift test is wide (sigma 1.25 against a lift of 0.65 per week per size unit). The YouTube arm read above the forecast but inside its range, so it nudges the curve rather than moving it.

**Run it** (after `python -m sim` and `dbt build` for the base world):

```bash
.venv\Scripts\python -m sim --through 2026-05-31 --plan plans/2026_test.yaml --out data/cut_2026-05-31
cd data\cut_2026-05-31 && ..\..\.venv\Scripts\dbt build --project-dir ..\..\warehouse --profiles-dir ..\..\warehouse --no-partial-parse --target-path target && cd ..\..
.venv\Scripts\python -m geotest.readout
.venv-mmm\Scripts\python -m geotest.crosscheck
.venv\Scripts\python -m geotest.readout
set MMM_WAREHOUSE=data\cut_2026-05-31\data\warehouse.duckdb
set MMM_OUTPUT_DIR=mmm\outputs\refit
.venv-mmm\Scripts\python -m mmm --name refit --market-tests geotest\outputs\readout.json --estimands-through 2025-12-22
.venv-mmm\Scripts\python -m mmm.grade --outputs mmm\outputs\refit --compare mmm\grading\grade_holdout.json
```

- dbt runs from the cut folder; `--no-partial-parse` stops it reusing a root build's seed paths.
- The second readout run puts the cross-check into `READOUT.md`. The refit takes about 25 minutes.

## Limits and next steps

- **More tests.** The 2026 market test ran ([readout](../../geotest/READOUT.md), [refit](#the-refit)). Its search arm had 35% power, so its lift test is wide. A second, larger search test, or brand-search pauses (on the dev seed 15 of them put brand search on target), would pin the level as well as the margin.
- **Seasonal brand pushes** need variation the season cannot explain. A test that holds Meta flat in a few markets through one busy season would separate the two.
- **Stage 1** sees about a third of the searches the upper funnel creates (6.3% of brand searches against 16.7%). Its carryover is linear and its season shares the confound; a saturating search response is the next thing to try on a dev seed.
- **Full-window fit:** these numbers come from the holdout fit's posterior applied to all 156 weeks. A `--holdout 0` fit uses the last 13 weeks too.
- **ROI** values every deal at its market's average won-deal revenue, so it cannot see channels that bring bigger or smaller deals.
- **Cross-check:** fit Google Meridian on the same marts and report where the two models disagree.
