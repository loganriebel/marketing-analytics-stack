"""Channel estimands computed from posterior draws.

Definitions (same as the scenario's grading definitions):

* incremental deals: expected closed-won deals caused by the channel's in-window
  spend, counting deals that close after the window ends;
* CPA: in-window spend / incremental deals;
* marginal CPA: extra spend per extra deal when the channel's whole in-window spend
  path is scaled by 1% (central difference between 0.99 and 1.01);
* ROI: incremental first-year revenue / spend, valuing each deal at its region's
  average won-deal revenue (a deals KPI cannot see deal-size differences by channel);
* response curve: incremental deals when the in-window spend path is scaled by a
  multiplier, other channels unchanged.

The engine re-implements the model's media path in numpy (adstock, Hill, scaling)
so any spend path can be scored per draw. tests/test_mmm_smoke.py checks it against
PyMC-Marketing's own channel_contribution.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import config as C
from .data import Panel
from .model import hill_np, lagged_geometric_weights_np


def hdi(samples: np.ndarray, prob: float = C.HDI_PROB) -> tuple[float, float]:
    """Narrowest interval holding `prob` of the samples."""
    s = np.sort(np.asarray(samples, float))
    s = s[np.isfinite(s)]
    n = len(s)
    k = int(np.floor(prob * n))
    if n == 0 or k < 1:
        return (float("nan"), float("nan"))
    widths = s[k:] - s[: n - k]
    i = int(np.argmin(widths))
    return (float(s[i]), float(s[i + k]))


def summarize(samples: np.ndarray) -> dict:
    lo, hi = hdi(samples)
    return {"mean": float(np.mean(samples)), "median": float(np.median(samples)),
            "hdi_90": [lo, hi]}


@dataclass
class MediaPosterior:
    channels: list[str]
    alpha: np.ndarray   # (S, C)
    slope: np.ndarray
    kappa: np.ndarray
    beta: np.ndarray
    channel_scale: np.ndarray  # (C,) per-size dollars
    target_scale: float        # per-size deals

    @classmethod
    def from_idata(cls, idata, channel_scale, target_scale, channels, max_draws=None, seed=0):
        post = idata.posterior

        def stack(name):
            a = post[name].transpose("chain", "draw", "channel").sel(channel=channels).values
            return a.reshape(-1, a.shape[-1])

        arrays = [stack(n) for n in ("adstock_alpha", "saturation_slope", "saturation_kappa",
                                     "saturation_beta")]
        if max_draws and arrays[0].shape[0] > max_draws:
            idx = np.random.default_rng(seed).choice(arrays[0].shape[0], max_draws, replace=False)
            arrays = [a[np.sort(idx)] for a in arrays]
        return cls(list(channels), *arrays, np.asarray(channel_scale, float), float(target_scale))

    @property
    def n_draws(self) -> int:
        return self.alpha.shape[0]


class Engine:
    """Scores spend paths for one channel at a time, per posterior draw."""

    def __init__(self, post: MediaPosterior, panel: Panel, tail_weeks: int = C.ADSTOCK_L_MAX):
        self.post = post
        self.panel = panel
        self.size = panel.size
        self.tail = tail_weeks
        won = panel.deals.sum(axis=0)
        self.deal_value = np.where(won > 0, panel.won_revenue.sum(axis=0) / np.maximum(won, 1), 0.0)
        self._adstock_cache: dict[str, np.ndarray] = {}

    def spend(self, channel: str) -> np.ndarray:
        return self.panel.spend[:, :, self.panel.channels.index(channel)]

    def adstocked(self, channel: str) -> np.ndarray:
        """(S, T + tail, G) adstocked scaled spend for the actual path (multiplier 1)."""
        if channel not in self._adstock_cache:
            self._adstock_cache.clear()  # one channel at a time keeps memory near 100 MB
            k = self.post.channels.index(channel)
            x = self.spend(channel) / self.size[None, :] / self.post.channel_scale[k]
            x = np.vstack([x, np.zeros((self.tail, x.shape[1]))])
            w = lagged_geometric_weights_np(self.post.alpha[:, k])  # (S, L)
            out = np.zeros((self.post.n_draws,) + x.shape)
            for lag in range(w.shape[1]):
                if lag == 0:
                    out += w[:, lag, None, None] * x[None]
                else:
                    out[:, lag:] += w[:, lag, None, None] * x[None, :-lag]
            self._adstock_cache[channel] = out
        return self._adstock_cache[channel]

    def deals_by_region(self, channel: str, multiplier: float = 1.0) -> np.ndarray:
        """(S, G) incremental deals over the window plus tail for a scaled path."""
        k = self.post.channels.index(channel)
        a = self.adstocked(channel) * multiplier
        h = hill_np(a, self.post.slope[:, k, None, None], self.post.kappa[:, k, None, None])
        if multiplier == 0:
            h = np.zeros_like(h)
        per_size = self.post.beta[:, k, None, None] * h * self.post.target_scale
        return per_size.sum(axis=1) * self.size[None, :]

    def deals(self, channel: str, multiplier: float = 1.0) -> np.ndarray:
        return self.deals_by_region(channel, multiplier).sum(axis=1)

    def scaled_path(self, channel: str) -> np.ndarray:
        """(T + tail, G) actual spend per size unit on the model's channel scale."""
        k = self.post.channels.index(channel)
        x = self.spend(channel) / self.size[None, :] / self.post.channel_scale[k]
        return np.vstack([x, np.zeros((self.tail, x.shape[1]))])

    def deals_for_path(self, channel: str, x: np.ndarray) -> np.ndarray:
        """(S,) deals over window plus tail for any scaled path, (T + tail, G) or per draw (S, T + tail, G)."""
        k = self.post.channels.index(channel)
        x = np.broadcast_to(x, (self.post.n_draws,) + x.shape[-2:])
        w = lagged_geometric_weights_np(self.post.alpha[:, k])
        a = np.zeros(x.shape)
        for lag in range(w.shape[1]):
            a[:, lag:] += w[:, lag, None, None] * x[:, : x.shape[1] - lag]
        h = hill_np(a, self.post.slope[:, k, None, None], self.post.kappa[:, k, None, None])
        per_size = self.post.beta[:, k, None, None] * h * self.post.target_scale
        return (per_size.sum(axis=1) * self.size[None, :]).sum(axis=1)

    def weekly(self, channel: str) -> np.ndarray:
        """(S, T + tail) national weekly contribution of the actual path."""
        k = self.post.channels.index(channel)
        h = hill_np(self.adstocked(channel), self.post.slope[:, k, None, None],
                    self.post.kappa[:, k, None, None])
        per_size = self.post.beta[:, k, None, None] * h * self.post.target_scale
        return (per_size * self.size[None, None, :]).sum(axis=2)

    def channel_estimands(self, channel: str) -> dict:
        spend = float(self.spend(channel).sum())
        by_region = self.deals_by_region(channel)
        inc = by_region.sum(axis=1)
        revenue = by_region @ self.deal_value
        up, down = self.deals(channel, 1.01), self.deals(channel, 0.99)
        with np.errstate(divide="ignore", invalid="ignore"):
            cpa = spend / inc
            mcpa = 0.02 * spend / (up - down)
        return {
            "spend": spend,
            "incremental_deals": summarize(inc),
            "cpa": summarize(cpa),
            "marginal_cpa": summarize(mcpa),
            "roi_revenue": summarize(revenue / spend),
            "_draws": {"incremental_deals": inc, "marginal_deals_per_1pct": (up - down) / 2},
        }

    def response_curve(self, channel: str, multipliers=C.RESPONSE_MULTIPLIERS) -> list[dict]:
        spend = float(self.spend(channel).sum())
        rows = []
        for m in multipliers:
            d = self.deals(channel, m)
            lo, hi = hdi(d)
            rows.append({"channel": channel, "spend_multiplier": m, "spend": spend * m,
                         "incremental_deals_mean": float(d.mean()), "hdi_90_low": lo,
                         "hdi_90_high": hi})
        return rows
