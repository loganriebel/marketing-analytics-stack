"""Grade the MMM against the hidden answer key.

This is the ONLY module in mmm/ allowed to read sim/truth/truth.json. Nothing it
writes goes to mmm/outputs/, so later steps that read the outputs never see truth.

    .venv-mmm\\Scripts\\python -m mmm.grade            # grades mmm/outputs/
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy import interpolate, stats

from . import config as C

TRUTH_PATH = C.REPO_ROOT / "sim" / "truth" / "truth.json"
GRADE_DIR = C.REPO_ROOT / "mmm" / "grading"
METRICS = ["incremental_deals", "cpa", "marginal_cpa", "roi_revenue"]
# Upper funnel through brand search; graded where both the answer key and the outputs have them.
MEDIATED = ["incremental_deals_via_brand_search", "incremental_deals_total", "cpa_total",
            "marginal_cpa_total"]
TOTAL_CURVE_KEYS = ("response_curve_total", "total_response_curve")


def _pct_err(est, true):
    if est is None or true in (None, 0) or not math.isfinite(est):
        return None
    return 100.0 * (est - true) / true


def _rank_stats(est: dict, true: dict) -> dict:
    chans = list(true)
    e = np.array([est[c] if est[c] is not None else np.inf for c in chans], float)
    t = np.array([true[c] for c in chans], float)
    e_rank, t_rank = stats.rankdata(e), stats.rankdata(t)
    return {
        "spearman": float(stats.spearmanr(e_rank, t_rank).statistic),
        "kendall_tau": float(stats.kendalltau(e_rank, t_rank).statistic),
        "best": chans[int(np.argmin(e))], "worst": chans[int(np.argmax(e))],
    }


def grade_model(channels_out: dict, truth: dict) -> dict:
    tc = truth["channels"]
    rows, covered = {}, []
    for ch in C.CHANNELS:
        m, t = channels_out["channels"][ch], tc[ch]
        r = {}
        for k in METRICS:
            lo, hi = m[k]["hdi_90"]
            inside = bool(lo <= t[k] <= hi)
            covered.append(inside)
            # median: the mean of a ratio like CPA is unstable when a draw's deals near zero
            r[k] = {"true": t[k], "median": m[k]["median"], "hdi_90": [lo, hi], "covered": inside,
                    "pct_error": _pct_err(m[k]["median"], t[k])}
        rows[ch] = r
    true_cpa = {c: tc[c]["cpa"] for c in C.CHANNELS}
    true_mcpa = {c: tc[c]["marginal_cpa"] for c in C.CHANNELS}
    cpa_rank = _rank_stats({c: rows[c]["cpa"]["median"] for c in C.CHANNELS}, true_cpa)
    mcpa_rank = _rank_stats({c: rows[c]["marginal_cpa"]["median"] for c in C.CHANNELS}, true_mcpa)
    true_m = _rank_stats(true_mcpa, true_mcpa)
    s, ts = channels_out["summary"], media_totals(truth)
    total = {
        "incremental_deals_paid_media": _vs(s["incremental_deals_paid_media"], ts["incremental_deals"]),
        "incremental_cpa_paid_media": _vs(s["incremental_cpa_paid_media"], ts["incremental_cpa"]),
    }
    return {
        "channels": rows,
        "hdi_coverage": {"covered": int(sum(covered)), "of": len(covered),
                         "rate": float(np.mean(covered)),
                         "by_metric": {k: float(np.mean([rows[c][k]["covered"] for c in C.CHANNELS]))
                                       for k in METRICS}},
        "median_abs_pct_error": {k: float(np.median([abs(rows[c][k]["pct_error"]) for c in C.CHANNELS]))
                                 for k in METRICS},
        "cpa_rank": cpa_rank,
        "marginal_cpa_rank": mcpa_rank,
        "best_marginal_cpa_right": mcpa_rank["best"] == true_m["best"],
        "worst_marginal_cpa_right": mcpa_rank["worst"] == true_m["worst"],
        "true_best_marginal": true_m["best"], "true_worst_marginal": true_m["worst"],
        "totals": total,
    }


def media_totals(truth: dict) -> dict:
    """True totals over the channels the MMM models (webinars are a control there)."""
    spend = sum(truth["channels"][c]["spend"] for c in C.CHANNELS)
    deals = sum(truth["channels"][c]["incremental_deals"] for c in C.CHANNELS)
    return {"spend": spend, "incremental_deals": deals, "incremental_cpa": spend / deals}


def _vs(est: dict, true: float) -> dict:
    lo, hi = est["hdi_90"]
    return {"true": true, "median": est["median"], "hdi_90": [lo, hi], "covered": bool(lo <= true <= hi),
            "pct_error": _pct_err(est["median"], true)}


def grade_baseline(base: dict, key: str, truth: dict) -> dict:
    tc = truth["channels"]
    rows = {}
    for ch in C.CHANNELS:
        b = base["channels"][ch][key]
        rows[ch] = {"deals": b["deals"], "cpa": b["cpa"],
                    "deals_pct_error": _pct_err(b["deals"], tc[ch]["incremental_deals"]),
                    "cpa_pct_error": _pct_err(b["cpa"], tc[ch]["cpa"])}
    true_cpa = {c: tc[c]["cpa"] for c in C.CHANNELS}
    true_m = _rank_stats({c: tc[c]["marginal_cpa"] for c in C.CHANNELS},
                         {c: tc[c]["marginal_cpa"] for c in C.CHANNELS})
    # A baseline has no marginal view; teams rank the next dollar by its average CPA.
    rank = _rank_stats({c: rows[c]["cpa"] for c in C.CHANNELS}, true_cpa)
    errs = [abs(r["cpa_pct_error"]) for r in rows.values() if r["cpa_pct_error"] is not None]
    return {
        "channels": rows,
        "median_abs_cpa_pct_error": float(np.median(errs)) if errs else None,
        "channels_with_no_credit": [c for c in C.CHANNELS if not rows[c]["deals"]],
        "cpa_rank": rank,
        "best_marginal_cpa_right": rank["best"] == true_m["best"],
        "worst_marginal_cpa_right": rank["worst"] == true_m["worst"],
    }


def grade_mediation(channels_out: dict, truth: dict) -> dict | None:
    rows = {}
    for ch, m in channels_out["channels"].items():
        t = truth["channels"].get(ch, {})
        keys = [k for k in MEDIATED if k in m and k in t]
        if not keys:
            continue
        rows[ch] = {}
        for k in keys:
            lo, hi = m[k]["hdi_90"]
            rows[ch][k] = {"true": t[k], "median": m[k]["median"], "hdi_90": [lo, hi],
                           "covered": bool(lo <= t[k] <= hi), "pct_error": _pct_err(m[k]["median"], t[k])}
    if not rows:
        return None
    cov = [v["covered"] for r in rows.values() for v in r.values()]
    return {"channels": rows, "hdi_coverage": {"covered": int(sum(cov)), "of": len(cov)}}


def halo_shares(outputs: Path, channels_out: dict, truth: dict) -> dict:
    """Upper funnel's share of brand searches (stage 1) and of brand-search deals."""
    out, ts = {}, truth["summary"]
    diag = next(iter(sorted(outputs.glob("diagnostics_*.json"))), None)
    if diag and "upper_funnel_share_of_brand_searches" in ts:
        bd = json.loads(diag.read_text(encoding="utf-8")).get("brand_demand", {})
        est = bd.get("share_of_brand_spend_from_upper_funnel")
        if est:
            out["upper_funnel_share_of_brand_searches"] = _vs(est, ts["upper_funnel_share_of_brand_searches"])
    brand = channels_out["channels"].get(C.BRAND, {})
    if "deals_from_upper_funnel_searches" in brand and "upper_funnel_share_of_brand_search_deals" in ts:
        share = brand["deals_from_upper_funnel_searches"]["median"] / brand["incremental_deals"]["median"]
        out["upper_funnel_share_of_brand_search_deals"] = {
            "true": ts["upper_funnel_share_of_brand_search_deals"], "median": share,
            "note": "ratio of posterior medians; no HDI"}
    return out


