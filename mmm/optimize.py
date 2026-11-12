"""Reallocate the in-window budget across channels at the same total spend.

The plan is one multiplier per channel on its actual weekly path (the same move the
marginal CPA and response curves describe), bounded to C.OPT_BOUNDS. Channels add
up independently in the model, so the objective is a sum of per-channel posterior
mean response curves, each tabulated on a fine grid and splined.
"""

from __future__ import annotations

import numpy as np
from scipy import interpolate, optimize

from . import config as C
from .estimands import Engine, summarize

GRID = np.round(np.arange(C.OPT_BOUNDS[0], C.OPT_BOUNDS[1] + 1e-9, 0.05), 4)


def optimize_mix(engine: Engine, channels: list[str]) -> dict:
    spend = np.array([float(engine.spend(c).sum()) for c in channels])
    curves = {}
    for c in channels:
        means = np.array([engine.deals(c, m).mean() for m in GRID])
        curves[c] = interpolate.CubicSpline(GRID, means)

    def neg_total(m):
        return -sum(float(curves[c](mi)) for c, mi in zip(channels, m))

    def neg_grad(m):
        return -np.array([float(curves[c](mi, 1)) for c, mi in zip(channels, m)])

    res = optimize.minimize(
        neg_total, x0=np.ones(len(channels)), jac=neg_grad, method="SLSQP",
        bounds=[C.OPT_BOUNDS] * len(channels),
        constraints=[{"type": "eq", "fun": lambda m: float(m @ spend - spend.sum()),
                      "jac": lambda m: spend}],
        options={"ftol": 1e-10, "maxiter": 500},
    )
    mult = np.clip(res.x, *C.OPT_BOUNDS)
    mult = mult * spend.sum() / (mult @ spend)  # exact budget after clipping

    # Score the chosen plan on every draw.
    delta = np.zeros(engine.post.n_draws)
    rows = []
    for c, m, s in zip(channels, mult, spend):
        d = engine.deals(c, float(m)) - engine.deals(c, 1.0)
        delta += d
        rows.append({"channel": c, "spend_now": s, "multiplier": float(m),
                     "spend_plan": float(s * m), "spend_change": float(s * (m - 1)),
                     "deal_change": summarize(d)})
    base = sum(engine.deals(c, 1.0) for c in channels)
    return {
        "objective": "max posterior-mean incremental deals at the same total paid spend",
        "bounds": list(C.OPT_BOUNDS),
        "converged": bool(res.success),
        "total_spend": float(spend.sum()),
        "plan": rows,
        "deal_change": summarize(delta),
        "deal_change_pct_of_paid_incremental": summarize(100 * delta / base),
        "prob_gain_positive": float((delta > 0).mean()),
    }
