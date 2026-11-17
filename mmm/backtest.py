"""Rolling-origin backtest: refit the unchanged MMM at several training cutoffs and
score each fit on the weeks right after its cutoff.

    .venv-mmm\\Scripts\\python -m mmm.backtest

The graded fit is checked on one 13-week holdout. Here the same model, priors, sampler
settings and gates are fit once per cutoff. Each fold loads only the weeks through the
end of its own holdout, so it never sees a later week, and it predicts its holdout from
those weeks' actual spend and controls, the way the graded holdout does.

A fold's posterior (about 3 GB) is saved, scored, then deleted. Its predictions stay in
a small file beside it (gitignored), so a rerun skips folds already scored and scores a
saved posterior without sampling again.
"""

from __future__ import annotations

import argparse
import gc
import json
import sys
import time
import warnings
from pathlib import Path

import arviz as az
import numpy as np
import pandas as pd

from . import config as C
from . import fit  # sets PyTensor up (numba mode, no C compiler) before PyMC loads
from . import validation
from .data import load_panel

FOLD_ENDS = ("2024-12-30", "2025-03-31", "2025-06-30", "2025-09-22")
HORIZON = C.HOLDOUT_WEEKS
FIT_DIR = C.FIT_DIR / "backtest"
OUT_JSON = C.OUTPUT_DIR / "backtest.json"
OUT_MD = C.REPO_ROOT / "mmm" / "grading" / "backtest.md"
PP_SEED = 8  # fit.diagnostics' holdout seed, so the last fold reproduces the graded holdout

DEFINITIONS = {
    "error": "predicted minus observed, so a negative bias or MPE means the model ran low",
    "predicted": "holdout: posterior predictive mean; training: posterior mean of the fitted "
                 "line, as in diagnostics fit_stats",
    "mape": "mean of |error| / observed, leaving out cells with zero deals",
    "wape": "sum of |error| / sum of observed",
    "mae": "mean |error|, in deals",
    "bias": "mean error, in deals per week (per market-week for market-week rows)",
    "bias_pct": "sum of error / sum of observed",
    "mpe": "mean of error / observed",
    "coverage_90": "share inside the 90% posterior predictive interval (5th to 95th percentile)",
    "nrmse_mean": "RMSE / mean observed",
    "nrmse_range": "RMSE / (max - min observed), over the same weeks",
    "holdout_over_training_nrmse": "holdout NRMSE / the same fold's training NRMSE; above 1 means "
                                   "the fit does worse on weeks it did not train on",
    "pooled": "every fold's holdout weeks together; training NRMSE is the mean over folds",
}


def fold_windows(weeks: pd.DatetimeIndex, ends, horizon: int) -> list[dict]:
    """Training and holdout weeks for each cutoff."""
    out = []
    for end in ends:
        end = pd.Timestamp(end)
        if end not in weeks:
            raise ValueError(f"{end.date()} is not a week start in the data")
        n_train = int(weeks.get_loc(end)) + 1
        if n_train + horizon > len(weeks):
            raise ValueError(f"{end.date()} leaves fewer than {horizon} weeks to predict")
        out.append({"fold": f"backtest_{end.date()}", "n_train": n_train, "n_weeks": n_train + horizon,
                    "train_start": str(weeks[0].date()), "train_end": str(end.date()),
                    "holdout_start": str(weeks[n_train].date()),
                    "holdout_end": str(weeks[n_train + horizon - 1].date())})
    return out


def forecast_stats(observed, predicted, lo=None, hi=None) -> dict:
    o, p = np.asarray(observed, float).ravel(), np.asarray(predicted, float).ravel()
    s = validation.error_stats(o, p)
    err, nz = p - o, o > 0
    s.update({
        "wape": float(np.abs(err).sum() / o.sum()),
        "mpe": float(np.mean(err[nz] / o[nz])),
        "bias_pct": float(err.sum() / o.sum()),
        "nrmse_mean": s["rmse"] / s["mean_observed"],
        "nrmse_range": s["rmse"] / float(o.max() - o.min()),
    })
    if lo is not None:
        s["coverage_90"] = float(((o >= np.ravel(lo)) & (o <= np.ravel(hi))).mean())
    return s


