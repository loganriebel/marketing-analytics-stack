"""The market test's arms as MMM lift tests, and the committed refit that used them.

Needs .venv-mmm; skipped in the main environment, which has no PyMC.
"""

import json
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pymc_marketing")

from mmm.model import market_lift_rows  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
READOUT = json.loads((REPO / "geotest" / "outputs" / "readout.json").read_text(encoding="utf-8"))
REFIT = REPO / "mmm" / "outputs" / "refit"


def test_rows_keep_their_measured_lift_when_the_sign_fits():
    rows = READOUT["mmm_lift_tests"]["rows"]
    df, entered = market_lift_rows(rows, "CAK")
    assert list(df.columns) == ["geo", "channel", "x", "delta_x", "delta_y", "sigma"]
    for r, e in zip(rows, entered):
        if np.sign(r["delta_y"]) == np.sign(r["delta_x"]):
            assert e["delta_y_entered"] == r["delta_y"]


def test_a_wrong_signed_lift_enters_as_no_change():
    rows = [{"channel": "youtube", "x": 1000.0, "delta_x": 2500.0, "delta_y": -0.4, "sigma": 0.5},
            {"channel": "paid_search_nonbrand", "x": 7000.0, "delta_x": -4000.0, "delta_y": 0.2, "sigma": 0.5}]
    df, _ = market_lift_rows(rows, "CAK")
    assert df.delta_y.tolist() == [1e-9, -1e-9]
    assert (df.geo == "CAK").all() and df.sigma.tolist() == [0.5, 0.5]


@pytest.mark.skipif(not (REFIT / "channels.json").exists(), reason="refit outputs not written")
def test_committed_refit_used_the_readout_and_scored_the_first_window():
    diag = json.loads((REFIT / "diagnostics_refit.json").read_text(encoding="utf-8"))
    entered = {r["arm"]: r for r in diag["lift_tests"]["market_test"]}
    for r in READOUT["mmm_lift_tests"]["rows"]:
        assert np.isclose(entered[r["arm"]]["delta_y"], r["delta_y"])
        assert np.isclose(entered[r["arm"]]["sigma"], r["sigma"])
    assert diag["gates"]["all_pass"]
    meta = json.loads((REFIT / "channels.json").read_text(encoding="utf-8"))["meta"]
    assert meta["estimands_through"] == "2025-12-22"
    assert meta["window"][1] == READOUT["data_cut"]["last_week"]
    before = json.loads((REPO / "mmm" / "outputs" / "baselines.json").read_text(encoding="utf-8"))
    after = json.loads((REFIT / "baselines.json").read_text(encoding="utf-8"))
    _close(after, before)  # the same window's CRM and platform views


def test_grade_comparison_sets_two_grades_side_by_side():
    from mmm import grade as G

    g = json.loads((REPO / "mmm" / "grading" / "grade_holdout.json").read_text(encoding="utf-8"))
    c = G.compare(g, g)
    for r in c["channels"].values():
        for v in r.values():
            assert v["before"] == v["after"] and v["covered_before"] == v["covered_after"]
    assert c["marginal_cpa_calls"]["before"] == c["marginal_cpa_calls"]["after"]
    md = G.compare_markdown(c)
    assert md.count("\n| ") >= len(c["channels"]) and "—" not in md
    committed = REPO / "mmm" / "grading" / "compare_holdout_refit.json"
    if committed.exists():
        after = json.loads((REPO / "mmm" / "grading" / "grade_refit.json").read_text(encoding="utf-8"))
        assert json.loads(json.dumps(G.compare(g, after))) == json.loads(committed.read_text(encoding="utf-8"))


def _close(a, b):
    if isinstance(a, dict):
        assert set(a) == set(b)
        for k in a:
            _close(a[k], b[k])
    elif isinstance(a, float) and isinstance(b, float):
        assert np.isclose(a, b, rtol=1e-9), (a, b)
    else:
        assert a == b
