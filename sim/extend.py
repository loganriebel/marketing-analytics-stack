"""Run the Fernhook world on into 2026, driven by plan files.

    python -m sim --through 2026-05-31 --plan plans/2026_test.yaml --out data/cut_2026-05-31

Rules:

* 2023 to 2025 does not change. The base simulate() runs exactly as before, and
  every 2026 draw comes from new child streams of the same seed.
* State carries across the boundary: adstock (the full spend history), the AR(1)
  noise in demand and in each market's media buying, sales headcount, the email list,
  the cost per brand search, and every lead already in the pipeline. A lead's fate
  was drawn when it was created; a later snapshot only shows more of it.
* Plans drive spend; the true world decides outcomes. 2026 spend is the plan's budget
  basis bought with each channel's usual habits (flighting, market split, noise), then
  the plan's test arms and national moves. Brand search follows searches, as before.
* No peeking. Draws whose count does not depend on spend (demand noise, buying habits,
  headcount, email, webinars, reporting noise) come from one stream per component,
  drawn for the whole year at once. Draws whose count depends on spend (leads and their
  fates, platform conversions, clicks) come from one stream per week. Data up to any
  date depend only on plans up to that date: running further, or adding a later plan,
  never changes earlier weeks.

The 2026 answer key (truth_2026) holds expected, noise-free deals under the plans and
under counterfactuals with each test arm or national move taken out. Only
mmm/grade.py may read it.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from . import config as C
from .generate import (SimResult, _adstock, _brand_flighting, _categorical, _date_str, _hill,
                       _monday_of_iso_week, _r, _season_log, simulate)
from .plans import Plan, load_all

EXT_START = C.WINDOW_START + timedelta(weeks=C.N_WEEKS)   # 2025-12-29, ISO 2026-W01
EXT_WEEKS = 53                                             # through the week of 2026-12-28
STREAM_EXOGENOUS, STREAM_WEEK, STREAM_TRUTH = 2, 3, 4      # spawn keys; base uses 0 and 1
BASE_SNAPSHOT = EXT_START - timedelta(days=1)
LAG_TAIL_WEEKS = 8


def _ar1_continue(rng, last: np.ndarray, t: int, sigma: float, rho: float) -> np.ndarray:
    out = np.zeros((t,) + np.shape(last))
    shocks = rng.normal(0.0, sigma * np.sqrt(1 - rho**2), out.shape)
    prev = np.asarray(last, float)
    for i in range(t):
        prev = rho * prev + shocks[i]
        out[i] = prev
    return out


def _calendar() -> dict:
    weeks = [EXT_START + timedelta(weeks=i) for i in range(EXT_WEEKS)]
    woy = np.array([w.isocalendar().week for w in weeks])
    slow = np.zeros(EXT_WEEKS, dtype=bool)
    for lo, hi in C.PLANNING["slow_weeks"]:
        slow |= (woy >= lo) & (woy <= hi)
    iso_years = sorted({w.isocalendar().year for w in weeks})
    return {
        "weeks": weeks, "week_d": np.array(weeks, dtype="datetime64[D]"), "woy": woy, "T": EXT_WEEKS,
        "slow": slow, "iso_years": iso_years,
        "iso_week1": {y: (date.fromisocalendar(y, 1, 1) - EXT_START).days // 7 for y in iso_years},
        # quarter -1 is the December 2025 week: it keeps 2025's last quarter draws
        "quarter": np.array([-1 if w.year == 2025 else (w.month - 1) // 3 for w in weeks]),
        "month": np.array([-1 if w.year == 2025 else w.month - 1 for w in weeks]),
        "holiday_cut": np.where(np.isin(woy, [52, 53, 1]), C.HOLIDAY_SPEND_CUT, 1.0),
        "is_q4": np.array([w.month >= 10 for w in weeks]),
        "years": (C.N_WEEKS + np.arange(EXT_WEEKS)) / 52.0,  # years since the window start
    }


def _week_mask(cal, start: date, end: date) -> np.ndarray:
    return np.array([start <= w <= end for w in cal["weeks"]])


# --- exogenous draws: plan-free, one stream per component -----------------------------

def _exogenous(st: dict, cal: dict, seed: int) -> dict:
    names = ["demand", "sales", "email", "webinars", "brand", "media_noise", "ctv_report", "dda", "ctv_impr",
             "add_noise"] + C.PLANNED_CHANNELS
    kids = np.random.SeedSequence(seed, spawn_key=(STREAM_EXOGENOUS,)).spawn(len(names))
    rngs = {k: np.random.default_rng(s) for k, s in zip(names, kids)}
    T, R = cal["T"], st["size"].size
    tp, size, lat, codes = st["tp"], st["size"], st["lat"], st["codes"]
    ex: dict = {}

    # Buying habits: budget basis, quarter draws, market split, AR(1) noise, flights.
    region_ok = {ch: (np.isin(codes, C.CTV_REGIONS) if ch == "ctv" else np.ones(R, bool)) for ch in C.PLANNED_CHANNELS}
    season = np.exp(_season_log(tp["season"], cal["woy"].astype(float), lat))
    for wk, m in C.SEASON["holiday_weeks"].items():
        season[cal["woy"] == wk] *= m
    ex["season"] = season
    bau, add_noise = {}, {}
    for ch in C.PLANNED_CHANNELS:
        p, h, r = C.SPEND[ch], st["habits"][ch], rngs[ch]
        level = h["plan_last"] * h["year_noise_last"]  # the 2025 plan as it was bought
        q_draw = np.exp(r.normal(0.0, p["quarter_sigma"], 4))
        q_mult = np.where(cal["quarter"] < 0, h["q_mult_last"], q_draw[np.maximum(cal["quarter"], 0)])
        national = level * cal["holiday_cut"] * q_mult * np.exp(r.normal(0.0, p["weekly_sigma"], T))
        noise = np.exp(_ar1_continue(r, h["log_noise_last"], T, p["region_sigma"], 0.6))
        if p["flight"] == "seasonal_push":
            shape = _brand_flighting(r, p["push"], cal, lat, region_ok[ch], habits=h.get("habits"))
        else:
            resplit = np.exp(r.normal(0.0, p["quarter_region_sigma"], (4, R)))
            resplit = resplit / (resplit * h["alloc"]).sum(axis=1, keepdims=True)
            rs = np.where(cal["quarter"][:, None] < 0, h["resplit_last"][None, :],
                          resplit[np.maximum(cal["quarter"], 0)])
            shape = season ** p["season_follow"] * rs
        shape = shape / (shape * h["alloc"]).sum(axis=1).mean()
        x = np.round(national[:, None] * h["alloc"][None, :] * shape * noise, 2)
        x[x < 10.0] = 0.0
        bau[ch] = x
        add_noise[ch] = np.exp(rngs["add_noise"].normal(0.0, p["weekly_sigma"], (T, R)))
    ex["bau"], ex["add_noise"], ex["region_ok"] = bau, add_noise, region_ok

    # Demand: national shock (AR(1) from end-2025), market-week noise, fleet index.
    b, r = C.BASE, rngs["demand"]
    eta = _ar1_continue(r, st["eta"][-1], T, b["national_shock_sigma"], b["national_shock_rho"])
    eps = r.normal(0.0, b["region_week_sigma"], (T, R))
    trend = np.exp(tp["base_growth"] * cal["years"])
    ex["mu_base"] = (b["leads_per_week_avg_region"] * size[None, :] * st["area_lead"][None, :]
                     * trend[:, None] * season * np.exp(eps + tp["macro_elasticity"] * eta[:, None]))
    ex["fleet_index"] = np.round(C.MACRO["index_level"] * np.exp(eta + r.normal(0.0, C.MACRO["measurement_sigma"], T)), 1)

    # Sales capacity: the 2025 path carries on, hiring in Jan to Mar, normal attrition.
    s_cfg, r = C.SALES, rngs["sales"]
    counts, mults = {}, {}
    for role in ("sdr", "ae"):
        cov, path = st["cov_last"][role], []
        for m in range(12):
            cov *= 1 - s_cfg["attrition_per_month"]
            if m + 1 in s_cfg["hiring_months"]:
                cov += s_cfg["hiring_gain_per_month"]
            path.append(cov)
        target = s_cfg[f"{role}_per_1k_accounts"] * st["accounts"] / 1000
        noise = r.normal(0.0, s_cfg["month_sigma"], (12, R))
        cov_r = np.array(path)[:, None] * np.exp(st["area_off"][None, :] + st["region_eff"][None, :] + noise)
        count = np.maximum(1, np.round(cov_r * target[None, :])).astype(np.int64)
        lo_b, hi_b = s_cfg["mult_bounds"]
        dec = st["counts_by_role"][role][-1]
        all_counts = np.vstack([dec[None, :], count])        # row 0 = Dec 2025
        mult = np.clip((all_counts / target[None, :]) ** tp[f"{role}_elasticity"], lo_b, hi_b)
        counts[role] = count
        mults[role] = mult[cal["month"] + 1]                  # (T, R)
    ex["sales_counts"], ex["sdr_mult"], ex["ae_mult"] = counts, mults["sdr"], mults["ae"]

    # Email: list growth, blasts (and the year-end promo), opens and clicks.
    e_cfg, r = C.EMAIL, rngs["email"]
    ye_lo, ye_hi = C.PROMO["year_end_weeks"]
    is_year_end = (cal["woy"] >= ye_lo) & (cal["woy"] <= ye_hi)
    is_holiday = np.isin(cal["woy"], [52, 53, 1])
    blast = (r.random(T) < e_cfg["blast_prob"]) | is_year_end
    list_size = e_cfg["list_per_avg_region"] * size[None, :] * np.exp(e_cfg["list_growth_per_year"] * cal["years"])[:, None]
    freq = (e_cfg["sends_per_contact_week"] + e_cfg["blast_extra"] * blast) * np.where(is_holiday, 0.6, 1.0)
    sends = np.round(list_size * freq[:, None] * np.exp(r.normal(0.0, 0.05, (T, R)))).astype(np.int64)
    open_rate = np.clip(e_cfg["open_rate_start"] + e_cfg["open_rate_drift_per_year"] * cal["years"]
                        + r.normal(0.0, 0.01, T), 0.05, 0.9)
    opens = r.binomial(sends, open_rate[:, None])
    ex["sends"], ex["opens"], ex["clicks"] = sends, opens, r.binomial(opens, e_cfg["click_rate_of_opens"])
    a_email = _adstock(np.vstack([st["sends"], sends]).astype(float), tp["email_alpha"], C.L_MAX)[-T:]
    ex["mu_email"] = st["beta_email"] * size * _hill(a_email / size, tp["email_K"], e_cfg["S"])
    ex["is_year_end"] = is_year_end

    # Webinars: regional events, as before.
    w_cfg, r = C.WEBINARS, rngs["webinars"]
    ev_counts = r.poisson(np.broadcast_to(w_cfg["events_per_week_national"] * size / R, (T, R)))
    nz_t, nz_r = np.nonzero(ev_counts)
    reps = ev_counts[nz_t, nz_r]
    ev_t, ev_r = np.repeat(nz_t, reps), np.repeat(nz_r, reps)
    n_ev = ev_t.size
    ev = {"t": ev_t, "r": ev_r,
          "cost": np.round(w_cfg["cost_median"] * np.exp(r.normal(0.0, w_cfg["cost_sigma"], n_ev)), 2),
          "day": r.integers(1, 4, n_ev), "topic": r.integers(0, len(w_cfg["topics"]), n_ev)}
    ev["regs"] = r.poisson(ev["cost"] / w_cfg["cost_per_registrant"])
    ev["attend"] = r.binomial(ev["regs"], w_cfg["attend_rate"])
    web = np.zeros((T, R))
    np.add.at(web, (ev_t, ev_r), ev["cost"])
    ex["webinar_events"], ex["webinars"] = ev, np.round(web, 2)

    # Reporting noise.
    ex["brand_cost_noise"] = np.exp(rngs["brand"].normal(0.0, C.BRAND_SEARCH["noise_sigma"], (T, R)))
    ex["cpm_noise"] = {ch: np.exp(rngs["media_noise"].normal(0.0, 0.08, (T, R)))
                       for ch in ("paid_search_brand", "paid_search_nonbrand", "meta", "linkedin", "youtube", "display")}
    ex["ctr_noise"] = {ch: np.exp(rngs["media_noise"].normal(0.0, 0.10, (T, R)))
                       for ch in ("paid_search_brand", "paid_search_nonbrand", "meta", "linkedin", "youtube", "display")}
    ex["ctv_report_noise"] = np.exp(rngs["ctv_report"].normal(0.0, C.PLATFORM["ctv"]["noise_sigma"], (T, R)))
    ex["dda_noise"] = np.exp(rngs["dda"].normal(0.0, 0.05, (T, R)))
    ex["ctv_impr_noise"] = np.exp(rngs["ctv_impr"].normal(0.0, 0.06, (T, R)))
    return ex


# --- plans -> spend -------------------------------------------------------------------

def _apply_plans(plans: list[Plan], ex: dict, cal: dict, st: dict) -> tuple[dict, list[dict]]:
    """Planned-channel spend (T, R) after every plan's moves, and a log of each move."""
    codes, size = st["codes"], st["size"]
    spend = {ch: x.copy() for ch, x in ex["bau"].items()}
    moves_log = []

    def apply(ch, mv, weeks, markets, tag):
        if not weeks.any():
            return
        g = np.isin(codes, markets) & ex["region_ok"][ch]
        before = spend[ch].copy()
        cell = np.ix_(weeks, g)
        if mv.multiplier is not None:
            spend[ch][cell] = np.round(spend[ch][cell] * mv.multiplier, 2)
        else:
            added = mv.add_per_week_per_size * size[None, g] * ex["add_noise"][ch][cell]
            spend[ch][cell] = np.round(spend[ch][cell] + added, 2)
        spend[ch][spend[ch] < 10.0] = 0.0
        moves_log.append({**tag, "channel": ch, "weeks": weeks, "markets": g,
                          "spend_change": spend[ch] - before})

    for plan in plans:
        if plan.national:
            n = plan.national
            for mv in n.moves:
                apply(mv.channel, mv, _week_mask(cal, n.start, n.end), codes,
                      {"kind": "national", "plan": plan.name, "id": "national"})
        if plan.test:
            t = plan.test
            for arm in t.arms:
                for mv in arm.moves:
                    apply(mv.channel, mv, _week_mask(cal, t.start, t.end), arm.markets,
                          {"kind": "test_arm", "plan": plan.name, "id": arm.id, "test_id": t.id})
    return spend, moves_log


