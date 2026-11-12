"""Fit the MMM, check the health gates, and write outputs only if every gate passes.

    .venv-mmm\\Scripts\\python -m mmm                 # holdout fit (last 13 weeks held out)
    .venv-mmm\\Scripts\\python -m mmm --holdout 0     # full-window fit
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from pathlib import Path

os.environ.setdefault("PYTENSOR_FLAGS", "cxx=")  # no C compiler on Windows; nutpie uses numba

import arviz as az  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import baselines, lift_tests  # noqa: E402
from . import config as C  # noqa: E402
from .data import Panel, affiliate_spend_check, load_panel  # noqa: E402
from .estimands import Engine, MediaPosterior, hdi  # noqa: E402
from .model import add_brand_lift, build_design, make_mmm  # noqa: E402
from .optimize import optimize_mix  # noqa: E402

FREE_VARS = ["intercept_contribution", "adstock_alpha", "saturation_slope", "saturation_kappa",
             "saturation_beta", "gamma_control", "gamma_fourier", "y_sigma"]


def _pp_deals(pp, mmm, design) -> np.ndarray:
    """Posterior predictive draws as deals, shape (sample, date, geo).

    PyMC-Marketing returns the target on the model's scaled axis.
    """
    arr = pp["y"].transpose("sample", "date", "geo").sel(geo=design.regions).values
    return arr * float(mmm.scalers._target.values) * design.size[None, None, :]


def _interval_coverage(draws: np.ndarray, observed: np.ndarray, prob=C.HDI_PROB) -> float:
    lo = np.quantile(draws, (1 - prob) / 2, axis=0)
    hi = np.quantile(draws, 1 - (1 - prob) / 2, axis=0)
    return float(((observed >= lo) & (observed <= hi)).mean())


def diagnostics(mmm, idata, design, panel: Panel) -> dict:
    summ = az.summary(idata, var_names=FREE_VARS, kind="diagnostics")
    n_div = int(idata.sample_stats.diverging.sum())
    n_samples = int(idata.sample_stats.diverging.size)
    out = {
        "rhat_max": float(summ.r_hat.max()),
        "rhat_worst": str(summ.r_hat.idxmax()),
        "ess_bulk_min": float(summ.ess_bulk.min()),
        "ess_bulk_worst": str(summ.ess_bulk.idxmin()),
        "ess_tail_min": float(summ.ess_tail.min()),
        "divergences": n_div,
        "divergence_rate": n_div / n_samples,
        "n_samples": n_samples,
    }

    X, _ = design.train()
    n = design.n_train
    pp = mmm.sample_posterior_predictive(X, extend_idata=False, progressbar=False, random_seed=7)
    draws = _pp_deals(pp, mmm, design)
    obs = panel.deals[:n]
    nat_draws, nat_obs = draws.sum(axis=2), obs.sum(axis=1)
    nat_mean = nat_draws.mean(axis=0)
    out["ppc"] = {
        "region_week_coverage_90": _interval_coverage(draws, obs),
        "national_week_coverage_90": _interval_coverage(nat_draws, nat_obs),
        "national_weekly_r2": float(1 - ((nat_obs - nat_mean) ** 2).sum()
                                    / ((nat_obs - nat_obs.mean()) ** 2).sum()),
        "national_weekly_mape": float(np.mean(np.abs(nat_mean - nat_obs) / nat_obs)),
        "total_deals_observed": float(obs.sum()),
        "total_deals_predicted": float(nat_draws.sum(axis=1).mean()),
    }

    if n < len(design.weeks):
        Xh, _ = design.holdout()
        pph = mmm.sample_posterior_predictive(Xh, extend_idata=False, include_last_observations=True,
                                              progressbar=False, random_seed=8)
        hd = _pp_deals(pph, mmm, design)
        hobs = panel.deals[n:]
        hnat, hnat_obs = hd.sum(axis=2), hobs.sum(axis=1)
        hmean = hnat.mean(axis=0)
        out["holdout"] = {
            "weeks": len(hobs),
            "national_weekly_mape": float(np.mean(np.abs(hmean - hnat_obs) / hnat_obs)),
            "national_total_error_pct": float(100 * (hmean.sum() - hnat_obs.sum()) / hnat_obs.sum()),
            "region_week_coverage_90": _interval_coverage(hd, hobs),
            "national_week_coverage_90": _interval_coverage(hnat, hnat_obs),
            "region_total_mape": float(np.mean(np.abs(hd.sum(axis=1).mean(axis=0) - hobs.sum(axis=0))
                                               / hobs.sum(axis=0))),
        }
    return out


def gate_results(diag: dict) -> dict:
    g = C.GATES
    lo, hi = g["ppc_coverage_range"]
    checks = {
        "rhat": diag["rhat_max"] < g["rhat_max"],
        "ess_bulk": diag["ess_bulk_min"] >= g["ess_bulk_min"],
        "ess_tail": diag["ess_tail_min"] >= g["ess_tail_min"],
        "divergences": diag["divergence_rate"] <= g["divergence_rate_max"],
        "ppc_coverage": lo <= diag["ppc"]["region_week_coverage_90"] <= hi,
    }
    if "holdout" in diag:
        hlo, hhi = g["holdout_coverage_range"]
        checks["holdout_mape"] = diag["holdout"]["national_weekly_mape"] <= g["holdout_national_mape_max"]
        checks["holdout_coverage"] = hlo <= diag["holdout"]["region_week_coverage_90"] <= hhi
    return {"thresholds": g, "checks": checks, "all_pass": all(checks.values())}


def _jsonable(o):
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(obj), indent=2) + "\n", encoding="utf-8")


def write_outputs(engine: Engine, panel: Panel, run_meta: dict, out_dir: Path) -> dict:
    channels = list(panel.channels)
    est, curves, weekly = {}, [], []
    total_inc = np.zeros(engine.post.n_draws)
    for ch in channels:
        e = engine.channel_estimands(ch)
        total_inc += e["_draws"]["incremental_deals"]
        est[ch] = e
        curves += engine.response_curve(ch)
        w = engine.weekly(ch)[:, : len(panel.weeks)]
        lo, hi = np.apply_along_axis(hdi, 0, w)
        weekly.append(pd.DataFrame({"week_start": panel.weeks.date, "channel": ch,
                                    "incremental_deals_mean": w.mean(axis=0),
                                    "hdi_90_low": lo, "hdi_90_high": hi}))
    paid_spend = float(panel.spend.sum())
    all_deals = float(panel.deals.sum())
    summary = {
        "paid_spend": paid_spend,
        "observed_deals_in_window": all_deals,
        "blended_cpa": paid_spend / all_deals,
        "incremental_deals_paid_media": _summ(total_inc),
        "incremental_cpa_paid_media": _summ(paid_spend / total_inc),
        "paid_media_share_of_deals": _summ(total_inc / all_deals),
    }
    opt = optimize_mix(engine, channels)

    flat = []
    for ch, e in est.items():
        row = {"channel": ch, "spend": e["spend"]}
        for k in ("incremental_deals", "cpa", "marginal_cpa", "roi_revenue"):
            row[f"{k}_median"] = e[k]["median"]
            row[f"{k}_mean"] = e[k]["mean"]
            row[f"{k}_hdi_90_low"], row[f"{k}_hdi_90_high"] = e[k]["hdi_90"]
        flat.append(row)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "channels.json", {"meta": run_meta, "summary": summary, "channels": est})
    pd.DataFrame(flat).to_csv(out_dir / "channels.csv", index=False, float_format="%.4f")
    pd.DataFrame(curves).to_csv(out_dir / "response_curves.csv", index=False, float_format="%.4f")
    contrib = pd.concat(weekly, ignore_index=True)
    contrib.to_csv(out_dir / "contributions_weekly.csv", index=False, float_format="%.4f")
    write_json(out_dir / "optimizer.json", {"meta": run_meta, **opt})
    write_json(out_dir / "baselines.json", baselines.compute())
    return {"summary": summary, "optimizer": opt}


def _summ(x):
    from .estimands import summarize
    return summarize(x)


def run(holdout_weeks: int = C.HOLDOUT_WEEKS, name: str | None = None, regions=None,
        n_weeks=None, sampler: dict | None = None, out_dir: Path = C.OUTPUT_DIR,
        fit_dir: Path = C.FIT_DIR, write: bool = True, estimand_draws: int = 2000,
        quiet: bool = False) -> dict:
    t0 = time.time()
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, flush=True))
    sampler = {**C.SAMPLER, **(sampler or {})}
    name = name or ("holdout" if holdout_weeks else "full")

    panel = load_panel()
    if regions or n_weeks:
        panel = panel.subset(regions, n_weeks)
    affiliate = affiliate_spend_check()
    if not (affiliate["mart_equals_fees"] and affiliate["staging_reads_partner_fees"]):
        raise RuntimeError(f"affiliate spend is not placement fees only: {affiliate}")

    design = build_design(panel, holdout_weeks)
    lift_rows = lift_tests.estimate(panel, design.n_train)
    lift = lift_tests.pooled(lift_rows) if len(lift_rows) else None

    X, y = design.train()
    mmm = make_mmm(design)
    mmm.build_model(X, y)
    lift_entered = add_brand_lift(mmm, lift) if lift else None
    log(f"[{name}] {len(panel.regions)} regions x {design.n_train} train weeks; "
        f"lift tests from {len(lift_rows)} pauses; sampling {sampler}")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        idata = mmm.fit(X, y, nuts_sampler="nutpie", progressbar=False,
                        chains=sampler["chains"], draws=sampler["draws"], tune=sampler["tune"],
                        target_accept=sampler["target_accept"], random_seed=sampler["random_seed"])
    log(f"[{name}] sampled in {time.time() - t0:.0f}s")

    if "brand_pause_lift" not in mmm.model.named_vars and lift:
        raise RuntimeError("lift test likelihood missing from the fitted model")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        diag = diagnostics(mmm, idata, design, panel)
    gates = gate_results(diag)
    log(f"[{name}] gates: {gates['checks']}")

    fit_dir.mkdir(parents=True, exist_ok=True)
    idata.to_netcdf(fit_dir / f"{name}.nc")
    scales = {"channel_scale": mmm.scalers._channel.sel(channel=panel.channels).values.tolist(),
              "target_scale": float(mmm.scalers._target.values)}
    write_json(fit_dir / f"{name}_scales.json", scales)

    run_meta = {
        "fit": name,
        "window": [str(panel.weeks[0].date()), str(panel.weeks[-1].date())],
        "train_weeks": design.n_train, "holdout_weeks": holdout_weeks,
        "regions": len(panel.regions), "sampler": sampler,
        "estimand_draws": estimand_draws, "seconds": round(time.time() - t0),
        "hdi_prob": C.HDI_PROB,
        "estimands_cover": "full window spend path with this fit's posterior",
    }
    result = {"meta": run_meta, "diagnostics": diag, "gates": gates, "affiliate_check": affiliate,
              "lift_tests": {"pauses": lift_rows.to_dict(orient="records"), "pooled": lift_entered},
              "idata": idata, "mmm": mmm, "design": design, "panel": panel}

    if write:
        write_json(out_dir / f"diagnostics_{name}.json",
                   {"meta": run_meta, "diagnostics": diag, "gates": gates,
                    "affiliate_check": affiliate, "lift_tests": result["lift_tests"]})
    if not gates["all_pass"]:
        log(f"[{name}] a health gate failed: no estimands written")
        return result

    post = MediaPosterior.from_idata(idata, scales["channel_scale"], scales["target_scale"],
                                     panel.channels, max_draws=estimand_draws)
    engine = Engine(post, panel)
    result["engine"] = engine
    if write:
        result.update(write_outputs(engine, panel, run_meta, out_dir))
        log(f"[{name}] outputs written to {out_dir} in {time.time() - t0:.0f}s")
    return result


def outputs_from_saved(name: str, out_dir: Path = C.OUTPUT_DIR, fit_dir: Path = C.FIT_DIR,
                       estimand_draws: int = 2000) -> dict:
    """Rebuild outputs from a saved fit whose gates passed, without sampling again."""
    diag = json.loads((out_dir / f"diagnostics_{name}.json").read_text(encoding="utf-8"))
    if not diag["gates"]["all_pass"]:
        raise RuntimeError(f"fit {name} failed a health gate: {diag['gates']['checks']}")
    idata = az.from_netcdf(fit_dir / f"{name}.nc")
    scales = json.loads((fit_dir / f"{name}_scales.json").read_text(encoding="utf-8"))
    panel = load_panel()
    post = MediaPosterior.from_idata(idata, scales["channel_scale"], scales["target_scale"],
                                     panel.channels, max_draws=estimand_draws)
    return write_outputs(Engine(post, panel), panel, diag["meta"], out_dir)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--holdout", type=int, default=C.HOLDOUT_WEEKS)
    ap.add_argument("--name")
    ap.add_argument("--draws", type=int, default=C.SAMPLER["draws"])
    ap.add_argument("--tune", type=int, default=C.SAMPLER["tune"])
    ap.add_argument("--chains", type=int, default=C.SAMPLER["chains"])
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild outputs from the saved fit instead of sampling")
    args = ap.parse_args(argv)
    if args.report_only:
        outputs_from_saved(args.name or ("holdout" if args.holdout else "full"))
        return 0
    res = run(holdout_weeks=args.holdout, name=args.name,
              sampler={"draws": args.draws, "tune": args.tune, "chains": args.chains})
    print(json.dumps(_jsonable({"diagnostics": res["diagnostics"], "gates": res["gates"]}), indent=2))
    return 0 if res["gates"]["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
