"""Chapter 7: the rollout plan (May 2026), from the refit MMM.

    .venv-mmm\\Scripts\\python -m rollout.plan

Rule 3 of the pre-registration says the rollout follows the refit model, not the test
plan, and rule 4's guardrails decide what it may not do. This module:

1. Reads the guardrails from the readout (geotest/outputs/readout.json). If one
   tripped, it stops: the plan would need a bound this module does not set.
2. Checks the refit optimizer. Its SLSQP run stopped with converged: False and four
   of its seven levers at a 50% bound. The same curves are rebuilt from the refit's
   saved posterior, the committed plan is checked against the optimum's conditions
   (mmm.optimize.optimality), and the problem is solved again exactly
   (mmm.optimize.solve_exact).
3. Plans the rollout weeks. The refit plan's multipliers were set on 2023 to 2025
   spend; 2026 runs heavier on non-brand search, so the same multipliers would spend
   less than the approved budget. So the same objective, posterior and bounds are
   solved again on the rollout's own weeks and markets, at the same total, with last
   year's same weeks as the stand-in for 2026 spend (as the test forecast did).
4. Forecasts what the plan adds in the rollout markets, on every posterior draw: the
   deals that close inside the rollout weeks (what a year-end readout can see) and all
   the deals it causes.
5. Registers the year-end readout before the rollout runs. The 5 markets in neither arm
   of the spring test stay on the old plan as a standing holdout, and the readout's
   estimator, interval, power and rules are written down now (rollout/holdout.py), the
   way the spring test was pre-registered.

The bounds stay at 50% either way: the model has never seen a channel moved further,
so the plan does not move one further.

Reads mmm/outputs/refit/optimizer.json, the refit's saved posterior (mmm/fits/refit.nc
and its scales), geotest/outputs/readout.json and the May 2026 data cut. Writes
rollout/outputs/plan.json, plans/2026_rollout.yaml and rollout/PLAN.md. The plan file
registers the rollout as a one-arm test (id RO2026H2), so the sim keeps the holdout
markets on the old plan and the market test registry records them.
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("PYTENSOR_FLAGS", "cxx=")

import pytensor  # noqa: E402

pytensor.config.mode = "NUMBA"

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import xarray as xr  # noqa: E402
import yaml  # noqa: E402

from geotest.data import load as load_markets  # noqa: E402
from mmm import brand_demand  # noqa: E402
from mmm import config as MC  # noqa: E402
from mmm.data import Panel, load_panel  # noqa: E402
from mmm.estimands import Engine, MediaPosterior, summarize  # noqa: E402
from mmm.mediation import Mediation  # noqa: E402
from mmm.model import hill_np, lagged_geometric_weights_np  # noqa: E402
from mmm.optimize import mean_curves, optimality, solve_exact  # noqa: E402

from . import holdout as H  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "rollout" / "outputs"
PLAN_JSON = OUT_DIR / "plan.json"
PLAN_YAML = REPO / "plans" / "2026_rollout.yaml"
PLAN_MD = REPO / "rollout" / "PLAN.md"
REFIT_OUT = REPO / "mmm" / "outputs" / "refit"
READOUT = REPO / "geotest" / "outputs" / "readout.json"
CUT = Path(os.environ.get("ROLLOUT_PLAN_WAREHOUSE",
                          REPO / "data" / "cut_2026-05-31" / "data" / "warehouse.duckdb"))
FIT = "refit"

NAME = "2026 rollout"
APPROVED = date(2026, 5, 29)
START = date(2026, 6, 1)               # ISO 2026-W23
LAST_WEEK = date(2026, 12, 28)         # ISO 2026-W53, the sim's last 2026 week
N_WEEKS = 31
PROXY_START = date(2025, 6, 2)         # last year's same ISO week, the stand-in for 2026 spend
SPRING_START = date(2026, 2, 2)        # the spring test's first week; the holdout's pre-period ends before it
READOUT_SNAPSHOT = date(2027, 1, 3)    # the year-end data cut
CARRY_IN_WEEKS = 20                    # spend before the rollout, held as it was, so saturation starts right
ESTIMANDS_WEEKS = 156                  # the refit scores its plan on 2023 to 2025
DRAWS = 2000
DECIMALS = 4                           # multipliers in the plan file
HOLDOUT = H.HOLDOUT                    # markets kept on the old plan all year


def load_posterior(fit_dir: Path = MC.FIT_DIR, name: str = FIT) -> tuple[MediaPosterior, dict[str, float]]:
    """The fit's media posterior, the same 2,000 draws its outputs used (seed 0)."""
    scales = json.loads((fit_dir / f"{name}_scales.json").read_text(encoding="utf-8"))
    ds = xr.open_dataset(fit_dir / f"{name}.nc", group="posterior", engine="h5netcdf")
    try:
        post = MediaPosterior.from_idata(SimpleNamespace(posterior=ds), scales["channel_scale"],
                                         scales["target_scale"], list(MC.CHANNELS), max_draws=DRAWS)
    finally:
        ds.close()
    return post, dict(zip(MC.CHANNELS, scales["channel_scale"]))


