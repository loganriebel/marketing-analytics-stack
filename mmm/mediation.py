"""Deals the upper funnel creates through brand search, per posterior draw.

Stage 1 (brand_demand) says how much brand-search spend each upper-funnel channel
creates. Stage 2 (the MMM) says how many deals brand search returns on its spend.
For channel u and a spend multiplier m on its in-window path:

    brand path(m) = actual brand path + (m - 1) * brand spend u creates
    deals via brand search(m) = brand curve(brand path(m)) - brand curve(actual)

Incremental deals via brand search = -(value at m = 0): the brand-search deals lost
if u's in-window spend and the searches it created were gone. Draws of the two
stages are paired at random; the stages are fit separately, so their uncertainty
is treated as independent.
"""

from __future__ import annotations

import numpy as np

from . import config as C
from .brand_demand import BrandDemand, created_brand_path
from .estimands import Engine, hdi, summarize


class Mediation:
    def __init__(self, engine: Engine, demand: BrandDemand, channel_scale: dict[str, float]):
        self.engine = engine
        self.demand = demand.draws(engine.post.n_draws, seed=11)
        self.scale = channel_scale
        self.brand_actual = engine.scaled_path(C.BRAND)
        self.brand_deals_actual = engine.deals(C.BRAND, 1.0)
        self._created: dict[str, np.ndarray] = {}

    @property
    def channels(self) -> list[str]:
        return list(self.demand.upper)

    def created(self, channel: str) -> np.ndarray:
        if channel not in self._created:
            self._created = {channel: created_brand_path(self.demand, self.engine.panel, self.scale,
                                                         channel, self.engine.tail)}
        return self._created[channel]

    def via_brand(self, channel: str, multiplier: float) -> np.ndarray:
        """(S,) change in brand-search deals when `channel`'s path is scaled by `multiplier`."""
        path = np.maximum(self.brand_actual[None] + (multiplier - 1.0) * self.created(channel), 0.0)
        return self.engine.deals_for_path(C.BRAND, path) - self.brand_deals_actual

    def created_brand_spend(self, channel: str) -> float:
        """Posterior mean in-window brand-search dollars the channel's searches create."""
        k = self.engine.post.channels.index(C.BRAND)
        T = len(self.engine.panel.weeks)
        per_size = self.created(channel)[:, :T].mean(axis=0) * self.engine.post.channel_scale[k]
        return float((per_size * self.engine.size[None, :]).sum())

    def channel_estimands(self, channel: str, direct: dict) -> dict:
        e = self.engine
        spend = direct["spend"]
        via = -self.via_brand(channel, 0.0)
        total = direct["_draws"]["incremental_deals"] + via
        d_up = e.deals(channel, 1.01) + self.via_brand(channel, 1.01)
        d_dn = e.deals(channel, 0.99) + self.via_brand(channel, 0.99)
        with np.errstate(divide="ignore", invalid="ignore"):
            cpa_total = spend / total
            mcpa_total = 0.02 * spend / (d_up - d_dn)
        return {
            "incremental_deals_via_brand_search": summarize(via),
            "incremental_deals_total": summarize(total),
            "cpa_total": summarize(cpa_total),
            "marginal_cpa_total": summarize(mcpa_total),
            "brand_search_spend_created": self.created_brand_spend(channel),
            "_draws": {"via": via, "total": total},
        }

    def total_response_curve(self, channel: str, multipliers=C.RESPONSE_MULTIPLIERS) -> list[dict]:
        """Direct plus via-brand-search deals at each multiplier, both measured from zero spend."""
        spend = float(self.engine.spend(channel).sum())
        at_zero = self.via_brand(channel, 0.0)
        rows = []
        for m in multipliers:
            via = self.via_brand(channel, m) - at_zero
            tot = self.engine.deals(channel, m) + via
            lo, hi = hdi(tot)
            rows.append({"channel": channel, "spend_multiplier": m, "spend": spend * m,
                         "incremental_deals_total_mean": float(tot.mean()), "hdi_90_low": lo,
                         "hdi_90_high": hi, "via_brand_search_mean": float(via.mean())})
        return rows
