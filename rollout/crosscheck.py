"""The model's own view of the rollout, beside the holdout readout. It decides nothing.

    .venv-mmm\\Scripts\\python -m rollout.crosscheck

The refit MMM (the same posterior and brand-search stage the plan came from) scores
the realized 2026 spend in the rollout markets twice: as it happened, and with each
channel's rollout weeks divided back by the plan's multiplier. The difference is the
deals the model says the rollout's moves caused, closing inside the rollout weeks.
It reads no outcomes, so it is the model checking its own plan on the spend that
really ran, not a measurement.

Reads rollout/outputs/plan.json, the refit's saved posterior, the May 2026 data cut
(for the brand-search stage, fit as the refit fit it) and the year-end data cut.
Writes rollout/outputs/model_view.json.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from mmm.data import load_panel
from mmm.estimands import summarize

from . import plan as P
from .results import MODEL_VIEW, PLAN_JSON, cut_warehouse


def model_view(plan: dict) -> dict:
    post, scale = P.load_posterior()
    demand = P.stage1(load_panel(P.CUT), scale)
    panel = load_panel(cut_warehouse(plan))
    start = int(panel.weeks.get_loc(pd.Timestamp(plan["dates"]["start"])))
    if start + P.N_WEEKS != len(panel.weeks):
        raise ValueError("the year-end cut must end with the rollout's last week")
    sc = P.Scorer(post, panel, demand, scale, start, plan["holdout"]["rollout_markets"])
    win = slice(P.CARRY_IN_WEEKS, P.CARRY_IN_WEEKS + P.N_WEEKS)
    total, in_win, rows = np.zeros(post.n_draws), np.zeros(post.n_draws), []
    for c, m in plan["rollout"]["plan"]["multipliers"].items():
        d = -sc.change(c, 1.0 / m)  # realized path minus the path without the move
        total += d.sum(axis=1)
        in_win += d[:, win].sum(axis=1)
        rows.append({"channel": c, "multiplier": m, "deal_change_in_window": summarize(d[:, win].sum(axis=1))})
    return {"method": "refit MMM on the realized 2026 spend, with and without the rollout's moves",
            "markets": plan["holdout"]["rollout_markets"],
            "weeks": [str(panel.weeks[start].date()), str(panel.weeks[-1].date())],
            "deal_change_in_window": summarize(in_win), "deal_change": summarize(total), "by_channel": rows}


def main() -> int:
    plan = json.loads(PLAN_JSON.read_text(encoding="utf-8"))
    out = P._jsonable(model_view(plan))
    MODEL_VIEW.parent.mkdir(parents=True, exist_ok=True)
    MODEL_VIEW.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: out[k] for k in ("deal_change_in_window", "deal_change")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