def _total_curve(t: dict) -> dict | None:
    for k in TOTAL_CURVE_KEYS:
        if k in t:
            return t[k]
    return None


def true_plan_gain(optimizer: dict, truth: dict) -> dict:
    """Run the optimizer's plan through the true, noise-free response curves.

    The answer key tabulates each channel's expected deals at spend multipliers
    0 to 3; a monotone PCHIP through those points scores any multiplier in between.
    """
    gain, rows = 0.0, []
    for p in optimizer["plan"]:
        t = truth["channels"][p["channel"]]
        # An upper-funnel plan row includes deals via brand search, so score it on the
        # true total curve when the answer key has one.
        total = _total_curve(t) if "brand_search_spend_change" in p else None
        rc = total or t["response_curve"]
        ys = rc.get("incremental_deals_total", rc.get("incremental_deals"))
        f = interpolate.PchipInterpolator(rc["spend_multiplier"], ys)
        d = float(f(p["multiplier"]) - f(1.0))
        gain += d
        rows.append({"channel": p["channel"], "multiplier": p["multiplier"],
                     "true_deal_change": d, "model_deal_change": p["deal_change"]["mean"]})
    pred = optimizer["deal_change"]
    lo, hi = pred["hdi_90"]
    return {
        "method": "PCHIP through the answer key's noise-free response curves",
        "true_deal_change": gain,
        "model_deal_change": pred["mean"], "model_hdi_90": [lo, hi],
        "true_inside_hdi": bool(lo <= gain <= hi),
        "true_gain_pct_of_true_paid_incremental": 100 * gain / media_totals(truth)["incremental_deals"],
        "by_channel": rows,
    }


