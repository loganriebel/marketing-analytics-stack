"""Export the golden marts and the MMM outputs as CSVs for Tableau Public.

Tableau Public cannot read DuckDB, so CSVs are the hand-off. Inputs:

* data/warehouse.duckdb, opened read-only, marts only (fct_*, dim_*).
* mmm/outputs/: MMM estimates, response curves, the optimizer plan, and the
  CRM last-touch and platform-reported baselines.
* mmm/grading/grade_<fit>.json: the grader's written results, for the answer-key
  columns. mmm/grade.py stays the only reader of the simulator's answer key.
* tableau/metro_centroids.csv: public longitudes of each market's main city
  (dim_region carries latitude only).
* For dashboard 4 (the spring test and the rollout): the year-end data cut
  (data/cut_2027-01-03/data/warehouse.duckdb, marts only), the test readout
  (geotest/outputs/readout.json), the rollout plan and its holdout readout
  (rollout/outputs/), and the grader's 2026 results (mmm/grading/grade_2026.json)
  for the answer-key columns. Skipped, with a note, until the year-end cut exists.

Writes tableau/data/*.csv: ISO dates, one row per grain, numbers as numbers,
flags as 1/0, blank where a value does not exist (CPA with no deals, clicks a
source does not report).

    python -m tableau.export [--out-dir DIR]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WAREHOUSE = REPO / "data" / "warehouse.duckdb"
MMM_OUTPUTS = REPO / "mmm" / "outputs"
MMM_GRADING = REPO / "mmm" / "grading"
YEAR_END = REPO / "data" / "cut_2027-01-03" / "data" / "warehouse.duckdb"
READOUT = REPO / "geotest" / "outputs" / "readout.json"
ROLLOUT = REPO / "rollout" / "outputs"
CENTROIDS = HERE / "metro_centroids.csv"
OUT_DIR = HERE / "data"

ANSWER_KEY_NOTE = ("Answer key, from the MMM grader. It exists only because the data is synthetic; "
                   "a real team never has it.")

# Organic and email leads have funnel rows but no media rows, hence the full join.
WEEKLY_SQL = """
with joined as (
    select
        coalesce(f.week_start, c.week_start) as week_start,
        coalesce(f.region_id, c.region_id) as region_id,
        coalesce(f.channel_id, c.channel_id) as channel_id,
        coalesce(c.spend, 0)::double as spend,
        c.impressions,
        c.clicks,
        c.platform_conversions::double as platform_conversions,
        coalesce(f.leads, 0) as leads,
        coalesce(f.mqls, 0) as mqls,
        coalesce(f.sqls, 0) as sqls,
        coalesce(f.opportunities, 0) as opportunities,
        coalesce(f.pipeline_amount, 0)::double as pipeline_amount,
        coalesce(f.won_deals, 0) as won_deals,
        coalesce(f.won_revenue, 0)::double as won_revenue,
        coalesce(f.lost_deals, 0) as lost_deals
    from fct_funnel as f
    full join fct_channel_weekly as c
        on f.week_start = c.week_start
        and f.region_id = c.region_id
        and f.channel_id = c.channel_id
)

select
    j.week_start,
    r.region_id,
    r.region_name as market,
    r.state,
    r.sales_area,
    r.latitude,
    r.target_accounts,
    ch.channel_id,
    ch.channel_name,
    ch.channel_group,
    ch.marketing_role,
    ch.is_paid::int as is_paid,
    ch.sort_order as channel_sort,
    j.spend,
    j.impressions,
    j.clicks,
    j.platform_conversions,
    j.leads,
    j.mqls,
    j.sqls,
    j.opportunities,
    j.pipeline_amount,
    j.won_deals,
    j.won_revenue,
    j.lost_deals
