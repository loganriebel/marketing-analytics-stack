"""Settings for the step 4 MMM. Every number here comes from the README, the marts,
or a modeling choice explained in docs/mmm/README.md."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy import optimize, stats

REPO_ROOT = Path(__file__).resolve().parents[1]
# Env overrides point a run at another simulated world (a development seed)
# without touching this checkout's warehouse or committed outputs.
WAREHOUSE = Path(os.environ.get("MMM_WAREHOUSE", REPO_ROOT / "data" / "warehouse.duckdb"))
OUTPUT_DIR = Path(os.environ.get("MMM_OUTPUT_DIR", REPO_ROOT / "mmm" / "outputs"))
FIT_DIR = Path(os.environ.get("MMM_FIT_DIR", REPO_ROOT / "mmm" / "fits"))

CHANNELS = [
    "paid_search_brand",
    "paid_search_nonbrand",
    "meta",
    "linkedin",
    "youtube",
    "ctv",
    "display",
    "affiliates",
]
BRAND = "paid_search_brand"
# Regional live events. Their cost sits in fct_channel_weekly, but they are an
# events program, not bought media, so they enter as a control.
WEBINARS = "webinars"

HOLDOUT_WEEKS = 13
HDI_PROB = 0.90

# Lead-side carryover runs up to GEO_L_MAX weeks; the lead-to-close delay adds up to
# len(lag kernel) - 1 more. ADSTOCK_L_MAX is the full kernel length the model uses.
GEO_L_MAX = 8
LAG_WEEKS = 5
ADSTOCK_L_MAX = GEO_L_MAX + LAG_WEEKS - 1

# README: "a lead closes in about two weeks; nine in ten close in 6 to 27 days".
CLOSE_DAYS_P05, CLOSE_DAYS_P95 = 6.0, 27.0

# Yearly seasonality: two switchover peaks, a summer lull and a soft winter need
# three Fourier modes. Seasons shift by latitude, so each market gets its own
# curve, partially pooled toward the shared Midwest shape.
FOURIER_MODES = 3

# Close weeks with a visible dip in national won deals (holiday leads closing late).
HOLIDAY_CLOSE_WEEKS = {"wk52": (52, 53), "wk01": (1,), "wk02": (2,), "wk03": (3,)}

# Hill slope prior (median, log-sd) by dim_channel.marketing_role. Performance
# channels harvest intent that already exists, so their first dollar is their best:
# concave. Brand channels can need a threshold of reach before they work: S-shapes
# allowed. 90% ranges: performance 0.55 to 1.47, brand 0.84 to 2.66.
SLOPE_PRIOR_BY_ROLE = {"performance": (0.9, 0.3), "brand": (1.5, 0.35)}
SLOPE_PRIOR_DEFAULT = (1.2, 0.4)

# Spend multipliers for response curves; 1.0 is the actual in-window path.
RESPONSE_MULTIPLIERS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]

# Budget shift guardrails: no channel moves more than half its own spend.
OPT_BOUNDS = (0.5, 1.5)

SAMPLER = {"chains": 4, "draws": 1000, "tune": 1500, "target_accept": 0.95, "random_seed": 4}

GATES = {
    "rhat_max": 1.01,
    "ess_bulk_min": 400,
    "ess_tail_min": 400,
    "divergence_rate_max": 0.001,
    # share of region-weeks inside the 90% posterior predictive interval
    "ppc_coverage_range": (0.85, 0.97),
    "holdout_national_mape_max": 0.10,
    "holdout_coverage_range": (0.80, 0.98),
}


@lru_cache(maxsize=1)
def lead_to_close_kernel() -> np.ndarray:
    """P(deal closes k weeks after the lead's week), k = 0..LAG_WEEKS-1.

    A gamma lag in days matched to the README's 5th and 95th percentiles, with the
    lead created on a uniform day of its week.
    """

    def ratio_gap(log_shape: float) -> float:
        a = np.exp(log_shape)
        return stats.gamma.ppf(0.95, a) / stats.gamma.ppf(0.05, a) - CLOSE_DAYS_P95 / CLOSE_DAYS_P05

    shape = float(np.exp(optimize.brentq(ratio_gap, np.log(0.5), np.log(200.0))))
    scale = CLOSE_DAYS_P05 / stats.gamma.ppf(0.05, shape)
    days = np.arange(0, 7 * (LAG_WEEKS + 2) + 1)
    lag_pmf = np.diff(stats.gamma.cdf(np.append(days, days[-1] + 1), shape, scale=scale))
    week_pmf = np.zeros(LAG_WEEKS + 3)
    for start_day in range(7):
        for d, p in zip(days, lag_pmf):
            week_pmf[min((start_day + d) // 7, len(week_pmf) - 1)] += p / 7
    kernel = week_pmf[:LAG_WEEKS]
    return kernel / kernel.sum()
