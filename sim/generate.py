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


def _flight(rng: np.random.Generator, t: int, kind: str) -> tuple[np.ndarray, np.ndarray]:
    """National flighting multiplier and, for 'flights', the flight id of each week."""
    mult = np.ones(t)
    flight_id = np.full(t, -1)
    if kind == "bursts":
        i = 0
        while i < t:
            u = rng.random()
            if u < 0.07:
                n = int(rng.integers(3, 7))
                mult[i : i + n] = rng.uniform(1.5, 2.1)
                i += n
            elif u < 0.10:
                n = int(rng.integers(2, 5))
                mult[i : i + n] = 0.0
                i += n
            else:
                i += 1
    elif kind == "flights":
        mult[:] = 0.0
        i = int(rng.integers(0, 4))
        fid = 0
        while i < t:
            on, off = int(rng.integers(4, 9)), int(rng.integers(3, 7))
            mult[i : i + on] = 1.0
            flight_id[i : i + on] = fid
            fid += 1
            i += on + off
        mult = mult / mult.mean()
    return mult, flight_id


def _dark_mask(rng, t: int, r: int, rate: float, length: tuple[int, int]) -> np.ndarray:
    mask = np.ones((t, r))
    counts = rng.poisson(rate, r)
    for j in range(r):
        for _ in range(counts[j]):
            n = int(rng.integers(length[0], length[1] + 1))
            start = int(rng.integers(0, t - n))
            mask[start : start + n, j] = 0.0
    return mask


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

