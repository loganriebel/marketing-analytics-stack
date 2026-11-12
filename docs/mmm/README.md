# Step 4: the MMM

A Bayesian geo MMM for Fernhook on [PyMC-Marketing](https://www.pymc-marketing.io/), fit on the golden marts and graded against the hidden answer key.

**First fit (holdout: 143 training weeks, last 13 held out). It passes every health gate and ranks the channels well, but it under-credits paid media as a whole.**

- **Health:** max r-hat 1.0095, min bulk ESS 494, 2 divergences in 4,000 draws. 91% of holdout region-weeks fall inside the 90% interval; holdout weekly error is 6.4%.
- **Fit:** national weekly RMSE is 14.8 deals, against a pure count-noise floor of about 14.6 (the square root of 212 deals a week). Residuals show no pattern (Ljung-Box p = 0.22).
- **Ranking:** CPA rank correlation with the truth is 0.80, against 0.27 for CRM last touch and 0.82 for platform-reported. YouTube and webinars land within 10% of their true CPA.
- **Scale:** paid media drives 33% of deals in the model (90% HDI 27% to 40%) against about 54% in truth. Most channels' incremental deals come out 40% to 70% low, so the 90% HDIs cover the truth only 21 of 36 times.
- **Budget shift:** the optimizer's plan at the same total spend gains 1,230 deals in the true world (+7%). That is inside the model's 90% HDI (1,031 to 3,063) but below its mean of 2,075.
- **The lesson:** every fit statistic looks healthy while the media total is off by a third. Fit statistics check prediction, not attribution; only the answer key catches this.

## Run it

Windows, Python 3.11, from the repo root, after `python -m sim` and `dbt build` (see the root README):

```bash
py -3.11 -m venv .venv-mmm
.venv-mmm\Scripts\python -m pip install -r requirements-mmm.txt
.venv-mmm\Scripts\python -m mmm
.venv-mmm\Scripts\python -m mmm.grade
.venv-mmm\Scripts\python -m pytest tests/test_mmm_smoke.py tests/test_mmm_no_truth_leak.py -q
```

- `python -m mmm` fits with the last 13 weeks held out, checks the health gates, and writes `mmm/outputs/` only if every gate passes. `--holdout 0` fits the full window.
- `python -m mmm --report-only` re-scores the saved posterior in `mmm/fits/` (gitignored): diagnostics, fit statistics and outputs, with no new sampling.
- The MMM has its own environment, so PyMC never moves the pinned warehouse stack. The `nutpie` sampler compiles through numba, so Windows needs no C compiler.
- The smoke test fits 2 regions for 80 weeks in about a minute. It skips in the main `.venv`, which has no PyMC.

## Data

The model reads three marts and nothing else. It never touches `data/raw/` or `sim/`, and a test enforces that.

| Piece | Source | Notes |
|---|---|---|
| KPI | `fct_funnel.won_deals`, summed over lead sources | Week x region, counted in the close week. |
| Media | `fct_channel_weekly.spend`, 9 paid channels | CTV is zero in 12 of 20 regions. |
| Controls | `fct_controls_weekly` | Headcount, email, promo, price, fleet activity index. |
| Region size | `fct_controls_weekly.target_accounts` | Size index = accounts / regional mean. |

**Affiliate spend is placement fees only.** The mart's affiliate spend equals the partner platform's `partner_fees` column through staging, staging never reads commissions, and week-to-week changes in affiliate spend do not move with affiliate-sourced wins (correlation -0.02). Commissions follow deals, so they would show up there.

## Model

PyMC-Marketing's multidimensional `MMM` with `dims=("geo",)`: 20 regions x 143 training weeks, 13 weeks held out. It is one joint model: every region shares the channel parameters. The 4 chains are four independent samplers of that one model, not four models.

### The equation

For region $g$ and week $t$, with $s_g$ the region size index (target accounts over the regional mean):

```math
y_{g,t} = \frac{\text{deals}_{g,t}}{s_g\,Y},
\qquad
x_{g,t,c} = \frac{\text{spend}_{g,t,c}}{s_g\,X_c}
```

$Y$ is the largest training value of deals per size unit, and $X_c$ the largest training value of channel $c$'s spend per size unit (both national).

```math
y_{g,t} \sim \mathcal{N}\!\left(\mu_{g,t},\ \sigma_g\right)
```

```math
\mu_{g,t} = \underbrace{b_g}_{\text{intercept}}
 + \sum_{c=1}^{9} \beta_c\,\frac{a_{g,t,c}^{\,s_c}}{a_{g,t,c}^{\,s_c} + \kappa_c^{\,s_c}}
 + \sum_{j} \gamma_j\, z_{j,g,t}
 + \sum_{m=1}^{2} \Big[\lambda_m \sin\!\big(\tfrac{2\pi m\,d_t}{365.25}\big) + \rho_m \cos\!\big(\tfrac{2\pi m\,d_t}{365.25}\big)\Big]
```

Adstock, with lead-side carryover $\alpha_c$ and the fixed lead-to-close kernel $k$:

```math
a_{g,t,c} = \sum_{l=0}^{11} w_c(l)\, x_{g,t-l,c},
\qquad
w_c(l) = \sum_{j=0}^{4} k_j\, \frac{\alpha_c^{\,l-j}}{\sum_{i=0}^{7}\alpha_c^{\,i}}\ \mathbb{1}[0 \le l-j \le 7],
\qquad
k = (0.025,\ 0.291,\ 0.409,\ 0.210,\ 0.065)
```

The weights sum to 1, so carryover moves when a dollar's effect lands, not how big it is. With $\alpha = 0.4$ a dollar's effect lands 2% in week 0, 18% in week 1, 32% in week 2, 25% in week 3, 14% in week 4 and 9% later.

The brand-search lift test adds one more likelihood term. With $H_b$ the brand Hill curve above and the pooled pause test $(x, \Delta x, \Delta y, \sigma_\ell)$ in the same scaled units:

```math
|\Delta y| \sim \mathcal{N}\!\left(\big|\beta_b\,[H_b(x + \Delta x) - H_b(x)]\big|,\ \sigma_\ell\right)
```

| Symbol | Meaning | Count |
|---|---|---|
| $b_g$, $\sigma_g$ | Region intercept and noise | 20 each |
| $\beta_c$ | Channel's maximum weekly effect (per size unit) | 9 |
| $\kappa_c$ | Adstocked spend at half of $\beta_c$ | 9 |
| $s_c$ | Curve shape: below 1 bends at once, above 1 is S-shaped | 9 |
| $\alpha_c$ | Weekly carryover of the lead-side effect | 9 |
| $\gamma_j$ | Control effects, shared by regions ($z$ = the 11 controls below) | 11 |
| $\lambda_m$, $\rho_m$ | Yearly seasonality, $d_t$ = day of year | 4 |

That is 91 parameters for 2,860 region-weeks. The full posterior summary for every one of them is in `mmm/outputs/parameters_<fit>.csv`.

**Population scaling.** Deals and spend are divided by each region's size index before the model sees them, the way Meridian scales by population. One set of channel parameters then serves every region: a region twice the size needs twice the spend to sit at the same point on the curve, and gets twice the deals from it. Channel and target scaling (max) are then national.

**Adstock = lead-side carryover, then the close delay.** Won deals land one to four weeks after the lead. Geometric adstock puts its biggest weight on week zero, so it would put the response too early. The model uses a custom `LaggedGeometricAdstock`: a normalized geometric kernel (8 weeks, one `alpha` per channel) convolved with a fixed lead-to-close kernel. The fixed kernel comes from the README's sales-cycle facts (a gamma lag with 5th and 95th percentiles at 6 and 27 days, lead created on a random weekday): weeks 0 to 4 get 2.5%, 29.1%, 40.9%, 21.0% and 6.5%. Total memory is 12 weeks. It costs no extra parameters, unlike delayed adstock's `theta`.

**Hill saturation, made safe at zero.** Hill can be concave or S-shaped, so the data decide whether the next dollar is worth more or less than the average one. A logistic curve would force marginal CPA above average CPA everywhere, which pre-decides question 3. The stock `HillSaturation` has a NaN gradient for its slope at exactly zero input (`d(x^s)/ds = x^s log x`), and CTV is zero in 12 regions: every draw diverged until the input was floored at 1e-12 (`ZeroSafeHillSaturation`).

**Priors.**

| Parameter | Prior | Why |
|---|---|---|
| `alpha` (carryover) | Beta(2, 3) | Mean 0.4 per week, wide. |
| Hill `slope` | LogNormal(log 1.2, 0.4) | 90% between 0.6 and 2.3: concave or mildly S-shaped. |
| Hill `kappa` | LogNormal at the channel's median on-week level, sd 0.7 | Half-saturation near where the channel actually runs; the data move it. |
| Hill `beta` | HalfNormal, scale from spend share | Prior median gives each channel its spend share of 40% of deals, so the default is equal ROI. Mass near zero lets a dud stay a dud. |
| Brand search `beta` | Same, at half scale | Skeptical: its spend follows demand (below). |
| Intercept, noise | Per region | Area differences in baseline leads and in count noise. |
| Controls, Fourier | Pooled across regions | In per-size units the effects are shared. |

**Controls.** Everything that acts on leads shows up in won deals after the lead-to-close delay, so each control gets the same fixed kernel: SDR and AE coverage (headcount per 1k accounts), email sends per size unit, log fleet activity index, the year-end promo flag, and the July 2024 price increase. A linear trend, 2 Fourier modes for yearly seasonality, and dummies for close weeks 52, 1, 2 and 3 (national won deals dip 10 to 23% in those weeks, holiday leads closing late) complete the baseline.

## Brand search: spend that follows demand

Brand search spend is set by how many people search "Fernhook", so it rises with the baseline. The likelihood cannot tell cause from echo and hands brand search the credit for demand. Two things push back:

1. **A skeptical prior** (half the spend-share scale), in line with published brand-keyword holdouts that find most brand clicks would have come anyway.
2. **The regional pauses as a lift test.** A pause is the one time brand spend drops while demand does not. Each pause is read as a small geo experiment (`mmm/lift_tests.py`):
   - effect window: the paused weeks plus 8 weeks of carryover and close delay, so the whole deal deficit counts;
   - counterfactual: the region's share of the other regions' deals in the 12 weeks before (after, for the pause at the very start);
   - lift per paused week = total deficit / paused weeks. With normalized adstock that is the steady-state weekly contribution of the pre-pause spend, which is what `add_lift_test_measurements` compares with `saturation(x) - saturation(x + delta_x)`;
   - sigma: the same estimator on placebo windows in the same region while brand ran.

Pauses used by the holdout fit (deals and spend per region, not yet per size unit):

| Region | Start | Paused weeks | Pre-pause spend / week | Lift per paused week (deals) | Placebo sigma | Reference |
|---|---|---:|---:|---:|---:|---|
| EU_NOR | 2023-05-01 | 5 | $1,023 | -0.62 | 2.72 | before |
| US_FL | 2023-10-16 | 5 | $2,341 | -1.96 | 5.21 | before |
| US_GL | 2023-01-02 | 3 | $4,301 | -15.74 | 6.80 | after |
| US_CA | 2024-06-10 | 7 | $5,013 | +2.82 | 5.08 | before |
| US_PL | 2025-03-17 | 6 | $1,322 | +2.36 | 2.09 | before |

**Pooled, per size unit:** pre-pause spend $2,491 a week, lift -0.23 deals a week, sigma 1.72. US_MW (September 2025) falls in the holdout and joins the full-window fit. EU_UKI (November 2025) ends too close to the window's end to measure.

**What it bought.** Five short pauses can bound brand search but not pin it: the 90% interval on the pooled lift is about ±2.8 deals a week per size unit. Brand search was not over-credited in the end. It came in low (480 incremental deals against 1,270 true) like most channels, and its wide HDI (1 to 1,372) covers the truth.

**Why pooled.** PyMC-Marketing's lift likelihood compares absolute values: `dist(abs(model_lift), sigma, observed=abs(delta_y))`. A single noisy pause that shows deals going up would be read as a drop of the same size, which biases the curve upward. Pooling in per-size units gives one test whose sign is stable. If the pooled test ever shows deals rising, it is entered as a zero drop, the closest a monotone curve can get.

## Health gates

No number is reported unless all of these pass (`mmm/config.py`):

| Gate | Threshold | First fit | Pass |
|---|---|---|---|
| r-hat, every parameter | below 1.01 | 1.0095 (US_MA intercept) | yes |
| Bulk ESS, every parameter | at least 400 | 494 (US_SE intercept) | yes |
| Tail ESS, every parameter | at least 400 | 691 | yes |
| Divergences | at most 0.1% of draws | 2 of 4,000 (0.05%) | yes |
| Posterior predictive: region-weeks inside the 90% interval | 85% to 97% | 90.6% | yes |
| Holdout: national weekly MAPE | at most 10% | 6.4% | yes |
| Holdout: region-weeks inside the 90% interval | 80% to 98% | 91.2% | yes |

The gates read `az.rhat` and `az.ess` directly. The first run gated on `az.summary`, which rounds r-hat to two decimals, so 1.0095 printed as 1.01 and failed. The threshold did not change. The r-hat pass is narrow, and the slowest parameters are the regional intercepts, not the media effects.

## Fit statistics

Reported for every fit in `diagnostics_<fit>.json` (`mmm/validation.py`). They describe the fit; they are not gates, because the gates were fixed before the first fit.

- **Error on deals:** MSE, RMSE, MAE, MAPE, R² and bias, on region-weeks and on national weeks, for the training weeks (posterior mean of $\mu$) and the 13 holdout weeks (posterior predictive mean).
- **PSIS-LOO:** expected log predictive density for leaving out one region-week, with its standard error, effective parameter count `p_loo`, and the share of Pareto k above 0.7 (points LOO cannot trust). Built from the posterior's own components, so it needs no extra sampling. It compares fits on the same data, such as a brand-prior sensitivity run.
- **Residual checks:** lag-1 autocorrelation, Durbin-Watson and Ljung-Box (lag 4) on national weekly residuals, and the same per region. Patterned residuals mean a missing driver and HDIs that are too narrow.
- **Residual vs spend:** correlation of residuals with each channel's spend. A channel whose spend still lines up with the misses is one the model has not explained; for brand search that is the demand echo.
- **Parameter table:** `parameters_<fit>.csv` lists every parameter with mean, sd, 90% HDI, share of draws above zero, r-hat and ESS.

There is no ANOVA table. F-tests split variance for least squares with fixed effects; here each effect has a full posterior, so the 90% HDI and the share of draws above zero answer the same question, and the contributions show how much of the deals each piece explains.

First fit, in deals:

| | Train region-week | Train national week | Holdout region-week | Holdout national week |
|---|---:|---:|---:|---:|
| Rows | 2,860 | 143 | 260 | 13 |
| Mean observed | 10.6 | 212.5 | 10.3 | 205.9 |
| MSE | 10.7 | 218.9 | 9.9 | 243.4 |
| RMSE | 3.28 | 14.8 | 3.14 | 15.6 |
| MAE | 2.51 | 11.3 | 2.41 | 12.7 |
| MAPE | 35% | 5.4% | 43% | 6.4% |
| R² | 0.76 | 0.68 | 0.78 | 0.55 |
| Bias (predicted - observed) | 0.00 | -0.06 | +0.33 | +6.7 |

- **The misses are count noise.** Deals are counts, so a region-week averaging 10.6 deals has a noise floor of about 3.26 (its square root), and a national week of 212 about 14.6. RMSE sits on both floors. Region-week MAPE is high only because small regions close 3 deals a week.
- **PSIS-LOO:** elpd 1,693 (se 40), p_loo 67 against 91 parameters, every Pareto k below 0.7 (max 0.41).
- **Residuals:** national lag-1 autocorrelation 0.12, Durbin-Watson 1.67, Ljung-Box p = 0.22. By region: median lag-1 -0.02, median Durbin-Watson 2.03, and 2 of 20 regions with Ljung-Box p below 0.05 (1 expected by chance).
- **Residual vs spend:** every channel's correlation is within ±0.02.
- **Controls:** SDR coverage, AE coverage and the promo carry clear positive effects, and the price increase a negative one. Email, the fleet activity index and trend sit near zero.

## Outputs

`mmm/outputs/` is what step 5's memo grounding check reads. Every estimate has a posterior mean, median and 90% HDI, from 2,000 posterior draws.

| File | What |
|---|---|
| `channels.json`, `channels.csv` | Per channel: spend, incremental deals, CPA, marginal CPA, ROI; plus paid-media totals. |
| `response_curves.csv` | Incremental deals at spend multipliers 0 to 3 of the actual path. |
| `contributions_weekly.csv` | National weekly incremental deals by channel. |
| `optimizer.json` | Reallocation at the same total spend, with the deal change and its HDI. |
| `baselines.json` | CRM last-touch and platform-reported deals and CPA, from the marts. |
| `diagnostics_<fit>.json` | Gates, sampler diagnostics, PPC and holdout checks, fit statistics, lift tests, affiliate check. |
| `parameters_<fit>.csv` | Posterior summary of all 91 parameters. |

Estimand definitions match the scenario's:

- **Incremental deals:** expected deals caused by the channel's in-window spend, counting deals that close after the window (the adstock runs 12 weeks past the last week with zero spend).
- **CPA:** in-window spend / incremental deals.
- **Marginal CPA:** extra spend per extra deal when the whole in-window path is scaled by 1% (central difference, 0.99 to 1.01).
- **ROI:** incremental first-year revenue / spend, valuing each deal at its region's average won-deal revenue. A deals KPI cannot see deal-size differences between channels.
- **Response curve:** incremental deals when the in-window path is scaled by a multiplier, other channels unchanged.

These come from a numpy copy of the media path (`mmm/estimands.py`), so any spend path can be scored per draw. The smoke test checks it against PyMC-Marketing's own `channel_contribution` to 1e-8.

**Optimizer** (`mmm/optimize.py`): one multiplier per channel on its actual weekly path, bounded to 0.5 to 1.5, same total spend, maximizing posterior-mean deals. Channels add up independently in the model, so the objective is a sum of splined per-channel curves. The chosen plan is then scored on every draw.

## Grading

`mmm/grade.py` is the only module that reads `sim/truth/truth.json`. It writes to `mmm/grading/`, never to `mmm/outputs/`, so the memo step never sees the answer key. It scores:

- 90% HDI coverage and percent error (posterior median) per channel for incremental deals, CPA, marginal CPA and ROI;
- CPA rank agreement (Spearman), and whether the best and worst marginal-CPA channels are right;
- the same for CRM last touch and platform-reported (deals = platform conversions x the company lead-to-won rate), which rank the next dollar by average CPA because they have no marginal view;
- the optimizer's plan run through the true, noise-free response curves (PCHIP through the answer key's 9 points per channel): model-predicted vs true gain.

