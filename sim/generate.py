"""Seeded simulator for Fernhook's ad spend, platform reports, controls, CRM funnel
and the answer key.

One numpy Generator drives every draw, in a fixed order, so a seed always produces
the same bytes. The true effects (adstock, saturation, lead quality, control
elasticities) live only in the returned truth dict; the raw tables carry only what
a real company could export.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from . import config as C

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_TRUTH_PATH = REPO_ROOT / "sim" / "truth" / "truth.json"

RESPONSE_MULTIPLIERS = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]


@dataclass
class SimResult:
    tables: dict[str, pd.DataFrame]
    truth: dict
    # Internal arrays a later period needs to carry on from this one (sim/extend.py).
    # Never written anywhere.
    state: dict | None = None
    truth_2026: dict | None = None


# --- small helpers ------------------------------------------------------------

def _adstock(x: np.ndarray, alpha: float, l_max: int) -> np.ndarray:
    w = alpha ** np.arange(l_max)
    w = w / w.sum()
    out = np.zeros_like(x, dtype=float)
    for lag in range(l_max):
        out[lag:] += w[lag] * x[: len(x) - lag]
    return out


def _hill(x: np.ndarray, k: float, s: float) -> np.ndarray:
    xs = np.power(x, s)
    return xs / (xs + k**s)


def _ar1(rng: np.random.Generator, t: int, r: int, sigma: float, rho: float) -> np.ndarray:
    out = np.zeros((t, r))
    out[0] = rng.normal(0.0, sigma, r)
    shocks = rng.normal(0.0, sigma * np.sqrt(1 - rho**2), (t, r))
    for i in range(1, t):
        out[i] = rho * out[i - 1] + shocks[i]
    return out


def _season_log(sp: dict, woy: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Log seasonal demand (T, R): spring and fall switchover humps, the summer lull
    and the winter dip, each moved by latitude and by the market's own offset."""
    dlat = lat - C.SEASON["ref_latitude"]
    offset = np.array(sp["market_offset_weeks"])
    shift = {"spring_peak": sp["spring_weeks_per_degree"] * dlat + offset,
             "fall_peak": -sp["fall_weeks_per_degree"] * dlat + offset,
             "winter_dip": offset}
    shift["summer_lull"] = (shift["spring_peak"] + shift["fall_peak"]) / 2
    out = np.zeros((woy.size, lat.size))
    for key, sign in (("spring_peak", 1.0), ("fall_peak", 1.0), ("summer_lull", -1.0), ("winter_dip", -1.0)):
        b = sp[key]
        d = woy[:, None] - (b["week"] + shift[key][None, :])
        d = (d + 26.0) % 52.0 - 26.0
        out += sign * b["size"] * np.exp(-0.5 * (d / b["width"]) ** 2)
    return out


def _brand_flighting(rng, f: dict, cal: dict, lat: np.ndarray, region_ok: np.ndarray,
                     keep: dict | None = None, habits: dict | None = None) -> np.ndarray:
    """Spend shape (T, R) for a brand channel: a push ahead of and into each planned
    busy season, a sustain level between pushes, and a soft level in slow weeks.

    habits: a market-bought channel's per-market timing and size, carried over from an
    earlier period instead of drawn. keep: receives them."""
    t_total, n_reg = cal["T"], lat.size
    m = np.repeat(np.where(cal["slow"], f["slow"], f["sustain"])[:, None], n_reg, axis=1)
    pl = C.PLANNING
    dlat = lat - pl["ref_latitude"]
    lo, hi = f["len"]
    if f["geo"] == "market":  # each market's own habit: some push early or big every year
        if habits is None:
            market_shift = rng.normal(0.0, f["market_timing_sigma"], n_reg)
            market_shift -= market_shift[region_ok].mean()  # markets differ around the plan, not all early
            market_size = np.exp(rng.normal(0.0, f["market_mult_sigma"], n_reg))
        else:
            market_shift, market_size = habits["market_shift"], habits["market_size"]
        if keep is not None:
            keep["habits"] = {"market_shift": market_shift, "market_size": market_size}
    for y in cal["iso_years"]:
        for season in ("spring", "fall"):
            if f["geo"] == "national":
                start = np.full(n_reg, pl[f"{season}_peak_week"] - f["lead"] + rng.normal(0.0, f["timing_sigma"]))
                length = np.full(n_reg, int(rng.integers(lo, hi + 1)))
                amp = np.full(n_reg, f["mult"] * float(np.exp(rng.normal(0.0, f["mult_sigma"]))))
                amp[rng.random(n_reg) >= f["market_share"]] = np.nan  # market left out of this flight
            else:
                peak = pl[f"{season}_peak_week"] + pl[f"{season}_weeks_per_degree"] * dlat
                start = peak - f["lead"] + market_shift + rng.normal(0.0, f["timing_sigma"], n_reg)
                length = rng.integers(lo, hi + 1, n_reg)
                season_size = float(np.exp(rng.normal(0.0, f["season_sigma"])))  # this season's national budget
                amp = f["mult"] * season_size * market_size * np.exp(rng.normal(0.0, f["mult_sigma"], n_reg))
            for j in range(n_reg):
                if np.isnan(amp[j]):
                    continue
                a = cal["iso_week1"][y] + int(round(start[j])) - 1
                b = min(a + int(length[j]), t_total)
                if b > max(a, 0):
                    m[max(a, 0) : b, j] = amp[j]
    return m


def _categorical(rng, probs: np.ndarray, rows: np.ndarray) -> np.ndarray:
    """Draw one category per element; probs is (n_groups, n_cats), rows picks the group."""
    cum = np.cumsum(probs, axis=1)
    cum[cum > 1.0 - 1e-9] = 1.0  # float drift must never select a zero-probability tail slot
    u = rng.random(rows.size)
    return (u[:, None] > cum[rows]).sum(axis=1)


def _date_str(d: np.ndarray) -> np.ndarray:
    s = np.datetime_as_string(d, unit="D")
    return np.where(np.isnat(d), "", s)


def _r(x: float, nd: int = 4) -> float:
    return float(round(float(x), nd))