def stage1(panel: Panel, scale: dict[str, float]) -> brand_demand.BrandDemand:
    """Brand-search demand, fit exactly as the refit fit it (same data, split and sampler)."""
    d = brand_demand.fit(panel, len(panel.weeks) - MC.HOLDOUT_WEEKS, scale, dict(MC.SAMPLER))
    if not d.diagnostics["all_pass"]:
        raise RuntimeError(f"stage 1 failed its gates: {d.diagnostics['gates']}")
    return d


def guardrails(readout: dict) -> dict:
    dec = readout["decision"]
    out = {"readout_valid": dec["valid"],
           "keep_nonbrand_at_todays_spend": dec["rule_4_keep_cut_channels_at_todays_spend"],
           "do_not_grow_youtube": dec["rule_4_do_not_grow"]}
    if not dec["valid"] or out["keep_nonbrand_at_todays_spend"] or out["do_not_grow_youtube"]:
        raise SystemExit(f"a rule 4 guardrail tripped or the readout is void: {out}")
    return out


def _levers(opt: dict) -> tuple[list[str], np.ndarray]:
    levers = list(opt["levers"])
    mult = {r["channel"]: r["multiplier"] for r in opt["plan"]}
    return levers, np.array([mult[c] for c in levers])


def window_check(post, panel: Panel, demand, scale, opt: dict) -> dict:
    """The committed refit plan on its own window (2023 to 2025), with the same curves."""
    eng = Engine(post, panel.subset(n_weeks=ESTIMANDS_WEEKS))
    med = Mediation(eng, demand, scale)
    levers, committed = _levers(opt)

    def dc(c, m):
        d = eng.deals(c, m) - eng.deals(c, 1.0)
        return d + med.via_brand(c, m) if c in med.channels else d

    spend = np.array([float(eng.spend(c).sum()) for c in levers])
    curves = mean_curves(dc, levers)
    exact = solve_exact(curves, levers, spend)
    gain = {k: float(sum(dc(c, m).mean() for c, m in zip(levers, ms))) for k, ms in
            (("committed", committed), ("exact", exact))}
    return {
        "weeks": f"{eng.panel.weeks[0].date()} to {eng.panel.weeks[-1].date()}",
        "solver_converged_flag": opt["converged"], "solver_message": opt["solver_message"],
        "committed_deal_change_mean": opt["deal_change"]["mean"],
        "rebuilt_deal_change_mean": gain["committed"],
        "committed": optimality(curves, levers, spend, committed),
        "exact": {"multipliers": dict(zip(levers, exact.tolist())), "deal_change_mean": gain["exact"],
                  "check": optimality(curves, levers, spend, exact)},
    }