def _media_response(st: dict, ex: dict, planned: dict) -> dict:
    """Brand-search spend and expected leads per paid channel (T, R) for 2026 paths."""
    tp, size, T = st["tp"], st["size"], next(iter(planned.values())).shape[0]
    hist = {ch: np.vstack([st["spend"][ch], planned[ch]]) for ch in planned}
    hist["webinars"] = np.vstack([st["spend"]["webinars"], ex["webinars"]])

    def reach(ch):
        h = tp["brand_searches"][ch]
        a = _adstock(hist[ch], h["alpha"], C.L_MAX)[-T:]
        return size * (1.0 - np.exp(-a / (h["reach_spend"] * size)))

    searches = ex["mu_base"] + sum(st["gamma"][ch] * reach(ch) for ch in C.BRAND_SEARCH["created_by"])
    brand = np.round(searches * ex["brand_cost_noise"] * st["cost_per_search"], 2)
    brand[brand < 25.0] = 0.0
    hist["paid_search_brand"] = np.vstack([st["spend"]["paid_search_brand"], brand])
    mu = {}
    for ch in C.PAID_CHANNELS:
        e = tp["effect"][ch]
        a = _adstock(hist[ch], e["alpha"], C.L_MAX)[-T:]
        mu[ch] = st["betas"][ch] * size * _hill(a / size, e["K"], e["S"])
    return {"brand": brand, "searches": searches, "mu": mu, "webinars": ex["webinars"]}