from joined as j
inner join dim_region as r on j.region_id = r.region_id
inner join dim_channel as ch on j.channel_id = ch.channel_id
order by j.week_start, r.region_id, ch.sort_order
"""

CONTROLS_SQL = """
select
    c.week_start,
    r.region_id,
    r.region_name as market,
    r.state,
    r.sales_area,
    r.latitude,
    r.target_accounts,
    c.sdr_headcount,
    c.ae_headcount,
    c.emails_sent,
    c.email_opens,
    c.email_clicks,
    c.is_discount_promo::int as is_discount_promo,
    c.list_price_index::double as list_price_index,
    c.fleet_activity_index::double as fleet_activity_index
from fct_controls_weekly as c
inner join dim_region as r on c.region_id = r.region_id
order by c.week_start, r.region_id
"""

CHANNELS_SQL = """
select channel_id, channel_name, channel_group, marketing_role, sort_order as channel_sort
from dim_channel
"""

VIEWS = (
    ("crm_last_touch", "CRM last touch", 1),
    ("platform_reported", "Platform reported", 2),
    ("mmm", "MMM", 3),
    ("truth", "Truth (answer key)", 4),
)


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _iso(df: pd.DataFrame) -> pd.DataFrame:
    df["week_start"] = pd.to_datetime(df["week_start"]).dt.strftime("%Y-%m-%d")
    return df


def _add_longitude(df: pd.DataFrame) -> pd.DataFrame:
    lon = pd.read_csv(CENTROIDS)
    merged = df.merge(lon, on="region_id", how="left", validate="many_to_one")
    bad = merged[merged["longitude"].isna() | (merged["region_name"] != merged["market"])]
    if len(bad):
        raise SystemExit(f"metro_centroids.csv does not match dim_region: {sorted(set(bad['region_id']))}")
    merged = merged.drop(columns="region_name")
    cols = list(df.columns)
    cols.insert(cols.index("latitude") + 1, "longitude")
    return merged[cols]


def check_same_world(con: duckdb.DuckDBPyConnection, mmm: dict) -> None:
    """The MMM outputs must describe the world in this warehouse (same seed, same window)."""
    spend = dict(con.sql("select channel_id, sum(spend)::double from fct_channel_weekly group by 1").fetchall())
    off = [ch for ch, est in mmm["channels"].items() if abs(spend.get(ch, 0.0) - est["spend"]) > 0.01]
    first, last = (d.isoformat() for d in con.sql("select min(week_start), max(week_start) from fct_funnel").fetchall()[0])
    if off or [first, last] != mmm["meta"]["window"]:
        raise SystemExit(f"mmm/outputs/ was fit on a different warehouse (spend differs for {off or 'none'}, "
                         f"window {first} to {last} vs {mmm['meta']['window']}). Rebuild one or the other.")


def weekly_channel_market(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = _iso(con.sql(WEEKLY_SQL).df())
    for col in ("impressions", "clicks"):
        df[col] = df[col].astype("Int64")
    return _add_longitude(df)


def controls_weekly_market(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    return _add_longitude(_iso(con.sql(CONTROLS_SQL).df()))


def _dims(dims: pd.DataFrame, ch: str) -> dict:
    d = dims.loc[ch]
    return {"channel_id": ch, "channel_name": d["channel_name"], "channel_group": d["channel_group"],
            "marketing_role": d["marketing_role"], "channel_sort": int(d["channel_sort"])}


def _post(est: dict | None, prefix: str) -> dict:
    """Posterior median and 90% HDI as three columns."""
    if est is None:
        return {prefix: None, f"{prefix}_hdi_low": None, f"{prefix}_hdi_high": None}
    return {prefix: est["median"], f"{prefix}_hdi_low": est["hdi_90"][0], f"{prefix}_hdi_high": est["hdi_90"][1]}


def _view(view_id: str) -> dict:
    vid, name, order = next(v for v in VIEWS if v[0] == view_id)
    return {"view_id": vid, "view_name": name, "view_order": order, "is_answer_key": int(vid == "truth")}


def _true(block: dict | None, key: str):
    return block[key]["true"] if block and key in block else None


def mmm_channel_views(dims: pd.DataFrame, mmm: dict, baselines: dict, grade: dict) -> pd.DataFrame:
    empty_post = {**_post(None, "deals"), **_post(None, "cpa"), **_post(None, "marginal_cpa"),
                  "deals_via_brand_search": None, **_post(None, "cpa_total")}
    rows = []
    for ch, est in mmm["channels"].items():
        base = {"grain": "channel", **_dims(dims, ch), "spend": est["spend"]}
        b = baselines["channels"][ch]
        true = grade["model"]["channels"][ch]
        true_med = grade.get("mediation", {}).get("channels", {}).get(ch)
        for vid in ("crm_last_touch", "platform_reported"):
            deals, cpa = b[vid]["deals"], b[vid]["cpa"]
            note = {"crm_last_touch": "Closed-won deals credited to the last UTM touch.",
                    "platform_reported": "Platform-claimed conversions times the company lead-to-won rate."}[vid]
            if not deals:
                note = "Last touch credits this channel with no deals, so it has no CPA."
            rows.append({**base, **_view(vid), **empty_post, "deals": deals, "cpa": cpa, "note": note})
        rows.append({**base, **_view("mmm"), **_post(est["incremental_deals"], "deals"), **_post(est["cpa"], "cpa"),
                     **_post(est["marginal_cpa"], "marginal_cpa"),
                     "deals_via_brand_search": (est.get("incremental_deals_via_brand_search") or {}).get("median"),
                     **_post(est.get("cpa_total"), "cpa_total"),
                     "note": "Incremental deals, posterior median with 90% HDI."})
        rows.append({**base, **_view("truth"), **empty_post,
                     "deals": _true(true, "incremental_deals"), "cpa": _true(true, "cpa"),
                     "marginal_cpa": _true(true, "marginal_cpa"),
                     "deals_via_brand_search": _true(true_med, "incremental_deals_via_brand_search"),
                     "cpa_total": _true(true_med, "cpa_total"), "note": ANSWER_KEY_NOTE})

    channels = list(mmm["channels"])
    spend = sum(mmm["channels"][ch]["spend"] for ch in channels)
    total = {"grain": "paid_media_total", "channel_id": "paid_media_total",
             "channel_name": f"Paid media ({len(channels)} channels)", "channel_group": None,
             "marketing_role": None, "channel_sort": 99, "spend": spend}
    # View-level scores from the grader sit on the total rows. CRM and platform rank the
    # next dollar by average CPA; the MMM by marginal CPA.
    def score(g: dict, rank_key: str, err: float) -> dict:
        return {"cpa_rank_corr_vs_truth": g["cpa_rank"]["spearman"], "median_abs_cpa_error_pct": err,
                "best_next_dollar": dims.loc[g[rank_key]["best"], "channel_name"],
                "best_next_dollar_right": int(g["best_marginal_cpa_right"])}

    for vid in ("crm_last_touch", "platform_reported"):
        deals = sum(baselines["channels"][ch][vid]["deals"] for ch in channels)
        rows.append({**total, **_view(vid), **empty_post, "deals": deals, "cpa": spend / deals,
                     **score(grade[vid], "cpa_rank", grade[vid]["median_abs_cpa_pct_error"]),
                     "note": "Sum over the channels the MMM measures; webinars are a control."})
    s = mmm["summary"]
    rows.append({**total, **_view("mmm"), **empty_post, **_post(s["incremental_deals_paid_media"], "deals"),
                 **_post(s["incremental_cpa_paid_media"], "cpa"),
                 **score(grade["model"], "marginal_cpa_rank", grade["model"]["median_abs_pct_error"]["cpa"]),
                 "note": "Total incremental deals, posterior median with 90% HDI."})
    t = grade["model"]["totals"]
    rows.append({**total, **_view("truth"), **empty_post, "deals": _true(t, "incremental_deals_paid_media"),
                 "cpa": _true(t, "incremental_cpa_paid_media"), "best_next_dollar": dims.loc[grade["model"]["true_best_marginal"], "channel_name"],
                 "note": ANSWER_KEY_NOTE})

    df = pd.DataFrame(rows)
    df = df[[c for c in df.columns if c != "note"] + ["note"]]
    df["best_next_dollar_right"] = df["best_next_dollar_right"].astype("Int64")
    df[["cpa_rank_corr_vs_truth", "median_abs_cpa_error_pct"]] = df[
        ["cpa_rank_corr_vs_truth", "median_abs_cpa_error_pct"]].astype(float).round(4)
    money = [c for c in df.columns if c.startswith(("cpa", "marginal_cpa")) or c == "spend"]
    df[money] = df[money].astype(float).round(2)
    count = [c for c in df.columns if c.startswith("deals")]
    df[count] = df[count].astype(float).round(2)
    return df.sort_values(["channel_sort", "view_order"], kind="stable").reset_index(drop=True)


def mmm_response_curves(dims: pd.DataFrame, optimizer: dict) -> pd.DataFrame:
    direct = pd.read_csv(MMM_OUTPUTS / "response_curves.csv").rename(columns={
        "channel": "channel_id", "incremental_deals_mean": "deals_direct_mean",
        "hdi_90_low": "deals_direct_hdi_low", "hdi_90_high": "deals_direct_hdi_high"})
    total = pd.read_csv(MMM_OUTPUTS / "response_curves_total.csv").rename(columns={
        "channel": "channel_id", "incremental_deals_total_mean": "total_mean", "hdi_90_low": "total_low",
        "hdi_90_high": "total_high", "via_brand_search_mean": "deals_via_brand_search_mean"}).drop(columns="spend")
    df = direct.merge(total, on=["channel_id", "spend_multiplier"], how="left", validate="one_to_one")
    # The optimizer moves upper-funnel channels on their total curve: direct plus via brand search.
    has_total = df["total_mean"].notna()
    df["curve_basis"] = has_total.map({True: "direct plus via brand search", False: "direct"})
    df["deals_mean"] = df["total_mean"].where(has_total, df["deals_direct_mean"])
    df["deals_hdi_low"] = df["total_low"].where(has_total, df["deals_direct_hdi_low"])
    df["deals_hdi_high"] = df["total_high"].where(has_total, df["deals_direct_hdi_high"])
    meta = pd.DataFrame([_dims(dims, ch) for ch in df["channel_id"].unique()])
    df = df.merge(meta, on="channel_id", how="left")
    df["is_lever"] = df["channel_id"].isin(optimizer["levers"]).astype(int)
    df["spend"] = df["spend"].round(2)
    cols = ["channel_id", "channel_name", "channel_group", "marketing_role", "channel_sort", "is_lever",
            "curve_basis", "spend_multiplier", "spend", "deals_mean", "deals_hdi_low", "deals_hdi_high",
            "deals_direct_mean", "deals_direct_hdi_low", "deals_direct_hdi_high", "deals_via_brand_search_mean"]
    return df[cols].sort_values(["channel_sort", "spend_multiplier"], kind="stable").reset_index(drop=True)


def mmm_optimizer_plan(dims: pd.DataFrame, optimizer: dict, mmm: dict, grade: dict) -> pd.DataFrame:
    lo, hi = optimizer["bounds"]
    true_by = {r["channel"]: r["true_deal_change"] for r in grade["optimizer"]["by_channel"]}
    blank = {"deal_change_mean": None, "deal_change_median": None, "deal_change_hdi_low": None,
             "deal_change_hdi_high": None, "prob_gain_positive": None, "true_deal_change": None}

    def deal_change(dc: dict) -> dict:
        return {"deal_change_mean": dc["mean"], "deal_change_median": dc["median"],
                "deal_change_hdi_low": dc["hdi_90"][0], "deal_change_hdi_high": dc["hdi_90"][1]}

    rows = []
    for p in optimizer["plan"]:
        m = p["multiplier"]
        rows.append({"grain": "channel", **_dims(dims, p["channel"]), "is_lever": 1,
                     "spend_now": p["spend_now"], "spend_plan": p["spend_plan"], "spend_change": p["spend_change"],
                     "multiplier": m, "at_bound": int(min(abs(m - lo), abs(m - hi)) < 1e-6), **blank,
                     **deal_change(p["deal_change"]), "true_deal_change": true_by[p["channel"]],
                     "brand_search_spend_change": p.get("brand_search_spend_change"),
                     "note": "Deal change, posterior mean and median with 90% HDI."})

    bs_change = optimizer["brand_search_spend_change"]
    bs_now = mmm["channels"]["paid_search_brand"]["spend"]
    rows.append({"grain": "channel", **_dims(dims, "paid_search_brand"), "is_lever": 0,
                 "spend_now": bs_now, "spend_plan": bs_now + bs_change, "spend_change": bs_change,
                 "multiplier": (bs_now + bs_change) / bs_now, "at_bound": 0, **blank,
                 "brand_search_spend_change": bs_change,
                 "note": "Not a lever: always on, and its spend follows searches. It rises with the plan's "
                         "upper-funnel moves; deals from those searches are counted in Meta, YouTube and CTV."})

    plan_spend = sum(p["spend_plan"] for p in optimizer["plan"])
    rows.append({"grain": "total", "channel_id": "levers_total", "channel_name": "All levers, same total spend",
                 "channel_group": None, "marketing_role": None, "channel_sort": 99, "is_lever": 1,
                 "spend_now": optimizer["total_spend"], "spend_plan": plan_spend,
                 "spend_change": plan_spend - optimizer["total_spend"], "multiplier": 1.0, "at_bound": 0, **blank,
                 **deal_change(optimizer["deal_change"]), "prob_gain_positive": optimizer["prob_gain_positive"],
                 "true_deal_change": grade["optimizer"]["true_deal_change"],
                 "brand_search_spend_change": bs_change,
                 "note": "Deal change for the whole plan, with 90% HDI. true_deal_change is the answer key: "
                         "the plan run through the true response curves."})

    df = pd.DataFrame(rows)
    money = ["spend_now", "spend_plan", "spend_change", "brand_search_spend_change"]
    df[money] = df[money].astype(float).round(2)
    df["spend_change"] = df["spend_change"].where(df["spend_change"].abs() >= 0.01, 0.0)
    df["multiplier"] = df["multiplier"].round(4)
    deals = [c for c in df.columns if c.startswith("deal_change") or c == "true_deal_change"]
    df[deals] = df[deals].astype(float).round(2)
    df["prob_gain_positive"] = df["prob_gain_positive"].astype(float).round(4)
    return df.sort_values(["channel_sort"], kind="stable").reset_index(drop=True)


TEST_WEEKLY_SQL = """
select
    f.week_start,
    r.region_id,
    r.region_name as market,
    r.sales_area,
    r.target_accounts,
    r.market_test_cell,
    r.youtube_test_group,
    r.search_test_group,
    r.rollout_group,
    f.won_deals,
    coalesce(s.paid_spend, 0) as paid_spend,
    coalesce(s.youtube, 0) as spend_youtube,
    coalesce(s.paid_search_nonbrand, 0) as spend_paid_search_nonbrand,
    coalesce(s.paid_search_brand, 0) as spend_paid_search_brand,
    coalesce(s.meta, 0) as spend_meta,
    coalesce(s.linkedin, 0) as spend_linkedin,
    coalesce(s.ctv, 0) as spend_ctv,
    coalesce(s.display, 0) as spend_display,
    coalesce(s.affiliates, 0) as spend_affiliates