def _fmt(x, nd=0):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "n/a"
    return f"{x:,.{nd}f}"


def to_markdown(g: dict) -> str:
    m = g["model"]
    lines = [f"# MMM grade: {g['fit']} fit, seed {g['seed']}", "",
             "Webinars are a control in the MMM, so the 8 media channels are graded.", "",
             f"90% HDI coverage: {m['hdi_coverage']['covered']} of {m['hdi_coverage']['of']} "
             f"({100 * m['hdi_coverage']['rate']:.0f}%).", "",
             "Point estimates are posterior medians.", "",
             "| Channel | True CPA | MMM CPA (90% HDI) | CPA err | True mCPA | MMM mCPA (90% HDI) | "
             "True deals | MMM deals | CRM CPA | Platform CPA |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    crm, plat = g["crm_last_touch"]["channels"], g["platform_reported"]["channels"]
    for ch in C.CHANNELS:
        r = m["channels"][ch]
        cpa, mc, dl = r["cpa"], r["marginal_cpa"], r["incremental_deals"]
        flag = lambda v: "" if v["covered"] else " (miss)"  # noqa: E731
        lines.append(
            f"| {ch} | {_fmt(cpa['true'])} | {_fmt(cpa['median'])} ({_fmt(cpa['hdi_90'][0])} to "
            f"{_fmt(cpa['hdi_90'][1])}){flag(cpa)} | {_fmt(cpa['pct_error'])}% | {_fmt(mc['true'])} | "
            f"{_fmt(mc['median'])} ({_fmt(mc['hdi_90'][0])} to {_fmt(mc['hdi_90'][1])}){flag(mc)} | "
            f"{_fmt(dl['true'])} | {_fmt(dl['median'])}{flag(dl)} | {_fmt(crm[ch]['cpa'])} | {_fmt(plat[ch]['cpa'])} |")
    rows = [("MMM", m["cpa_rank"]["spearman"], m["median_abs_pct_error"]["cpa"],
             m["marginal_cpa_rank"]["best"], m["best_marginal_cpa_right"],
             m["marginal_cpa_rank"]["worst"], m["worst_marginal_cpa_right"])]
    for name, key in (("CRM last touch", "crm_last_touch"), ("Platform reported", "platform_reported")):
        b = g[key]
        rows.append((name, b["cpa_rank"]["spearman"], b["median_abs_cpa_pct_error"],
                     b["cpa_rank"]["best"], b["best_marginal_cpa_right"],
                     b["cpa_rank"]["worst"], b["worst_marginal_cpa_right"]))
    lines += ["", f"True best marginal CPA: {m['true_best_marginal']}. True worst: {m['true_worst_marginal']}.", "",
              "| View | CPA rank corr | Median abs CPA error | Picks best | Right? | Picks worst | Right? |",
              "|---|---:|---:|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r[0]} | {r[1]:.2f} | {_fmt(r[2])}% | {r[3]} | {'yes' if r[4] else 'no'} | "
                     f"{r[5]} | {'yes' if r[6] else 'no'} |")
    t = m["totals"]
    lines += ["", "| Total paid media | True | MMM (90% HDI) | Covered |", "|---|---:|---:|---|"]
    for k, v in t.items():
        lines.append(f"| {k} | {_fmt(v['true'])} | {_fmt(v['median'])} ({_fmt(v['hdi_90'][0])} to "
                     f"{_fmt(v['hdi_90'][1])}) | {'yes' if v['covered'] else 'no'} |")
    if "mediation" in g:
        med = g["mediation"]
        lines += ["", f"Upper funnel through brand search: 90% HDI coverage {med['hdi_coverage']['covered']} "
                  f"of {med['hdi_coverage']['of']}.", "",
                  "| Channel | Metric | True | MMM (90% HDI) | Error |", "|---|---|---:|---:|---:|"]
        for k, v in med.get("shares", {}).items():
            rng = (f" ({v['hdi_90'][0]:.1%} to {v['hdi_90'][1]:.1%})" if "hdi_90" in v else "")
            lines.append(f"| all | {k} | {v['true']:.1%} | {v['median']:.1%}{rng} | "
                         f"{_fmt(_pct_err(v['median'], v['true']))}% |")
        for ch, r in med["channels"].items():
            for k, v in r.items():
                lines.append(f"| {ch} | {k} | {_fmt(v['true'])} | {_fmt(v['median'])} ({_fmt(v['hdi_90'][0])} "
                             f"to {_fmt(v['hdi_90'][1])}){'' if v['covered'] else ' (miss)'} | "
                             f"{_fmt(v['pct_error'])}% |")
    if "optimizer" in g:
        o = g["optimizer"]
        lines += ["", f"Optimizer plan at the same total spend: model predicts {_fmt(o['model_deal_change'])} "
                  f"deals ({_fmt(o['model_hdi_90'][0])} to {_fmt(o['model_hdi_90'][1])}); the true world gives "
                  f"{_fmt(o['true_deal_change'])} ({'inside' if o['true_inside_hdi'] else 'outside'} the HDI)."]
    return "\n".join(lines) + "\n"


def grade(outputs: Path = C.OUTPUT_DIR, truth_path: Path = TRUTH_PATH) -> dict:
    """Grade the media channels. Webinars are a control in the MMM, so they are not graded."""
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    ch = json.loads((outputs / "channels.json").read_text(encoding="utf-8"))
    base = json.loads((outputs / "baselines.json").read_text(encoding="utf-8"))
    g = {
        "fit": ch["meta"]["fit"],
        "seed": truth["seed"],
        "model": grade_model(ch, truth),
        "crm_last_touch": grade_baseline(base, "crm_last_touch", truth),
        "platform_reported": grade_baseline(base, "platform_reported", truth),
    }
    med = grade_mediation(ch, truth)
    if med:
        g["mediation"] = med
        shares = halo_shares(outputs, ch, truth)
        if shares:
            med["shares"] = shares
    opt_path = outputs / "optimizer.json"
    if opt_path.exists():
        g["optimizer"] = true_plan_gain(json.loads(opt_path.read_text(encoding="utf-8")), truth)
    return g


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outputs", type=Path, default=C.OUTPUT_DIR)
    ap.add_argument("--truth", type=Path, default=TRUTH_PATH,
                    help="answer key of the world the outputs came from (a dev seed's own file)")
    ap.add_argument("--grade-dir", type=Path, default=GRADE_DIR)
    args = ap.parse_args(argv)
    g = grade(args.outputs, args.truth)
    args.grade_dir.mkdir(parents=True, exist_ok=True)
    stem = f"grade_{g['fit']}" + ("" if g["seed"] == 2026 else f"_seed{g['seed']}")
    (args.grade_dir / f"{stem}.json").write_text(json.dumps(g, indent=2) + "\n", encoding="utf-8")
    md = to_markdown(g)
    (args.grade_dir / f"{stem}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