class Scorer:
    """Deal changes from scaling each lever's spend in the rollout weeks and markets, per draw.

    The slice holds CARRY_IN_WEEKS of earlier spend at its actual level, so each
    channel starts the rollout as saturated as it really was, then the rollout weeks,
    then the model's 12-week tail with no new spend.
    """

    def __init__(self, post: MediaPosterior, panel: Panel, demand, scale, start: int, markets: list[str]):
        self.post, self.scale = post, scale
        self.p = panel.subset(n_weeks=CARRY_IN_WEEKS + N_WEEKS, first_week=start - CARRY_IN_WEEKS)
        self.eng = Engine(post, self.p)
        self.T = len(self.p.weeks)
        self.rows = np.arange(CARRY_IN_WEEKS, CARRY_IN_WEEKS + N_WEEKS)
        self.mask = np.zeros((self.T, len(self.p.regions)), bool)
        self.mask[np.ix_(self.rows, np.where(np.isin(self.p.regions, markets))[0])] = True
        self.demand = demand.draws(post.n_draws, seed=11)  # paired with stage 2 as Mediation pairs them
        self.brand_x = self.eng.scaled_path(MC.BRAND)
        self.brand_w = self.weekly(MC.BRAND, self.brand_x)
        self._base: dict[str, np.ndarray] = {}
        self._created: dict[str, np.ndarray] = {}

    def spend(self, ch: str) -> float:
        return float(self.p.spend[:, :, self.p.channels.index(ch)][self.mask].sum())

    def weekly(self, ch: str, x: np.ndarray) -> np.ndarray:
        """(S, T + tail, G) the model's deals by close week for a scaled path."""
        k = self.post.channels.index(ch)
        x = np.broadcast_to(x, (self.post.n_draws,) + x.shape[-2:])
        w = lagged_geometric_weights_np(self.post.alpha[:, k])
        a = np.zeros(x.shape)
        for lag in range(w.shape[1]):
            a[:, lag:] += w[:, lag, None, None] * x[:, : x.shape[1] - lag]
        h = hill_np(a, self.post.slope[:, k, None, None], self.post.kappa[:, k, None, None])
        return self.post.beta[:, k, None, None] * h * self.post.target_scale * self.p.size[None, None, :]

    def created(self, u: str) -> np.ndarray:
        """(S, T + tail, G) brand-search spend (scaled) that u's rollout-week spend creates."""
        if u not in self._created:
            k = self.p.channels.index(u)
            sp = self.p.spend.copy()
            sp[:, :, k] = np.where(self.mask, sp[:, :, k], 0.0)
            self._created[u] = brand_demand.created_brand_path(
                self.demand, dataclasses.replace(self.p, spend=sp), self.scale, u, self.eng.tail)
        return self._created[u]

    def change(self, ch: str, m: float) -> np.ndarray:
        """(S, T + tail) national deal change by close week; upper funnel includes brand search."""
        x = self.eng.scaled_path(ch)
        x1 = x.copy()
        top = x1[: self.T]
        top[self.mask] *= m
        if ch not in self._base:
            self._base[ch] = self.weekly(ch, x)
        d = (self.weekly(ch, x1) - self._base[ch]).sum(axis=2)
        if ch in self.demand.upper:
            path = np.maximum(self.brand_x[None] + (m - 1.0) * self.created(ch), 0.0)
            d = d + (self.weekly(MC.BRAND, path) - self.brand_w).sum(axis=2)
        return d

    def brand_spend_change(self, u: str, m: float) -> float:
        k = self.post.channels.index(MC.BRAND)
        per_size = self.created(u)[:, : self.T].mean(axis=0) * self.post.channel_scale[k]
        return float((m - 1.0) * (per_size * self.p.size[None, :]).sum())


def score_plan(sc: Scorer, levers: list[str], mult) -> dict:
    """Every draw's deal change for a plan: all deals it causes, and those closing in the rollout weeks."""
    total = np.zeros(sc.post.n_draws)
    in_win = np.zeros(sc.post.n_draws)
    rows, brand = [], 0.0
    win = slice(CARRY_IN_WEEKS, CARRY_IN_WEEKS + N_WEEKS)
    for c, m in zip(levers, mult):
        d = sc.change(c, float(m))
        total += d.sum(axis=1)
        in_win += d[:, win].sum(axis=1)
        s = sc.spend(c)
        row = {"channel": c, "multiplier": float(m), "spend_now": s, "spend_plan": s * float(m),
               "spend_change": s * (float(m) - 1.0), "deal_change": summarize(d.sum(axis=1)),
               "deal_change_in_window": summarize(d[:, win].sum(axis=1))}
        if c in sc.demand.upper:
            row["brand_search_spend_change"] = sc.brand_spend_change(c, float(m))
            brand += row["brand_search_spend_change"]
        rows.append(row)
    spend_change = float(sum(r["spend_change"] for r in rows))
    return {"by_channel": rows, "spend_change": spend_change, "brand_search_spend_change": brand,
            "deal_change": summarize(total), "deal_change_in_window": summarize(in_win),
            "prob_gain_positive": float((total > 0).mean()), "_in_window": in_win, "_total": total}