from (select week_start, region_id, sum(won_deals) as won_deals from fct_funnel group by 1, 2) as f
inner join dim_region as r on f.region_id = r.region_id
left join (
    select
        week_start, region_id,
        sum(spend)::double as paid_spend,
        sum(case when channel_id = 'youtube' then spend end)::double as youtube,
        sum(case when channel_id = 'paid_search_nonbrand' then spend end)::double as paid_search_nonbrand,
        sum(case when channel_id = 'paid_search_brand' then spend end)::double as paid_search_brand,
        sum(case when channel_id = 'meta' then spend end)::double as meta,
        sum(case when channel_id = 'linkedin' then spend end)::double as linkedin,
        sum(case when channel_id = 'ctv' then spend end)::double as ctv,
        sum(case when channel_id = 'display' then spend end)::double as display,
        sum(case when channel_id = 'affiliates' then spend end)::double as affiliates
    from fct_channel_weekly
    group by 1, 2
) as s on f.week_start = s.week_start and f.region_id = s.region_id
order by f.week_start, r.region_id
"""


def test_rollout_weekly_market(con: duckdb.DuckDBPyConnection, readout: dict, plan: dict) -> pd.DataFrame:
    """Week x market from the year-end cut, with each market's test cell and rollout group and
    each week's period: test weeks, the test's readout window, the rollout weeks, and the
    pre-periods each readout scales by."""
    df = _iso(con.sql(TEST_WEEKLY_SQL).df())
    w, h = readout["window"], plan["holdout"]
    wk = df["week_start"]
    first_test = pd.Timestamp(w["test_start"])
    df["is_test_week"] = wk.between(w["test_start"], w["test_end"]).astype(int)
    df["is_test_window"] = wk.between(w["window_start"], w["window_end"]).astype(int)
    df["is_test_pre_period"] = wk.between(str((first_test - pd.Timedelta(weeks=w["pre_period_weeks"])).date()),
                                          str((first_test - pd.Timedelta(days=1)).date())).astype(int)
    df["is_rollout_week"] = wk.between(*h["window"]).astype(int)
    df["is_rollout_pre_period"] = wk.between(*h["pre_period"]).astype(int)
    money = [c for c in df.columns if c == "paid_spend" or c.startswith("spend_")]
    df[money] = df[money].round(2)
    return df.reset_index(drop=True)


def _readout_row(what: str, window: list, measured: dict, forecast: dict, power: float, decision: str,
                 truth: dict | None) -> dict:
    return {"readout": what, "window_start": window[0], "window_end": window[1],
            "measured": measured["value"], "measured_low": measured["low"], "measured_high": measured["high"],
            "forecast": forecast["value"], "forecast_low": forecast["low"], "forecast_high": forecast["high"],
            "power_at_forecast": power, "decision": decision,
            "true_in_window": None if truth is None else truth["true_in_window"],
            "answer_key_note": ANSWER_KEY_NOTE if truth is not None else None}


def story_readouts(readout: dict, plan: dict, results: dict, grade: dict | None) -> pd.DataFrame:
    """One row per readout: the spring test's two arms and the rollout, measured against forecast."""
    w, d = readout["window"], readout["decision"]
    rows = []
    for key, what, decision in (("grow", "Spring test: YouTube push", f"YouTube works; {d['rule_2_grow']}"),
                                ("cut", "Spring test: non-brand search pullback",
                                 f"No clear drop; {d['rule_2_cut']}")):
        a = readout["arms"][key]
        rows.append(_readout_row(
            what, [w["window_start"], w["window_end"]],
            {"value": a["lift"], "low": a["interval_90"][0], "high": a["interval_90"][1]},
            {"value": a["forecast"]["lift_mean"], "low": a["forecast"]["hdi_90"][0],
             "high": a["forecast"]["hdi_90"][1]},
            a["power_at_forecast"], decision, (grade or {}).get("test", {}).get(key)))
    m, f, h = results["measured"], plan["holdout"]["forecast"], plan["holdout"]
    rd = results["decision"]
    verdict = "works" if rd["rule_1_rollout_works"] else ("clear drop" if rd["rule_3_drop_is_clear"] else "not clear")
    rows.append(_readout_row(
        "Rollout: 15 markets against the 5 held out", h["window"],
        {"value": m["lift"], "low": m["interval_90"][0], "high": m["interval_90"][1]},
        {"value": f["mean"], "low": f["hdi_90"][0], "high": f["hdi_90"][1]},
        h["power_at_forecast"], f"{verdict}; {rd['rule_2_against_forecast']}", (grade or {}).get("rollout")))
    mv = results.get("model_view")
    if mv:
        dv = mv["deal_change_in_window"]
        rows.append(_readout_row("Rollout: the model's own view (cross-check)", h["window"],
                                 {"value": dv["mean"], "low": dv["hdi_90"][0], "high": dv["hdi_90"][1]},
                                 {"value": f["mean"], "low": f["hdi_90"][0], "high": f["hdi_90"][1]},
                                 None, "decides nothing", (grade or {}).get("rollout")))
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if c.startswith(("measured", "forecast", "true_"))]
    df[num] = df[num].astype(float).round(2)
    df["power_at_forecast"] = df["power_at_forecast"].astype(float).round(4)
    return df


