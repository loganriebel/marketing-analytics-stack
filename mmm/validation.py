"""Fit statistics for the MMM beyond the health gates.

* error stats (MSE, RMSE, MAE, MAPE, R^2) on region-weeks and national weeks,
  in training and in the holdout;
* PSIS-LOO (expected log predictive density, leave one region-week out) from a
  pointwise log-likelihood built from the posterior's own components;
* residual checks: lag-1 autocorrelation, Durbin-Watson and Ljung-Box (lag 4);
* a parameter table: mean, sd, 90% HDI, share of draws above zero, r-hat, ESS.

None of these are gates. The gates in config.GATES were fixed before the first fit.
"""

from __future__ import annotations

import arviz as az
import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats

from . import config as C

LJUNG_BOX_LAGS = 4


def error_stats(observed: np.ndarray, predicted: np.ndarray) -> dict:
    o, p = np.asarray(observed, float).ravel(), np.asarray(predicted, float).ravel()
    resid = o - p
    mse = float(np.mean(resid**2))
    nz = o > 0
    return {
        "n": int(o.size),
        "mse": mse,
        "rmse": float(np.sqrt(mse)),
        "mae": float(np.mean(np.abs(resid))),
        "mape": float(np.mean(np.abs(resid[nz]) / o[nz])),
        "r2": float(1 - np.sum(resid**2) / np.sum((o - o.mean()) ** 2)),
        "mean_observed": float(o.mean()),
        "bias": float(np.mean(p - o)),
    }


def residual_checks(resid: np.ndarray) -> dict:
    """Checks on one weekly residual series."""
    r = np.asarray(resid, float) - np.mean(resid)
    n = len(r)
    denom = np.sum(r**2)
    acf = [float(np.sum(r[k:] * r[:-k]) / denom) for k in range(1, LJUNG_BOX_LAGS + 1)]
    q = float(n * (n + 2) * sum(a**2 / (n - k) for k, a in enumerate(acf, start=1)))
    return {
        "lag1_autocorrelation": acf[0],
        "durbin_watson": float(np.sum(np.diff(r) ** 2) / denom),
        "ljung_box_q": q,
        "ljung_box_lags": LJUNG_BOX_LAGS,
        "ljung_box_p": float(stats.chi2.sf(q, LJUNG_BOX_LAGS)),
    }


def _season(da) -> np.ndarray:
    """(draw, date, geo) seasonality, broadcasting when it is shared by every geo."""
    if "geo" in da.dims:
        return da.transpose("draw", "date", "geo").values
    return da.transpose("draw", "date").values[:, :, None]


def pointwise(idata, mmm, design) -> dict:
    """Pointwise log-likelihood (chain, draw, obs) and the posterior mean of mu.

    mu = intercept + channel + control + seasonality contributions, exactly as the
    model adds them, on the model's scaled target axis.
    """
    post = idata.posterior
    geos = list(post.geo.values)
    dates = post.date.values
    X, y = design.train()
    obs = (pd.DataFrame({"date": X.date.values, "geo": X.geo.values, "y": y.values})
           .pivot(index="date", columns="geo", values="y")
           .reindex(index=pd.DatetimeIndex(dates), columns=geos).to_numpy(float))
    y_scaled = obs / float(mmm.scalers._target.values)

    ll_chains, mu_sum, n = [], np.zeros_like(y_scaled), 0
    for c in post.chain.values:
        p = post.sel(chain=c)
        mu = (p["intercept_contribution"].transpose("draw", "geo").values[:, None, :]
              + p["channel_contribution"].sum("channel").transpose("draw", "date", "geo").values
              + p["control_contribution"].sum("control").transpose("draw", "date", "geo").values
              + _season(p["yearly_seasonality_contribution"]))
        sigma = p["y_sigma"].transpose("draw", "geo").values[:, None, :]
        ll = stats.norm.logpdf(y_scaled[None], loc=mu, scale=sigma)
        ll_chains.append(ll.reshape(ll.shape[0], -1))
        mu_sum += mu.sum(axis=0)
        n += mu.shape[0]
    return {"loglik": np.stack(ll_chains), "mu_mean_scaled": mu_sum / n, "geos": geos,
            "y_scaled": y_scaled}


