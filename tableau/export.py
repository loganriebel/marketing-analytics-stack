"""Export the golden marts and the MMM outputs as CSVs for Tableau Public.

Tableau Public cannot read DuckDB, so CSVs are the hand-off. Inputs:

* data/warehouse.duckdb, opened read-only, marts only (fct_*, dim_*).
* mmm/outputs/: MMM estimates, response curves, the optimizer plan, and the
  CRM last-touch and platform-reported baselines.
* mmm/grading/grade_<fit>.json: the grader's written results, for the answer-key
  columns. mmm/grade.py stays the only reader of the simulator's answer key.
* tableau/metro_centroids.csv: public longitudes of each market's main city
  (dim_region carries latitude only).

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
                "best_next_dollar": g[rank_key]["best"], "best_next_dollar_right": int(g["best_marginal_cpa_right"])}

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
                 "cpa": _true(t, "incremental_cpa_paid_media"), "best_next_dollar": grade["model"]["true_best_marginal"],
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