def rollout_plan(dims: pd.DataFrame, plan: dict, results: dict) -> pd.DataFrame:
    """Per channel: the rollout's move, its spend on last year's same weeks, the May forecast,
    and delivered spend against the media plan over the rollout weeks (the move check)."""
    real = results["validity"]["moves"]["channels"]
    rows = []
    for r in plan["rollout"]["plan"]["by_channel"]:
        c = r["channel"]
        dc = r["deal_change_in_window"]
        rows.append({**_dims(dims, c), "multiplier": r["multiplier"], "change_pct": 100 * (r["multiplier"] - 1),
                     "spend_proxy_weeks": r["spend_now"], "spend_change_proxy_weeks": r["spend_change"],
                     "forecast_deals_in_window": dc["mean"], "forecast_deals_low": dc["hdi_90"][0],
                     "forecast_deals_high": dc["hdi_90"][1],
                     "brand_search_spend_change": r.get("brand_search_spend_change"),
                     "delivered_over_planned": real[c]["rollout_ratio"], "check_line": real[c]["rollout_line"],
                     "holdout_delivered_over_planned": real[c]["holdout_ratio"],
                     "move_shows": int(real[c]["move_shows"])})
    df = pd.DataFrame(rows)
    num = [c for c in df.columns if df[c].dtype.kind == "f"]
    df[num] = df[num].round(4)
    return df.sort_values("channel_sort", kind="stable").reset_index(drop=True)


