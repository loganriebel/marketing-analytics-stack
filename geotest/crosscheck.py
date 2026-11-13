"""Cross-check the readout with a Bayesian synthetic control (CausalPy). It does not decide.

    .venv-mmm\\Scripts\\python -m geotest.crosscheck

Pre-registered as a cross-check on the same window. For each arm, the treated series
is the arm's markets' mean weekly won deals, and the donors are the other 10 markets,
one series each. CausalPy's WeightedSumFitter puts Dirichlet weights on the donors,
fits them on the 52 pre-test weeks, and projects them over the 16-week window. The
arm's lift is the gap summed over the window, times its number of markets.

Limit: one arm's donors include markets of the other arm, so unlike the registered
estimator this does not take out the other arm's effect. The output reports how much
donor weight sits on the other arm's markets.

Reads the same data cut as geotest.readout. Writes geotest/outputs/synthetic_control.json.
"""

from __future__ import annotations

import json
import os
import warnings

os.environ.setdefault("PYTENSOR_FLAGS", "cxx=")

import pytensor  # noqa: E402

pytensor.config.mode = "NUMBA"   # no C compiler on Windows; as in mmm/fit.py

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .data import load  # noqa: E402
from .readout import ARM_KEYS, CROSSCHECK_PATH, DESIGN_PATH, arm_masks, cut_warehouse  # noqa: E402

SAMPLER = {"chains": 4, "draws": 1000, "tune": 1000, "random_seed": 20260531, "progressbar": False,
           "nuts_sampler": "nutpie"}


def _hdi(x: np.ndarray, prob: float = 0.9) -> list[float]:
    s = np.sort(x)
    k = int(np.floor(prob * len(s)))
    i = int(np.argmin(s[k:] - s[:len(s) - k]))
    return [float(s[i]), float(s[i + k])]


def synth(m, d: dict) -> dict:
    import causalpy as cp

    dt = d["dates"]
    s = m.week_index(dt["test_start"])
    n_pre, n_win = dt["pre_period_weeks"], dt["window_weeks"]
    rows = slice(s - n_pre, s + n_win)
    arms = arm_masks(d, m.regions)
    out = {}
    for i, k in enumerate(ARM_KEYS):
        t = arms[i]
        donors = [m.regions[g] for g in np.where(~t)[0]]
        df = pd.DataFrame(m.deals[rows][:, ~t], index=m.weeks[rows], columns=donors)
        df["arm"] = m.deals[rows][:, t].mean(axis=1)
        model = cp.pymc_models.WeightedSumFitter(sample_kwargs=dict(SAMPLER))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = cp.SyntheticControl(df, pd.Timestamp(dt["test_start"]), control_units=donors,
                                      treated_units=["arm"], model=model)
        gap = res.post_impact.sel(treated_units="arm").sum("obs_ind")
        lift = gap.values.reshape(-1) * int(t.sum())
        pre_mean = res.pre_pred.sel(treated_units="arm").mean(("chain", "draw"))
        pre_mean = np.asarray(pre_mean["y_hat"] if hasattr(pre_mean, "data_vars") else pre_mean).reshape(-1)
        obs = df["arm"].to_numpy()[:n_pre]
        beta = model.idata.posterior["beta"].mean(("chain", "draw")).sel(treated_units="arm")
        weights = dict(zip(beta["coeffs"].values.tolist(), beta.values.tolist()))
        other = arms[1 - i]
        out[k] = {
            "lift_mean": float(lift.mean()), "lift_hdi_90": _hdi(lift),
            "pre_r2": float(1 - ((obs - pre_mean) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()),
            "donor_weights": weights,
            "weight_on_other_arm": float(sum(w for c, w in weights.items() if other[m.regions.index(c)])),
            "markets": int(t.sum()),
        }
    return {"method": "CausalPy SyntheticControl with WeightedSumFitter, per arm: the arm's mean weekly won "
                      "deals against the other 10 markets, fit on the pre-test weeks",
            "causalpy_version": cp.__version__, "sampler": {k: v for k, v in SAMPLER.items() if k != "progressbar"},
            "pre_weeks": n_pre, "window_weeks": n_win,
            "note": "Each arm's donors include markets of the other arm, so this check does not take out the "
                    "other arm's effect the way the registered 2x2 estimator does.",
            "arms": out}


def main() -> int:
    d = json.loads(DESIGN_PATH.read_text(encoding="utf-8"))
    m = load(cut_warehouse(d), through=d["dates"]["readout_snapshot"])
    r = synth(m, d)
    CROSSCHECK_PATH.write_text(json.dumps(r, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "donor_weights"} for k, v in r["arms"].items()},
                     indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
