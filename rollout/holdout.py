"""The rollout's standing holdout: its registered estimator, interval, power and rules.

Pure numpy, so the plan (MMM environment) and the year-end readout (either
environment) share one copy.

* The 15 rollout markets are compared with the 5 holdout markets, which stay on the
  old plan: the markets in neither arm of the spring test, untouched all year.
* Estimator: the spring test's ratio difference-in-differences with one arm,
      lift = W(rollout) - r * W(holdout),   r = P(rollout) / P(holdout)
  W is won deals over the window, P over the pre-period. The pre-period is the 52 weeks
  before the spring test began, so the test's own effect cannot leak into the ratio.
* Interval: 90%, from placebo windows with the same geometry (window, gap, pre-period)
  on weeks before the spring test, where nothing moved. The sd used is the largest of
  the windows starting in 2024, those starting in 2025, and the count-noise floor.
* Validity: the media plan (fct_media_plan_weekly) holds each channel's weekly budget
  line by market, moves applied. A move ran when the delivered spend over the rollout
  weeks sits nearer, in logs, to the new plan's line than to the old plan's (for a
  multiplier m: delivered / planned nearer 1 than 1 / m). The holdout stayed on the
  old plan when its delivered spend sits nearer to the old line than to the new one.
"""

from __future__ import annotations

import numpy as np

from geotest import estimator as E

TEST_ID = "RO2026H2"
ARM_ID = "rollout"
HOLDOUT = ["CAK", "CID", "CLE", "FSD", "MSP"]     # the spring test's "neither" cell
PRE_WEEKS = 52


def sums(deals: np.ndarray, start: int, n_win: int, gap: int, n_pre: int = PRE_WEEKS) -> tuple[np.ndarray, np.ndarray]:
    """Pre-period and window deal sums (G,) for a window starting at `start`, with the
    pre-period ending `gap` weeks before it."""
    end_pre = start - gap
    return deals[end_pre - n_pre:end_pre].sum(0), deals[start:start + n_win].sum(0)


def lift(pre: np.ndarray, win: np.ndarray, rollout: np.ndarray) -> float:
    r = pre[rollout].sum() / pre[~rollout].sum()
    return float(win[rollout].sum() - r * win[~rollout].sum())


def placebo(deals: np.ndarray, rollout: np.ndarray, starts, n_win: int, gap: int) -> np.ndarray:
    return np.array([lift(*sums(deals, s, n_win, gap), rollout) for s in starts])


def design(weeks, deals: np.ndarray, rollout: np.ndarray, gap: int, n_win: int, first_untouched_after: int,
           forecast: np.ndarray) -> dict:
    """The registered interval, power and smallest detectable lift, from data before the spring test.

    weeks: Mondays (DatetimeIndex) of `deals` (T, G). gap: weeks from the end of the
    pre-period to the rollout's first week. first_untouched_after: index of the spring
    test's first week; placebo windows end before it. forecast: draws of the MMM's
    in-window lift in the rollout markets.
    """
    starts = np.arange(gap + PRE_WEEKS, first_untouched_after - n_win + 1)
    errs = placebo(deals, rollout, starts, n_win, gap)
    year = np.array([weeks[s].year for s in starts])
    rms = {str(y): float(np.sqrt(np.mean(errs[year == y] ** 2))) for y in sorted(set(year))}
    floor = float(E.count_noise_floor(deals[:first_untouched_after], rollout[None, :], n_win)[0])
    sd = max(max(rms.values()), floor)
    mean = float(np.mean(forecast))
    return {
        "test_id": TEST_ID, "holdout": HOLDOUT, "pre_period_weeks": PRE_WEEKS, "gap_weeks": int(gap),
        "pre_period": [str(weeks[first_untouched_after - PRE_WEEKS].date()),
                       str(weeks[first_untouched_after - 1].date())],
        "window_weeks": n_win,
        "placebo": {"windows": int(len(starts)), "first_start": str(weeks[starts[0]].date()),
                    "last_start": str(weeks[starts[-1]].date()), "rms_by_start_year": rms,
                    "mean": float(errs.mean()), "count_noise_floor": floor, "sd_used": sd,
                    "false_positive_rate": float(np.mean(errs / sd > E.Z_90))},
        "smallest_detectable_lift": float(E.MDE_Z * sd),
        "power_at_forecast": float(_power(mean, sd)),
        "assurance": float(np.mean([_power(f, sd) for f in forecast])),
        "rollout_share_of_pre_period_deals": float(deals[first_untouched_after - PRE_WEEKS:first_untouched_after]
                                                   [:, rollout].sum()
                                                   / deals[first_untouched_after - PRE_WEEKS:first_untouched_after].sum()),
    }