def plan_rollout(post, panel: Panel, demand, scale, opt: dict) -> dict:
    start = int(panel.weeks.get_loc(pd.Timestamp(PROXY_START)))
    markets = [r for r in panel.regions if r not in HOLDOUT]
    sc = Scorer(post, panel, demand, scale, start, markets)
    levers, committed = _levers(opt)
    spend = np.array([sc.spend(c) for c in levers])
    curves = mean_curves(lambda c, m: sc.change(c, m).sum(axis=1), levers)
    exact = solve_exact(curves, levers, spend)
    plan = np.round(exact, DECIMALS)
    scored = score_plan(sc, levers, plan)
    as_is = score_plan(sc, levers, committed)
    return {
        "proxy_weeks": f"{sc.p.weeks[CARRY_IN_WEEKS].date()} to {sc.p.weeks[-1].date()}",
        "markets": markets, "holdout": HOLDOUT,
        "lever_spend_in_proxy_weeks": float(spend.sum()),
        "solved": {"multipliers": dict(zip(levers, exact.tolist())),
                   "check": optimality(curves, levers, spend, exact)},
        "plan": {"multipliers": dict(zip(levers, plan.tolist())), **scored},
        "refit_multipliers_as_is": {"multipliers": dict(zip(levers, committed.tolist())),
                                    **{k: v for k, v in as_is.items() if not k.startswith("_")}},
    }


def plan_yaml(out: dict) -> str:
    moves = {c: {"multiplier": m} for c, m in out["rollout"]["plan"]["multipliers"].items()}
    plan = {"name": NAME, "approved": str(APPROVED),
            "test": {"id": H.TEST_ID, "start": str(START), "end": str(LAST_WEEK),
                     "arms": [{"id": H.ARM_ID, "markets": out["rollout"]["markets"], "moves": moves}]}}
    head = ("# Written by python -m rollout.plan from the refit MMM (rollout/outputs/plan.json).\n"
            "# Do not edit by hand. The rollout is one arm, so the holdout markets\n"
            f"# ({', '.join(out['rollout']['holdout'])}) stay on the old plan.\n")
    return head + yaml.safe_dump(plan, sort_keys=False, default_flow_style=None)


def build() -> dict:
    opt = json.loads((REFIT_OUT / "optimizer.json").read_text(encoding="utf-8"))
    readout = json.loads(READOUT.read_text(encoding="utf-8"))
    rails = guardrails(readout)
    panel = load_panel(CUT)
    post, scale = load_posterior()
    demand = stage1(panel, scale)
    out = {
        "name": NAME, "approved": str(APPROVED),
        "dates": {"start": str(START), "last_week": str(LAST_WEEK),
                  "end": str(LAST_WEEK + timedelta(days=6)), "weeks": N_WEEKS,
                  "proxy_start": str(PROXY_START), "carry_in_weeks": CARRY_IN_WEEKS},
        "source": {"optimizer": "mmm/outputs/refit/optimizer.json", "posterior": f"mmm/fits/{FIT}.nc",
                   "data_cut": f"{panel.weeks[0].date()} to {panel.weeks[-1].date()}",
                   "readout": "geotest/outputs/readout.json"},
        "guardrails": rails,
        "bounds": list(MC.OPT_BOUNDS),
        "stage1_gates": demand.diagnostics["gates"],
        "refit_plan_check": window_check(post, panel, demand, scale, opt),
    }
    out["rollout"] = plan_rollout(post, panel, demand, scale, opt)

    # The year-end readout, registered now from data before the spring test.
    m = load_markets(CUT)
    rollout = ~np.isin(m.regions, HOLDOUT)
    spring = m.week_index(SPRING_START)
    reg = H.design(m.weeks, m.deals, rollout, (START - SPRING_START).days // 7, N_WEEKS, spring,
                   out["rollout"]["plan"]["_in_window"])
    reg.update({"rollout_markets": [r for r, k in zip(m.regions, rollout) if k],
                "window": [str(START), str(LAST_WEEK + timedelta(days=6))],
                "readout_snapshot": str(READOUT_SNAPSHOT),
                "forecast": {k: out["rollout"]["plan"]["deal_change_in_window"][k] for k in ("mean", "hdi_90")},
                "rules": H.rules(reg["power_at_forecast"])})
    out["holdout"] = reg
    return out


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def main() -> int:
    out = _jsonable(build())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PLAN_JSON.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    PLAN_YAML.write_text(plan_yaml(out), encoding="utf-8", newline="\n")
    from .plan_md import plan_md
    PLAN_MD.write_text(plan_md(out), encoding="utf-8", newline="\n")
    r = out["rollout"]
    print(json.dumps({"refit_plan_check": out["refit_plan_check"],
                      "solved": r["solved"], "plan": {k: v for k, v in r["plan"].items() if k != "by_channel"},
                      "as_is": {k: v for k, v in r["refit_multipliers_as_is"].items() if k != "by_channel"}},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
