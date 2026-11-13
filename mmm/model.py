"""The Fernhook geo MMM on PyMC-Marketing.

Design (reasons in docs/mmm/README.md):

* Population scaling, as in Meridian: deals and spend are divided by each region's
  size index (target accounts over the mean) before the model sees them, so one
  set of channel parameters serves all 20 regions.
* Adstock = geometric carryover on the lead side, convolved with a fixed
  lead-to-close kernel from the README's sales-cycle facts. One alpha per channel;
  the kernel peaks one to two weeks after spend, like a B2B close.
* Hill saturation, which can be concave or S-shaped. The slope prior follows the
  channel's marketing role: concave for performance channels, S-shapes allowed for
  brand channels.
* Controls act on leads, so they get the same lead-to-close kernel. Webinars are an
  events program, not bought media, so their cost enters as a control.
* One shared Midwest season that shifts with each market's latitude.
* Brand search gets a skeptical prior (its spend follows demand). Brand and non-brand
  search get pooled lift tests from their planned regional pauses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pymc.dims as pmd
import pytensor.tensor as pt
import pytensor.xtensor as ptx
import xarray as xr
from pymc_extras.prior import Prior
from pymc_marketing.mmm import AdstockTransformation, HillSaturation
from pymc_marketing.mmm.multidimensional import MMM
from pymc_marketing.mmm.transformers import ConvMode, batched_convolution
from pytensor.xtensor import as_xtensor

from . import config as C
from .data import Panel

# --- adstock ------------------------------------------------------------------


def lagged_geometric_weights_np(alpha: np.ndarray) -> np.ndarray:
    """Kernel weights (..., ADSTOCK_L_MAX) for alpha (...,). Mirrors the model."""
    lags = np.arange(C.GEO_L_MAX)
    g = np.power(np.asarray(alpha)[..., None], lags)
    g = g / g.sum(axis=-1, keepdims=True)
    lag = C.lead_to_close_kernel()
    w = np.zeros(g.shape[:-1] + (C.ADSTOCK_L_MAX,))
    for j, p in enumerate(lag):
        w[..., j:j + C.GEO_L_MAX] += p * g
    return w


def _toeplitz() -> np.ndarray:
    """M[l, k] = lag[l - k]: maps geometric weights (k) to full kernel weights (l)."""
    lag = C.lead_to_close_kernel()
    m = np.zeros((C.ADSTOCK_L_MAX, C.GEO_L_MAX))
    for k in range(C.GEO_L_MAX):
        m[k:k + len(lag), k] = lag
    return m


class LaggedGeometricAdstock(AdstockTransformation):
    """Normalized geometric carryover followed by the fixed lead-to-close delay."""

    lookup_name = "lagged_geometric"
    default_priors = {"alpha": Prior("Beta", alpha=2, beta=3)}

    def function(self, x, alpha, *, dim: str):
        kernel_dim = f"{dim}_kernel"
        geo_dim = f"{dim}_geo"
        x = as_xtensor(x)
        alpha = as_xtensor(alpha)
        lags = ptx.as_xtensor(pt.arange(C.GEO_L_MAX, dtype=x.dtype), dims=(geo_dim,))
        g = ptx.math.power(alpha, lags)
        g = g / g.sum(dim=geo_dim)
        m = ptx.as_xtensor(pt.as_tensor(_toeplitz().astype(x.dtype)), dims=(kernel_dim, geo_dim))
        w = (m * g).sum(dim=geo_dim)
        return batched_convolution(x, w, dim=dim, kernel_dim=kernel_dim, mode=ConvMode.After)


# --- saturation ---------------------------------------------------------------------

HILL_FLOOR = 1e-12


def hill_np(x, slope, kappa):
    """Hill curve on numpy arrays. Mirrors ZeroSafeHillSaturation without beta."""
    x = np.maximum(x, HILL_FLOOR)
    return 1.0 - kappa**slope / (kappa**slope + x**slope)


class ZeroSafeHillSaturation(HillSaturation):
    """Hill saturation with x floored above zero.

    d(x**s)/ds = x**s * log(x) is NaN at x = 0, and CTV is zero in 12 of 20 regions,
    so the stock curve breaks NUTS. The floor changes the value by under 1e-12.
    """

    lookup_name = "zero_safe_hill"

    def function(self, x, slope, kappa, beta, *, dim: str | None = None):
        x = ptx.math.maximum(as_xtensor(x), HILL_FLOOR)
        return super().function(x, slope, kappa, beta, dim=dim)


# --- design matrix ----------------------------------------------------------------


def _lag_filter(a: np.ndarray) -> np.ndarray:
    """Apply the lead-to-close kernel along time (axis 0); the first value fills the start."""
    k = C.lead_to_close_kernel()
    pad = np.concatenate([np.repeat(a[:1], len(k) - 1, axis=0), a], axis=0)
    out = np.zeros_like(a, dtype=float)
    for j, p in enumerate(k):
        out += p * pad[len(k) - 1 - j: len(k) - 1 - j + len(a)]
    return out


LATITUDE_SEASON = [f"lat_{f}{k}" for k in range(1, C.FOURIER_MODES + 1) for f in ("sin", "cos")]
CONTROL_COLUMNS = ["sdr_coverage", "ae_coverage", "email_sends", "fleet_activity", "promo",
                   "price_increase", "trend", "webinars", *C.HOLIDAY_CLOSE_WEEKS, *LATITUDE_SEASON]
STANDARDIZED = ["sdr_coverage", "ae_coverage", "email_sends", "fleet_activity", "trend", "webinars"]


@dataclass
class Design:
    X: pd.DataFrame
    y: pd.Series
    n_train: int
    weeks: pd.DatetimeIndex
    regions: list[str]
    size: np.ndarray
    control_stats: dict = field(default_factory=dict)
    roles: dict = field(default_factory=dict)

    def train(self) -> tuple[pd.DataFrame, pd.Series]:
        if self.n_train >= len(self.weeks):
            return self.X, self.y
        keep = self.X.date < self.weeks[self.n_train]
        return self.X[keep].reset_index(drop=True), self.y[keep].reset_index(drop=True)

    def holdout(self) -> tuple[pd.DataFrame, pd.Series]:
        keep = self.X.date >= self.weeks[self.n_train]
        return self.X[keep].reset_index(drop=True), self.y[keep].reset_index(drop=True)



def latitude_season(panel: Panel) -> dict[str, np.ndarray]:
    """Standardized latitude x each yearly Fourier term, on the same day-of-year
    axis PyMC-Marketing's YearlyFourier uses. Lets the shared season shift by latitude."""
    lat = panel.latitude
    dlat = (lat - lat.mean()) / lat.std() if len(lat) > 1 and lat.std() > 0 else np.zeros(len(panel.regions))
    doy = panel.weeks.dayofyear.to_numpy() / 365.25
    out = {}
    for k in range(1, C.FOURIER_MODES + 1):
        out[f"lat_sin{k}"] = np.sin(2 * np.pi * k * doy)[:, None] * dlat[None, :]
        out[f"lat_cos{k}"] = np.cos(2 * np.pi * k * doy)[:, None] * dlat[None, :]
    return out