def _power(mean: float, sd: float) -> float:
    from math import erf, sqrt
    z = mean / sd - E.Z_90
    return 0.5 * (1 + erf(z / sqrt(2)))


def decide(lift_: float, low: float, high: float, forecast: float, valid: bool) -> dict:
    """The registered rules, as written."""
    if low > forecast:
        vs = "beats the forecast"
    elif high < forecast:
        vs = "falls short of the forecast"
    else:
        vs = "agrees with the forecast"
    return {"valid": bool(valid), "rule_1_rollout_works": bool(low > 0), "rule_2_against_forecast": vs,
            "rule_3_not_clear": bool(low <= 0 <= high), "rule_3_drop_is_clear": bool(high < 0)}


def plan_ratios(rows, rollout_markets: list[str], first: str, last: str) -> dict:
    """Delivered over planned spend per channel, weeks with Monday in [first, last]: the
    rollout markets summed, the holdout markets summed, and each market.

    rows: (week_start ISO, region_id, channel_id, planned_spend, spend) from fct_media_plan_weekly.
    """
    acc: dict = {}
    for wk, region, ch, planned, spend in rows:
        if not first <= wk <= last:
            continue
        c = acc.setdefault(ch, {"rollout": [0.0, 0.0], "holdout": [0.0, 0.0], "markets": {}})
        side = "rollout" if region in rollout_markets else "holdout"
        c[side][0] += spend
        c[side][1] += planned
        m = c["markets"].setdefault(region, [0.0, 0.0])
        m[0] += spend
        m[1] += planned
    out = {}
    for ch, c in acc.items():
        out[ch] = {"rollout": c["rollout"][0] / c["rollout"][1], "holdout": c["holdout"][0] / c["holdout"][1],
                   "markets": {r: v[0] / v[1] for r, v in sorted(c["markets"].items()) if v[1] > 0}}
    return out


def _nearer_one(ratio: float, other: float) -> bool:
    """True when ratio is nearer, in logs, to 1 than to `other`."""
    return abs(np.log(ratio)) < abs(np.log(ratio) - np.log(other))


def plan_check(ratios: dict, mult: dict, rollout_markets: list[str], ran: bool = True) -> dict:
    """The registered move check. ran=False reads the same spend against the new plan as
    if the rollout had not run (delivered spend on the old line), the check's dry run."""
    out, named = {}, []
    for ch, m in mult.items():
        r = ratios[ch]
        k = 1.0 if ran else 1.0 / m
        roll = r["rollout"] * k
        out[ch] = {"multiplier": m, "rollout_ratio": roll, "rollout_line": float(np.sqrt(1.0 / m)),
                   "move_shows": bool(_nearer_one(roll, 1.0 / m)),
                   "holdout_ratio": r["holdout"], "holdout_stays": bool(_nearer_one(r["holdout"], m))}
        for reg, v in r["markets"].items():
            rolled = reg in rollout_markets
            v = v * k if rolled else v
            if not _nearer_one(v, 1.0 / m if rolled else m):
                named.append({"market": reg, "channel": ch, "ratio": v, "rollout": rolled})
    return {"channels": out, "named_markets": named,
            "passes": bool(all(v["move_shows"] and v["holdout_stays"] for v in out.values()))}


def rules(power: float) -> list[str]:
    return [
        "The rollout works if the holdout readout's 90% interval is above zero.",
        "Against the model: the rollout beats the May forecast if the interval lies above it, falls short if it "
        "lies below, and agrees otherwise.",
        f"If the interval reaches zero, the result is not clear. At {power:.0%} power that is the likely read even "
        "if the forecast is right, so it is not evidence that the plan failed. A clear drop (the whole interval "
        "below zero) would be.",
        "The model's own counterfactual, the refit MMM scoring the realized 2026 spend with and without the "
        "rollout's moves, is shown beside the readout as a cross-check. It decides nothing.",
        "Validity: the plan file assigns the registered markets, moves and dates. For every moved channel, the "
        "rollout markets' delivered spend over the rollout weeks sits nearer, in logs, to the new plan's budget "
        "line than to the old one, and the holdout markets' sits nearer to the old line than to the new. "
        "Otherwise the readout is void. A single market that misses is named, never void.",
    ]