The model was specified before the first grade and was not tuned to it.

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

**Reading it.**

- **Order, yes; scale, no.** The model ranks CPA about as well as platform-reported numbers and far better than last touch, but its total paid-media deals are 38% low. Because the scale is off, its median CPA error (88%) is worse than platform-reported (34%), whose over-claiming happens to land closer once converted to deals.
- **Where it is right:** YouTube (CPA 9% off) and webinars (8% off). The optimizer's plan gains true deals overall, and every channel it moves up gains true deals. Two of its cuts are mistakes: CTV and LinkedIn have better true marginal CPAs than non-brand search, which gets the money.
- **Where it is wrong:** most channels lose credit to the baseline (non-brand search -41%, Meta -47%, CTV -48%, affiliates -68%, LinkedIn -71% in incremental deals). Display is the one channel strongly over-credited (445 deals against 121).
- **Best and worst picks miss by one place.** It picks webinars as the best marginal dollar (true best: YouTube, which it ranks second) and brand search as the worst (true worst: display, which it ranks second worst).
- **HDIs are too narrow for the bias.** 58% coverage against a nominal 90% means the error is structural, not sampling noise.

## Limits and next steps

- **Paid media is under-credited by about a third.** The likely causes, none tested yet: the spend-share prior centered at 40% of deals with HalfNormal shrinkage, per-region intercepts plus trend soaking up always-on spend that moves in yearly steps, and an additive model fit to a world where media leads convert at the same time-varying rates as baseline leads.
- **Any fix from here is post-hoc.** The grade has been seen. The clean way is to change the model on a different simulator seed (each seed draws new true parameters), then grade once more on this seed.
- **Full-window fit.** These numbers come from the holdout fit's posterior applied to all 156 weeks. A `--holdout 0` fit (about an hour) uses the last 13 weeks too.
- **Optimizer:** SLSQP reports no convergence. Seven of nine channels sit at the 0.5 or 1.5 bound and the budget holds exactly, but the interior channels' marginal returns have not been checked for equality.
- **ROI** values every deal at its region's average won-deal revenue, so it cannot see channels that bring bigger or smaller deals.
- **Brand search** rests on a skeptical prior plus five noisy pauses. A prior sensitivity run (full scale vs half scale), compared by LOO and by the grade, would show how much the prior decides.
- **Cross-check:** fit Google Meridian on the same marts and report where the two models disagree.