def _funnel(st: dict, ex: dict, cal: dict) -> dict:
    tp, fp, p_cfg = st["tp"], st["fp"], C.PROMO
    win_time = np.where(ex["is_year_end"], tp["year_end_win_mult"], 1.0) * tp["price_win_mult"]
    amount_time = (np.where(ex["is_year_end"], 1 - p_cfg["year_end_discount_pct"] / 100, 1.0)
                   * (1 + p_cfg["price_change_pct"] / 100))
    p_sql = np.minimum(fp["p_sql"][:, None, None] * ex["sdr_mult"][None], 0.95)
    p_won = np.minimum(fp["p_won"][:, None, None] * ex["ae_mult"][None] * win_time[None, :, None], 0.95)
    p_opp_lead = fp["p_mql"][:, None, None] * p_sql * fp["p_opp"][:, None, None]
    return {"p_sql": p_sql, "p_won": p_won, "p_deal": p_opp_lead * p_won, "p_opp_lead": p_opp_lead,
            "amount_time": amount_time,
            "amount_mean": (C.AMOUNT_MEDIAN * np.exp(C.AMOUNT_SIGMA**2 / 2) * fp["amount_mult"][:, None, None]
                            * amount_time[None, :, None] * st["area_amount"][None, None, :])}


# --- weekly outcomes: one stream per week ----------------------------------------------