def controls_cube(panel: Panel) -> dict[str, np.ndarray]:
    """Raw control series as (T, G) arrays, before standardizing."""
    c = panel.controls_raw
    T, G = len(panel.weeks), len(panel.regions)

    def cube(col):
        w = c.pivot(index="week_start", columns="region_id", values=col)
        return w.reindex(index=panel.weeks, columns=panel.regions).to_numpy(float)

    acc = panel.accounts[None, :]
    woy = panel.weeks.isocalendar().week.to_numpy()
    out = {
        "sdr_coverage": _lag_filter(cube("sdr_headcount") / acc * 1000),
        "ae_coverage": _lag_filter(cube("ae_headcount") / acc * 1000),
        "email_sends": _lag_filter(cube("emails_sent") / panel.size[None, :]),
        "fleet_activity": _lag_filter(np.log(cube("fleet_activity_index"))),
        "promo": _lag_filter(cube("is_discount_promo").astype(float)),
        "price_increase": _lag_filter((cube("list_price_index") - 1.0) * 10.0),
        "trend": np.repeat((np.arange(T) / 52.0)[:, None], G, axis=1),
        "webinars": _lag_filter(panel.webinar_spend / panel.size[None, :]),
    }
    out.update(latitude_season(panel))
    for name, weeks in C.HOLIDAY_CLOSE_WEEKS.items():
        out[name] = np.repeat(np.isin(woy, weeks).astype(float)[:, None], G, axis=1)
    return out


def build_design(panel: Panel, holdout_weeks: int = C.HOLDOUT_WEEKS) -> Design:
    T, G = len(panel.weeks), len(panel.regions)
    n_train = T - holdout_weeks
    size = panel.size
    ctrl = controls_cube(panel)
    stats = {}
    for name in STANDARDIZED:
        mu, sd = ctrl[name][:n_train].mean(), ctrl[name][:n_train].std()
        ctrl[name] = (ctrl[name] - mu) / sd
        stats[name] = {"mean": float(mu), "sd": float(sd)}

    frame = {
        "date": np.repeat(panel.weeks.to_numpy(), G),
        "geo": np.tile(np.array(panel.regions, dtype=object), T),
    }
    for k, ch in enumerate(panel.channels):
        frame[ch] = (panel.spend[:, :, k] / size[None, :]).ravel()
    for name in CONTROL_COLUMNS:
        frame[name] = ctrl[name].ravel()
    X = pd.DataFrame(frame)
    y = pd.Series((panel.deals / size[None, :]).ravel(), name="deals_per_size")
    return Design(X, y, n_train, panel.weeks, list(panel.regions), size, stats, dict(panel.roles))


