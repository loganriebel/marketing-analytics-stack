"""Stage 1 of the brand-search mediation: what drives brand-search spend.

Brand search is always on, so its spend follows how many people search "Fernhook".
Some of those searches are baseline demand, and some are created by the upper
funnel (Meta, YouTube, CTV). This model splits the two:

    brand_g,t = b_g + sum_k gamma_k z_k,g,t + sum_u theta_u * A_u,g,t + noise,  noise ~ N(0, sigma_g)

* brand and upper-funnel spend are per size unit and on the MMM's channel scale, so
  stage 1 and the MMM (stage 2) speak the same units;
* A_u is a normalized geometric carryover of channel u (searches follow exposure
  within days to weeks; no close delay, since a search is not a deal);
* z is baseline search demand on the lead side: the shared yearly season, its
  latitude shift, trend, the fleet activity index and the holiday lead weeks;
* theta_u >= 0: brand-search spend created per unit of upper-funnel carryover.

Stage 2 (the MMM) already has brand search's curve from spend to deals. A channel's
deals via brand search = the brand curve at actual brand spend minus the brand curve
with that channel's created searches taken out. Brand search's own effect stays as
wide as the data leave it: with no tests, its spend still moves with demand.
"""

from __future__ import annotations

from dataclasses import dataclass

import arviz as az
import numpy as np
import pymc as pm
import pytensor.tensor as pt

from . import config as C
from .data import Panel
from .estimands import summarize
from .model import latitude_season

UPPER = ("meta", "youtube", "ctv")
SEARCH_L_MAX = 8
SEARCH_HOLIDAY_WEEKS = {"lead_wk51": (51,), "lead_wk52": (52, 53), "lead_wk01": (1,)}


def geometric_weights(alpha: np.ndarray) -> np.ndarray:
    """(..., SEARCH_L_MAX) normalized geometric weights."""
    w = np.power(np.asarray(alpha)[..., None], np.arange(SEARCH_L_MAX))
    return w / w.sum(axis=-1, keepdims=True)


def shifted(x: np.ndarray) -> np.ndarray:
    """(L, T, G) copies of x (T, G) delayed by 0..L-1 weeks, zeros before the start."""
    out = np.zeros((SEARCH_L_MAX,) + x.shape)
    for lag in range(SEARCH_L_MAX):
        out[lag, lag:] = x[: len(x) - lag]
    return out


def covariates(panel: Panel) -> tuple[np.ndarray, list[str]]:
    """(T, G, K) lead-side search-demand drivers, standardized where continuous."""
    T, G = len(panel.weeks), len(panel.regions)
    doy = panel.weeks.dayofyear.to_numpy() / 365.25
    woy = panel.weeks.isocalendar().week.to_numpy()
    cols, names = [], []
    for k in range(1, C.FOURIER_MODES + 1):
        for f, fn in (("sin", np.sin), ("cos", np.cos)):
            cols.append(np.repeat(fn(2 * np.pi * k * doy)[:, None], G, axis=1))
            names.append(f"season_{f}{k}")
    for name, arr in latitude_season(panel).items():
        cols.append(arr)
        names.append(name)
    trend = np.arange(T) / 52.0
    cols.append(np.repeat(((trend - trend.mean()) / trend.std())[:, None], G, axis=1))
    names.append("trend")
    fleet = panel.controls_raw.pivot(index="week_start", columns="region_id", values="fleet_activity_index")
    fleet = np.log(fleet.reindex(index=panel.weeks, columns=panel.regions).to_numpy(float))
    cols.append((fleet - fleet.mean()) / fleet.std())
    names.append("fleet_activity")
    for name, weeks in SEARCH_HOLIDAY_WEEKS.items():
        cols.append(np.repeat(np.isin(woy, weeks).astype(float)[:, None], G, axis=1))
        names.append(name)
    return np.stack(cols, axis=-1), names


@dataclass
class BrandDemand:
    theta: np.ndarray       # (S, U) brand spend created per unit of upper carryover
    alpha: np.ndarray       # (S, U) search carryover
    upper: list[str]
    diagnostics: dict
    idata: object

    def draws(self, n: int, seed: int = 0) -> "BrandDemand":
        idx = np.random.default_rng(seed).choice(self.theta.shape[0], n, replace=n > self.theta.shape[0])
        return BrandDemand(self.theta[idx], self.alpha[idx], self.upper, self.diagnostics, self.idata)


def scaled(panel: Panel, channel_scale: dict[str, float], channel: str) -> np.ndarray:
    k = panel.channels.index(channel)
    return panel.spend[:, :, k] / panel.size[None, :] / channel_scale[channel]