def _week_outcomes(w: int, seed: int, st: dict, cal: dict, mu_w: np.ndarray, fun: dict, spend_w: dict,
                   ex: dict, mu_media_w: dict, mu_base_w: np.ndarray) -> dict:
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(STREAM_WEEK, w)))
    fp, size = st["fp"], st["size"]
    R, O = mu_w.shape
    counts = rng.poisson(mu_w)
    flat = np.repeat(np.arange(counts.size), counts.ravel())
    lr, lo_ = np.unravel_index(flat, counts.shape)
    n = flat.size
    day = rng.choice(7, size=n, p=np.array(C.WEEKDAY_WEIGHTS) / sum(C.WEEKDAY_WEIGHTS))
    created = cal["week_d"][w] + day.astype("timedelta64[D]")
    rec = _categorical(rng, st["attr"], lo_)
    var = _categorical(rng, st["vprob"], rec)
    u = rng.random((4, n))
    is_mql = u[0] < fp["p_mql"][lo_]
    is_sql = is_mql & (u[1] < fun["p_sql"][lo_, w, lr])
    is_opp = is_sql & (u[2] < fp["p_opp"][lo_])
    is_won = is_opp & (u[3] < fun["p_won"][lo_, w, lr])

    def lag(key):
        shape, scale_ = C.LAGS[key]
        return np.floor(rng.gamma(shape, scale_, n)).astype("timedelta64[D]")

    mql_date = created + lag("mql")
    sql_date = mql_date + lag("sql")
    opp_date = sql_date + lag("opp")
    lag_won, lag_lost = lag("close_won"), lag("close_lost")
    close_date = opp_date + np.where(is_won, lag_won, lag_lost)
    amount = (C.AMOUNT_MEDIAN * fp["amount_mult"][lo_] * st["area_amount"][lr] * fun["amount_time"][w]
              * np.exp(rng.normal(0.0, C.AMOUNT_SIGMA, n)))
    amount = np.round(amount / 10.0) * 10.0
    perm = rng.permutation(n)
    order = perm[np.argsort(created[perm], kind="stable")]
    leads = {"created": created, "r": lr, "rec": rec, "var": var, "is_mql": is_mql, "is_sql": is_sql,
             "is_opp": is_opp, "is_won": is_won, "mql_date": mql_date, "sql_date": sql_date,
             "opp_date": opp_date, "close_date": close_date, "amount": amount}
    leads = {k: v[order] for k, v in leads.items()}

    reported = {}
    for ch in C.PLATFORM_CHANNELS:
        p = C.PLATFORM[ch]
        x = spend_w[ch]
        reach = 1.0 - np.exp(-x / (p["reach_spend"] * size))
        rate = p["claim_mult"] * mu_media_w[ch] + p["halo"] * mu_base_w * reach
        for src, share in p["halo_from"].items():
            rate = rate + share * mu_media_w[src] * (x > 0)
        if p["noise_sigma"] > 0:
            rate = rate * ex["ctv_report_noise"][w]
        reported[ch] = rng.poisson(rate)
    delivery = {}
    for ch in ("paid_search_brand", "paid_search_nonbrand", "meta", "linkedin", "youtube", "display"):
        m = C.MEDIA[ch]
        cpm = m["cpm"] * (1 + C.Q4_CPM_LIFT * cal["is_q4"][w]) * ex["cpm_noise"][ch][w]
        impressions = np.round(spend_w[ch] / cpm * 1000).astype(np.int64)
        ctr = np.clip(m["ctr"] * ex["ctr_noise"][ch][w], 0, 1)
        delivery[ch] = {"impressions": impressions, "clicks": rng.binomial(impressions, ctr)}
    post_click = rng.binomial(reported["display"], 1 - C.DISPLAY_POST_VIEW_SHARE)
    ctv_impr = np.round(spend_w["ctv"] / C.MEDIA["ctv"]["cpm"] * 1000 * ex["ctv_impr_noise"][w]).astype(np.int64)
    ctv_views = rng.binomial(ctv_impr, C.MEDIA["ctv"]["completion_rate"])
    partner_clicks = rng.poisson(spend_w["affiliates"] / C.MEDIA["affiliates"]["cpc"])
    return {"leads": leads, "reported": reported, "delivery": delivery, "post_click": post_click,
            "ctv_impr": ctv_impr, "ctv_views": ctv_views, "partner_clicks": partner_clicks}