def _monday_of_iso_week(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


# --- true parameters ----------------------------------------------------------

def _draw_true_params(rng: np.random.Generator, n_reg: int) -> dict:
    """Every true effect, drawn from the config ranges in a fixed order."""
    def uni(lo_hi):
        return float(rng.uniform(*lo_hi))

    def log_uni(lo_hi):
        return float(np.exp(rng.uniform(np.log(lo_hi[0]), np.log(lo_hi[1]))))

    effect = {}
    for ch in C.PAID_CHANNELS:
        r = C.EFFECT_RANGES[ch]
        effect[ch] = {"alpha": round(uni(r["alpha"]), 3), "K": round(log_uni(r["K"]), -1),
                      "S": round(uni(r["S"]), 3), "cpa": round(log_uni(r["cpa"]), 2)}
    jit = C.FUNNEL_JITTER
    funnel = {}
    for o in C.ORIGINS:
        f = C.FUNNEL[o]
        funnel[o] = {k: round(min(f[k] * float(np.exp(rng.normal(0.0, jit["rate_sigma"]))), 0.95), 4)
                     for k in ("p_mql", "p_sql", "p_opp", "p_won")}
        funnel[o]["amount_mult"] = round(f["amount_mult"] * float(np.exp(rng.normal(0.0, jit["amount_sigma"]))), 4)
    s = C.SEASON
    season = {k: {"week": round(uni(s[k]["week"]), 2), "size": round(uni(s[k]["size"]), 3),
                  "width": round(uni(s[k]["width"]), 2)}
              for k in ("spring_peak", "fall_peak", "summer_lull", "winter_dip")}
    season["spring_weeks_per_degree"] = round(uni(s["spring_weeks_per_degree"]), 3)
    season["fall_weeks_per_degree"] = round(uni(s["fall_weeks_per_degree"]), 3)
    offset_sigma = uni(s["market_offset_sigma_weeks"])
    season["market_offset_sigma_weeks"] = round(offset_sigma, 3)
    season["market_offset_weeks"] = [round(float(v), 2) for v in rng.normal(0.0, offset_sigma, n_reg)]
    params = {
        "season": season,
        "effect": effect,
        "funnel": funnel,
        "base_growth": round(uni(C.BASE["growth_per_year_range"]), 4),
        "macro_elasticity": round(uni(C.MACRO["demand_elasticity_range"]), 3),
        "sdr_elasticity": round(uni(C.SALES["sdr_elasticity_range"]), 3),
        "ae_elasticity": round(uni(C.SALES["ae_elasticity_range"]), 3),
        "email_alpha": round(uni(C.EMAIL["alpha_range"]), 3),
        "email_K": round(log_uni(C.EMAIL["K_range"]), -1),
        "year_end_win_mult": round(uni(C.PROMO["year_end_win_mult_range"]), 3),
        "price_win_mult": round(uni(C.PROMO["price_win_mult_range"]), 3),
    }
    params["brand_searches"] = {
        ch: {"alpha": round(uni(r["alpha"]), 3), "reach_spend": round(log_uni(r["reach_spend"]), -1),
             "lift": round(uni(r["lift"]), 4)}
        for ch, r in C.BRAND_SEARCH["created_by"].items()}
    params["nonbrand_quality_slope"] = round(uni(C.NONBRAND_QUALITY["slope_range"]), 3)
    return params


# --- spend ------------------------------------------------------------------

def _planned_spend(rng, ch: str, cal: dict, size: np.ndarray, region_ok: np.ndarray,
                   lat: np.ndarray, keep: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Actual spend (T, R) and the national plan it was bought against (T,).

    keep: receives the channel's buying habits (market split, noise state, quarter
    draws) so a later period can carry on from them. It changes no draw."""
    p = C.SPEND[ch]
    t_total, n_reg = cal["T"], size.size
    budget = p["annual_budget"]
    year = np.maximum(cal["year_of"], min(budget))  # burn-in weeks run at the first year's pace
    q_draw = np.exp(rng.normal(0.0, p["quarter_sigma"], cal["quarter"].max() + 1))
    q_mult = q_draw[cal["quarter"]]
    plan = np.array([budget[y] for y in year]) / 52.0 * cal["event_mult"][ch] * cal["holiday_cut"]
    national = plan * q_mult * np.exp(rng.normal(0.0, p["weekly_sigma"], t_total))
    tilt = np.exp(rng.normal(0.0, p["tilt_sigma"], n_reg))
    alloc = size * tilt * region_ok
    alloc = alloc / alloc.sum()
    log_noise = _ar1(rng, t_total, n_reg, p["region_sigma"], 0.6)
    noise = np.exp(log_noise)

    resplit = None
    if p["flight"] == "seasonal_push":
        shape = _brand_flighting(rng, p["push"], cal, lat, region_ok, keep)
    else:
        n_q = cal["quarter"].max() + 1
        resplit = np.exp(rng.normal(0.0, p["quarter_region_sigma"], (n_q, n_reg)))
        resplit = resplit / (resplit * alloc).sum(axis=1, keepdims=True)  # moves budget between markets, not the total
        shape = cal["season"] ** p["season_follow"] * resplit[cal["quarter"]]
    # The budget sets the average week, so the shape only moves spend around the year.
    shape = shape / (shape[cal["win"]] * alloc).sum(axis=1).mean()
    x = national[:, None] * alloc[None, :] * shape * noise
    x = _pace(x, cal["year_of"], budget)
    x = np.round(x, 2)
    x[x < 10.0] = 0.0  # platforms do not serve tiny budgets
    if keep is not None:
        last = max(budget)
        weeks_last = int((cal["year_of"] == last).sum())
        keep.update(alloc=alloc, log_noise_last=log_noise[-1].copy(), q_mult_last=float(q_draw[-1]),
                    resplit_last=None if resplit is None else resplit[-1].copy(),
                    weekly_level_last=float(budget[last] / weeks_last / cal["holiday_cut"][cal["year_of"] == last].mean()))
    return x, plan


def _pace(x: np.ndarray, year_of: np.ndarray, budget: dict) -> np.ndarray:
    """Scale each year's weeks so the year adds up to its budget. Burn-in weeks before
    the first budget year take the first year's factor."""
    x = x.copy()
    first = min(budget)
    for y in sorted(budget):
        rows = year_of == y
        f = budget[y] / x[rows].sum()
        x[rows] *= f
        if y == first:
            x[year_of < first] *= f
    return x


def _depth_price(m: dict, x: np.ndarray, size: np.ndarray) -> np.ndarray | float:
    """CPM multiplier for a channel whose auctions get pricier as it buys deeper."""
    if "depth_ref" not in m:
        return 1.0
    depth = np.maximum(x / (size[None, :] * m["depth_ref"]), 0.25)
    return depth ** m["depth_elasticity"]


def _nonbrand_quality(x: np.ndarray, size: np.ndarray, slope: float) -> np.ndarray:
    """Lead quality of non-brand search leads by week and market (1 = full quality)."""
    depth = x / (size[None, :] * C.NONBRAND_QUALITY["ref_spend"])
    return 1.0 / (1.0 + slope * np.maximum(depth - 1.0, 0.0))


# --- simulation ---------------------------------------------------------------

def simulate(seed: int = C.DEFAULT_SEED, keep_state: bool = False) -> SimResult:
    """The 2023 to 2025 world. keep_state also returns the internal arrays that
    sim/extend.py needs to run the world on into 2026; the tables and truth are the
    same either way."""
    # Two child streams: one draws the hidden true parameters, one draws the data.
    truth_seq, data_seq = np.random.SeedSequence(seed).spawn(2)
    tp = _draw_true_params(np.random.default_rng(truth_seq), len(C.REGIONS))
    rng = np.random.default_rng(data_seq)

    # --- calendar and regions ---------------------------------------------------
    t_total = C.BURN_IN_WEEKS + C.N_WEEKS
    t0 = C.WINDOW_START - timedelta(weeks=C.BURN_IN_WEEKS)
    weeks = [t0 + timedelta(weeks=i) for i in range(t_total)]
    week_d = np.array(weeks, dtype="datetime64[D]")
    snapshot = np.datetime64(C.WINDOW_START + timedelta(weeks=C.N_WEEKS) - timedelta(days=1), "D")
    win = slice(C.BURN_IN_WEEKS, t_total)

    codes = [r[0] for r in C.REGIONS]
    names = [r[1] for r in C.REGIONS]
    states = [r[2] for r in C.REGIONS]
    areas = [r[3] for r in C.REGIONS]
    accounts = np.array([r[4] for r in C.REGIONS], dtype=float)
    lat = np.array([r[5] for r in C.REGIONS], dtype=float)
    n_reg = len(codes)
    size = accounts / accounts.mean()
    area_lead = np.array([C.AREA[a]["base_leads"] for a in areas])
    area_amount = np.array([C.AREA[a]["amount"] for a in areas])

    woy = np.array([w.isocalendar().week for w in weeks])
    iso_year = np.array([w.isocalendar().year for w in weeks])
    years = (np.arange(t_total) - C.BURN_IN_WEEKS) / 52.0
    quarter = np.array([(w.year - weeks[0].year) * 4 + (w.month - 1) // 3 for w in weeks])
    month_idx = np.array([(w.year - weeks[0].year) * 12 + w.month - weeks[0].month for w in weeks])
    is_q4 = np.array([w.month >= 10 for w in weeks])
    is_holiday = np.isin(woy, [52, 53, 1])
    holiday_cut = np.where(is_holiday, C.HOLIDAY_SPEND_CUT, 1.0)

    season = np.exp(_season_log(tp["season"], woy.astype(float), lat))  # (T, R)
    for wk, m in C.SEASON["holiday_weeks"].items():
        season[woy == wk] *= m
    slow = np.zeros(t_total, dtype=bool)
    for lo, hi in C.PLANNING["slow_weeks"]:
        slow |= (woy >= lo) & (woy <= hi)
    event_mult = {ch: np.ones(t_total) for ch in C.PLANNED_CHANNELS}
    for ev_date, _reason, changes in C.BUDGET_EVENTS:
        for ch, change in changes.items():
            event_mult[ch][week_d >= np.datetime64(ev_date, "D")] *= 1 + change
    iso_years = range(int(iso_year[0]), int(iso_year[-1]) + 1)
    cal = {"T": t_total, "win": win, "quarter": quarter, "season": season, "holiday_cut": holiday_cut,
           "slow": slow, "iso_years": iso_years,
           "iso_week1": {y: (date.fromisocalendar(y, 1, 1) - t0).days // 7 for y in iso_years},
           "year_idx": np.array([w.year - C.WINDOW_START.year for w in weeks]), "event_mult": event_mult,
           "year_of": np.array([w.year for w in weeks])}  # the house week rule: a week's year is its Monday's
    year_of = cal["year_of"]

    # --- planned spend and webinars -------------------------------------------
    spend: dict[str, np.ndarray] = {}
    plans: dict[str, np.ndarray] = {}
    habits: dict[str, dict] = {ch: {} for ch in C.PLANNED_CHANNELS}
    all_regions = np.ones(n_reg, dtype=bool)
    ctv_regions = np.isin(codes, C.CTV_REGIONS)
    for ch in C.PLANNED_CHANNELS:
        spend[ch], plans[ch] = _planned_spend(rng, ch, cal, size, ctv_regions if ch == "ctv" else all_regions, lat,
                                              keep=habits[ch])

    w_cfg = C.WEBINARS
    ev_rate = w_cfg["events_per_week_national"] * size / n_reg
    ev_counts = rng.poisson(np.broadcast_to(ev_rate, (t_total, n_reg)))
    nz_t, nz_r = np.nonzero(ev_counts)
    reps = ev_counts[nz_t, nz_r]
    ev_t, ev_r = np.repeat(nz_t, reps), np.repeat(nz_r, reps)
    n_ev = ev_t.size
    ev_cost = w_cfg["cost_median"] * np.exp(rng.normal(0.0, w_cfg["cost_sigma"], n_ev))
    ev_paced = _pace(ev_cost[:, None], year_of[ev_t], w_cfg["annual_budget"])[:, 0]  # events paced to the budget
    webinar_factor_last = float(ev_paced[year_of[ev_t] == max(w_cfg["annual_budget"])].sum()
                                / ev_cost[year_of[ev_t] == max(w_cfg["annual_budget"])].sum())
    ev_cost = np.round(ev_paced, 2)
    ev_day = rng.integers(1, 4, n_ev)  # Tue to Thu
    ev_topic = rng.integers(0, len(w_cfg["topics"]), n_ev)
    ev_regs = rng.poisson(ev_cost / w_cfg["cost_per_registrant"])
    ev_attend = rng.binomial(ev_regs, w_cfg["attend_rate"])
    web = np.zeros((t_total, n_reg))
    np.add.at(web, (ev_t, ev_r), ev_cost)
    spend["webinars"] = np.round(web, 2)

    # --- organic baseline and the market-activity index -----------------------
    b = C.BASE
    eta = _ar1(rng, t_total, 1, b["national_shock_sigma"], b["national_shock_rho"])[:, 0]
    eps = rng.normal(0.0, b["region_week_sigma"], (t_total, n_reg))
    trend = np.exp(tp["base_growth"] * years)
    mu_base = (b["leads_per_week_avg_region"] * size[None, :] * area_lead[None, :]
               * trend[:, None] * season * np.exp(eps + tp["macro_elasticity"] * eta[:, None]))
    fleet_index = np.round(C.MACRO["index_level"] * np.exp(eta + rng.normal(0.0, C.MACRO["measurement_sigma"], t_total)), 1)

    # --- sales capacity ---------------------------------------------------------
    s_cfg = C.SALES
    n_months = month_idx.max() + 1
    month_starts = [date(weeks[0].year + (weeks[0].month - 1 + m) // 12, (weeks[0].month - 1 + m) % 12 + 1, 1)
                    for m in range(n_months)]
    region_eff = rng.normal(0.0, s_cfg["region_sigma"], n_reg)
    area_off = np.array([s_cfg["area_offset"][a] for a in areas])
    counts_by_role, mult_by_role, cov_last = {}, {}, {}
    for role in ("sdr", "ae"):
        path = np.zeros(n_months)
        cov = s_cfg["start_coverage"]
        for m, ms in enumerate(month_starts):
            frozen = s_cfg["freeze"][0] <= ms <= s_cfg["freeze"][1]
            if m > 0:
                cov *= 1 - (s_cfg["freeze_attrition_per_month"] if frozen else s_cfg["attrition_per_month"])
                if ms.month in s_cfg["hiring_months"] and not frozen:
                    cov += s_cfg["hiring_gain_per_month"]
            path[m] = cov
        cov_last[role] = cov
        target = s_cfg[f"{role}_per_1k_accounts"] * accounts / 1000
        noise = rng.normal(0.0, s_cfg["month_sigma"], (n_months, n_reg))
        cov_r = path[:, None] * np.exp(area_off[None, :] + region_eff[None, :] + noise)
        count = np.maximum(1, np.round(cov_r * target[None, :])).astype(np.int64)
        lo_b, hi_b = s_cfg["mult_bounds"]
        mult = np.clip((count / target[None, :]) ** tp[f"{role}_elasticity"], lo_b, hi_b)
        counts_by_role[role] = count
        mult_by_role[role] = mult[month_idx]  # (T, R)
    sdr_mult, ae_mult = mult_by_role["sdr"], mult_by_role["ae"]

    # --- email -------------------------------------------------------------------
    e_cfg = C.EMAIL
    ye_lo, ye_hi = C.PROMO["year_end_weeks"]
    is_year_end = (woy >= ye_lo) & (woy <= ye_hi)
    blast = (rng.random(t_total) < e_cfg["blast_prob"]) | is_year_end
    list_size = e_cfg["list_per_avg_region"] * size[None, :] * np.exp(e_cfg["list_growth_per_year"] * years)[:, None]
    freq = (e_cfg["sends_per_contact_week"] + e_cfg["blast_extra"] * blast) * np.where(is_holiday, 0.6, 1.0)
    sends = np.round(list_size * freq[:, None] * np.exp(rng.normal(0.0, 0.05, (t_total, n_reg)))).astype(np.int64)
    open_rate = np.clip(e_cfg["open_rate_start"] + e_cfg["open_rate_drift_per_year"] * years
                        + rng.normal(0.0, 0.01, t_total), 0.05, 0.9)
    opens = rng.binomial(sends, open_rate[:, None])
    email_clicks = rng.binomial(opens, e_cfg["click_rate_of_opens"])
    a_email = _adstock(sends.astype(float), tp["email_alpha"], C.L_MAX)
    email_shape = size * _hill(a_email / size, tp["email_K"], e_cfg["S"])
    beta_email = e_cfg["leads_per_week_avg_region"] * C.N_WEEKS * size.sum() / email_shape[win].sum()
    mu_email = beta_email * email_shape

    # --- promo and price calendar (applies by lead created week) -------------------
    p_cfg = C.PROMO
    after_price = week_d >= np.datetime64(p_cfg["price_change_date"], "D")
    win_time = np.where(is_year_end, tp["year_end_win_mult"], 1.0) * np.where(after_price, tp["price_win_mult"], 1.0)
    amount_time = (np.where(is_year_end, 1 - p_cfg["year_end_discount_pct"] / 100, 1.0)
                   * np.where(after_price, 1 + p_cfg["price_change_pct"] / 100, 1.0))

    # --- conversion by origin, region and created week ---------------------------
    fp = {k: np.array([tp["funnel"][o][k] for o in C.ORIGINS]) for k in ("p_mql", "p_sql", "p_opp", "p_won", "amount_mult")}
    i_nb = C.ORIGINS.index("paid_search_nonbrand")
    quality_nb = _nonbrand_quality(spend["paid_search_nonbrand"], size, tp["nonbrand_quality_slope"])  # (T, R)
    q_half = np.ones((len(C.ORIGINS), t_total, n_reg))
    q_half[i_nb] = np.sqrt(quality_nb)  # half on the MQL rate, half on the win rate
    p_mql_eff = fp["p_mql"][:, None, None] * q_half  # (O, T, R)
    p_sql_eff = np.minimum(fp["p_sql"][:, None, None] * sdr_mult[None], 0.95)
    p_won_base = np.minimum(fp["p_won"][:, None, None] * ae_mult[None] * win_time[None, :, None], 0.95)
    p_won_eff = p_won_base * q_half
    p_opp_lead = p_mql_eff * p_sql_eff * fp["p_opp"][:, None, None]
    p_deal = p_opp_lead * p_won_eff
    p_deal_base = fp["p_mql"][:, None, None] * p_sql_eff * fp["p_opp"][:, None, None] * p_won_base  # before quality
    amount_mean = (C.AMOUNT_MEDIAN * np.exp(C.AMOUNT_SIGMA**2 / 2) * fp["amount_mult"][:, None, None]
                   * amount_time[None, :, None] * area_amount[None, None, :])

    def extend(a: np.ndarray) -> np.ndarray:  # carry the last week into the adstock tail
        return np.concatenate([a, np.repeat(a[-1:], C.L_MAX, axis=0)], axis=0)

    o_index = {o: i for i, o in enumerate(C.ORIGINS)}

    # --- true media effects, calibrated to the drawn CPA -----------------------
    pad = np.zeros((C.L_MAX, n_reg))
    mu_media: dict[str, np.ndarray] = {}
    channel_truth: dict[str, dict] = {}
    betas: dict[str, float] = {}
    direct_deals: dict = {}

    ref_year = C.WINDOW_START.year
    year_ext = np.concatenate([year_of, np.full(C.L_MAX, 0)])

    def fit_channel(ch: str) -> None:
        """beta is set so the channel's 2023 spend, run on its own, costs the drawn cpa
        per deal it causes. Later years' cost per deal is whatever the curve gives."""
        e = tp["effect"][ch]
        x_full = np.vstack([spend[ch], pad])
        x_burn = x_full.copy()
        x_burn[C.BURN_IN_WEEKS :] = 0.0
        a_full = _adstock(x_full, e["alpha"], C.L_MAX)
        a_burn = _adstock(x_burn, e["alpha"], C.L_MAX)
        a_win = a_full - a_burn
        base_resp = _hill(a_burn / size, e["K"], e["S"])
        i = o_index[ch]
        deal_base, amt_x = extend(p_deal_base[i]), extend(amount_mean[i])
        opp_base = extend(fp["p_mql"][i] * p_sql_eff[i] * fp["p_opp"][i])

        def quality(path: np.ndarray) -> np.ndarray:
            if ch != "paid_search_nonbrand":
                return np.ones_like(path)
            q = _nonbrand_quality(path[:t_total], size, tp["nonbrand_quality_slope"])
            return np.vstack([q, np.repeat(q[-1:], C.L_MAX, axis=0)])

        def lead_rate(path: np.ndarray) -> np.ndarray:  # leads per unit of beta, by week and market
            return size * _hill(_adstock(path, e["alpha"], C.L_MAX) / size, e["K"], e["S"])

        base_leads, base_q = size * base_resp, quality(x_burn)

        def deals_for(path: np.ndarray, beta: float = 1.0) -> float:
            """Deals the path causes against burn-in spend only (window weeks at zero)."""
            return float((beta * (lead_rate(path) * quality(path) - base_leads * base_q) * deal_base).sum())

        x_ref = x_burn.copy()
        x_ref[year_ext == ref_year] = x_full[year_ext == ref_year]
        spend_ref = float(spend[ch][year_of == ref_year].sum())
        beta = spend_ref / (e["cpa"] * deals_for(x_ref))
        mu_media[ch] = beta * size * _hill(a_full[:t_total] / size, e["K"], e["S"])
        betas[ch] = beta

        def deals(mult: float) -> float:
            return deals_for(x_burn + mult * (x_full - x_burn), beta)

        direct_deals[ch] = deals

        leads_1 = beta * size * (_hill(a_full / size, e["K"], e["S"]) - base_resp)
        q1 = quality(x_full)
        dealt = beta * (lead_rate(x_full) * q1 - base_leads * base_q)  # deal-weighted lead increments
        inc_deals = deals(1.0)
        inc_rev = float((dealt * deal_base * amt_x).sum())
        inc_pipe = float((leads_1 * opp_base * np.sqrt(q1) * amt_x).sum())
        spend_win = float(spend[ch][win].sum())
        by_year = {}
        for y in sorted(set(year_of[win])):
            x_wo = x_full.copy()
            x_wo[year_ext == y] = 0.0
            d = deals_for(x_full, beta) - deals_for(x_wo, beta)
            s_y = float(spend[ch][year_of == y].sum())
            by_year[str(y)] = {"spend": _r(s_y, 2), "incremental_deals": _r(d, 2),
                               "cpa": _r(s_y / d, 2) if d > 0 else None}
        f = tp["funnel"][ch]
        channel_truth[ch] = {
            "spend": _r(spend_win, 2),
            "incremental_leads": _r(leads_1.sum(), 2),
            "incremental_deals": _r(inc_deals, 2),
            "incremental_revenue": _r(inc_rev, 2),
            "incremental_pipeline": _r(inc_pipe, 2),
            "cpa": _r(spend_win / inc_deals, 2),
            "cpa_2023_reference": e["cpa"],
            "by_year": by_year,
            "marginal_cpa": _r(0.02 * spend_win / (deals(1.01) - deals(0.99)), 2),
            "roi_revenue": _r(inc_rev / spend_win),
            "roi_pipeline": _r(inc_pipe / spend_win),
            "cost_per_incremental_lead": _r(spend_win / leads_1.sum(), 2),
            "adstock": {"type": "geometric", "alpha": e["alpha"], "l_max": C.L_MAX, "normalized": True},
            "saturation": {"type": "hill", "half_saturation": e["K"], "slope": e["S"],
                           "input": "adstocked weekly spend / region size index"},
            "beta_leads_per_week_per_size_unit": _r(beta, 6),
            "lead_quality": {k: f[k] for k in ("p_mql", "p_sql", "p_opp", "p_won", "amount_mult")},
            **({"lead_quality_depth": {"ref_spend": C.NONBRAND_QUALITY["ref_spend"],
                                       "slope": tp["nonbrand_quality_slope"]}} if ch == "paid_search_nonbrand" else {}),
            "crm_last_touch_recording": C.CRM_ATTRIBUTION[ch],
            "platform_reporting": C.PLATFORM.get(ch, {"source": "webinar registrants",
                                                      "cost_per_registrant": w_cfg["cost_per_registrant"]}),
            "response_curve": {
                "spend_multiplier": RESPONSE_MULTIPLIERS,
                "spend": [_r(spend_win * m, 2) for m in RESPONSE_MULTIPLIERS],
                "incremental_deals": [_r(deals(m), 3) for m in RESPONSE_MULTIPLIERS],
            },
        }

    for ch in C.PLANNED_CHANNELS + ["webinars"]:
        fit_channel(ch)

    # --- brand searches: baseline demand plus what the upper funnel creates ------
    bs = C.BRAND_SEARCH
    search_drivers = list(bs["created_by"])
    cost_noise = np.exp(rng.normal(0.0, bs["noise_sigma"], (t_total, n_reg)))

    def reach(ch: str, x: np.ndarray) -> np.ndarray:
        h = tp["brand_searches"][ch]
        a = _adstock(x, h["alpha"], C.L_MAX)
        return size * (1.0 - np.exp(-a / (h["reach_spend"] * size)))

    gamma = {ch: tp["brand_searches"][ch]["lift"] * float(mu_base[win].sum()) / float(reach(ch, spend[ch])[win].sum())
             for ch in search_drivers}

    def brand_searches(paths: dict[str, np.ndarray]) -> np.ndarray:
        return mu_base + sum(gamma[ch] * reach(ch, paths[ch]) for ch in search_drivers)

    searches = brand_searches(spend)
    # One cost per search per year, set so the year's brand-search spend lands on budget;
    # within the year spend follows searches. Burn-in weeks use the first year's.
    raw = searches * cost_noise
    cps = np.zeros(t_total)
    for y, target in bs["annual_budget"].items():
        cps[year_of == y] = target / float(raw[year_of == y].sum())
    first_bs = min(bs["annual_budget"])
    cps[year_of < first_bs] = cps[year_of == first_bs][0]
    cost_per_search = float(cps[year_of == max(bs["annual_budget"])][0])

    def brand_spend(s: np.ndarray) -> np.ndarray:
        x = np.round(s * cost_noise * cps[:, None], 2)
        x[x < 25.0] = 0.0
        return x

    spend["paid_search_brand"] = brand_spend(searches)
    fit_channel("paid_search_brand")

    e_b = tp["effect"]["paid_search_brand"]
    brand_deal_x = extend(p_deal[o_index["paid_search_brand"]])

    def brand_search_deals(x: np.ndarray) -> float:
        a = _adstock(np.vstack([x, pad]), e_b["alpha"], C.L_MAX)
        return float((betas["paid_search_brand"] * size * _hill(a / size, e_b["K"], e_b["S"]) * brand_deal_x).sum())

    def via_brand_search(ch: str, mult: float) -> float:
        """Brand-search deals from the brand searches this channel's in-window spend creates,
        with that spend scaled by mult, against the same path with it removed."""
        def path(m: float) -> np.ndarray:
            x = spend[ch].copy()
            x[win] *= m
            return brand_spend(brand_searches({**spend, ch: x}))
        return brand_search_deals(path(mult)) - brand_search_deals(path(0.0))

    created_win = {ch: float((gamma[ch] * reach(ch, spend[ch]))[win].sum()) for ch in search_drivers}
    for ch in search_drivers:
        t_ch = channel_truth[ch]
        spend_win = t_ch["spend"]

        def total(m: float, ch: str = ch) -> float:
            return direct_deals[ch](m) + via_brand_search(ch, m)

        via = via_brand_search(ch, 1.0)
        tot = direct_deals[ch](1.0) + via
        t_ch["brand_searches_created"] = _r(created_win[ch], 2)
        t_ch["incremental_deals_via_brand_search"] = _r(via, 2)
        t_ch["incremental_deals_total"] = _r(tot, 2)
        t_ch["cpa_total"] = _r(spend_win / tot, 2)
        t_ch["marginal_cpa_total"] = _r(0.02 * spend_win / (total(1.01) - total(0.99)), 2)
        h = tp["brand_searches"][ch]
        t_ch["brand_search_creation"] = {
            "type": "reach", "alpha": h["alpha"], "l_max": C.L_MAX, "reach_spend": h["reach_spend"],
            "lift_over_baseline_searches": h["lift"], "gamma": _r(gamma[ch], 6)}
        t_ch["response_curve_total"] = {
            "spend_multiplier": RESPONSE_MULTIPLIERS,
            "spend": [_r(spend_win * m, 2) for m in RESPONSE_MULTIPLIERS],
            "incremental_deals": [_r(total(m), 3) for m in RESPONSE_MULTIPLIERS],
        }
    channel_truth = {ch: channel_truth[ch] for ch in C.PAID_CHANNELS}

    # --- leads ---------------------------------------------------------------
    mu_origin = {"base": mu_base, "email": mu_email, **mu_media}
    mu = np.stack([mu_origin[o] for o in C.ORIGINS], axis=2)  # (T, R, O)
    counts = rng.poisson(mu)
    flat_idx = np.repeat(np.arange(counts.size), counts.ravel())
    lt, lr, lo_ = np.unravel_index(flat_idx, counts.shape)
    n = flat_idx.size
    day = rng.choice(7, size=n, p=np.array(C.WEEKDAY_WEIGHTS) / sum(C.WEEKDAY_WEIGHTS))
    created = week_d[lt] + day.astype("timedelta64[D]")

    attr = np.array([[C.CRM_ATTRIBUTION[o].get(k, 0.0) for k in C.CRM_CHANNELS] for o in C.ORIGINS])
    rec = _categorical(rng, attr, lo_)
    max_v = max(len(v) for v in C.UTM_VARIANTS.values())
    vprob = np.zeros((len(C.CRM_CHANNELS), max_v))
    vsrc, vmed, vcamp = (np.full((len(C.CRM_CHANNELS), max_v), "", dtype=object) for _ in range(3))
    for k, ch in enumerate(C.CRM_CHANNELS):
        for j, ((src, med, camp), p) in enumerate(C.UTM_VARIANTS[ch]):
            vprob[k, j], vsrc[k, j], vmed[k, j], vcamp[k, j] = p, src, med, camp
    var = _categorical(rng, vprob, rec)
    utm_source, utm_medium, utm_campaign = vsrc[rec, var], vmed[rec, var], vcamp[rec, var]

    u = rng.random((4, n))
    is_mql = u[0] < p_mql_eff[lo_, lt, lr]
    is_sql = is_mql & (u[1] < p_sql_eff[lo_, lt, lr])
    is_opp = is_sql & (u[2] < fp["p_opp"][lo_])
    is_won = is_opp & (u[3] < p_won_eff[lo_, lt, lr])

    def lag(key: str) -> np.ndarray:
        shape, scale_ = C.LAGS[key]
        return np.floor(rng.gamma(shape, scale_, n)).astype("timedelta64[D]")

    mql_date = created + lag("mql")
    sql_date = mql_date + lag("sql")
    opp_date = sql_date + lag("opp")
    lag_won, lag_lost = lag("close_won"), lag("close_lost")
    close_date = opp_date + np.where(is_won, lag_won, lag_lost)
    amount = (C.AMOUNT_MEDIAN * fp["amount_mult"][lo_] * area_amount[lr] * amount_time[lt]
              * np.exp(rng.normal(0.0, C.AMOUNT_SIGMA, n)))
    amount = np.round(amount / 10.0) * 10.0

    nat = np.datetime64("NaT", "D")
    mql_obs = np.where(is_mql & (mql_date <= snapshot), mql_date, nat)
    sql_obs = np.where(is_sql & (sql_date <= snapshot), sql_date, nat)
    opp_exists = is_opp & (opp_date <= snapshot)
    closed = opp_exists & (close_date <= snapshot)

    # Shuffle before the stable sort so lead ids carry no trace of true origin.
    perm = rng.permutation(n)
    order = perm[np.argsort(created[perm], kind="stable")]
    lead_ids = np.array([f"LD{i:07d}" for i in range(1, n + 1)], dtype=object)
    lead_id_of = np.empty(n, dtype=object)
    lead_id_of[order] = lead_ids

    leads_df = pd.DataFrame({
        "lead_id": lead_ids,
        "created_date": _date_str(created[order]),
        "region_code": np.array(codes, dtype=object)[lr[order]],
        "utm_source": utm_source[order],
        "utm_medium": utm_medium[order],
        "utm_campaign": utm_campaign[order],
        "mql_date": _date_str(mql_obs[order]),
        "sql_date": _date_str(sql_obs[order]),
    })

    opp_rows = order[opp_exists[order]]
    opp_rows = opp_rows[np.argsort(opp_date[opp_rows], kind="stable")]
    stage = np.where(~closed[opp_rows], "Open", np.where(is_won[opp_rows], "Closed Won", "Closed Lost"))
    opps_df = pd.DataFrame({
        "opportunity_id": [f"OP{i:06d}" for i in range(1, opp_rows.size + 1)],
        "lead_id": lead_id_of[opp_rows],
        "created_date": _date_str(opp_date[opp_rows]),
        "amount": amount[opp_rows],
        "stage": stage,
        "close_date": _date_str(np.where(closed[opp_rows], close_date[opp_rows], nat)),
    })

    # --- platform-reported conversions and delivery metrics -----------------
    reported: dict[str, np.ndarray] = {}
    for ch in C.PLATFORM_CHANNELS:
        p = C.PLATFORM[ch]
        reach = 1.0 - np.exp(-spend[ch] / (p["reach_spend"] * size[None, :]))
        rate = p["claim_mult"] * mu_media[ch] + p["halo"] * mu_base * reach
        for src, share in p["halo_from"].items():
            rate = rate + share * mu_media[src] * (spend[ch] > 0)
        if p["noise_sigma"] > 0:
            rate = rate * np.exp(rng.normal(0.0, p["noise_sigma"], (t_total, n_reg)))
        reported[ch] = rng.poisson(rate)

    delivery: dict[str, dict[str, np.ndarray]] = {}
    for ch in ("paid_search_brand", "paid_search_nonbrand", "meta", "linkedin", "youtube", "display"):
        m = C.MEDIA[ch]
        cpm = m["cpm"] * (1 + C.Q4_CPM_LIFT * is_q4)[:, None] * np.exp(rng.normal(0.0, 0.08, (t_total, n_reg)))
        cpm = cpm * _depth_price(m, spend[ch], size)
        impressions = np.round(spend[ch] / cpm * 1000).astype(np.int64)
        ctr = np.clip(m["ctr"] * np.exp(rng.normal(0.0, 0.10, (t_total, n_reg))), 0, 1)
        delivery[ch] = {"impressions": impressions, "clicks": rng.binomial(impressions, ctr)}
    dda_noise = np.exp(rng.normal(0.0, 0.05, (t_total, n_reg)))
    post_click = rng.binomial(reported["display"], 1 - C.DISPLAY_POST_VIEW_SHARE)
    ctv_impr = np.round(spend["ctv"] / C.MEDIA["ctv"]["cpm"] * 1000
                        * np.exp(rng.normal(0.0, 0.06, (t_total, n_reg)))).astype(np.int64)
    ctv_views = rng.binomial(ctv_impr, C.MEDIA["ctv"]["completion_rate"])
    partner_clicks = rng.poisson(spend["affiliates"] / C.MEDIA["affiliates"]["cpc"])

    # --- raw tables ------------------------------------------------------------
    week_str = _date_str(week_d)
    code_arr = np.array(codes, dtype=object)
    name_arr = np.array(names, dtype=object)

    def rows(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        tt, rr = np.nonzero(x[win] > 0)
        return tt + C.BURN_IN_WEEKS, rr

    google_parts = []
    for ch, ctype, cname in (("paid_search_brand", "SEARCH", "FH_Search_Brand"),
                             ("paid_search_nonbrand", "SEARCH", "FH_Search_NonBrand"),
                             ("youtube", "VIDEO", "FH_YouTube_Prospecting")):
        tt, rr = rows(spend[ch])
        google_parts.append(pd.DataFrame({
            "week_start_date": week_str[tt],
            "geo_target_region": code_arr[rr],
            "campaign_type": ctype,
            "campaign_name": cname,
            "cost_micros": np.round(spend[ch][tt, rr] * 1_000_000).astype(np.int64),
            "impressions": delivery[ch]["impressions"][tt, rr],
            "clicks": delivery[ch]["clicks"][tt, rr],
            "conversions": np.round(reported[ch][tt, rr] * dda_noise[tt, rr], 2),
        }))
    google_df = (pd.concat(google_parts, ignore_index=True)
                 .sort_values(["week_start_date", "geo_target_region", "campaign_name"], kind="stable")
                 .reset_index(drop=True))

    tt, rr = rows(spend["meta"])
    meta_df = pd.DataFrame({
        "date_start": week_str[tt],
        "date_stop": _date_str(week_d[tt] + np.timedelta64(6, "D")),
        "region": name_arr[rr],
        "spend": spend["meta"][tt, rr],
        "impressions": delivery["meta"]["impressions"][tt, rr],
        "clicks": delivery["meta"]["clicks"][tt, rr],
        "leads": reported["meta"][tt, rr],
    })

    tt, rr = rows(spend["linkedin"])
    linkedin_df = pd.DataFrame({
        "start_date": week_str[tt],
        "region_code": code_arr[rr],
        "cost_usd": spend["linkedin"][tt, rr],
        "impressions": delivery["linkedin"]["impressions"][tt, rr],
        "clicks": delivery["linkedin"]["clicks"][tt, rr],
        "conversions": reported["linkedin"][tt, rr],
    })

    tt, rr = rows(spend["display"])
    display_df = pd.DataFrame({
        "week": week_str[tt],
        "region_code": code_arr[rr],
        "media_cost": spend["display"][tt, rr],
        "impressions": delivery["display"]["impressions"][tt, rr],
        "clicks": delivery["display"]["clicks"][tt, rr],
        "post_click_conversions": post_click[tt, rr],
        "post_view_conversions": reported["display"][tt, rr] - post_click[tt, rr],
    })

    tt, rr = rows(spend["ctv"])
    ctv_df = pd.DataFrame({
        "week_start": week_str[tt],
        "geo_region": code_arr[rr],
        "spend": spend["ctv"][tt, rr],
        "impressions": ctv_impr[tt, rr],
        "completed_views": ctv_views[tt, rr],
        "attributed_leads": reported["ctv"][tt, rr],
    })

    tt, rr = rows(spend["affiliates"])
    partners_df = pd.DataFrame({
        "week_start": week_str[tt],
        "region_code": code_arr[rr],
        "partner_fees": spend["affiliates"][tt, rr],
        "partner_clicks": partner_clicks[tt, rr],
        "referred_signups": reported["affiliates"][tt, rr],
    })

    keep = ev_t >= C.BURN_IN_WEEKS
    ev_date = week_d[ev_t] + ev_day.astype("timedelta64[D]")
    ev_order = np.lexsort((ev_r[keep], ev_date[keep]))
    webinar_df = pd.DataFrame({
        "event_id": [f"WB{i:04d}" for i in range(1, keep.sum() + 1)],
        "event_date": _date_str(ev_date[keep][ev_order]),
        "region_code": code_arr[ev_r[keep][ev_order]],
        "topic": np.array(w_cfg["topics"], dtype=object)[ev_topic[keep][ev_order]],
        "total_cost": ev_cost[keep][ev_order],
        "registrants": ev_regs[keep][ev_order],
        "attendees": ev_attend[keep][ev_order],
    })

    first_month = month_idx[C.BURN_IN_WEEKS]
    m_rows = np.arange(first_month, n_months)
    sales_df = pd.DataFrame({
        "month_start": np.repeat([str(month_starts[m]) for m in m_rows], n_reg),
        "region_code": np.tile(codes, m_rows.size),
        "sdr_headcount": counts_by_role["sdr"][m_rows].ravel(),
        "ae_headcount": counts_by_role["ae"][m_rows].ravel(),
    })

    email_df = pd.DataFrame({
        "week_start": np.repeat(week_str[win], n_reg),
        "region_code": np.tile(codes, C.N_WEEKS),
        "emails_sent": sends[win].ravel(),
        "unique_opens": opens[win].ravel(),
        "unique_clicks": email_clicks[win].ravel(),
    })

    promo_rows = []
    for yr in range(C.WINDOW_START.year, weeks[-1].year + 1):
        promo_rows.append({
            "promo_id": f"YE{yr}",
            "promo_name": f"Year-end annual plan offer {yr}",
            "promo_type": "discount",
            "start_date": str(_monday_of_iso_week(yr, ye_lo)),
            "end_date": str(_monday_of_iso_week(yr, ye_hi) + timedelta(days=6)),
            "discount_pct": p_cfg["year_end_discount_pct"],
            "price_change_pct": "",
        })
    promo_rows.append({
        "promo_id": f"PRICE{p_cfg['price_change_date'].year}",
        "promo_name": "List price increase",
        "promo_type": "price_change",
        "start_date": str(p_cfg["price_change_date"]),
        "end_date": "",
        "discount_pct": "",
        "price_change_pct": p_cfg["price_change_pct"],
    })
    promo_df = pd.DataFrame(promo_rows)

    plan_rows = [{"change_date": str(ev_date), "channel": ch, "budget_change_pct": round(change * 100), "reason": reason}
                 for ev_date, reason, changes in C.BUDGET_EVENTS for ch, change in changes.items()]
    plan_changes_df = pd.DataFrame(plan_rows)

    index_df = pd.DataFrame({"week_start": week_str[win], "fleet_activity_index": fleet_index[win]})

    regions_df = pd.DataFrame({
        "region_code": codes,
        "region_name": names,
        "state": states,
        "sales_area": areas,
        "target_accounts": accounts.astype(np.int64),
        "latitude": lat,
    })

    tables = {
        "regions": regions_df,
        "ads_google_weekly": google_df,
        "ads_meta_weekly": meta_df,
        "ads_linkedin_weekly": linkedin_df,
        "ads_display_weekly": display_df,
        "ctv_weekly": ctv_df,
        "partners_weekly": partners_df,
        "webinar_events": webinar_df,
        "crm_leads": leads_df,
        "crm_opportunities": opps_df,
        "sales_capacity_monthly": sales_df,
        "email_weekly": email_df,
        "promo_calendar": promo_df,
        "media_plan_changes": plan_changes_df,
        "fleet_activity_index_weekly": index_df,
    }

    # --- answer key ----------------------------------------------------------
    def expected_deals(origin: str) -> float:
        i = o_index[origin]
        return float((mu_origin[origin][win] * p_deal[i][win]).sum())

    base_deals, email_deals = expected_deals("base"), expected_deals("email")
    paid_deals = sum(v["incremental_deals"] for v in channel_truth.values())
    paid_spend = sum(v["spend"] for v in channel_truth.values())
    truth = {
        "company": C.COMPANY,
        "seed": seed,
        "window": {
            "first_week": str(C.WINDOW_START),
            "last_week": str(weeks[-1]),
            "weeks": C.N_WEEKS,
            "crm_snapshot_date": str(snapshot),
        },
        "model_frame": {
            "dependent_variable": "closed-won deals by region and week (fct_funnel.won_deals)",
            "independent_variables": "weekly spend per paid channel (fct_channel_weekly.spend)",
            "controls": ["sdr_headcount", "ae_headcount", "emails_sent", "is_year_end_promo",
                         "list_price_index", "fleet_activity_index", "seasonality", "trend"],
        },
        "definitions": {
            "cpa": "in-window spend divided by the expected closed-won deals it causes",
            "cpa_2023_reference": "the drawn cost per deal: 2023 spend divided by the deals 2023 spend causes on its own. beta is set to hit it, so later years cost whatever the curve gives",
            "by_year": "per year (weeks by their Monday): that year's spend, the deals it causes (all spend minus the same path with that year's weeks at zero) and their ratio",
            "nonbrand_lead_quality": "non-brand leads in a market-week have quality 1 / (1 + slope * max(spend / (size * ref_spend) - 1, 0)); the MQL rate and the win rate are each multiplied by its square root. Deals and response curves include it",
            "marginal_cpa": "extra spend per extra deal when the channel's whole in-window spend path is scaled by 1%",
            "incremental": "expected value, net of noise, counting deals that land after the window ends",
            "response_curve": "incremental deals when the channel's in-window spend path is scaled by spend_multiplier, other channels unchanged",
            "lead_model": "leads(r,t) = base(r,t) + email(r,t) + sum_c beta_c * size_r * hill(adstock_c(spend_rc)(t) / size_r)",
            "deal_model": "deal probability per lead = p_mql * p_sql * sdr_mult(r,t) * p_opp * p_won * ae_mult(r,t) * promo(t) * price(t), by lead created week",
            "parameter_draws": "every true parameter here was drawn from the ranges in sim/config.py by a child stream of the seed; none is typed in",
            "brand_searches": "searches(r,t) = baseline(r,t) + sum over meta, youtube, ctv of gamma_c * size_r * (1 - exp(-adstock_c(spend_rc)(t) / (reach_spend_c * size_r))), adstock geometric and normalized; baseline is the organic lead rate base(r,t). Brand-search spend = searches * cost per search * weekly cost noise, so it moves with every term",
            "brand_searches_created": "in-window brand searches the channel's spend creates, in the units of baseline searches (organic leads per week)",
            "incremental_deals_via_brand_search": "meta, youtube and ctv: expected deals brand search causes because of the extra brand searches, and so extra brand-search spend, that the channel's in-window spend creates. Counterfactual: remove the channel's in-window spend, recompute brand searches and brand-search spend, and take the difference in deals brand search causes. Counts deals that close after the window; brand-search spend after the last window week is not simulated",
            "incremental_deals_total": "incremental_deals (direct) + incremental_deals_via_brand_search",
            "cpa_total": "in-window spend divided by incremental_deals_total",
            "marginal_cpa_total": "extra spend per extra total deal when the channel's whole in-window spend path is scaled by 1% (central difference, 0.99 to 1.01), with brand-search spend responding",
            "response_curve_total": "incremental_deals_total when the channel's in-window spend path is scaled by spend_multiplier; brand-search spend responds, other channels unchanged",
            "brand_search_incremental_deals": "paid_search_brand incremental_deals is given its actual spend path, which already includes the searches the upper funnel created",
            "upper_funnel_share_of_brand_search_deals": "sum of incremental_deals_via_brand_search over meta, youtube and ctv, divided by paid_search_brand incremental_deals",
        },
        "channels": channel_truth,
        "summary": {
            "paid_spend": _r(paid_spend, 2),
            "expected_deals_all_sources": _r(paid_deals + base_deals + email_deals, 2),
            "incremental_deals_paid_media": _r(paid_deals, 2),
            "blended_cpa_paid_media": _r(paid_spend / (paid_deals + base_deals + email_deals), 2),
            "incremental_cpa_paid_media": _r(paid_spend / paid_deals, 2),
            "paid_media_share_of_deals": _r(paid_deals / (paid_deals + base_deals + email_deals)),
            "nonbrand_share_of_search_spend": _r(channel_truth["paid_search_nonbrand"]["spend"]
                                                 / (channel_truth["paid_search_nonbrand"]["spend"]
                                                    + channel_truth["paid_search_brand"]["spend"])),
            "highest_cpa_channel": max(channel_truth, key=lambda c: channel_truth[c]["cpa"]),
            "upper_funnel_share_of_brand_searches": _r(sum(created_win.values()) / float(searches[win].sum())),
            "upper_funnel_share_of_brand_search_deals": _r(
                sum(channel_truth[c]["incremental_deals_via_brand_search"] for c in search_drivers)
                / channel_truth["paid_search_brand"]["incremental_deals"]),
        },
        "controls": {
            "baseline": {
                "expected_deals_in_window": _r(base_deals, 2),
                "leads_per_week_avg_region": b["leads_per_week_avg_region"],
                "growth_per_year_log": tp["base_growth"],
                "seasonality": {
                    "form": "log season(r, w) = sum of humps size * exp(-0.5 * ((w - week - shift_r) / width) ** 2), "
                            "summer_lull and winter_dip entering with a minus sign, w = ISO week; then holiday multipliers",
                    "shift_r": "spring: spring_weeks_per_degree * (lat_r - ref) + offset_r; fall: "
                               "-fall_weeks_per_degree * (lat_r - ref) + offset_r; summer_lull: mean of the two; "
                               "winter_dip: offset_r",
                    "ref_latitude": C.SEASON["ref_latitude"],
                    **{k: v for k, v in tp["season"].items() if k != "market_offset_weeks"},
                    "market_offset_weeks": dict(zip(codes, tp["season"]["market_offset_weeks"])),
                    "holiday_weeks": C.SEASON["holiday_weeks"]},
                "lead_quality": tp["funnel"]["base"],
                "crm_last_touch_recording": C.CRM_ATTRIBUTION["base"],
            },
            "fleet_activity_index": {"effect": "baseline leads scale with (index / 100) ** demand_elasticity",
                                     "demand_elasticity": tp["macro_elasticity"],
                                     "measurement_sigma_log": C.MACRO["measurement_sigma"]},
            "sales_capacity": {
                "sdr_elasticity_on_p_sql": tp["sdr_elasticity"],
                "ae_elasticity_on_p_won": tp["ae_elasticity"],
                "coverage": "headcount / (per_1k_accounts * target_accounts / 1000)",
                "sdr_per_1k_accounts": s_cfg["sdr_per_1k_accounts"],
                "ae_per_1k_accounts": s_cfg["ae_per_1k_accounts"],
                "multiplier_bounds": list(s_cfg["mult_bounds"]),
                "hiring_freeze": [str(s_cfg["freeze"][0]), str(s_cfg["freeze"][1])],
            },
            "email": {
                "expected_deals_in_window": _r(email_deals, 2),
                "deals_per_1k_sends": _r(1000 * email_deals / float(sends[win].sum()), 4),
                "adstock": {"type": "geometric", "alpha": tp["email_alpha"], "l_max": C.L_MAX, "normalized": True},
                "saturation": {"type": "hill", "half_saturation": tp["email_K"], "slope": e_cfg["S"],
                               "input": "adstocked weekly sends / region size index"},
                "beta_leads_per_week_per_size_unit": _r(beta_email, 6),
                "lead_quality": tp["funnel"]["email"],
            },
            "promo": {
                "year_end_win_mult": tp["year_end_win_mult"],
                "year_end_amount_mult": 1 - p_cfg["year_end_discount_pct"] / 100,
                "price_change_win_mult": tp["price_win_mult"],
                "price_change_amount_mult": 1 + p_cfg["price_change_pct"] / 100,
            },
        },
        "deal_size": {"median_at_list": C.AMOUNT_MEDIAN, "lognormal_sigma": C.AMOUNT_SIGMA,
                      "area_multiplier": {k: v["amount"] for k, v in C.AREA.items()}},
        "funnel_lags_days_gamma_shape_scale": {k: list(v) for k, v in C.LAGS.items()},
        "region_size_index": {c: _r(s, 6) for c, s in zip(codes, size)},
        "ctv_regions": C.CTV_REGIONS,
    }
    state = None
    if keep_state:
        state = {
            "seed": seed, "tp": tp, "codes": codes, "names": names, "areas": areas, "accounts": accounts,
            "lat": lat, "size": size, "area_lead": area_lead, "area_amount": area_amount, "t0": t0,
            "weeks": weeks, "week_d": week_d, "t_total": t_total, "snapshot": snapshot,
            "spend": spend, "habits": habits, "eta": eta, "sends": sends, "beta_email": beta_email,
            "betas": betas, "gamma": gamma, "cost_per_search": cost_per_search, "fp": fp,
            "month_starts": month_starts, "counts_by_role": counts_by_role, "cov_last": cov_last,
            "region_eff": region_eff, "area_off": area_off, "attr": attr, "vprob": vprob,
            "vsrc": vsrc, "vmed": vmed, "vcamp": vcamp,
            "leads": {"t": lt, "r": lr, "o": lo_, "created": created, "rec": rec, "var": var,
                      "is_mql": is_mql, "is_sql": is_sql, "is_opp": is_opp, "is_won": is_won,
                      "mql_date": mql_date, "sql_date": sql_date, "opp_date": opp_date,
                      "close_date": close_date, "amount": amount, "order": order, "lead_ids": lead_ids,
                      "lead_id_of": lead_id_of, "n_opps": int(opp_rows.size)},
            "n_events": int(keep.sum()), "webinar_factor_last": webinar_factor_last,
        }
    return SimResult(tables=tables, truth=truth, state=state)


def write_outputs(result: SimResult, raw_dir: Path = DEFAULT_RAW_DIR,
                  truth_path: Path = DEFAULT_TRUTH_PATH, truth_2026_path: Path | None = None) -> None:
    raw_dir = Path(raw_dir)
    truth_path = Path(truth_path)
    raw_dir.mkdir(parents=True, exist_ok=True)
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    for name, df in result.tables.items():
        df.to_csv(raw_dir / f"{name}.csv", index=False, lineterminator="\n", float_format="%.2f")
    keys = [(result.truth, truth_path)]
    if result.truth_2026 is not None:
        keys.append((result.truth_2026, Path(truth_2026_path or truth_path.with_name("truth_2026.json"))))
    for obj, path in keys:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, indent=2)
            fh.write("\n")
