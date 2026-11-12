"""Turn regional dark periods into lift tests.

An MMM sees how deals move when spend moves a little, so it learns the slope of
each response curve well. The level (deals at today's spend against zero spend) is
an extrapolation along the curve's assumed shape. A regional pause measures that
level directly: spend drops to zero in one region while the others keep running.
The README calls these dark weeks natural geo holdouts.

Brand search is the sharpest case: its spend follows demand, so its ordinary
week-to-week movement is confounded with the baseline, and a pause is the one time
it drops while demand does not.

Each pause is read as a small geo experiment:

* effect window: the paused weeks plus TAIL_WEEKS for carryover and the
  lead-to-close delay, so the whole deal deficit is counted;
* counterfactual: the paused region's share of the other regions' deals over the
  REF_WEEKS before the pause (after the effect window when there is no pre-period).
  Regions that never buy the channel are always valid controls;
* lift per paused week = total deficit / paused weeks. With normalized adstock this
  is the steady-state weekly contribution of the pre-pause spend level, which is
  what PyMC-Marketing compares with saturation(x) - saturation(x + delta_x);
* sigma: the spread of the same estimator on placebo windows in the same region
  while the channel ran.

Only steady channels qualify (on in at least STEADY_ON_SHARE of the region-weeks
where they are bought). Flighted channels switch on and off constantly, so their
level is already identified inside the MMM, and a "pre-pause level" is not defined.
Pauses are pooled per channel in per-size units (deals and spend divided by the
region size index), because single pauses are too noisy to carry a sign.
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
MIN_PAUSES = 2
STEADY_ON_SHARE = 0.85
COLUMNS = ["channel", "geo", "start_week", "paused_weeks", "size", "x", "delta_x", "delta_y",
           "placebo_mean", "sigma", "n_placebo", "ref"]


@dataclass
class Pause:
    region: str
    start: int   # first paused week index
    weeks: int   # paused weeks


def _spend(panel: Panel, channel: str) -> np.ndarray:
    return panel.spend[:, :, panel.channels.index(channel)]


def find_pauses(panel: Panel, channel: str = C.BRAND) -> list[Pause]:
    s = _spend(panel, channel)
    out = []
    for g, region in enumerate(panel.regions):
        if s[:, g].sum() <= 0:
            continue  # never bought here: a control, not a pause
        off = s[:, g] <= 0
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


def on_share(panel: Panel, channel: str, n_train: int) -> float:
    s = _spend(panel, channel)[:n_train]
    bought = s.sum(axis=0) > 0
    return float((s[:, bought] > 0).mean()) if bought.any() else 0.0


def steady_channels(panel: Panel, n_train: int) -> list[str]:
    return [c for c in panel.channels if on_share(panel, c, n_train) >= STEADY_ON_SHARE]


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


def estimate(panel: Panel, n_train: int, channel: str = C.BRAND) -> pd.DataFrame:
    """One row per usable pause of `channel` inside the first n_train weeks."""
    y = panel.deals[:n_train]
    spend = _spend(panel, channel)[:n_train]
    size = panel.size
    pauses = find_pauses(panel, channel)
    paused = np.zeros_like(spend, dtype=bool)
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
        if len(others) == 0:
            continue
        lift = _lift_per_week(y, g, others, eff, ref, p.weeks)
        x = float(spend[ref[0]:ref[1], g].mean())

        # Placebo: same window lengths, same region, start weeks with the channel running.
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
            if len(pothers):
                placebo.append(_lift_per_week(y, g, pothers, pe, pr, p.weeks))
        if len(placebo) < MIN_PLACEBO or x <= 0:
            continue  # no honest noise estimate, or no pre-pause spend to remove
        rows.append({
            "channel": channel, "geo": p.region, "start_week": str(panel.weeks[p.start].date()),
            "paused_weeks": p.weeks, "size": float(size[g]),
            "x": x, "delta_x": -x, "delta_y": lift,
            "placebo_mean": float(np.mean(placebo)), "sigma": float(np.std(placebo, ddof=1)),
            "n_placebo": len(placebo), "ref": "pre" if ref[0] < eff[0] else "post",
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def pooled(df: pd.DataFrame, channel: str = C.BRAND) -> dict:
    """Inverse-variance pooled lift in per-size units."""
    xs = df.x / df["size"]
    ys = df.delta_y / df["size"]
    ss = df.sigma / df["size"]
    w = 1.0 / ss**2
    return {
        "channel": channel,
        "x": float((w * xs).sum() / w.sum()),
        "delta_x": float(-(w * xs).sum() / w.sum()),
        "delta_y": float((w * ys).sum() / w.sum()),
        "sigma": float(np.sqrt(1.0 / w.sum())),
        "n_pauses": int(len(df)),
        "units": "deals and dollars per week per size unit (region value / size index)",
    }


def all_tests(panel: Panel, n_train: int) -> tuple[pd.DataFrame, list[dict]]:
    """Pause rows for every steady channel, and one pooled test per channel."""
    frames, tests = [], []
    for ch in steady_channels(panel, n_train):
        df = estimate(panel, n_train, ch)
        if len(df) >= MIN_PAUSES:
            frames.append(df)
            tests.append({**pooled(df, ch), "on_share": on_share(panel, ch, n_train)})
    rows = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    return rows, tests
