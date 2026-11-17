"""Fast backtest on the smoke subset: 2 markets, 2 folds, a few hundred draws.

Needs .venv-mmm (requirements-mmm.txt) and a built warehouse:
    .venv-mmm\\Scripts\\python -m pytest tests/test_mmm_backtest.py -q
Skipped in the main environment, which has no PyMC.
"""

import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("pymc_marketing")
pytest.importorskip("nutpie")

from mmm import backtest  # noqa: E402
from mmm import config as C  # noqa: E402

if not C.WAREHOUSE.exists():
    pytest.skip("warehouse not built", allow_module_level=True)

ENDS = ["2023-12-25", "2024-03-25"]
HORIZON = 8
ARGS = {"fold_ends": ENDS, "horizon": HORIZON, "regions": ["CAK", "CMH"],
        "sampler": {"chains": 2, "draws": 100, "tune": 150}, "quiet": True}


@pytest.fixture(scope="module")
def bt(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("backtest")
    paths = {"fit_dir": tmp / "fits", "out_json": tmp / "backtest.json", "out_md": tmp / "backtest.md"}
    return {"res": backtest.run(**ARGS, **paths), "paths": paths}


def test_forecast_stats_on_known_numbers():
    s = backtest.forecast_stats([10, 20, 30, 40], [12, 18, 30, 44], lo=[11, 15, 25, 30], hi=[13, 25, 35, 39])
    assert np.isclose(s["mape"], 0.1) and np.isclose(s["wape"], 0.08) and np.isclose(s["mae"], 2.0)
    assert np.isclose(s["bias"], 1.0) and np.isclose(s["bias_pct"], 0.04) and np.isclose(s["mpe"], 0.05)
    assert np.isclose(s["nrmse_mean"], np.sqrt(6) / 25) and np.isclose(s["nrmse_range"], np.sqrt(6) / 30)
    assert np.isclose(s["coverage_90"], 0.5)


def test_fold_windows_check_the_cutoff():
    weeks = pd.date_range("2023-01-02", periods=30, freq="W-MON")
    w = backtest.fold_windows(weeks, ["2023-03-27"], 4)[0]
    assert (w["n_train"], w["holdout_start"], w["holdout_end"]) == (13, "2023-04-03", "2023-04-24")
    with pytest.raises(ValueError):
        backtest.fold_windows(weeks, ["2023-03-28"], 4)  # not a week start
    with pytest.raises(ValueError):
        backtest.fold_windows(weeks, ["2023-07-03"], 4)  # too few weeks left


def test_each_fold_trains_through_its_cutoff_and_predicts_the_next_weeks(bt):
    folds = bt["res"]["folds"]
    assert [f["train_end"] for f in folds] == ENDS
    for f in folds:
        start = pd.Timestamp(f["train_end"]) + pd.Timedelta(weeks=1)
        assert f["holdout_start"] == str(start.date())
        assert [r["week"] for r in f["weekly"]] == [str(d.date()) for d in
                                                     pd.date_range(start, periods=HORIZON, freq="W-MON")]
        assert set(f["gates"]["checks"]) >= {"rhat", "ess_bulk", "holdout_mape", "holdout_coverage"}


def test_fold_scores_match_the_fit_diagnostics(bt):
    # the same posterior predictive seed as fit.diagnostics, so the holdout MAPE agrees
    for f in bt["res"]["folds"]:
        pred = json.loads((bt["paths"]["fit_dir"] / f"{f['fold']}_predictions.json").read_text())
        assert np.isclose(f["holdout"]["national_week"]["mape"], pred["diagnostics_holdout"]["national_weekly_mape"])
        t = f["training"]["national_week"]
        assert np.isclose(t["nrmse_mean"], t["rmse"] / t["mean_observed"])
        assert np.isclose(f["holdout_over_training_nrmse"]["mean"],
                          f["holdout"]["national_week"]["nrmse_mean"] / t["nrmse_mean"])


def test_pooled_stats_cover_every_fold_week(bt):
    p = bt["res"]["pooled"]
    assert p["fold_weeks"] == len(ENDS) * HORIZON
    nat = p["holdout"]["national_week"]
    assert nat["n"] == len(ENDS) * HORIZON
    lo, hi = p["fold_range"]["wape"]
    assert lo - 1e-12 <= nat["wape"] <= hi + 1e-12  # pooled WAPE is a weighted mean of the folds'
    assert 0 <= nat["coverage_90"] <= 1
    assert p["holdout"]["market_week"]["n"] == len(ENDS) * HORIZON * 2
    assert set(p["holdout"]["market_week_by_size"]) == {"smaller_half", "larger_half"}


def test_posteriors_are_deleted_once_scored(bt):
    assert not list(bt["paths"]["fit_dir"].glob("*.nc"))


def test_outputs_are_written(bt):
    saved = json.loads(bt["paths"]["out_json"].read_text())
    assert saved["meta"]["folds_done"] == len(ENDS)
    assert "truth" not in bt["paths"]["out_json"].read_text().lower()
    md = bt["paths"]["out_md"].read_text()
    assert "WAPE" in md and "Pooled" in md


def test_rerun_reuses_scored_folds(bt):
    again = backtest.run(**ARGS, **bt["paths"])
    assert again["pooled"]["holdout"]["national_week"] == bt["res"]["pooled"]["holdout"]["national_week"]
