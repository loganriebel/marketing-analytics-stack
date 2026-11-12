"""Fast smoke fit of the MMM: 2 markets, 100 weeks, a few hundred draws (~1 minute).

Needs .venv-mmm (requirements-mmm.txt) and a built warehouse:
    .venv-mmm\\Scripts\\python -m pytest tests/test_mmm_smoke.py tests/test_mmm_no_truth_leak.py -q
Skipped in the main environment, which has no PyMC.
"""

import json

import numpy as np
import pytest

pytest.importorskip("pymc_marketing")
pytest.importorskip("nutpie")

from mmm import config as C  # noqa: E402
from mmm import fit, lift_tests, validation  # noqa: E402
from mmm.data import Panel  # noqa: E402
from mmm.estimands import Engine, MediaPosterior, hdi  # noqa: E402

if not C.WAREHOUSE.exists():
    pytest.skip("warehouse not built", allow_module_level=True)


@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("mmm")
    res = fit.run(holdout_weeks=8, name="smoke", regions=["CAK", "CMH"], n_weeks=100,
                  sampler={"chains": 2, "draws": 100, "tune": 150}, out_dir=tmp / "out",
                  fit_dir=tmp / "fits", write=True, quiet=True)
    scales = json.loads((tmp / "fits" / "smoke_scales.json").read_text())
    post = MediaPosterior.from_idata(res["idata"], scales["channel_scale"], scales["target_scale"],
                                     C.CHANNELS)
    res["engine"] = Engine(post, res["panel"])
    res["tmp"] = tmp
    return res


def test_lead_to_close_kernel_matches_readme():
    k = C.lead_to_close_kernel()
    assert np.isclose(k.sum(), 1.0)
    assert int(np.argmax(k)) == 2  # a lead closes in about two weeks


def test_fit_runs_with_lift_test_and_reports_gates(smoke):
    assert "pause_lift_tests" in smoke["mmm"].model.named_vars
    d = smoke["diagnostics"]
    for key in ("rhat_max", "ess_bulk_min", "divergence_rate", "ppc", "holdout"):
        assert key in d
    assert set(smoke["gates"]["checks"]) >= {"rhat", "ess_bulk", "divergences", "ppc_coverage",
                                             "holdout_mape"}


def test_fit_stats_are_reported(smoke):
    fs = smoke["diagnostics"]["fit_stats"]
    for scope in ("region_week", "national_week"):
        for k in ("mse", "rmse", "mae", "mape", "r2"):
            assert np.isfinite(fs[scope][k]), (scope, k)
        assert np.isclose(fs[scope]["rmse"] ** 2, fs[scope]["mse"])
    assert np.isfinite(fs["loo"]["elpd_loo"]) and fs["loo"]["n_obs"] == 2 * smoke["design"].n_train
    assert 0 < fs["residuals_national"]["durbin_watson"] < 4
    assert set(fs["residual_corr_with_spend"]) == set(C.CHANNELS)
    for k in ("rmse", "mae", "r2"):
        assert k in smoke["diagnostics"]["holdout"]["national_week"]
    params = (smoke["tmp"] / "out" / "parameters_smoke.csv").read_text()
    assert "saturation_beta[paid_search_brand]" in params and "p_above_zero" in params


def test_rescore_saved_fit_matches_the_original(smoke):
    again = fit.rescore_saved("smoke", 8, out_dir=smoke["tmp"] / "out", fit_dir=smoke["tmp"] / "fits",
                              quiet=True)
    a, b = smoke["diagnostics"], again["diagnostics"]
    assert a["rhat_max"] == b["rhat_max"]
    assert np.isclose(a["fit_stats"]["region_week"]["rmse"], b["fit_stats"]["region_week"]["rmse"])
    assert np.isclose(a["fit_stats"]["loo"]["elpd_loo"], b["fit_stats"]["loo"]["elpd_loo"])


def test_error_stats_and_residual_checks():
    e = validation.error_stats(np.array([1.0, 2.0, 3.0, 4.0]), np.array([1.0, 2.0, 3.0, 6.0]))
    assert np.isclose(e["mse"], 1.0) and np.isclose(e["mae"], 0.5) and np.isclose(e["bias"], 0.5)
    white = np.random.default_rng(0).normal(size=2000)
    r = validation.residual_checks(white)
    assert abs(r["lag1_autocorrelation"]) < 0.06 and abs(r["durbin_watson"] - 2) < 0.15
    trend = np.cumsum(white)
    assert validation.residual_checks(trend)["ljung_box_p"] < 1e-6


def test_engine_matches_pymc_marketing_contributions(smoke):
    idata, design, eng = smoke["idata"], smoke["design"], smoke["engine"]
    cc = (idata.posterior["channel_contribution"]
          .transpose("chain", "draw", "date", "channel", "geo").sel(geo=design.regions))
    cc = cc.values.reshape(-1, *cc.shape[2:]) * eng.post.target_scale * design.size[None, None, None, :]
    for k, ch in enumerate(C.CHANNELS):
        mine = eng.weekly(ch)[:, : design.n_train]
        assert np.allclose(mine, cc[:, :, k, :].sum(axis=-1), atol=1e-8), ch


def test_outputs_have_every_channel_with_hdis(smoke):
    out = smoke["tmp"] / "out"
    fit.write_outputs(smoke["engine"], smoke["panel"], smoke["meta"], out)
    ch = json.loads((out / "channels.json").read_text())
    assert set(ch["channels"]) == set(C.CHANNELS)
    for e in ch["channels"].values():
        for k in ("incremental_deals", "cpa", "marginal_cpa", "roi_revenue"):
            lo, hi = e[k]["hdi_90"]
            assert lo <= e[k]["median"] <= hi
    opt = json.loads((out / "optimizer.json").read_text())
    plan_spend = sum(p["spend_plan"] for p in opt["plan"])
    assert np.isclose(plan_spend, opt["total_spend"], rtol=1e-9)
    for f in ("channels.csv", "response_curves.csv", "contributions_weekly.csv", "baselines.json"):
        assert (out / f).exists(), f


def test_hdi_is_the_narrowest_interval():
    x = np.concatenate([np.zeros(50), np.linspace(0, 1, 950)])
    lo, hi = hdi(x, 0.9)
    assert lo == 0.0 and hi < 0.91


def test_find_pauses_on_a_synthetic_panel():
    import pandas as pd
    T, G = 40, 2
    spend = np.ones((T, G, len(C.CHANNELS)))
    spend[10:15, 1, C.CHANNELS.index(C.BRAND)] = 0.0
    panel = Panel(pd.date_range("2023-01-02", periods=T, freq="W-MON"), ["A", "B"], list(C.CHANNELS),
                  spend, np.ones((T, G)), np.ones((T, G)), np.array([1.0, 1.0]), pd.DataFrame(),
                  np.zeros((T, G)))
    pauses = lift_tests.find_pauses(panel)
    assert [(p.region, p.start, p.weeks) for p in pauses] == [("B", 10, 5)]