def loo(idata, loglik: np.ndarray) -> dict:
    ll = xr.DataArray(loglik, dims=("chain", "draw", "obs"),
                      coords={"chain": idata.posterior.chain.values,
                              "draw": idata.posterior.draw.values})
    data = az.InferenceData(posterior=idata.posterior[["adstock_alpha"]],
                            log_likelihood=xr.Dataset({"y": ll}))
    res = az.loo(data, pointwise=True)
    k = np.asarray(res.pareto_k)
    return {
        "elpd_loo": float(res.elpd_loo),
        "se": float(res.se),
        "p_loo": float(res.p_loo),
        "pareto_k_over_0_7": float((k > 0.7).mean()),
        "pareto_k_max": float(k.max()),
        "n_obs": int(k.size),
        "scale": "log density on the model's scaled target axis; compare fits on the same data only",
    }


def _labels(da) -> list[str]:
    """az.summary-style labels for every element of a parameter array."""
    dims = [d for d in da.dims if d not in ("chain", "draw")]
    if not dims:
        return [da.name]
    grids = np.meshgrid(*[da[d].values for d in dims], indexing="ij")
    return [f"{da.name}[{', '.join(str(g.flat[i]) for g in grids)}]" for i in range(grids[0].size)]


def flatten(ds: xr.Dataset) -> pd.Series:
    """Per-parameter values from an arviz result, labeled like az.summary rows."""
    out = {}
    for v, da in ds.data_vars.items():
        da = da.rename(v)
        out.update(dict(zip(_labels(da), np.ravel(da.values).astype(float))))
    return pd.Series(out)


def parameter_table(idata, var_names: list[str]) -> pd.DataFrame:
    """One row per model parameter."""
    summ = az.summary(idata, var_names=var_names, hdi_prob=C.HDI_PROB, kind="all", round_to="none")
    above = {}
    for v in var_names:
        da = idata.posterior[v].rename(v)
        share = (da > 0).mean(("chain", "draw"))
        above.update(dict(zip(_labels(share), np.ravel(share.values).astype(float))))
    summ.insert(0, "parameter", summ.index)
    summ["p_above_zero"] = summ.parameter.map(above)
    return summ.reset_index(drop=True)


def training_stats(idata, mmm, design, panel) -> dict:
    pw = pointwise(idata, mmm, design)
    regions = design.regions
    order = [pw["geos"].index(r) for r in regions]
    scale = float(mmm.scalers._target.values) * design.size[None, :]
    pred = pw["mu_mean_scaled"][:, order] * scale
    obs = panel.deals[: design.n_train]
    resid = obs - pred
    region_resid = [residual_checks(resid[:, g]) for g in range(len(regions))]
    return {
        "region_week": error_stats(obs, pred),
        "national_week": error_stats(obs.sum(axis=1), pred.sum(axis=1)),
        "loo": loo(idata, pw["loglik"]),
        "residuals_national": residual_checks(resid.sum(axis=1)),
        "residuals_by_region": {
            "lag1_autocorrelation_median": float(np.median([r["lag1_autocorrelation"] for r in region_resid])),
            "durbin_watson_median": float(np.median([r["durbin_watson"] for r in region_resid])),
            "ljung_box_p_below_0_05": int(sum(r["ljung_box_p"] < 0.05 for r in region_resid)),
            "regions": len(regions),
        },
        "residual_corr_with_spend": {
            ch: float(np.corrcoef(resid.ravel(), panel.spend[: design.n_train, :, k].ravel())[0, 1])
            for k, ch in enumerate(panel.channels)
        },
    }
