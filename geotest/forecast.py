"""What the MMM expects a test arm to do, on every posterior draw.

The test runs in 2026, so its business-as-usual spend is not known yet. The forecast
uses last year's same weeks as the stand-in: each channel's actual 2025 path, with
the arm's move applied in its markets during the test weeks. The lift is the MMM's
deals with the move minus without it, counted in the close weeks of the measurement
window (the model's adstock already holds the lead-to-close delay).

Reads the MMM's saved posterior (mmm/fits/<name>.nc) and its scales; needs the
.venv-mmm environment for h5netcdf.
"""

from __future__ import annotations

import json

import numpy as np
import xarray as xr

from mmm import config as MC
from mmm.model import hill_np, lagged_geometric_weights_np

from .data import Markets

CARRY_IN_WEEKS = 20


class Forecaster:
    def __init__(self, name: str = "holdout", fit_dir=MC.FIT_DIR, n_draws: int = 2000, seed: int = 0):
        scales = json.loads((fit_dir / f"{name}_scales.json").read_text(encoding="utf-8"))
        ds = xr.open_dataset(fit_dir / f"{name}.nc", group="posterior", engine="h5netcdf")
        chans = list(MC.CHANNELS)

        def stack(v):
            a = ds[v].transpose("chain", "draw", "channel").sel(channel=chans).values
            return a.reshape(-1, a.shape[-1])

        p = {k: stack(v) for k, v in (("alpha", "adstock_alpha"), ("slope", "saturation_slope"),
                                       ("kappa", "saturation_kappa"), ("beta", "saturation_beta"))}
        ds.close()
        idx = np.sort(np.random.default_rng(seed).choice(p["alpha"].shape[0], n_draws, replace=False))
        self.p = {k: v[idx] for k, v in p.items()}
        self.channels = chans
        self.channel_scale = np.asarray(scales["channel_scale"], float)
        self.target_scale = float(scales["target_scale"])
        self.name = name

    def weekly(self, ch: str, x: np.ndarray, size: np.ndarray) -> np.ndarray:
        """Spend (T, G) in dollars -> the MMM's deals (S, T + tail, G) by close week."""
        k = self.channels.index(ch)
        xs = x / size[None, :] / self.channel_scale[k]
        xs = np.vstack([xs, np.zeros((MC.ADSTOCK_L_MAX, xs.shape[1]))])
        w = lagged_geometric_weights_np(self.p["alpha"][:, k])
        a = np.zeros((w.shape[0],) + xs.shape)
        for lag in range(w.shape[1]):
            a[:, lag:] += w[:, lag, None, None] * xs[None, : xs.shape[0] - lag]
        h = hill_np(a, self.p["slope"][:, k, None, None], self.p["kappa"][:, k, None, None])
        return self.p["beta"][:, k, None, None] * h * self.target_scale * size[None, None, :]

    def arm(self, m: Markets, markets: np.ndarray, moves: dict, proxy_start: int, n_test: int,
            n_win: int) -> dict:
        """Lift draws for an arm. moves: {channel: ("add", $/week/size) or ("mult", m)}."""
        lo = proxy_start - CARRY_IN_WEEKS
        test = np.arange(CARRY_IN_WEEKS, CARRY_IN_WEEKS + n_test)
        win = np.arange(CARRY_IN_WEEKS, CARRY_IN_WEEKS + n_win)
        size = m.size
        in_win = np.zeros(next(iter(self.p.values())).shape[0])
        total = np.zeros_like(in_win)
        dspend, by_ch = 0.0, {}
        g = np.where(markets)[0]
        for ch, (kind, val) in moves.items():
            x0 = m.spend[ch][lo:proxy_start + n_win].copy()
            x1 = x0.copy()
            cell = np.ix_(test, g)
            if kind == "add":
                x1[cell] += val * size[None, g]
            else:
                x1[cell] *= val
            d = self.weekly(ch, x1, size) - self.weekly(ch, x0, size)
            d = d[:, :, g]
            in_win += d[:, win].sum(axis=(1, 2))
            total += d.sum(axis=(1, 2))
            by_ch[ch] = {"spend_change": float((x1 - x0).sum()), "lift_in_window_mean": float(d[:, win].sum(axis=(1, 2)).mean())}
            dspend += float((x1 - x0).sum())
        return {"in_window": in_win, "total": total, "spend_change": dspend, "by_channel": by_ch}
