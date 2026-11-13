# Step 4: the MMM

A Bayesian geo MMM for Fernhook on [PyMC-Marketing](https://www.pymc-marketing.io/), fit on the golden marts, with brand search modeled as a mediator of the upper funnel, and graded once against the hidden answer key.

**Final fit (the rebuilt world: budgets drift from brand to non-brand search, last 13 weeks held out): it passes every health gate, predicts well, ranks channels better than before, and still gives paid media 28% too little credit. It reads non-brand search's average cost per deal almost exactly, but thinks its next dollar is cheaper than it is.**

- **Health:** max r-hat 1.003, min bulk ESS 1,704, 2 divergences in 8,000 draws. The brand-search stage passes its own gates.
- **Prediction:** holdout weekly error 5.6%, 90% of holdout market-weeks inside the 90% interval. Residuals show no pattern.
- **Scale:** paid media drives 11,060 deals in the model (90% HDI 8,515 to 13,937) against 15,389 in truth. The 90% HDIs cover the truth 27 of 32 times.
- **Ranking:** CPA rank correlation with the truth is 0.48. Platform-reported numbers rank better (0.79); CRM last touch worse (0.10).
- **What it gets right:** YouTube as the best next dollar and display as the worst; non-brand search's average cost per deal (7% off); YouTube and CTV within 20%.
- **What it misses:** non-brand search's next dollar costs $11,116 in truth and $6,835 in the model, so the model understates how saturated search is. Meta comes out 77% low and affiliates 70% low.
- **The budget shift:** at the same spend the plan gains 1,045 true deals, above the model's 90% HDI (363 to 932).
- **The lesson:** the rebuilt world makes non-brand search grow fast, so its spend ramp lines up with time. The model separates them well enough on average cost, not on the margin. Only a test that moves search can show what the extra dollars buy.

## Run it

Windows, Python 3.11, from the repo root, after `python -m sim` and `dbt build` (see the root README):

```bash
py -3.11 -m venv .venv-mmm
.venv-mmm\Scripts\python -m pip install -r requirements-mmm.txt
.venv-mmm\Scripts\python -m mmm
.venv-mmm\Scripts\python -m mmm.grade
.venv-mmm\Scripts\python -m pytest tests/test_mmm_smoke.py tests/test_mmm_no_truth_leak.py -q
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

**Lift tests.** `mmm/lift_tests.py` turns any channel's planned regional pauses into a pooled lift test through `add_lift_test_measurements`: the deal deficit over the pause plus carryover, against the market's share of the other markets, with placebo windows for sigma. PyMC-Marketing compares absolute lifts, so pauses are pooled per channel, and a pooled test with the wrong sign enters as a zero drop. The current world has no pauses, so no lift test enters the fit.

## Health gates

No number is reported unless every gate passes (`mmm/config.py`). The gates read `az.rhat` and `az.ess` directly; `az.summary` rounds r-hat to two decimals, which once turned 1.0095 into a failing 1.01.

| Gate | Threshold | Final fit | Pass |
|---|---|---|---|
| r-hat, every sampled parameter | below 1.01 | 1.003 (display $\beta$) | yes |
| Bulk ESS | at least 400 | 1,704 (brand search $\beta$) | yes |
| Tail ESS | at least 400 | 1,053 | yes |
| Divergences | at most 0.1% | 2 of 8,000 | yes |
| Posterior predictive: market-weeks inside the 90% interval | 85% to 97% | 91.5% | yes |
| Holdout: national weekly MAPE | at most 10% | 5.6% | yes |
| Holdout: market-weeks inside the 90% interval | 80% to 98% | 90.4% | yes |
| Stage 1: r-hat, bulk ESS, divergences | same | 1.003, 8,283, 0 | yes |

## Fit statistics

Reported in `diagnostics_<fit>.json` (`mmm/validation.py`). They describe the fit; they are not gates.

| | Train market-week | Train national week | Holdout market-week | Holdout national week |
|---|---:|---:|---:|---:|
| Rows | 2,860 | 143 | 260 | 13 |
| Mean observed | 9.9 | 199.0 | 10.7 | 214.3 |
| MSE | 10.3 | 197.7 | 9.2 | 311.7 |
| RMSE | 3.21 | 14.1 | 3.03 | 17.7 |
| MAE | 2.40 | 11.0 | 2.35 | 12.4 |
| MAPE | 41% | 5.7% | 36% | 5.6% |
| R² | 0.87 | 0.76 | 0.89 | -0.37 |
| Bias (predicted - observed) | 0.00 | -0.09 | -0.43 | -8.7 |

- **The misses are count noise.** A market-week averaging 9.9 deals has a noise floor of about 3.1 (its square root), and RMSE sits on it. Market-week MAPE is high only because small markets close a few deals a week. The holdout's national R² is negative because 13 weeks barely vary; its MAPE is 5.6%.
- **PSIS-LOO:** elpd 2,239 (se 46), p_loo 78 against 96 parameters; 1 of 2,860 Pareto k above 0.7 (max 0.71).
- **Residuals:** national lag-1 autocorrelation -0.03, Durbin-Watson 2.03, Ljung-Box p = 0.25. By market: median lag-1 0.02, median Durbin-Watson 1.94, no market with Ljung-Box p below 0.05.
- **Residual vs spend:** every channel's correlation is within ±0.03.
- **Stage 1:** R² 0.66 in training and 0.69 in the holdout, holdout national weekly MAPE 4.3%.

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

**Optimizer** (`mmm/optimize.py`): one multiplier per channel on its actual weekly path, bounded to 0.5 to 1.5, same total spend, maximizing posterior-mean deals. Brand search is not a lever: it is always on and its spend follows searches. Upper-funnel curves include their deals via brand search, and the plan reports the brand-search spend those searches add (about $189,000 for the final plan). SLSQP stops with "positive directional derivative" with most channels at a bound; the budget holds exactly.

## Grading

`mmm/grade.py` is the only module that reads an answer key. It writes to `mmm/grading/`, never to `mmm/outputs/`. It scores 90% HDI coverage and percent error (posterior median) per channel, CPA rank agreement, the best and worst marginal-CPA picks, the same for CRM last touch and platform-reported (which rank the next dollar by average CPA), the mediation estimands, and the optimizer's plan run through the true, noise-free response curves (total curves for upper-funnel moves).

Webinars are a control in the MMM, so the 8 media channels are graded. 90% HDI coverage: 27 of 32 (84%). Point estimates are posterior medians. Full table: [`mmm/grading/grade_holdout.md`](../../mmm/grading/grade_holdout.md).

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals |
|---|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 6,123 | 12,557 (1,366 to 85,642) | 105% | 37,735 | 27,198 (3,306 to 192,726) | 1,212 | 591 |
| paid_search_nonbrand | 3,068 | 3,293 (1,860 to 5,409) | 7% | 11,116 | 6,835 (4,094 to 11,336) | 5,551 | 5,171 |
| meta | 1,482 | 6,522 (1,091 to 26,506) | 340% | 1,834 | 7,099 (1,863 to 31,721) (miss) | 2,969 | 675 (miss) |
| linkedin | 2,550 | 4,600 (798 to 26,806) | 80% | 3,294 | 8,093 (1,802 to 47,872) | 1,004 | 556 |
| youtube | 1,542 | 1,829 (1,182 to 2,573) | 19% | 1,637 | 2,265 (1,580 to 3,093) | 1,815 | 1,531 |
| ctv | 2,516 | 2,979 (2,235 to 3,841) | 18% | 3,096 | 3,850 (2,949 to 4,897) | 1,153 | 973 |
| display | 42,123 | 11,515 (1,232 to 77,976) | -73% | 113,255 | 27,517 (3,359 to 182,094) | 103 | 378 |
| affiliates | 1,232 | 4,161 (565 to 22,418) | 238% | 1,982 | 10,134 (1,639 to 53,687) | 1,583 | 469 (miss) |

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.48 | 77% | youtube | yes | display | yes |
| CRM last touch | 0.10 | 80% | paid_search_brand | no | ctv | no |
| Platform reported | 0.79 | 41% | meta | no | paid_search_nonbrand | no |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 15,389 | 11,060 (8,515 to 13,937) | no |
| incremental_cpa_paid_media | 2,821 | 3,925 (2,987 to 4,916) | no |

Upper funnel through brand search: 90% HDI coverage 10 of 12. The upper funnel's share of brand-search deals comes out 2.8% against 2.8% true; stage 1 sees it creating 5.9% of brand searches against 16.7% true.

Optimizer plan at the same total spend: the model predicts 654 deals (363 to 932); the true world gives 1,045, above the HDI.

**Reading it.**

- **Prediction is not attribution.** Every fit statistic is healthy while paid media is 28% low.
- **Average is not margin.** Non-brand search's average cost per deal is 7% off, but its next dollar costs $11,116 in truth against $6,835 in the model. The search ramp lines up with time, so the model cannot tell how fast search saturated. The memo's market test pulls search back to its 2023 pace for exactly this reason.
- **Flighted channels are measured; always-on channels are not.** YouTube and CTV land within 20%. Meta pushes into the busy seasons and the season curve absorbs most of it (77% low). Affiliates come out 70% low.
- **The budget move still works, and better than modeled.** Growing YouTube and CTV and cutting display gains 1,045 true deals against the model's 654.

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
| Rebuilt: budgets drift to search, seed 2026 | refit | Same model; LinkedIn's role prior is now brand | 11,060 vs 15,389 (-28%) | graded |

**Disclosures.** The first seed-2026 grade (old world) was seen before the dev-seed work began, and it suggested the curve-shape hypothesis. While checking the new answer key's field names, some seed-2026 true values were printed: Meta's, YouTube's and CTV's direct and via-brand-search deals, and the paid-media summary. No model change followed. The only change after that was more draws, made because the final fit failed the tail ESS gate.

**Rebuild (step 6).** At Logan's direction the 2023 to 2025 world was rebuilt so budgets drift from brand to non-brand search (60/40 to 80/20) and search saturates. The same model was refit once on the new seed-2026 world; no model change was made. `python -m sim` prints each channel's true average CPA when it writes the world, so those 9 numbers were seen when the world was generated; the test design and memo use none of them.

The scenario changed twice during step 4, at Logan's direction: the business now sells only in seven Midwest states, and paid search is always on with the upper funnel creating brand searches. The original plan to turn brand-search pauses into lift tests still exists in code, but the current world has no pauses.

## Limits and next steps

- **Run the experiment.** On the dev seed, 15 planned brand-search pauses put brand search on target; without them it came out 54% low. The 2026 market test ([`geotest/PREREGISTRATION.md`](../../geotest/PREREGISTRATION.md)) pulls non-brand search back to its 2023 pace in 10 markets and pushes YouTube in a crossing 10, and both results enter the refit as lift tests.
- **Seasonal brand pushes** need variation the season cannot explain. A test that holds Meta flat in a few markets through one busy season would separate the two.
- **Stage 1** sees about a third of the searches the upper funnel creates (5.9% of brand searches against 16.7%). Its carryover is linear and its season shares the confound; a saturating search response is the next thing to try on a dev seed.
- **Full-window fit:** these numbers come from the holdout fit's posterior applied to all 156 weeks. A `--holdout 0` fit uses the last 13 weeks too.
- **ROI** values every deal at its market's average won-deal revenue, so it cannot see channels that bring bigger or smaller deals.
- **Cross-check:** fit Google Meridian on the same marts and report where the two models disagree.
