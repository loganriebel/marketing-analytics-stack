"""Seeded simulator for Fernhook's ad spend, platform reports, CRM funnel and the answer key.

One numpy Generator drives every draw, in a fixed order, so a seed always produces
the same bytes. The true effects (adstock, saturation, lead quality) live only in
the returned truth dict; the raw tables carry only what a real company could export.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import json

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
    out = np.zeros_like(x)
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


# --- simulation ---------------------------------------------------------------

def simulate(seed: int = C.DEFAULT_SEED) -> SimResult:
    rng = np.random.default_rng(seed)

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
    is_q4 = np.array([w.month >= 10 for w in weeks])
    holiday_cut = np.where(np.isin(woy, [52, 53, 1]), C.HOLIDAY_SPEND_CUT, 1.0)

    season_log = np.zeros(t_total)
    for h, s_coef, c_coef in C.SEASON["fourier"]:
        season_log += s_coef * np.sin(2 * np.pi * h * woy / 52) + c_coef * np.cos(2 * np.pi * h * woy / 52)
    season = np.exp(season_log)
    for wk, m in C.SEASON["holiday_weeks"].items():
        season[woy == wk] *= m
    lo, hi = C.SEASON["summer_weeks"]
    season[(woy >= lo) & (woy <= hi)] *= C.SEASON["summer_mult"]

    # --- spend ---------------------------------------------------------------
    spend: dict[str, np.ndarray] = {}
    for ch in C.AD_CHANNELS:
        p = C.SPEND[ch]
        q_mult = np.exp(rng.normal(0.0, p["quarter_sigma"], quarter.max() + 1))[quarter]
        level = p["weekly_budget"] * np.exp(p["growth"] * years) * q_mult
        level = level * season ** p["season_follow"] * holiday_cut
        flight_mult, flight_id = _flight(rng, t_total, p["flight"])
        national = level * flight_mult * np.exp(rng.normal(0.0, p["weekly_sigma"], t_total))
        tilt = np.exp(rng.normal(0.0, p["tilt_sigma"], n_reg))
        alloc = size * tilt
        alloc = alloc / alloc.sum()
        noise = np.exp(_ar1(rng, t_total, n_reg, p["region_sigma"], 0.6))
        dark = _dark_mask(rng, t_total, n_reg, p["dark_rate"], p["dark_len"])
        x = national[:, None] * alloc[None, :] * noise * dark
        if p["flight"] == "flights":
            n_flights = flight_id.max() + 1
            include = (rng.random((n_flights, n_reg)) < 0.75).astype(float)
            on = flight_id >= 0
            x[on] *= include[flight_id[on]]
        x = np.round(x, 2)
        x[x < 25.0] = 0.0
        spend[ch] = x

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

    # --- organic baseline ----------------------------------------------------
    b = C.BASE
    eta = _ar1(rng, t_total, 1, b["national_shock_sigma"], b["national_shock_rho"])[:, 0]
    eps = rng.normal(0.0, b["region_week_sigma"], (t_total, n_reg))
    trend = np.exp(b["growth_per_year"] * years)
    mu_base = (b["leads_per_week_avg_region"] * size[None, :] * area_lead[None, :]
               * (trend * season)[:, None] * np.exp(eps + eta[:, None]))

    # --- true media effect, calibrated to target ROI -------------------------
    amount_mean_factor = np.exp(C.AMOUNT_SIGMA**2 / 2)

    def p_opp_total(o: str) -> float:
        f = C.FUNNEL[o]
        return f["p_mql"] * f["p_sql"] * f["p_opp"]

    def pipeline_per_lead(o: str) -> np.ndarray:  # by region
        return p_opp_total(o) * C.AMOUNT_MEDIAN * C.FUNNEL[o]["amount_mult"] * area_amount * amount_mean_factor

    pad = np.zeros((C.L_MAX, n_reg))
    mu_media: dict[str, np.ndarray] = {}
    channel_truth: dict[str, dict] = {}
    for ch in C.PAID_CHANNELS:
        e = C.EFFECT[ch]
        x_full = np.vstack([spend[ch], pad])
        x_burn = x_full.copy()
        x_burn[C.BURN_IN_WEEKS :] = 0.0
        a_full = _adstock(x_full, e["alpha"], C.L_MAX)
        a_burn = _adstock(x_burn, e["alpha"], C.L_MAX)
        a_win = a_full - a_burn
        base_resp = _hill(a_burn / size, e["K"], e["S"])

        def contrib(mult: float) -> np.ndarray:
            return size * (_hill((a_burn + mult * a_win) / size, e["K"], e["S"]) - base_resp)

        ppl = pipeline_per_lead(ch)
        spend_win = float(spend[ch][win].sum())
        beta = e["target_roi_pipeline"] * spend_win / float((contrib(1.0) * ppl).sum())
        mu_media[ch] = beta * size * _hill(a_full[:t_total] / size, e["K"], e["S"])

        leads_1 = beta * contrib(1.0)
        inc_leads = float(leads_1.sum())
        inc_pipe = float((leads_1 * ppl).sum())
        curve = [float((beta * contrib(m) * ppl).sum()) for m in RESPONSE_MULTIPLIERS]
        hi_p = float((beta * contrib(1.01) * ppl).sum())
        lo_p = float((beta * contrib(0.99) * ppl).sum())
        f = C.FUNNEL[ch]
        channel_truth[ch] = {
            "spend": _r(spend_win, 2),
            "incremental_leads": _r(inc_leads, 2),
            "incremental_opportunities": _r(inc_leads * p_opp_total(ch), 2),
            "incremental_pipeline": _r(inc_pipe, 2),
            "incremental_revenue": _r(inc_pipe * f["p_won"], 2),
            "roi_pipeline": _r(inc_pipe / spend_win),
            "roi_revenue": _r(inc_pipe * f["p_won"] / spend_win),
            "marginal_roi_pipeline": _r((hi_p - lo_p) / (0.02 * spend_win)),
            "cost_per_incremental_lead": _r(spend_win / inc_leads, 2),
            "adstock": {"type": "geometric", "alpha": e["alpha"], "l_max": C.L_MAX, "normalized": True},
            "saturation": {"type": "hill", "half_saturation": e["K"], "slope": e["S"],
                           "input": "adstocked weekly spend / region size index"},
            "beta_leads_per_week_per_size_unit": _r(beta, 6),
            "lead_quality": {**{k: f[k] for k in ("p_mql", "p_sql", "p_opp", "p_won")},
                             "p_opp_per_lead": _r(p_opp_total(ch), 6),
                             "deal_size_multiplier": f["amount_mult"]},
            "crm_last_touch_recording": C.CRM_ATTRIBUTION[ch],
            "platform_reporting": C.PLATFORM.get(ch, {"source": "webinar registrants",
                                                      "cost_per_registrant": w_cfg["cost_per_registrant"]}),
            "response_curve": {
                "spend_multiplier": RESPONSE_MULTIPLIERS,
                "spend": [_r(spend_win * m, 2) for m in RESPONSE_MULTIPLIERS],
                "incremental_pipeline": [_r(v, 2) for v in curve],
            },
        }

    # --- leads ---------------------------------------------------------------
    mu = np.stack([mu_base] + [mu_media[ch] for ch in C.PAID_CHANNELS], axis=2)  # (T, R, O)
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
    vsrc = np.full((len(C.CRM_CHANNELS), max_v), "", dtype=object)
    vmed = np.full((len(C.CRM_CHANNELS), max_v), "", dtype=object)
    for k, ch in enumerate(C.CRM_CHANNELS):
        for j, ((src, med), p) in enumerate(C.UTM_VARIANTS[ch]):
            vprob[k, j], vsrc[k, j], vmed[k, j] = p, src, med
    var = _categorical(rng, vprob, rec)
    utm_source = vsrc[rec, var]
    utm_medium = vmed[rec, var]

    fp = {k: np.array([C.FUNNEL[o][k] for o in C.ORIGINS]) for k in ("p_mql", "p_sql", "p_opp", "p_won", "amount_mult")}
    u = rng.random((4, n))
    is_mql = u[0] < fp["p_mql"][lo_]
    is_sql = is_mql & (u[1] < fp["p_sql"][lo_])
    is_opp = is_sql & (u[2] < fp["p_opp"][lo_])
    is_won = is_opp & (u[3] < fp["p_won"][lo_])

    def lag(key: str) -> np.ndarray:
        shape, scale = C.LAGS[key]
        return np.floor(rng.gamma(shape, scale, n)).astype("timedelta64[D]")

    mql_date = created + lag("mql")
    sql_date = mql_date + lag("sql")
    opp_date = sql_date + lag("opp")
    lag_won, lag_lost = lag("close_won"), lag("close_lost")
    close_date = opp_date + np.where(is_won, lag_won, lag_lost)
    amount = (C.AMOUNT_MEDIAN * fp["amount_mult"][lo_] * area_amount[lr]
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
    platform: dict[str, dict[str, np.ndarray]] = {}
    for ch in C.AD_CHANNELS:
        p, m = C.PLATFORM[ch], C.MEDIA[ch]
        reach = 1.0 - np.exp(-spend[ch] / (p["reach_spend"] * size[None, :]))
        rate = p["claim_mult"] * mu_media[ch] + p["halo"] * mu_base * reach
        for src, share in p["halo_from"].items():
            rate = rate + share * mu_media[src] * (spend[ch] > 0)
        reported = rng.poisson(rate)
        cpm = m["cpm"] * (1 + C.Q4_CPM_LIFT * is_q4)[:, None] * np.exp(rng.normal(0.0, 0.08, (t_total, n_reg)))
        impressions = np.round(spend[ch] / cpm * 1000).astype(np.int64)
        ctr = np.clip(m["ctr"] * np.exp(rng.normal(0.0, 0.10, (t_total, n_reg))), 0, 1)
        clicks = rng.binomial(impressions, ctr)
        platform[ch] = {"reported": reported, "impressions": impressions, "clicks": clicks}
    dda_noise = np.exp(rng.normal(0.0, 0.05, (t_total, n_reg)))
    post_click = rng.binomial(platform["display"]["reported"], 1 - C.DISPLAY_POST_VIEW_SHARE)

    def ad_rows(ch: str) -> tuple[np.ndarray, np.ndarray]:
        tt, rr = np.nonzero(spend[ch][win] > 0)
        return tt + C.BURN_IN_WEEKS, rr

    week_str = _date_str(week_d)
    code_arr = np.array(codes, dtype=object)
    name_arr = np.array(names, dtype=object)

    google_parts = []
    for ch, ctype in (("paid_search", "SEARCH"), ("youtube", "VIDEO")):
        tt, rr = ad_rows(ch)
        google_parts.append(pd.DataFrame({
            "week_start_date": week_str[tt],
            "geo_target_region": code_arr[rr],
            "campaign_type": ctype,
            "cost_micros": np.round(spend[ch][tt, rr] * 1_000_000).astype(np.int64),
            "impressions": platform[ch]["impressions"][tt, rr],
            "clicks": platform[ch]["clicks"][tt, rr],
            "conversions": np.round(platform[ch]["reported"][tt, rr] * dda_noise[tt, rr], 2),
        }))
    google_df = (pd.concat(google_parts, ignore_index=True)
                 .sort_values(["week_start_date", "geo_target_region", "campaign_type"], kind="stable")
                 .reset_index(drop=True))

    tt, rr = ad_rows("meta")
    meta_df = pd.DataFrame({
        "date_start": week_str[tt],
        "date_stop": _date_str(week_d[tt] + np.timedelta64(6, "D")),
        "region": name_arr[rr],
        "spend": spend["meta"][tt, rr],
        "impressions": platform["meta"]["impressions"][tt, rr],
        "clicks": platform["meta"]["clicks"][tt, rr],
        "leads": platform["meta"]["reported"][tt, rr],
    })

    tt, rr = ad_rows("linkedin")
    linkedin_df = pd.DataFrame({
        "start_date": week_str[tt],
        "region_code": code_arr[rr],
        "cost_usd": spend["linkedin"][tt, rr],
        "impressions": platform["linkedin"]["impressions"][tt, rr],
        "clicks": platform["linkedin"]["clicks"][tt, rr],
        "conversions": platform["linkedin"]["reported"][tt, rr],
    })

    tt, rr = ad_rows("display")
    display_df = pd.DataFrame({
        "week": week_str[tt],
        "region_code": code_arr[rr],
        "media_cost": spend["display"][tt, rr],
        "impressions": platform["display"]["impressions"][tt, rr],
        "clicks": platform["display"]["clicks"][tt, rr],
        "post_click_conversions": post_click[tt, rr],
        "post_view_conversions": platform["display"]["reported"][tt, rr] - post_click[tt, rr],
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
        "webinar_events": webinar_df,
        "crm_leads": leads_df,
        "crm_opportunities": opps_df,
    }

    # --- answer key ----------------------------------------------------------
    base_ppl = pipeline_per_lead("base")
    base_pipe = float((mu_base[win] * base_ppl).sum())
    media_pipe = sum(v["incremental_pipeline"] for v in channel_truth.values())
    truth = {
        "company": C.COMPANY,
        "seed": seed,
        "window": {
            "first_week": str(C.WINDOW_START),
            "last_week": str(weeks[-1]),
            "weeks": C.N_WEEKS,
            "crm_snapshot_date": str(snapshot),
        },
        "definitions": {
            "roi_pipeline": "expected pipeline $ (opportunity amount) caused by in-window spend, divided by in-window spend",
            "roi_revenue": "same, for closed-won revenue",
            "marginal_roi_pipeline": "extra expected pipeline per extra $ when the channel's whole in-window spend path is scaled by 1%",
            "incremental": "expected value, net of noise, counting outcomes that land after the window ends",
            "response_curve": "incremental pipeline when the channel's in-window spend path is scaled by spend_multiplier, other channels unchanged",
            "lead_model": "leads(r,t) = base(r,t) + sum_c beta_c * size_r * hill(adstock_c(spend_rc)(t) / size_r)",
        },
        "channels": channel_truth,
        "baseline": {
            "expected_pipeline_in_window": _r(base_pipe, 2),
            "leads_per_week_avg_region": b["leads_per_week_avg_region"],
            "growth_per_year_log": b["growth_per_year"],
            "seasonality": {"fourier": C.SEASON["fourier"],
                            "holiday_weeks": C.SEASON["holiday_weeks"],
                            "summer_weeks": list(C.SEASON["summer_weeks"]),
                            "summer_mult": C.SEASON["summer_mult"]},
            "lead_quality": C.FUNNEL["base"],
            "crm_last_touch_recording": C.CRM_ATTRIBUTION["base"],
        },
        "media_share_of_expected_pipeline": _r(media_pipe / (media_pipe + base_pipe)),
        "deal_size": {"median": C.AMOUNT_MEDIAN, "lognormal_sigma": C.AMOUNT_SIGMA,
                      "area_multiplier": {k: v["amount"] for k, v in C.AREA.items()}},
        "funnel_lags_days_gamma_shape_scale": {k: list(v) for k, v in C.LAGS.items()},
        "region_size_index": {c: _r(s, 6) for c, s in zip(codes, size)},
        "near_zero_channel": min(channel_truth, key=lambda c: channel_truth[c]["roi_pipeline"]),
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