def _sample(prep: dict, sampler: dict):
    # the same call fit.run makes
    X, y = prep["design"].train()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return prep["mmm"].fit(X, y, nuts_sampler="nutpie", progressbar=False,
                               chains=sampler["chains"], draws=sampler["draws"], tune=sampler["tune"],
                               target_accept=sampler["target_accept"], random_seed=sampler["random_seed"],
                               nuts_sampler_kwargs={"low_rank_modified_mass_matrix": True})


def predict_fold(w: dict, horizon: int, regions, sampler: dict, fit_dir: Path, log) -> dict:
    """Fit one fold (or load its saved posterior), check its gates, and return its holdout
    predictions. The posterior is deleted once the predictions are saved."""
    cache = fit_dir / f"{w['fold']}_predictions.json"
    if cache.exists():
        cached = json.loads(cache.read_text(encoding="utf-8"))
        if cached["sampler"] == sampler and cached["regions"] == regions:
            log(f"[{w['fold']}] already scored: {cache.name}")
            return cached
    t0 = time.time()
    prep = fit._prepare(horizon, regions, w["n_weeks"])
    panel, design, mmm = prep["panel"], prep["design"], prep["mmm"]
    if design.n_train != w["n_train"] or str(design.weeks[design.n_train - 1].date()) != w["train_end"]:
        raise RuntimeError(f"{w['fold']}: design does not train through {w['train_end']}")
    nc = fit_dir / f"{w['fold']}.nc"
    if nc.exists():
        log(f"[{w['fold']}] scoring the saved posterior {nc.name}")
        with az.rc_context(rc={"data.load": "eager"}):  # eager, so the file can be deleted after
            idata = az.from_netcdf(nc)
        mmm.idata = idata
    else:
        log(f"[{w['fold']}] training {w['train_start']} to {w['train_end']} ({w['n_train']} weeks), "
            f"predicting {w['holdout_start']} to {w['holdout_end']}; sampling {sampler}")
        idata = _sample(prep, sampler)
        fit_dir.mkdir(parents=True, exist_ok=True)
        idata.to_netcdf(nc)
        log(f"[{w['fold']}] sampled in {time.time() - t0:.0f}s")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        diag = fit.diagnostics(mmm, idata, design, panel)
        Xh, _ = design.holdout()
        pp = mmm.sample_posterior_predictive(Xh, extend_idata=False, include_last_observations=True,
                                             progressbar=False, random_seed=PP_SEED)
    gates = fit.gate_results(diag)
    log(f"[{w['fold']}] gates: {gates['checks']}")
    draws = fit._pp_deals(pp, mmm, design)  # (sample, week, market)
    nat = draws.sum(axis=2)
    q = (1 - C.HDI_PROB) / 2
    n = design.n_train
    obs = panel.deals[n:]
    train_nat = panel.deals[:n].sum(axis=1)
    fs = diag["fit_stats"]
    pred = {
        **w,
        "regions": regions,
        "sampler": sampler,
        "seconds": round(time.time() - t0),
        "health": {k: diag[k] for k in ("rhat_max", "rhat_worst", "ess_bulk_min", "ess_tail_min",
                                        "divergences", "n_samples")},
        "gates": {"checks": gates["checks"], "all_pass": gates["all_pass"]},
        "diagnostics_holdout": {k: diag["holdout"][k] for k in ("national_weekly_mape",
                                                                "region_week_coverage_90")},
        "training": {"national_week": {**fs["national_week"],
                                       "range_observed": float(train_nat.max() - train_nat.min())},
                     "market_week": fs["region_week"]},
        "weeks": [str(d.date()) for d in panel.weeks[n:]],
        "markets": list(design.regions),
        "size": design.size.tolist(),
        "national": {"observed": obs.sum(axis=1).tolist(), "predicted": nat.mean(axis=0).tolist(),
                     "lo_90": np.quantile(nat, q, axis=0).tolist(),
                     "hi_90": np.quantile(nat, 1 - q, axis=0).tolist()},
        "market_week": {"observed": obs.tolist(), "predicted": draws.mean(axis=0).tolist(),
                        "lo_90": np.quantile(draws, q, axis=0).tolist(),
                        "hi_90": np.quantile(draws, 1 - q, axis=0).tolist()},
    }
    fit.write_json(cache, pred)
    del idata, pp, draws, nat, prep, mmm
    gc.collect()
    nc.unlink(missing_ok=True)
    log(f"[{w['fold']}] scored and posterior deleted in {time.time() - t0:.0f}s")
    return pred