def write(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, lineterminator="\n")
    print(f"{path.name:<30} {len(df):>7,} rows")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export marts and MMM outputs as CSVs for Tableau Public.")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)

    mmm = _json(MMM_OUTPUTS / "channels.json")
    baselines = _json(MMM_OUTPUTS / "baselines.json")
    optimizer = _json(MMM_OUTPUTS / "optimizer.json")
    grade = _json(MMM_GRADING / f"grade_{mmm['meta']['fit']}.json")

    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    try:
        check_same_world(con, mmm)
        weekly = weekly_channel_market(con)
        controls = controls_weekly_market(con)
        dims = con.sql(CHANNELS_SQL).df().set_index("channel_id")
    finally:
        con.close()

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    write(weekly, out / "weekly_channel_market.csv")
    write(controls, out / "controls_weekly_market.csv")
    write(mmm_channel_views(dims, mmm, baselines, grade), out / "mmm_channel_views.csv")
    write(mmm_response_curves(dims, optimizer), out / "mmm_response_curves.csv")
    write(mmm_optimizer_plan(dims, optimizer, mmm, grade), out / "mmm_optimizer_plan.csv")

    if not (YEAR_END.exists() and (ROLLOUT / "results.json").exists()):
        print("dashboard 4 skipped: run the yearend and results stages first")
        return 0
    readout, plan, results = _json(READOUT), _json(ROLLOUT / "plan.json"), _json(ROLLOUT / "results.json")
    grade26 = MMM_GRADING / "grade_2026.json"
    con = duckdb.connect(str(YEAR_END), read_only=True)
    try:
        weekly26 = test_rollout_weekly_market(con, readout, plan)
    finally:
        con.close()
    write(weekly26, out / "test_rollout_weekly_market.csv")
    write(story_readouts(readout, plan, results, _json(grade26) if grade26.exists() else None),
          out / "story_readouts.csv")
    write(rollout_plan(dims, plan, results), out / "rollout_plan.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