def fit(panel: Panel, n_train: int, channel_scale: dict[str, float], sampler: dict) -> BrandDemand:
    upper = [u for u in UPPER if u in panel.channels]
    y = scaled(panel, channel_scale, C.BRAND)
    xs = np.stack([shifted(scaled(panel, channel_scale, u)) for u in upper], axis=-1)  # (L, T, G, U)
    Z, znames = covariates(panel)
    obs = y > 0  # planned pauses, if any, are not demand
    tr = np.zeros_like(obs)
    tr[:n_train] = True
    keep = obs & tr

    ybar = float(y[keep].mean())
    ybar_g = np.array([y[keep[:, g], g].mean() for g in range(y.shape[1])])
    xbar = np.array([scaled(panel, channel_scale, u)[:n_train].mean() for u in upper])
    with pm.Model(coords={"geo": panel.regions, "upper": upper, "z": znames}) as model:
        b = pm.Normal("brand_intercept", mu=ybar_g, sigma=0.5 * ybar, dims="geo")
        gamma = pm.Normal("brand_gamma", mu=0.0, sigma=0.25 * ybar, dims="z")
        theta = pm.HalfNormal("halo_theta", sigma=0.5 * ybar / xbar, dims="upper")
        alpha = pm.Beta("halo_alpha", alpha=2, beta=3, dims="upper")
        sigma = pm.HalfNormal("brand_sigma", sigma=0.5 * ybar, dims="geo")
        lags = pt.arange(SEARCH_L_MAX)
        w = alpha[None, :] ** lags[:, None]
        w = w / w.sum(axis=0, keepdims=True)                      # (L, U)
        A = (w[:, None, None, :] * xs[:, :n_train]).sum(axis=0)     # (T, G, U)
        mu = b[None, :] + (Z[:n_train] * gamma).sum(axis=-1) + (A * theta).sum(axis=-1)
        m = keep[:n_train]
        pm.Normal("brand_obs", mu=mu[m], sigma=pt.broadcast_to(sigma[None, :], mu.shape)[m],
                  observed=y[:n_train][m])
        idata = pm.sample(nuts_sampler="nutpie", progressbar=False, chains=sampler["chains"],
                          draws=sampler["draws"], tune=sampler["tune"],
                          target_accept=sampler["target_accept"], random_seed=sampler["random_seed"] + 1,
                          nuts_sampler_kwargs={"low_rank_modified_mass_matrix": True})

    post = idata.posterior
    th = post["halo_theta"].transpose("chain", "draw", "upper").values.reshape(-1, len(upper))
    al = post["halo_alpha"].transpose("chain", "draw", "upper").values.reshape(-1, len(upper))
    diag = _diagnostics(idata, y, xs, Z, obs, n_train, upper)
    return BrandDemand(th, al, upper, diag, idata)


def _diagnostics(idata, y, xs, Z, obs, n_train, upper) -> dict:
    names = ["brand_intercept", "brand_gamma", "halo_theta", "halo_alpha", "brand_sigma"]
    rhat = az.rhat(idata, var_names=names)
    ess = az.ess(idata, var_names=names, method="bulk")
    post = idata.posterior.stack(s=("chain", "draw"))
    b = post["brand_intercept"].transpose("s", "geo").values
    g = post["brand_gamma"].transpose("s", "z").values
    th = post["halo_theta"].transpose("s", "upper").values
    al = post["halo_alpha"].transpose("s", "upper").values
    w = geometric_weights(al)                                       # (S, U, L)
    A = np.einsum("sul,ltgu->stgu", w, xs)                          # (S, T, G, U)
    halo = np.einsum("stgu,su->stg", A, th)
    mu = b[:, None, :] + np.einsum("tgk,sk->stg", Z, g) + halo
    mean = mu.mean(axis=0)
    tr, ho = obs.copy(), obs.copy()
    tr[n_train:] = False
    ho[:n_train] = False
    keep = obs

    def r2(mask):
        o, p = y[mask], mean[mask]
        return float(1 - ((o - p) ** 2).sum() / ((o - o.mean()) ** 2).sum())

    nat_o, nat_p = (y * keep).sum(axis=1), (mean * keep).sum(axis=1)
    share = (halo * keep[None]).sum(axis=(1, 2)) / (mu * keep[None]).sum(axis=(1, 2))
    out = {
        "rhat_max": float(max(float(rhat[v].max()) for v in names)),
        "ess_bulk_min": float(min(float(ess[v].min()) for v in names)),
        "divergences": int(idata.sample_stats.diverging.sum()),
        "divergence_rate": float(idata.sample_stats.diverging.mean()),
        "train_r2_region_week": r2(tr),
        "holdout_r2_region_week": r2(ho) if ho.any() else None,
        "holdout_national_weekly_mape": float(np.mean(np.abs(nat_p[n_train:] - nat_o[n_train:]) / nat_o[n_train:]))
        if ho.any() else None,
        "share_of_brand_spend_from_upper_funnel": summarize(share),
        "theta": {u: summarize(th[:, i]) for i, u in enumerate(upper)},
        "search_carryover_alpha": {u: summarize(al[:, i]) for i, u in enumerate(upper)},
        "paused_region_weeks_excluded": int((~(y > 0)).sum()),
    }
    g_ = C.GATES
    out["gates"] = {
        "rhat": out["rhat_max"] < g_["rhat_max"],
        "ess_bulk": out["ess_bulk_min"] >= g_["ess_bulk_min"],
        "divergences": out["divergence_rate"] <= g_["divergence_rate_max"],
    }
    out["all_pass"] = all(out["gates"].values())
    return out


def created_brand_path(demand: BrandDemand, panel: Panel, channel_scale: dict[str, float], channel: str,
                       tail: int) -> np.ndarray:
    """(S, T + tail, G) brand spend (scaled, per size) that `channel`'s in-window spend creates."""
    i = demand.upper.index(channel)
    x = scaled(panel, channel_scale, channel)
    x = np.vstack([x, np.zeros((tail, x.shape[1]))])
    xs = shifted(x)                                                  # (L, T+tail, G)
    w = geometric_weights(demand.alpha[:, i])                        # (S, L)
    return demand.theta[:, i, None, None] * np.einsum("sl,ltg->stg", w, xs)