def _training_view(t: dict) -> dict:
    nw, mw = t["national_week"], t["market_week"]
    keep = ("n", "mean_observed", "mape", "mae", "rmse", "bias", "r2")
    return {
        "national_week": {**{k: nw[k] for k in keep}, "wape": nw["mae"] / nw["mean_observed"],
                          "nrmse_mean": nw["rmse"] / nw["mean_observed"],
                          "nrmse_range": nw["rmse"] / nw["range_observed"]},
        "market_week": {"n": mw["n"], "mean_observed": mw["mean_observed"], "mape": mw["mape"],
                        "wape": mw["mae"] / mw["mean_observed"]},
    }


def _market_halves(preds: list[dict]) -> dict:
    """Market-week MAPE and WAPE for the smaller and the larger half of the markets."""
    p0 = preds[0]
    order = np.argsort(p0["size"], kind="stable")
    half = len(order) // 2
    groups = {"smaller_half": order[:half], "larger_half": order[half:]}
    out = {}
    for name, idx in groups.items():
        cols = {k: np.concatenate([np.asarray(p["market_week"][k])[:, idx].ravel() for p in preds])
                for k in ("observed", "predicted")}
        s = forecast_stats(cols["observed"], cols["predicted"])
        out[name] = {"markets": [p0["markets"][i] for i in idx], "n": s["n"],
                     "mean_observed": s["mean_observed"], "mape": s["mape"], "wape": s["wape"]}
    return out


MARKET_KEYS = ("n", "mean_observed", "mape", "wape", "mae", "bias", "coverage_90")


def _holdout_views(preds: list[dict]) -> dict:
    def cat(scope, k):
        return np.concatenate([np.ravel(p[scope][k]) for p in preds])

    nat = forecast_stats(cat("national", "observed"), cat("national", "predicted"),
                         cat("national", "lo_90"), cat("national", "hi_90"))
    mw = forecast_stats(cat("market_week", "observed"), cat("market_week", "predicted"),
                        cat("market_week", "lo_90"), cat("market_week", "hi_90"))
    return {"national_week": nat, "market_week": {k: mw[k] for k in MARKET_KEYS},
            "market_week_by_size": _market_halves(preds)}


def score_fold(pred: dict) -> dict:
    hold = _holdout_views([pred])
    train = _training_view(pred["training"])
    n = pred["national"]
    return {
        **{k: pred[k] for k in ("fold", "train_start", "train_end", "n_train", "holdout_start",
                                "holdout_end", "seconds", "health", "gates")},
        "holdout": hold,
        "training": train,
        "holdout_over_training_nrmse": {
            "mean": hold["national_week"]["nrmse_mean"] / train["national_week"]["nrmse_mean"],
            "range": hold["national_week"]["nrmse_range"] / train["national_week"]["nrmse_range"]},
        "weekly": [{"week": wk, "observed": o, "predicted": p, "lo_90": lo, "hi_90": hi}
                   for wk, o, p, lo, hi in zip(pred["weeks"], n["observed"], n["predicted"],
                                               n["lo_90"], n["hi_90"])],
    }