# --- priors and model ---------------------------------------------------------------

MEDIA_SHARE_PRIOR = 0.4    # prior guess for the share of deals paid media drives
BRAND_PRIOR_FACTOR = 0.5   # skeptical: brand search spend follows demand


def _scaled_stats(design: Design, channels: list[str]):
    X, y = design.train()
    ch = X[channels].to_numpy(float)
    ch_scale = ch.max(axis=0)
    xs = np.where(ch_scale > 0, ch / np.where(ch_scale > 0, ch_scale, 1.0), 0.0)
    ys = y.to_numpy(float) / y.max()
    return xs, ys


def _by_channel(v: np.ndarray, channels: list[str]) -> xr.DataArray:
    return xr.DataArray(np.asarray(v, float), dims=("channel",), coords={"channel": channels})


def model_config(design: Design, channels: list[str]) -> dict:
    xs, ys = _scaled_stats(design, channels)
    ybar = float(ys.mean())
    spend = design.train()[0][channels].to_numpy(float).sum(axis=0)
    share = spend / spend.sum()
    on_level = np.array([np.median(xs[xs[:, k] > 0, k]) for k in range(len(channels))])
    slope_prior = np.array([C.SLOPE_PRIOR_BY_ROLE.get(design.roles.get(c), C.SLOPE_PRIOR_DEFAULT)
                            for c in channels])
    slope0 = slope_prior[:, 0]
    hill0 = np.array([np.sum(xs[:, k] ** slope0[k] / (xs[:, k] ** slope0[k] + on_level[k] ** slope0[k]))
                      for k in range(len(channels))])
    b = share * MEDIA_SHARE_PRIOR * ys.sum() / hill0
    b[channels.index(C.BRAND)] *= BRAND_PRIOR_FACTOR

    return {
        "intercept": Prior("Normal", mu=0.6 * ybar, sigma=0.5 * ybar, dims="geo"),
        "likelihood": Prior("Normal", sigma=Prior("HalfNormal", sigma=0.5 * ybar, dims="geo"),
                            dims=("date", "geo")),
        "gamma_control": Prior("Normal", mu=0.0, sigma=0.25 * ybar, dims="control"),
        "gamma_fourier": Prior("Normal", mu=0.0, sigma=0.2 * ybar, dims="fourier_mode"),
        "adstock_alpha": Prior("Beta", alpha=2, beta=3, dims="channel"),
        "saturation_slope": Prior("LogNormal", mu=_by_channel(np.log(slope0), channels),
                                  sigma=_by_channel(slope_prior[:, 1], channels), dims="channel"),
        "saturation_kappa": Prior("LogNormal", mu=_by_channel(np.log(on_level), channels), sigma=0.7, dims="channel"),
        "saturation_beta": Prior("HalfNormal", sigma=_by_channel(b / 0.674, channels), dims="channel"),
    }


def make_mmm(design: Design, channels: list[str] | None = None) -> MMM:
    channels = channels or list(C.CHANNELS)
    return MMM(
        date_column="date",
        channel_columns=channels,
        target_column="deals_per_size",
        dims=("geo",),
        adstock=LaggedGeometricAdstock(l_max=C.ADSTOCK_L_MAX, normalize=True),
        saturation=ZeroSafeHillSaturation(),
        control_columns=CONTROL_COLUMNS,
        yearly_seasonality=C.FOURIER_MODES,
        model_config=model_config(design, channels),
    )


def add_pause_lifts(mmm: MMM, tests: list[dict]) -> list[dict]:
    """Add the pooled pause lift tests (one per channel) via add_lift_test_measurements.

    PyMC-Marketing compares absolute lifts. A pooled test with the wrong sign (deals
    rose during pauses) is entered as a zero drop: the closest value a monotone
    saturation curve can reach.
    """
    rows, entered = [], []
    for t in tests:
        delta_y = t["delta_y"] if t["delta_y"] < 0 else -1e-9
        rows.append({"geo": mmm.model.coords["geo"][0], "channel": t["channel"], "x": t["x"],
                     "delta_x": t["delta_x"], "delta_y": delta_y, "sigma": t["sigma"]})
        entered.append({**t, "delta_y_entered": delta_y})
    mmm.add_lift_test_measurements(pd.DataFrame(rows), dist=pmd.Normal, name=LIFT_NAME)
    return entered


LIFT_NAME = "pause_lift_tests"