# --- answer key ---------------------------------------------------------------------------

def _close_lag_pmf(seed: int) -> np.ndarray:
    """P(a won deal closes k weeks after its lead's created week), from the true lag model."""
    rng = np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(STREAM_TRUTH,)))
    n = 2_000_000
    day = rng.choice(7, size=n, p=np.array(C.WEEKDAY_WEIGHTS) / sum(C.WEEKDAY_WEIGHTS))
    total = day.astype(float)
    for key in ("mql", "sql", "opp", "close_won"):
        shape, scale_ = C.LAGS[key]
        total += np.floor(rng.gamma(shape, scale_, n))
    weeks = np.minimum(total // 7, LAG_TAIL_WEEKS).astype(int)
    return np.bincount(weeks, minlength=LAG_TAIL_WEEKS + 1) / n


def _expected_deals(st: dict, ex: dict, fun: dict, planned: dict) -> dict:
    """Expected deals (T, R) by lead-created week per origin, and spend, for 2026 paths."""
    resp = _media_response(st, ex, planned)
    o_index = {o: i for i, o in enumerate(C.ORIGINS)}
    mu = {"base": ex["mu_base"], "email": ex["mu_email"], **resp["mu"]}
    deals = {o: mu[o] * fun["p_deal"][o_index[o]] for o in C.ORIGINS}
    return {"deals": deals, "brand": resp["brand"], "mu": mu}


def _by_close_week(x: np.ndarray, pmf: np.ndarray) -> np.ndarray:
    """(T, R) expected deals by created week -> (T + tail, R) by close week."""
    out = np.zeros((x.shape[0] + len(pmf) - 1,) + x.shape[1:])
    for k, p in enumerate(pmf):
        out[k:k + x.shape[0]] += p * x
    return out


def _truth_2026(seed, st, ex, cal, fun, plans, planned, moves_log, through_idx) -> dict:
    pmf = _close_lag_pmf(seed)
    codes = st["codes"]
    actual = _expected_deals(st, ex, fun, planned)
    week_str = list(_date_str(cal["week_d"]))
    paid = [c for c in C.PAID_CHANNELS if c != "webinars"]

    def total(e):
        return sum(e["deals"].values())

    def summarize_effect(cf, mask_r, label):
        """Actual minus counterfactual, in the markets of mask_r."""
        d_created = {o: (actual["deals"][o] - cf["deals"][o])[:, mask_r] for o in C.ORIGINS}
        by_ch = {o: float(v.sum()) for o, v in d_created.items() if o in paid and abs(v.sum()) > 1e-9}
        tot_created = sum(d_created.values()).sum(axis=1)
        tot_close = _by_close_week(tot_created[:, None], pmf)[:, 0]
        weeks_close = [str(cal["weeks"][0] + timedelta(weeks=i)) for i in range(len(tot_close))]
        return {
            "label": label,
            "incremental_deals": _r(tot_created.sum(), 3),
            "incremental_deals_by_channel": {k: _r(v, 3) for k, v in by_ch.items()},
            "incremental_deals_by_close_week": dict(zip(weeks_close, [_r(v, 4) for v in tot_close])),
            "brand_search_spend_change": _r((actual["brand"] - cf["brand"])[:, mask_r].sum(), 2),
        }

    out = {"cells": {}, "national_moves": {}}
    for plan in plans:
        if plan.test:
            for arm in plan.test.arms:
                logs = [m for m in moves_log if m["kind"] == "test_arm" and m["id"] == arm.id]
                cf_paths = {ch: x.copy() for ch, x in planned.items()}
                for m in logs:
                    cf_paths[m["channel"]] = cf_paths[m["channel"]] - m["spend_change"]
                cf = _expected_deals(st, ex, fun, cf_paths)
                mask_r = np.isin(codes, arm.markets)
                eff = summarize_effect(cf, mask_r, f"{plan.test.id} arm {arm.id}")
                eff.update({
                    "test_id": plan.test.id, "markets": arm.markets,
                    "start": str(plan.test.start), "end": str(plan.test.end),
                    "spend_change_by_channel": {m["channel"]: _r(m["spend_change"].sum(), 2) for m in logs},
                    "spend_change_by_market": {c: _r(sum(m["spend_change"][:, i].sum() for m in logs), 2)
                                               for i, c in enumerate(codes) if c in arm.markets},
                })
                out["cells"][arm.id] = eff
        if plan.national:
            logs = [m for m in moves_log if m["kind"] == "national" and m["plan"] == plan.name]
            cf_paths = {ch: x.copy() for ch, x in planned.items()}
            for m in logs:
                cf_paths[m["channel"]] = cf_paths[m["channel"]] - m["spend_change"]
            cf = _expected_deals(st, ex, fun, cf_paths)
            eff = summarize_effect(cf, np.ones(len(codes), bool), f"{plan.name} national moves")
            eff["spend_change_by_channel"] = {m["channel"]: _r(m["spend_change"].sum(), 2) for m in logs}
            out["national_moves"][plan.name] = eff
    bau = _expected_deals(st, ex, fun, ex["bau"])
    gen = slice(0, through_idx)
    out["year"] = {
        "weeks_generated": through_idx,
        "expected_deals_by_created_week_actual": _r(total(actual)[gen].sum(), 2),
        "expected_deals_by_created_week_bau": _r(total(bau)[gen].sum(), 2),
        "paid_spend_actual": _r(sum(planned[c][gen].sum() for c in planned) + actual["brand"][gen].sum()
                                + ex["webinars"][gen].sum(), 2),
        "paid_spend_bau": _r(sum(ex["bau"][c][gen].sum() for c in planned) + bau["brand"][gen].sum()
                             + ex["webinars"][gen].sum(), 2),
        "first_week": week_str[0], "last_week": week_str[through_idx - 1],
    }
    out["definitions"] = {
        "incremental_deals": "expected deals (noise-free) from leads created in 2026, actual plans minus the same "
                             "plans with this arm's or move's spend change taken out, in the markets it touched. "
                             "Counts deals from leads created after the move ends (carryover) and the deals "
                             "brand search adds from the extra brand searches the upper funnel creates",
        "incremental_deals_by_close_week": "the same, spread over close weeks with the true lead-to-close lag",
        "close_lag_pmf_weeks": [round(float(p), 6) for p in pmf],
        "bau": "the plans' budget basis with no test arm and no national move; same draws for everything else",
    }
    return out


# --- tables --------------------------------------------------------------------------------

def simulate_through(seed: int, through: date, plan_paths=()) -> SimResult:
    """The base world plus 2026 weeks up to the snapshot date `through`."""
    base = simulate(seed, keep_state=True)
    st = base.state
    plans = load_all(plan_paths) if plan_paths else load_all([])
    cal = _calendar()
    last_monday = through - timedelta(days=6)
    n_gen = sum(1 for w in cal["weeks"] if w <= last_monday)
    if n_gen <= 0:
        return base
    ex = _exogenous(st, cal, seed)
    planned, moves_log = _apply_plans(plans, ex, cal, st)
    resp = _media_response(st, ex, planned)
    spend = {**planned, "paid_search_brand": resp["brand"], "webinars": ex["webinars"]}
    fun = _funnel(st, ex, cal)
    mu_origin = {"base": ex["mu_base"], "email": ex["mu_email"], **resp["mu"]}
    mu = np.stack([mu_origin[o] for o in C.ORIGINS], axis=2)  # (T, R, O)

    weeks_out = [_week_outcomes(w, seed, st, cal, mu[w], fun, {c: spend[c][w] for c in C.PAID_CHANNELS},
                                ex, {c: resp["mu"][c][w] for c in C.PAID_CHANNELS}, ex["mu_base"][w])
                 for w in range(n_gen)]
    snapshot = np.datetime64(through, "D")
    tables = _tables(base, st, cal, ex, plans, spend, weeks_out, n_gen, snapshot)
    truth26 = _truth_2026(seed, st, ex, cal, fun, plans, planned, moves_log, n_gen)
    truth26 = {"company": C.COMPANY, "seed": seed, "snapshot": str(through),
               "plans": [p.path for p in plans], **truth26}
    return SimResult(tables=tables, truth=base.truth, truth_2026=truth26)


def _tables(base: SimResult, st: dict, cal: dict, ex: dict, plans: list[Plan], spend: dict,
            weeks_out: list[dict], n_gen: int, snapshot) -> dict[str, pd.DataFrame]:
    t = dict(base.tables)
    codes = np.array(st["codes"], dtype=object)
    names = np.array(st["names"], dtype=object)
    week_str = _date_str(cal["week_d"][:n_gen])

    def cells(x):
        tt, rr = np.nonzero(x[:n_gen] > 0)
        return tt, rr

    def per_week(key, ch=None, sub=None):
        arrs = [wo[key] if ch is None else (wo[key][ch] if sub is None else wo[key][ch][sub]) for wo in weeks_out]
        return np.stack(arrs)

    rep = {ch: per_week("reported", ch) for ch in C.PLATFORM_CHANNELS}
    imp = {ch: per_week("delivery", ch, "impressions") for ch in
           ("paid_search_brand", "paid_search_nonbrand", "meta", "linkedin", "youtube", "display")}
    clk = {ch: per_week("delivery", ch, "clicks") for ch in imp}

    parts = []
    for ch, ctype, cname in (("paid_search_brand", "SEARCH", "FH_Search_Brand"),
                             ("paid_search_nonbrand", "SEARCH", "FH_Search_NonBrand"),
                             ("youtube", "VIDEO", "FH_YouTube_Prospecting")):
        tt, rr = cells(spend[ch])
        parts.append(pd.DataFrame({
            "week_start_date": week_str[tt], "geo_target_region": codes[rr], "campaign_type": ctype,
            "campaign_name": cname, "cost_micros": np.round(spend[ch][tt, rr] * 1_000_000).astype(np.int64),
            "impressions": imp[ch][tt, rr], "clicks": clk[ch][tt, rr],
            "conversions": np.round(rep[ch][tt, rr] * ex["dda_noise"][tt, rr], 2)}))
    g26 = (pd.concat(parts, ignore_index=True)
           .sort_values(["week_start_date", "geo_target_region", "campaign_name"], kind="stable"))
    t["ads_google_weekly"] = pd.concat([t["ads_google_weekly"], g26], ignore_index=True)

    tt, rr = cells(spend["meta"])
    t["ads_meta_weekly"] = pd.concat([t["ads_meta_weekly"], pd.DataFrame({
        "date_start": week_str[tt], "date_stop": _date_str(cal["week_d"][tt] + np.timedelta64(6, "D")),
        "region": names[rr], "spend": spend["meta"][tt, rr], "impressions": imp["meta"][tt, rr],
        "clicks": clk["meta"][tt, rr], "leads": rep["meta"][tt, rr]})], ignore_index=True)
    tt, rr = cells(spend["linkedin"])
    t["ads_linkedin_weekly"] = pd.concat([t["ads_linkedin_weekly"], pd.DataFrame({
        "start_date": week_str[tt], "region_code": codes[rr], "cost_usd": spend["linkedin"][tt, rr],
        "impressions": imp["linkedin"][tt, rr], "clicks": clk["linkedin"][tt, rr],
        "conversions": rep["linkedin"][tt, rr]})], ignore_index=True)
    post_click = per_week("post_click")
    tt, rr = cells(spend["display"])
    t["ads_display_weekly"] = pd.concat([t["ads_display_weekly"], pd.DataFrame({
        "week": week_str[tt], "region_code": codes[rr], "media_cost": spend["display"][tt, rr],
        "impressions": imp["display"][tt, rr], "clicks": clk["display"][tt, rr],
        "post_click_conversions": post_click[tt, rr],
        "post_view_conversions": rep["display"][tt, rr] - post_click[tt, rr]})], ignore_index=True)
    ctv_impr, ctv_views = per_week("ctv_impr"), per_week("ctv_views")
    tt, rr = cells(spend["ctv"])
    t["ctv_weekly"] = pd.concat([t["ctv_weekly"], pd.DataFrame({
        "week_start": week_str[tt], "geo_region": codes[rr], "spend": spend["ctv"][tt, rr],
        "impressions": ctv_impr[tt, rr], "completed_views": ctv_views[tt, rr],
        "attributed_leads": rep["ctv"][tt, rr]})], ignore_index=True)
    pclk = per_week("partner_clicks")
    tt, rr = cells(spend["affiliates"])
    t["partners_weekly"] = pd.concat([t["partners_weekly"], pd.DataFrame({
        "week_start": week_str[tt], "region_code": codes[rr], "partner_fees": spend["affiliates"][tt, rr],
        "partner_clicks": pclk[tt, rr], "referred_signups": rep["affiliates"][tt, rr]})], ignore_index=True)

    ev = ex["webinar_events"]
    keep = ev["t"] < n_gen
    ev_date = cal["week_d"][ev["t"]] + ev["day"].astype("timedelta64[D]")
    o = np.lexsort((ev["r"][keep], ev_date[keep]))
    n0 = st["n_events"]
    t["webinar_events"] = pd.concat([t["webinar_events"], pd.DataFrame({
        "event_id": [f"WB{i:04d}" for i in range(n0 + 1, n0 + keep.sum() + 1)],
        "event_date": _date_str(ev_date[keep][o]), "region_code": codes[ev["r"][keep][o]],
        "topic": np.array(C.WEBINARS["topics"], dtype=object)[ev["topic"][keep][o]],
        "total_cost": ev["cost"][keep][o], "registrants": ev["regs"][keep][o],
        "attendees": ev["attend"][keep][o]})], ignore_index=True)

    months = sorted({m for m in cal["month"][:n_gen] if m >= 0})
    t["sales_capacity_monthly"] = pd.concat([t["sales_capacity_monthly"], pd.DataFrame({
        "month_start": np.repeat([str(date(2026, m + 1, 1)) for m in months], len(codes)),
        "region_code": np.tile(codes, len(months)),
        "sdr_headcount": ex["sales_counts"]["sdr"][months].ravel(),
        "ae_headcount": ex["sales_counts"]["ae"][months].ravel()})], ignore_index=True)

    t["email_weekly"] = pd.concat([t["email_weekly"], pd.DataFrame({
        "week_start": np.repeat(week_str, len(codes)), "region_code": np.tile(codes, n_gen),
        "emails_sent": ex["sends"][:n_gen].ravel(), "unique_opens": ex["opens"][:n_gen].ravel(),
        "unique_clicks": ex["clicks"][:n_gen].ravel()})], ignore_index=True)
    t["fleet_activity_index_weekly"] = pd.concat([t["fleet_activity_index_weekly"], pd.DataFrame({
        "week_start": week_str, "fleet_activity_index": ex["fleet_index"][:n_gen]})], ignore_index=True)

    promo = t["promo_calendar"]
    ye_lo, ye_hi = C.PROMO["year_end_weeks"]
    years = sorted({w.year for w in cal["weeks"][:n_gen]} - set(range(C.WINDOW_START.year, 2026)))
    new = pd.DataFrame([{"promo_id": f"YE{yr}", "promo_name": f"Year-end annual plan offer {yr}",
                         "promo_type": "discount", "start_date": str(_monday_of_iso_week(yr, ye_lo)),
                         "end_date": str(_monday_of_iso_week(yr, ye_hi) + timedelta(days=6)),
                         "discount_pct": C.PROMO["year_end_discount_pct"], "price_change_pct": ""}
                        for yr in years])
    is_ye = promo.promo_type == "discount"
    t["promo_calendar"] = pd.concat([promo[is_ye], new, promo[~is_ye]], ignore_index=True)

    last_day = cal["weeks"][n_gen - 1] + timedelta(days=6)
    changes = [{"change_date": str(p.national.start), "channel": mv.channel,
                "budget_change_pct": round(100 * (mv.multiplier - 1)) if mv.multiplier is not None else "",
                "reason": p.name}
               for p in plans if p.national and p.national.start <= last_day for mv in p.national.moves]
    if changes:
        t["media_plan_changes"] = pd.concat([t["media_plan_changes"], pd.DataFrame(changes)], ignore_index=True)

    rows = []
    for p in plans:
        if p.test and p.test.start <= last_day:
            for arm in p.test.arms:
                for m in arm.markets:
                    for mv in arm.moves:
                        kind = "multiplier" if mv.multiplier is not None else "add_per_week_per_size"
                        rows.append({"test_id": p.test.id, "test_name": p.name, "arm_id": arm.id,
                                     "region_code": m, "channel": mv.channel, "move": kind,
                                     "move_value": mv.multiplier if mv.multiplier is not None else mv.add_per_week_per_size,
                                     "start_date": str(p.test.start),
                                     "end_date": str(p.test.end + timedelta(days=6)),
                                     "approved_date": str(p.approved)})
    t["market_tests"] = pd.DataFrame(rows, columns=["test_id", "test_name", "arm_id", "region_code", "channel",
                                                    "move", "move_value", "start_date", "end_date", "approved_date"])

    t["crm_leads"], t["crm_opportunities"] = _crm(st, weeks_out, snapshot)
    return t


def _crm(st: dict, weeks_out: list[dict], snapshot) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CRM leads and opportunities as exported at `snapshot`: base leads in their
    original order with their later stages now visible, then the 2026 leads."""
    L = st["leads"]
    o = L["order"]
    base = {"created": L["created"][o], "r": L["r"][o], "rec": L["rec"][o], "var": L["var"][o]}
    for k in ("is_mql", "is_sql", "is_opp", "is_won", "mql_date", "sql_date", "opp_date", "close_date", "amount"):
        base[k] = L[k][o]
    keys = list(base)
    new = {k: np.concatenate([wo["leads"][k] for wo in weeks_out]) for k in keys}
    a = {k: np.concatenate([base[k], new[k]]) for k in keys}
    n_base, n = base["created"].size, a["created"].size
    nat = np.datetime64("NaT", "D")
    codes = np.array(st["codes"], dtype=object)
    lead_ids = np.concatenate([L["lead_ids"], np.array([f"LD{i:07d}" for i in range(n_base + 1, n + 1)], dtype=object)])
    src, med, camp = st["vsrc"][a["rec"], a["var"]], st["vmed"][a["rec"], a["var"]], st["vcamp"][a["rec"], a["var"]]
    leads = pd.DataFrame({
        "lead_id": lead_ids, "created_date": _date_str(a["created"]), "region_code": codes[a["r"]],
        "utm_source": src, "utm_medium": med, "utm_campaign": camp,
        "mql_date": _date_str(np.where(a["is_mql"] & (a["mql_date"] <= snapshot), a["mql_date"], nat)),
        "sql_date": _date_str(np.where(a["is_sql"] & (a["sql_date"] <= snapshot), a["sql_date"], nat)),
    })
    base_snap = np.datetime64(BASE_SNAPSHOT, "D")
    exists = a["is_opp"] & (a["opp_date"] <= snapshot)
    old = np.where(exists & (a["opp_date"] <= base_snap))[0]
    old = old[np.argsort(a["opp_date"][old], kind="stable")]
    later = np.where(exists & (a["opp_date"] > base_snap))[0]
    later = later[np.argsort(a["opp_date"][later], kind="stable")]
    rows = np.concatenate([old, later])
    assert old.size == st["leads"]["n_opps"], "base opportunities must keep their ids"
    closed = a["close_date"][rows] <= snapshot
    stage = np.where(~closed, "Open", np.where(a["is_won"][rows], "Closed Won", "Closed Lost"))
    opps = pd.DataFrame({
        "opportunity_id": [f"OP{i:06d}" for i in range(1, rows.size + 1)],
        "lead_id": lead_ids[rows], "created_date": _date_str(a["opp_date"][rows]), "amount": a["amount"][rows],
        "stage": stage, "close_date": _date_str(np.where(closed, a["close_date"][rows], nat)),
    })
    return leads, opps
