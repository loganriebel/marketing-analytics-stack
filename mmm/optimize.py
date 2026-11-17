"""Reallocate the in-window budget across channels at the same total spend.

The plan is one multiplier per channel on its actual weekly path (the same move the
marginal CPA and response curves describe), bounded to C.OPT_BOUNDS. Channels add
up independently in the model, so the objective is a sum of per-channel posterior
mean response curves, each tabulated on a fine grid and splined.

With the brand-search mediation, brand search is not a lever: it is always on and
its spend follows searches. The levers are the other channels, an upper-funnel
channel's curve includes the deals it creates through brand search, and the plan
reports the brand-search spend those searches add.

SLSQP can stop at the right plan and still report failure ("Positive directional
derivative for linesearch") when several levers sit at their bounds. solve_exact
finds the optimum another way, and optimality checks any plan against the optimum's
conditions; the rollout (rollout/plan.py) uses both.
"""

from __future__ import annotations

import numpy as np
from scipy import interpolate, optimize

from . import config as C
from .estimands import Engine, summarize

GRID = np.round(np.arange(C.OPT_BOUNDS[0], C.OPT_BOUNDS[1] + 1e-9, 0.05), 4)


def mean_curves(deal_change, levers: list[str]) -> dict:
    """Posterior-mean deal change at each multiplier on GRID, splined, per lever."""
    return {c: interpolate.CubicSpline(GRID, np.array([deal_change(c, m).mean() for m in GRID])) for c in levers}


def solve_exact(curves: dict, levers: list[str], spend: np.ndarray, bounds=C.OPT_BOUNDS) -> np.ndarray:
    """Multipliers that maximize the summed curves at the same total spend, inside the bounds.

    The problem is separable, so the optimum has one price per dollar, lam: a lever
    inside its bounds earns lam extra deals per extra dollar, a lever at its cap earns
    at least lam, and one at its floor at most lam. For a given lam each lever's
    multiplier is the best point of its own curve minus lam times its spend (a fine
    grid, so a curve need not be concave), and the total spend falls as lam rises, so
    bisection on lam finds the plan that spends the budget. The last dollars go to the
    lever whose curve is flattest there, which closes the budget exactly.
    """
    fine = np.linspace(bounds[0], bounds[1], 20001)
    vals = {c: curves[c](fine) for c in levers}

    def pick(lam):
        return np.array([fine[np.argmax(vals[c] - lam * s * fine)] for c, s in zip(levers, spend)])

    marg = np.array([curves[c](fine, 1) / s for c, s in zip(levers, spend)])
    lo, hi = float(marg.min()) - 1.0, float(marg.max()) + 1.0
    for _ in range(200):
        lam = 0.5 * (lo + hi)
        if pick(lam) @ spend > spend.sum():
            lo = lam
        else:
            hi = lam
    m = pick(hi)
    gap = spend.sum() - m @ spend
    inner = [i for i, v in enumerate(m) if bounds[0] < v < bounds[1]]
    if inner:  # spend the last dollars on the inner lever that can take them
        i = max(inner, key=lambda j: spend[j])
        m[i] = float(np.clip(m[i] + gap / spend[i], *bounds))
    return m


def optimality(curves: dict, levers: list[str], spend: np.ndarray, mult, bounds=C.OPT_BOUNDS,
               tol: float = 0.01) -> dict:
    """Check the plan against the optimum's conditions (Karush-Kuhn-Tucker).

    Each lever's extra deals per extra dollar at its multiplier: levers inside their
    bounds must agree (within tol, relative), levers at the cap must earn at least that
    much, and levers at the floor at most that much. Passing means no small move of
    money between levers, at the same total, adds deals.
    """
    mult = np.asarray(mult, float)
    marg = np.array([float(curves[c](m, 1)) / s for c, m, s in zip(levers, mult, spend)])
    eps = 1e-4
    at_lo, at_hi = mult <= bounds[0] + eps, mult >= bounds[1] - eps
    inner = ~(at_lo | at_hi)
    lam = float(np.mean(marg[inner])) if inner.any() else float("nan")
    rows, ok = [], bool(abs(mult @ spend - spend.sum()) <= 1e-6 * spend.sum())
    for c, m, g, lo_, hi_ in zip(levers, mult, marg, at_lo, at_hi):
        where = "floor" if lo_ else ("cap" if hi_ else "inside")
        if where == "inside":
            good = abs(g - lam) <= tol * abs(lam)
        elif where == "cap":
            good = g >= lam * (1 - tol)
        else:
            good = g <= lam * (1 + tol)
        ok &= bool(good)
        rows.append({"channel": c, "multiplier": float(m), "where": where,
                     "extra_deals_per_extra_1000_dollars": 1000 * g, "condition_holds": bool(good)})
    return {"price_extra_deals_per_extra_1000_dollars": 1000 * lam, "tolerance": tol,
            "budget_holds": bool(abs(mult @ spend - spend.sum()) <= 1e-6 * spend.sum()),
            "optimum": ok, "levers": rows}


def optimize_mix(engine: Engine, channels: list[str], mediation=None) -> dict:
    levers = [c for c in channels if not (mediation is not None and c == C.BRAND)]
    upper = set(mediation.channels) if mediation is not None else set()

    def deal_change(c: str, m: float) -> np.ndarray:
        d = engine.deals(c, m) - engine.deals(c, 1.0)
        if c in upper:
            d = d + mediation.via_brand(c, m)
        return d

    spend = np.array([float(engine.spend(c).sum()) for c in levers])
    curves = mean_curves(deal_change, levers)

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