def pool(preds: list[dict], folds: list[dict]) -> dict:
    hold = _holdout_views(preds)
    train = {k: float(np.mean([f["training"]["national_week"][k] for f in folds]))
             for k in ("nrmse_mean", "nrmse_range", "mape", "wape")}
    spread = {k: [min(f["holdout"]["national_week"][k] for f in folds),
                  max(f["holdout"]["national_week"][k] for f in folds)]
              for k in ("mape", "wape", "bias_pct", "coverage_90", "r2")}
    weeks = [wk for p in preds for wk in p["weeks"]]
    return {
        "fold_weeks": len(weeks), "distinct_weeks": len(set(weeks)),
        "holdout": hold,
        "training_mean_over_folds": train,
        "holdout_over_training_nrmse": {
            "mean": hold["national_week"]["nrmse_mean"] / train["nrmse_mean"],
            "range": hold["national_week"]["nrmse_range"] / train["nrmse_range"]},
        "fold_range": spread,
        "folds_passing_every_gate": sum(f["gates"]["all_pass"] for f in folds),
    }


def assemble(preds: list[dict], meta: dict) -> dict:
    folds = [score_fold(p) for p in preds]
    return {"meta": {**meta, "folds_done": len(folds)}, "definitions": DEFINITIONS,
            "folds": folds, "pooled": pool(preds, folds)}