def _draw_true_params(rng: np.random.Generator) -> dict:
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
    return {
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


# --- spend ------------------------------------------------------------------

def _planned_spend(rng, ch: str, cal: dict, size: np.ndarray,
                   region_ok: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Actual spend (T, R) and the national plan it was bought against (T,)."""
    p = C.SPEND[ch]
    t_total, n_reg = cal["T"], size.size
    yr = cal["year_idx"]
    year_noise = np.exp(rng.normal(0.0, C.YEAR_PLAN_SIGMA, yr.max() - yr.min() + 1))[yr - yr.min()]
    q_mult = np.exp(rng.normal(0.0, p["quarter_sigma"], cal["quarter"].max() + 1))[cal["quarter"]]
    plan = (p["weekly_budget"] * np.exp(p["yearly_drift"] * yr) * cal["event_mult"][ch]
            * cal["season"] ** p["season_follow"] * cal["holiday_cut"])
    level = plan * year_noise * q_mult
    tilt = np.exp(rng.normal(0.0, p["tilt_sigma"], n_reg))
    alloc = size * tilt * region_ok
    alloc = alloc / alloc.sum()
    noise = np.exp(_ar1(rng, t_total, n_reg, p["region_sigma"], 0.6))

    if p["flight"] == "regional_flights":
        national = level * np.exp(rng.normal(0.0, p["weekly_sigma"], t_total))
        on = np.zeros((t_total, n_reg))
        lo_on, hi_on = p["on_weeks"]
        lo_off, hi_off = p["off_weeks"]
        for j in np.nonzero(region_ok)[0]:
            i = int(rng.integers(0, hi_off))
            while i < t_total:
                n_on = int(rng.integers(lo_on, hi_on + 1))
                on[i : i + n_on, j] = 1.0
                i += n_on + int(rng.integers(lo_off, hi_off + 1))
        duty = on[:, region_ok].mean()
        x = national[:, None] * alloc[None, :] * on / duty * noise
    else:
        flight_mult, flight_id = _flight(rng, t_total, p["flight"])
        national = level * flight_mult * np.exp(rng.normal(0.0, p["weekly_sigma"], t_total))
        dark = _dark_mask(rng, t_total, n_reg, p["dark_rate"], p["dark_len"])
        x = national[:, None] * alloc[None, :] * noise * dark
        if p["flight"] == "flights":
            include = (rng.random((flight_id.max() + 1, n_reg)) < 0.75).astype(float)
            on_w = flight_id >= 0
            x[on_w] *= include[flight_id[on_w]]
    x = np.round(x, 2)
    x[x < 25.0] = 0.0
    return x, plan


# --- simulation ---------------------------------------------------------------

def simulate(seed: int = C.DEFAULT_SEED) -> SimResult:
    # Two child streams: one draws the hidden true parameters, one draws the data.
    truth_seq, data_seq = np.random.SeedSequence(seed).spawn(2)
    tp = _draw_true_params(np.random.default_rng(truth_seq))
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
    areas = [r[2] for r in C.REGIONS]
    accounts = np.array([r[3] for r in C.REGIONS], dtype=float)
    n_reg = len(codes)
    size = accounts / accounts.mean()
    area_lead = np.array([C.AREA[a]["base_leads"] for a in areas])
    area_amount = np.array([C.AREA[a]["amount"] for a in areas])

    woy = np.array([w.isocalendar().week for w in weeks])
    years = (np.arange(t_total) - C.BURN_IN_WEEKS) / 52.0
    quarter = np.array([(w.year - weeks[0].year) * 4 + (w.month - 1) // 3 for w in weeks])
    month_idx = np.array([(w.year - weeks[0].year) * 12 + w.month - weeks[0].month for w in weeks])
    is_q4 = np.array([w.month >= 10 for w in weeks])
    is_holiday = np.isin(woy, [52, 53, 1])
    holiday_cut = np.where(is_holiday, C.HOLIDAY_SPEND_CUT, 1.0)

    season_log = np.zeros(t_total)
    for h, s_coef, c_coef in C.SEASON["fourier"]:
        season_log += s_coef * np.sin(2 * np.pi * h * woy / 52) + c_coef * np.cos(2 * np.pi * h * woy / 52)
    season = np.exp(season_log)
    for wk, m in C.SEASON["holiday_weeks"].items():
        season[woy == wk] *= m
    lo, hi = C.SEASON["summer_weeks"]
    season[(woy >= lo) & (woy <= hi)] *= C.SEASON["summer_mult"]
    event_mult = {ch: np.ones(t_total) for ch in C.PLANNED_CHANNELS}
    for ev_date, _reason, changes in C.BUDGET_EVENTS:
        for ch, change in changes.items():
            event_mult[ch][week_d >= np.datetime64(ev_date, "D")] *= 1 + change
    cal = {"T": t_total, "quarter": quarter, "season": season, "holiday_cut": holiday_cut,
           "year_idx": np.array([w.year - C.WINDOW_START.year for w in weeks]), "event_mult": event_mult}

    # --- planned spend and webinars -------------------------------------------
    spend: dict[str, np.ndarray] = {}
    plans: dict[str, np.ndarray] = {}
    all_regions = np.ones(n_reg, dtype=bool)
    ctv_regions = np.isin(codes, C.CTV_REGIONS)
    for ch in C.PLANNED_CHANNELS:
        spend[ch], plans[ch] = _planned_spend(rng, ch, cal, size, ctv_regions if ch == "ctv" else all_regions)

    w_cfg = C.WEBINARS
    ev_rate = w_cfg["events_per_week_national"] * size / n_reg
    ev_counts = rng.poisson(np.broadcast_to(ev_rate, (t_total, n_reg)))
    nz_t, nz_r = np.nonzero(ev_counts)
    reps = ev_counts[nz_t, nz_r]
    ev_t, ev_r = np.repeat(nz_t, reps), np.repeat(nz_r, reps)
    n_ev = ev_t.size
    ev_cost = np.round(w_cfg["cost_median"] * np.exp(rng.normal(0.0, w_cfg["cost_sigma"], n_ev)), 2)
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
               * (trend * season)[:, None] * np.exp(eps + tp["macro_elasticity"] * eta[:, None]))
    fleet_index = np.round(C.MACRO["index_level"] * np.exp(eta + rng.normal(0.0, C.MACRO["measurement_sigma"], t_total)), 1)

    # --- sales capacity ---------------------------------------------------------
    s_cfg = C.SALES
    n_months = month_idx.max() + 1
    month_starts = [date(weeks[0].year + (weeks[0].month - 1 + m) // 12, (weeks[0].month - 1 + m) % 12 + 1, 1)
                    for m in range(n_months)]
    region_eff = rng.normal(0.0, s_cfg["region_sigma"], n_reg)
    area_off = np.array([s_cfg["area_offset"][a] for a in areas])
    counts_by_role, mult_by_role = {}, {}
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
    p_sql_eff = np.minimum(fp["p_sql"][:, None, None] * sdr_mult[None], 0.95)  # (O, T, R)
    p_won_eff = np.minimum(fp["p_won"][:, None, None] * ae_mult[None] * win_time[None, :, None], 0.95)
    p_opp_lead = fp["p_mql"][:, None, None] * p_sql_eff * fp["p_opp"][:, None, None]
    p_deal = p_opp_lead * p_won_eff
    amount_mean = (C.AMOUNT_MEDIAN * np.exp(C.AMOUNT_SIGMA**2 / 2) * fp["amount_mult"][:, None, None]
                   * amount_time[None, :, None] * area_amount[None, None, :])

    def extend(a: np.ndarray) -> np.ndarray:  # carry the last week into the adstock tail
        return np.concatenate([a, np.repeat(a[-1:], C.L_MAX, axis=0)], axis=0)

    o_index = {o: i for i, o in enumerate(C.ORIGINS)}

    # --- true media effects, calibrated to the drawn CPA -----------------------
    pad = np.zeros((C.L_MAX, n_reg))
    mu_media: dict[str, np.ndarray] = {}
    channel_truth: dict[str, dict] = {}

    def fit_channel(ch: str) -> None:
        e = tp["effect"][ch]
        x_full = np.vstack([spend[ch], pad])
        x_burn = x_full.copy()
        x_burn[C.BURN_IN_WEEKS :] = 0.0
        a_full = _adstock(x_full, e["alpha"], C.L_MAX)
        a_burn = _adstock(x_burn, e["alpha"], C.L_MAX)
        a_win = a_full - a_burn
        base_resp = _hill(a_burn / size, e["K"], e["S"])

        def contrib(mult: float) -> np.ndarray:
            return size * (_hill((a_burn + mult * a_win) / size, e["K"], e["S"]) - base_resp)

        i = o_index[ch]
        deal_x, opp_x, amt_x = extend(p_deal[i]), extend(p_opp_lead[i]), extend(amount_mean[i])
        spend_win = float(spend[ch][win].sum())
        beta = spend_win / (e["cpa"] * float((contrib(1.0) * deal_x).sum()))
        mu_media[ch] = beta * size * _hill(a_full[:t_total] / size, e["K"], e["S"])

        def deals(mult: float) -> float:
            return float((beta * contrib(mult) * deal_x).sum())

        leads_1 = beta * contrib(1.0)
        inc_deals = deals(1.0)
        inc_rev = float((leads_1 * deal_x * amt_x).sum())
        inc_pipe = float((leads_1 * opp_x * amt_x).sum())
        f = tp["funnel"][ch]
        channel_truth[ch] = {
            "spend": _r(spend_win, 2),
            "incremental_leads": _r(leads_1.sum(), 2),
            "incremental_deals": _r(inc_deals, 2),
            "incremental_revenue": _r(inc_rev, 2),
            "incremental_pipeline": _r(inc_pipe, 2),
            "cpa": _r(spend_win / inc_deals, 2),
            "marginal_cpa": _r(0.02 * spend_win / (deals(1.01) - deals(0.99)), 2),
            "roi_revenue": _r(inc_rev / spend_win),
            "roi_pipeline": _r(inc_pipe / spend_win),
            "cost_per_incremental_lead": _r(spend_win / leads_1.sum(), 2),
            "adstock": {"type": "geometric", "alpha": e["alpha"], "l_max": C.L_MAX, "normalized": True},
            "saturation": {"type": "hill", "half_saturation": e["K"], "slope": e["S"],
                           "input": "adstocked weekly spend / region size index"},
            "beta_leads_per_week_per_size_unit": _r(beta, 6),
            "lead_quality": {k: f[k] for k in ("p_mql", "p_sql", "p_opp", "p_won", "amount_mult")},
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

    bs = C.BRAND_SEARCH
    demand = mu_base + sum(share * mu_media[src] for src, share in bs["demand_from"].items())
    brand_raw = (demand * np.exp(rng.normal(0.0, bs["noise_sigma"], (t_total, n_reg)))
                 * _dark_mask(rng, t_total, n_reg, bs["dark_rate"], bs["dark_len"]))
    planned_nonbrand_win = plans["paid_search_nonbrand"][win].sum()
    share = bs["planned_share_of_search"]
    scale = share / (1 - share) * planned_nonbrand_win / brand_raw[win].sum()
    brand = np.round(brand_raw * scale, 2)
    brand[brand < 25.0] = 0.0
    spend["paid_search_brand"] = brand
    fit_channel("paid_search_brand")
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
    is_mql = u[0] < fp["p_mql"][lo_]
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

    index_df = pd.DataFrame({"week_start": week_str[win], "fleet_activity_index": fleet_index[win]})

    regions_df = pd.DataFrame({
        "region_code": codes,
        "region_name": names,
        "sales_area": areas,
        "target_accounts": accounts.astype(np.int64),
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
            "marginal_cpa": "extra spend per extra deal when the channel's whole in-window spend path is scaled by 1%",
            "incremental": "expected value, net of noise, counting deals that land after the window ends",
            "response_curve": "incremental deals when the channel's in-window spend path is scaled by spend_multiplier, other channels unchanged",
            "lead_model": "leads(r,t) = base(r,t) + email(r,t) + sum_c beta_c * size_r * hill(adstock_c(spend_rc)(t) / size_r)",
            "deal_model": "deal probability per lead = p_mql * p_sql * sdr_mult(r,t) * p_opp * p_won * ae_mult(r,t) * promo(t) * price(t), by lead created week",
            "parameter_draws": "every true parameter here was drawn from the ranges in sim/config.py by a child stream of the seed; none is typed in",
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
        },
        "controls": {
            "baseline": {
                "expected_deals_in_window": _r(base_deals, 2),
                "leads_per_week_avg_region": b["leads_per_week_avg_region"],
                "growth_per_year_log": tp["base_growth"],
                "seasonality": {"fourier": C.SEASON["fourier"],
                                "holiday_weeks": C.SEASON["holiday_weeks"],
                                "summer_weeks": list(C.SEASON["summer_weeks"]),
                                "summer_mult": C.SEASON["summer_mult"]},
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
    return SimResult(tables=tables, truth=truth)


def write_outputs(result: SimResult, raw_dir: Path = DEFAULT_RAW_DIR,
                  truth_path: Path = DEFAULT_TRUTH_PATH) -> None:
    raw_dir = Path(raw_dir)
    truth_path = Path(truth_path)
    raw_dir.mkdir(parents=True, exist_ok=True)
    truth_path.parent.mkdir(parents=True, exist_ok=True)
    for name, df in result.tables.items():
        df.to_csv(raw_dir / f"{name}.csv", index=False, lineterminator="\n", float_format="%.2f")
    with open(truth_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result.truth, fh, indent=2)
        fh.write("\n")
