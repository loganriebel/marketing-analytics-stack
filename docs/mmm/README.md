# Step 4: the MMM

A Bayesian geo MMM for Fernhook on [PyMC-Marketing](https://www.pymc-marketing.io/), fit on the golden marts, with brand search modeled as a mediator of the upper funnel, and graded once against the hidden answer key.

**Final fit (Midwest world, paid search always on, last 13 weeks held out): it passes every health gate, predicts well, and still gives paid media 41% too little credit. With no experiments, the data cannot show what always-on channels add.**

- **Health:** max r-hat 1.004, min bulk ESS 1,005, 1 divergence in 8,000 draws. The brand-search stage passes its own gates.
- **Prediction:** holdout weekly error 5.6%, 90% of holdout market-weeks inside the 90% interval. Residuals show no pattern.
- **Scale:** paid media drives 9,579 deals in the model (90% HDI 7,185 to 12,204) against 16,145 in truth. The 90% HDIs cover the truth 21 of 32 times.
- **Ranking:** CPA rank correlation with the truth is 0.00. Platform-reported numbers rank better (0.81).
- **What it gets right:** CTV (CPA 6% off), YouTube as the best next dollar, and the budget shift: at the same spend the plan gains 582 true deals, inside the model's 90% HDI (30 to 1,001).
- **Brand search as a mediator:** the upper funnel's share of brand-search deals comes out 2.9% against 2.8% true. CTV's deals through brand search land within 4%. Stage 1 sees the upper funnel creating 6.7% of brand searches against 16.7% true.
- **The lesson:** on the dev seed, brand search landed on target (0% off) while 15 planned pauses gave it a lift test, and came out 54% low once search went always on. Without tests, every always-on channel's level rests on the prior. Fit statistics cannot catch that; only a test can.

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

**Curve shape by role.** Performance channels harvest intent that already exists, so their first dollar is their best: slope prior median 0.9 (90% 0.55 to 1.47). Brand channels can need a threshold of reach: median 1.5 (0.84 to 2.66).

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

**Controls.** Everything that acts on leads shows up in won deals after the lead-to-close delay, so these get the same fixed kernel: SDR and AE coverage (headcount per 1k accounts), email sends, log fleet activity index, the year-end promo, the July 2024 price increase and webinar cost. A linear trend, close-week dummies for weeks 52, 1, 2 and 3, and the latitude terms complete the baseline. On the graded seed, SDR and AE coverage, the promo and webinars carry clear positive effects and the price increase a negative one; email, the fleet index and trend sit near zero.

**Lift tests.** `mmm/lift_tests.py` turns any channel's planned regional pauses into a pooled lift test through `add_lift_test_measurements`: the deal deficit over the pause plus carryover, against the market's share of the other markets, with placebo windows for sigma. PyMC-Marketing compares absolute lifts, so pauses are pooled per channel, and a pooled test with the wrong sign enters as a zero drop. The current world has no pauses, so no lift test enters the fit.

## Health gates

No number is reported unless every gate passes (`mmm/config.py`). The gates read `az.rhat` and `az.ess` directly; `az.summary` rounds r-hat to two decimals, which once turned 1.0095 into a failing 1.01.

| Gate | Threshold | Final fit | Pass |
|---|---|---|---|
| r-hat, every sampled parameter | below 1.01 | 1.004 (display $\beta$) | yes |
| Bulk ESS | at least 400 | 1,005 (display $\beta$) | yes |
| Tail ESS | at least 400 | 586 | yes |
| Divergences | at most 0.1% | 1 of 8,000 | yes |
| Posterior predictive: market-weeks inside the 90% interval | 85% to 97% | 91.4% | yes |
| Holdout: national weekly MAPE | at most 10% | 5.6% | yes |
| Holdout: market-weeks inside the 90% interval | 80% to 98% | 89.6% | yes |
| Stage 1: r-hat, bulk ESS, divergences | same | 1.005, 652, 0 | yes |

At 1,000 draws per chain the final fit's tail ESS was 292 and 304 on brand search's and display's $\beta$, the two channels the data barely see. It now runs 2,000 draws per chain: same model, same seed.

## Fit statistics

Reported in `diagnostics_<fit>.json` (`mmm/validation.py`). They describe the fit; they are not gates.

| | Train market-week | Train national week | Holdout market-week | Holdout national week |
|---|---:|---:|---:|---:|
| Rows | 2,860 | 143 | 260 | 13 |
| Mean observed | 10.3 | 205.7 | 10.4 | 208.8 |
| MSE | 10.4 | 173.3 | 10.6 | 247.3 |
| RMSE | 3.23 | 13.2 | 3.26 | 15.7 |
| MAE | 2.44 | 10.7 | 2.49 | 12.2 |
| MAPE | 39% | 5.4% | 42% | 5.6% |
| R² | 0.85 | 0.77 | 0.85 | -0.09 |
| Bias (predicted - observed) | 0.00 | -0.07 | -0.42 | -8.4 |

- **The misses are count noise.** A market-week averaging 10.3 deals has a noise floor of about 3.2 (its square root), and RMSE sits on it. Market-week MAPE is high only because small markets close a few deals a week. The holdout's national R² is negative because 13 weeks barely vary; its MAPE is 5.6%.
- **PSIS-LOO:** elpd 2,392 (se 44), p_loo 73 against 96 parameters, every Pareto k below 0.7 (max 0.37).
- **Residuals:** national lag-1 autocorrelation 0.06, Durbin-Watson 1.81, Ljung-Box p = 0.61. By market: median lag-1 0.02, median Durbin-Watson 1.94, no market with Ljung-Box p below 0.05.
- **Residual vs spend:** every channel's correlation is within ±0.04.
- **Stage 1:** R² 0.61 in training and 0.63 in the holdout, holdout national weekly MAPE 5.0%.

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

**Optimizer** (`mmm/optimize.py`): one multiplier per channel on its actual weekly path, bounded to 0.5 to 1.5, same total spend, maximizing posterior-mean deals. Brand search is not a lever: it is always on and its spend follows searches. Upper-funnel curves include their deals via brand search, and the plan reports the brand-search spend those searches add (about $208,000 for the final plan). SLSQP stops with "positive directional derivative" with most channels at a bound; the budget holds exactly.

## Grading

`mmm/grade.py` is the only module that reads an answer key. It writes to `mmm/grading/`, never to `mmm/outputs/`. It scores 90% HDI coverage and percent error (posterior median) per channel, CPA rank agreement, the best and worst marginal-CPA picks, the same for CRM last touch and platform-reported (which rank the next dollar by average CPA), the mediation estimands, and the optimizer's plan run through the true, noise-free response curves (total curves for upper-funnel moves).

Webinars are a control in the MMM, so the 8 media channels are graded.

90% HDI coverage: 21 of 32 (66%).

Point estimates are posterior medians.

| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | True deals | MMM deals | CRM CPA | Platform CPA |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| paid_search_brand | 5,756 | 13,374 (1,623 to 78,055) | 132% | 35,584 | 28,914 (2,762 to 176,618) | 1,284 | 552 | 1,232 | 1,345 |
| paid_search_nonbrand | 2,067 | 3,736 (1,763 to 6,777) | 81% | 5,074 | 6,198 (3,455 to 11,382) | 6,482 | 3,586 (miss) | 2,461 | 1,719 |
| meta | 1,441 | 5,578 (1,064 to 25,828) | 287% | 1,725 | 6,827 (1,357 to 32,014) | 2,597 | 671 (miss) | 2,832 | 432 |
| linkedin | 2,670 | 5,576 (1,057 to 29,512) | 109% | 3,954 | 12,109 (1,869 to 65,331) | 1,440 | 690 | 3,690 | 1,977 |
| youtube | 1,516 | 2,179 (1,187 to 3,194) | 44% | 1,446 | 2,446 (1,562 to 3,482) (miss) | 1,328 | 924 | 14,918 | 802 |
| ctv | 2,578 | 2,411 (1,949 to 2,979) | -6% | 3,141 | 3,888 (2,919 to 4,982) | 1,161 | 1,241 | n/a | 1,693 |
| display | 37,654 | 5,568 (988 to 28,891) (miss) | -85% | 103,464 | 11,667 (1,731 to 73,732) (miss) | 123 | 833 | 5,138 | 2,027 |
| affiliates | 1,160 | 6,668 (887 to 36,353) | 475% | 1,875 | 16,409 (2,565 to 85,376) (miss) | 1,730 | 301 (miss) | 1,367 | 719 |

True best marginal CPA: youtube. True worst: display.

| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |
|---|---:|---:|---|---|---|---|
| MMM | 0.00 | 97% | youtube | yes | paid_search_brand | no |
| CRM last touch | 0.14 | 79% | paid_search_brand | no | ctv | no |
| Platform reported | 0.81 | 43% | meta | no | display | yes |

| Total paid media | True | MMM (90% HDI) | Covered |
|---|---:|---:|---|
| incremental_deals_paid_media | 16,145 | 9,579 (7,185 to 12,204) | no |
| incremental_cpa_paid_media | 2,479 | 4,178 (3,127 to 5,309) | no |

Upper funnel through brand search: 90% HDI coverage 9 of 12.

| Channel | Metric | True | MMM (90% HDI) | Error |
|---|---|---:|---:|---:|
| all | upper_funnel_share_of_brand_searches | 16.7% | 6.7% (5.5% to 7.8%) | -60% |
| all | upper_funnel_share_of_brand_search_deals | 2.8% | 2.9% | 2% |
| meta | incremental_deals_via_brand_search | 19 | 4 (0 to 13) (miss) | -80% |
| meta | incremental_deals_total | 2,615 | 676 (6 to 1,621) (miss) | -74% |
| meta | cpa_total | 1,430 | 5,537 (777 to 24,592) | 287% |
| meta | marginal_cpa_total | 1,715 | 6,750 (1,522 to 30,395) | 293% |
| youtube | incremental_deals_via_brand_search | 10 | 5 (0 to 15) | -55% |
| youtube | incremental_deals_total | 1,338 | 932 (502 to 1,367) | -30% |
| youtube | cpa_total | 1,505 | 2,160 (1,209 to 3,200) | 44% |
| youtube | marginal_cpa_total | 1,440 | 2,428 (1,542 to 3,441) (miss) | 69% |
| ctv | incremental_deals_via_brand_search | 8 | 7 (0 to 23) | -4% |
| ctv | incremental_deals_total | 1,168 | 1,252 (995 to 1,514) | 7% |
| ctv | cpa_total | 2,561 | 2,390 (1,946 to 2,960) | -7% |
| ctv | marginal_cpa_total | 3,130 | 3,838 (2,902 to 4,892) | 23% |

Optimizer plan at the same total spend: model predicts 499 deals (30 to 1,001); the true world gives 582 (inside the HDI).

**Reading it.**

- **Prediction is not attribution.** Every fit statistic is healthy while paid media is 41% low. A model that predicts deals well can still split them wrongly between baseline and media.
- **Flighted channels are measured; always-on channels are not.** CTV runs its own flights in 8 markets and lands within 6% of its true CPA. YouTube's on and off flights put it at the top of the next-dollar ranking. The always-on channels (search, LinkedIn, display, affiliates) never stop, so their level comes from the prior: affiliates and non-brand search come out low, display (the true dud) high.
- **Seasonal pushes hide in the season.** Meta pushes into the busy seasons in every market, and the shared season curve absorbs most of its effect (74% low).
- **The halo is real in spend and small in deals.** The upper funnel creates about a sixth of brand searches, but brand search adds few deals per dollar, so only about 3% of brand search's deals trace back to the upper funnel. The model gets that share right (2.9%), but it sees fewer created searches than there are.
- **The budget move still works.** Shifting toward YouTube, CTV and Meta and away from LinkedIn, display and affiliates gains 582 true deals (3.6% of true paid-media deals). The model's mean prediction is 499.

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
| same, seed 2026 | final | 2,000 draws per chain for tail ESS | 9,579 vs 16,145 (-41%) | graded |

**Disclosures.** The first seed-2026 grade (old world) was seen before the dev-seed work began, and it suggested the curve-shape hypothesis. While checking the new answer key's field names, some seed-2026 true values were printed: Meta's, YouTube's and CTV's direct and via-brand-search deals, and the paid-media summary. No model change followed. The only change after that was more draws, made because the final fit failed the tail ESS gate.

The scenario changed twice during this step, at Logan's direction: the business now sells only in seven Midwest states, and paid search is always on with the upper funnel creating brand searches. The original plan to turn brand-search pauses into lift tests still exists in code, but the current world has no pauses.

## Limits and next steps

- **Run one experiment.** On the dev seed, 15 planned brand-search pauses put brand search on target; without them it came out 54% low. A single planned budget test for non-brand search (a few markets at 50% to 70% of plan for 6 to 8 weeks) would give the biggest always-on channel the same anchor without pausing it.
- **Seasonal brand pushes** need variation the season cannot explain. A test that holds Meta flat in a few markets through one busy season would separate the two.
- **Stage 1** sees 40% of the searches the upper funnel creates. Its carryover is linear and its season shares the confound; a saturating search response is the next thing to try on a dev seed.
- **Full-window fit:** these numbers come from the holdout fit's posterior applied to all 156 weeks. A `--holdout 0` fit uses the last 13 weeks too.
- **ROI** values every deal at its market's average won-deal revenue, so it cannot see channels that bring bigger or smaller deals.
- **Cross-check:** fit Google Meridian on the same marts and report where the two models disagree.