def _pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def render_md(res: dict) -> str:
    folds, pooled = res["folds"], res["pooled"]
    lines = [
        "# Rolling-origin backtest",
        "",
        f"The unchanged MMM refit {len(folds)} times, each fold trained from "
        f"{res['meta']['window'][0]} through its cutoff and predicting the next "
        f"{res['meta']['horizon_weeks']} weeks it never saw, from their actual spend and controls. "
        f"Written by `python -m mmm.backtest` from `mmm/outputs/backtest.json`. "
        f"Reading: [docs/mmm/README.md](../../docs/mmm/README.md#backtest).",
        "",
        "## National weekly deals, holdout",
        "",
        "| Fold | Trained through (weeks) | Predicts | Gates | MAPE | WAPE | MAE | Bias | MPE | "
        "In 90% interval | R² |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for i, f in enumerate(folds, 1):
        h = f["holdout"]["national_week"]
        lines.append(
            f"| {i} | {f['train_end']} ({f['n_train']}) | {f['holdout_start']} to {f['holdout_end']} | "
            f"{'pass' if f['gates']['all_pass'] else 'FAIL'} | {_pct(h['mape'])} | {_pct(h['wape'])} | "
            f"{h['mae']:.1f} | {h['bias']:+.1f} | {_pct(h['mpe'])} | "
            f"{round(h['coverage_90'] * h['n'])} of {h['n']} | {h['r2']:.2f} |")
    h = pooled["holdout"]["national_week"]
    lines += [
        f"| Pooled | | {pooled['fold_weeks']} fold-weeks ({pooled['distinct_weeks']} distinct) | "
        f"{pooled['folds_passing_every_gate']} of {len(folds)} pass | {_pct(h['mape'])} | "
        f"{_pct(h['wape'])} | {h['mae']:.1f} | {h['bias']:+.1f} | {_pct(h['mpe'])} | "
        f"{round(h['coverage_90'] * h['n'])} of {h['n']} | {h['r2']:.2f} |",
        "",
        "## NRMSE, holdout against training",
        "",
        "| Fold | Holdout RMSE / mean | Training RMSE / mean | Ratio | Holdout RMSE / range | "
        "Training RMSE / range | Ratio |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for i, f in enumerate(folds, 1):
        h, t, r = (f["holdout"]["national_week"], f["training"]["national_week"],
                   f["holdout_over_training_nrmse"])
        lines.append(f"| {i} | {_pct(h['nrmse_mean'])} | {_pct(t['nrmse_mean'])} | {r['mean']:.2f} | "
                     f"{_pct(h['nrmse_range'])} | {_pct(t['nrmse_range'])} | {r['range']:.2f} |")
    h, t, r = (pooled["holdout"]["national_week"], pooled["training_mean_over_folds"],
               pooled["holdout_over_training_nrmse"])
    lines += [
        f"| Pooled | {_pct(h['nrmse_mean'])} | {_pct(t['nrmse_mean'])} | {r['mean']:.2f} | "
        f"{_pct(h['nrmse_range'])} | {_pct(t['nrmse_range'])} | {r['range']:.2f} |",
        "",
        "## Market-weeks: small weeks inflate MAPE",
        "",
        "| Fold | Training MAPE | Training WAPE | Holdout MAPE | Holdout WAPE | Smaller half of markets: "
        "MAPE / WAPE | Larger half: MAPE / WAPE | In 90% interval |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    rows = [(str(i), f) for i, f in enumerate(folds, 1)] + [("Pooled", None)]
    for label, f in rows:
        hold = f["holdout"] if f else pooled["holdout"]
        m, s = hold["market_week"], hold["market_week_by_size"]
        if f:
            t = f["training"]["market_week"]
            tm, tw = _pct(t["mape"]), _pct(t["wape"])
        else:
            tm = tw = ""
        lines.append(
            f"| {label} | {tm} | {tw} | {_pct(m['mape'])} | {_pct(m['wape'])} | "
            f"{_pct(s['smaller_half']['mape'])} / {_pct(s['smaller_half']['wape'])} | "
            f"{_pct(s['larger_half']['mape'])} / {_pct(s['larger_half']['wape'])} | "
            f"{_pct(m['coverage_90'])} |")
    s = pooled["holdout"]["market_week_by_size"]
    lines += [
        "",
        f"The smaller half of markets close {s['smaller_half']['mean_observed']:.1f} deals a week on "
        f"average in the holdouts, the larger half {s['larger_half']['mean_observed']:.1f}.",
        "",
        "## Definitions",
        "",
        *[f"- **{k}:** {v}" for k, v in DEFINITIONS.items()],
        "",
    ]
    return "\n".join(lines)


def run(fold_ends=FOLD_ENDS, horizon: int = HORIZON, regions=None, sampler: dict | None = None,
        fit_dir: Path = FIT_DIR, out_json: Path = OUT_JSON, out_md: Path = OUT_MD,
        quiet: bool = False) -> dict:
    t0 = time.time()
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, flush=True))
    sampler = {**C.SAMPLER, **(sampler or {})}
    panel = load_panel()
    if regions:
        panel = panel.subset(regions)
    windows = fold_windows(panel.weeks, fold_ends, horizon)
    meta = {"fold_ends": [str(pd.Timestamp(e).date()) for e in fold_ends], "horizon_weeks": horizon,
            "folds": len(windows), "regions": len(panel.regions), "subset": {"regions": regions},
            "window": [str(panel.weeks[0].date()), str(panel.weeks[-1].date())],
            "sampler": sampler, "hdi_prob": C.HDI_PROB, "posterior_predictive_seed": PP_SEED}
    preds, res = [], {}
    for w in windows:
        preds.append(predict_fold(w, horizon, regions, sampler, Path(fit_dir), log))
        res = assemble(preds, {**meta, "seconds": round(time.time() - t0)})
        fit.write_json(Path(out_json), res)
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        Path(out_md).write_text(render_md(res), encoding="utf-8")
        f = res["folds"][-1]["holdout"]["national_week"]
        log(f"[{w['fold']}] national weekly MAPE {_pct(f['mape'])}, WAPE {_pct(f['wape'])}, "
            f"bias {_pct(f['bias_pct'])}; wrote {Path(out_json).name} and {Path(out_md).name}")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fold-ends", nargs="+", default=list(FOLD_ENDS),
                    help="last training week of each fold (a Monday in the data)")
    ap.add_argument("--horizon", type=int, default=HORIZON, help="weeks each fold predicts")
    args = ap.parse_args(argv)
    res = run(args.fold_ends, args.horizon)
    p = res["pooled"]
    print(json.dumps(fit._jsonable({"pooled_national_week": p["holdout"]["national_week"],
                                    "fold_range": p["fold_range"],
                                    "folds_passing_every_gate": p["folds_passing_every_gate"]}), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
