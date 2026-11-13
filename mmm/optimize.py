"""Reallocate the in-window budget across channels at the same total spend.

The plan is one multiplier per channel on its actual weekly path (the same move the
marginal CPA and response curves describe), bounded to C.OPT_BOUNDS. Channels add
up independently in the model, so the objective is a sum of per-channel posterior
mean response curves, each tabulated on a fine grid and splined.

With the brand-search mediation, brand search is not a lever: it is always on and
its spend follows searches. The levers are the other channels, an upper-funnel
channel's curve includes the deals it creates through brand search, and the plan
reports the brand-search spend those searches add.
"""

from __future__ import annotations

import numpy as np
from scipy import interpolate, optimize

from . import config as C
from .estimands import Engine, summarize

GRID = np.round(np.arange(C.OPT_BOUNDS[0], C.OPT_BOUNDS[1] + 1e-9, 0.05), 4)


def optimize_mix(engine: Engine, channels: list[str], mediation=None) -> dict:
    levers = [c for c in channels if not (mediation is not None and c == C.BRAND)]
    upper = set(mediation.channels) if mediation is not None else set()

    def deal_change(c: str, m: float) -> np.ndarray:
        d = engine.deals(c, m) - engine.deals(c, 1.0)
        if c in upper:
            d = d + mediation.via_brand(c, m)
        return d

    spend = np.array([float(engine.spend(c).sum()) for c in levers])
    curves = {c: interpolate.CubicSpline(GRID, np.array([deal_change(c, m).mean() for m in GRID]))
              for c in levers}

    def neg_total(m):
        return -sum(float(curves[c](mi)) for c, mi in zip(levers, m))

    def neg_grad(m):
        return -np.array([float(curves[c](mi, 1)) for c, mi in zip(levers, m)])

    res = optimize.minimize(
        neg_total, x0=np.ones(len(levers)), jac=neg_grad, method="SLSQP",
        bounds=[C.OPT_BOUNDS] * len(levers),
        constraints=[{"type": "eq", "fun": lambda m: float(m @ spend - spend.sum()),
                      "jac": lambda m: spend}],
        options={"ftol": 1e-10, "maxiter": 500},
    )
    mult = np.clip(res.x, *C.OPT_BOUNDS)
    mult = mult * spend.sum() / (mult @ spend)  # exact budget after clipping

    # Score the chosen plan on every draw.
    delta = np.zeros(engine.post.n_draws)
    rows, brand_spend_change = [], 0.0
    for c, m, s in zip(levers, mult, spend):
        d = deal_change(c, float(m))
        delta += d
        row = {"channel": c, "spend_now": s, "multiplier": float(m), "spend_plan": float(s * m),
               "spend_change": float(s * (m - 1)), "deal_change": summarize(d)}
        if c in upper:
            created = mediation.created_brand_spend(c) * (m - 1)
            row["brand_search_spend_change"] = created
            brand_spend_change += created
        rows.append(row)
    base = sum(engine.deals(c, 1.0) for c in channels)
    out = {
        "objective": "max posterior-mean incremental deals at the same total spend on the levers",
        "levers": levers,
        "bounds": list(C.OPT_BOUNDS),
        "converged": bool(res.success),
        "solver_message": str(res.message),
        "total_spend": float(spend.sum()),
        "plan": rows,
        "deal_change": summarize(delta),
        "deal_change_pct_of_paid_incremental": summarize(100 * delta / base),
        "prob_gain_positive": float((delta > 0).mean()),
    }
    if mediation is not None:
        out["brand_search"] = ("not a lever: always on, spend follows searches; the plan's upper-funnel "
                               "moves change it by brand_search_spend_change")
        out["brand_search_spend_change"] = brand_spend_change
    return out
