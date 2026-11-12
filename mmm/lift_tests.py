"""Turn the regional brand-search pauses into lift tests.

Brand search spend follows demand, so its week-to-week movement is confounded with
the baseline. A pause is the exception: the spend goes to zero while demand does
not. Each pause is read as a small geo experiment:

* effect window: the paused weeks plus TAIL_WEEKS for carryover and the
  lead-to-close delay, so the whole deal deficit is counted;
* counterfactual: the paused region's share of the other regions' deals over the
  REF_WEEKS before the pause (after the effect window when there is no pre-period);
* lift per paused week = total deficit / paused weeks. With normalized adstock this
  is the steady-state weekly contribution of the pre-pause spend level, which is
  what PyMC-Marketing compares with saturation(x) - saturation(x + delta_x);
* sigma: the spread of the same estimator on placebo windows in the same region
  when brand search was running.

All pauses are pooled into one lift test in per-size units (deals and spend divided
by the region size index), because single pauses are too noisy to carry a sign.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config as C
from .data import Panel

REF_WEEKS = 12
TAIL_WEEKS = 8
MIN_PAUSE_WEEKS = 3
MIN_PLACEBO = 10
COLUMNS = ["geo", "start_week", "paused_weeks", "size", "x", "delta_x", "delta_y", "placebo_mean",
           "sigma", "n_placebo", "ref"]


@dataclass
class Pause:
    region: str
    start: int   # first paused week index
    weeks: int   # paused weeks


def find_pauses(panel: Panel) -> list[Pause]:
    b = panel.spend[:, :, panel.channels.index(C.BRAND)]
    out = []
    for g, region in enumerate(panel.regions):
        off = b[:, g] <= 0
        t = 0
        while t < len(off):
            if off[t]:
                end = t
                while end < len(off) and off[end]:
                    end += 1
                if end - t >= MIN_PAUSE_WEEKS:
                    out.append(Pause(region, t, end - t))
                t = end
            else:
                t += 1
    return out


def _windows(start: int, weeks: int, n_weeks: int):
    eff = (start, start + weeks + TAIL_WEEKS)
    if start - REF_WEEKS >= 0:
        ref = (start - REF_WEEKS, start)
    else:
        ref = (eff[1], eff[1] + REF_WEEKS)
    if eff[1] > n_weeks or ref[1] > n_weeks:
        return None
    return eff, ref


def _lift_per_week(y: np.ndarray, g: int, others: np.ndarray, eff, ref, weeks: int) -> float:
    """Deficit in region g over the effect window, per paused week, in deals."""
    pool = y[:, others].sum(axis=1)
    share = y[ref[0]:ref[1], g].sum() / pool[ref[0]:ref[1]].sum()
    expected = share * pool[eff[0]:eff[1]].sum()
    return float((y[eff[0]:eff[1], g].sum() - expected) / weeks)


def estimate(panel: Panel, n_train: int) -> pd.DataFrame:
    """One row per usable pause inside the first n_train weeks."""
    y = panel.deals[:n_train]
    brand = panel.spend[:n_train, :, panel.channels.index(C.BRAND)]
    size = panel.size
    pauses = find_pauses(panel)
    paused = np.zeros_like(brand, dtype=bool)
    for p in pauses:
        g = panel.regions.index(p.region)
        paused[p.start:p.start + p.weeks + TAIL_WEEKS, g] = True

    rows = []
    for p in pauses:
        g = panel.regions.index(p.region)
        w = _windows(p.start, p.weeks, n_train)
        if w is None:
            continue
        eff, ref = w
        span = slice(min(eff[0], ref[0]), max(eff[1], ref[1]))
        others = np.array([h for h in range(len(panel.regions))
                           if h != g and not paused[span, h].any()])
        lift = _lift_per_week(y, g, others, eff, ref, p.weeks)
        x = float(brand[ref[0]:ref[1], g].mean())

        # Placebo: same window lengths, same region, start weeks with brand running.
        placebo = []
        for s in range(0, n_train):
            pw = _windows(s, p.weeks, n_train)
            if pw is None:
                continue
            pe, pr = pw
            pspan = slice(min(pe[0], pr[0]), max(pe[1], pr[1]))
            if paused[pspan, g].any():
                continue
            pothers = np.array([h for h in range(len(panel.regions))
                                if h != g and not paused[pspan, h].any()])
            placebo.append(_lift_per_week(y, g, pothers, pe, pr, p.weeks))
        if len(placebo) < MIN_PLACEBO:
            continue  # no honest noise estimate for this pause
        rows.append({
            "geo": p.region, "start_week": str(panel.weeks[p.start].date()),
            "paused_weeks": p.weeks, "size": float(size[g]),
            "x": x, "delta_x": -x, "delta_y": lift,
            "placebo_mean": float(np.mean(placebo)), "sigma": float(np.std(placebo, ddof=1)),
            "n_placebo": len(placebo), "ref": "pre" if ref[0] < eff[0] else "post",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def pooled(df: pd.DataFrame) -> dict:
    """Inverse-variance pooled lift in per-size units."""
    xs = df.x / df["size"]
    ys = df.delta_y / df["size"]
    ss = df.sigma / df["size"]
    w = 1.0 / ss**2
    return {
        "channel": C.BRAND,
        "x": float((w * xs).sum() / w.sum()),
        "delta_x": float(-(w * xs).sum() / w.sum()),
        "delta_y": float((w * ys).sum() / w.sum()),
        "sigma": float(np.sqrt(1.0 / w.sum())),
        "n_pauses": int(len(df)),
        "units": "deals and dollars per week per size unit (region value / size index)",
    }
