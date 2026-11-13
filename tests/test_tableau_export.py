"""The Tableau export: one row per grain, totals that match the governed metrics, and
no path to the answer key. Only mmm/grade.py may read sim/truth/; the export takes the
answer-key columns from the grader's written results in mmm/grading/.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parents[1]
TABLEAU = REPO / "tableau"
COMMITTED = TABLEAU / "data"
DB = REPO / "data" / "warehouse.duckdb"
needs_warehouse = pytest.mark.skipif(not DB.exists(), reason="run python -m sim and dbt build first")

FILES = ("weekly_channel_market.csv", "controls_weekly_market.csv", "mmm_channel_views.csv",
         "mmm_response_curves.csv", "mmm_optimizer_plan.csv")

# Runs the export under an audit hook that logs every file Python opens and every module imported.
AUDITED_RUN = r"""
import json, os, runpy, sys
opened = []
def hook(event, args):
    if event == "open" and isinstance(args[0], (str, os.PathLike)):
        opened.append(os.path.abspath(os.fspath(args[0])))
sys.addaudithook(hook)
log, out = sys.argv[1], sys.argv[2]
sys.argv = ["tableau.export", "--out-dir", out]
try:
    runpy.run_module("tableau.export", run_name="__main__")
except SystemExit as exc:
    if exc.code:
        raise
record = {"opened": list(opened), "modules": sorted(sys.modules)}
with open(log, "w", encoding="utf-8") as f:
    json.dump(record, f)
"""


GOVERNED_2025 = r"""
import json, sys
from servers.semantic_layer import SemanticLayer
layer = SemanticLayer()
totals = {m: layer.query([m], grain="year", start_date="2025-01-01", end_date="2025-12-31")["rows"]
          for m in ("spend", "leads", "closed_won_deals")}
with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(totals, f)
"""


def _child(code: str, *args: Path) -> None:
    # A child process, so no DuckDB handle outlives the test: dbt-duckdb keeps the file
    # open for the life of the process, which locks out other readers on Windows.
    run = subprocess.run([sys.executable, "-c", code, *map(str, args)], cwd=REPO, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr


@pytest.fixture(scope="module")
def export(tmp_path_factory):
    out = tmp_path_factory.mktemp("tableau_export")
    log = out / "audit.json"
    _child(AUDITED_RUN, log, out)
    return out, json.loads(log.read_text(encoding="utf-8"))


def test_tableau_code_never_mentions_the_answer_key_or_raw_data():
    files = sorted(TABLEAU.glob("*.py"))
    assert files, "tableau package missing"
    for p in files:
        text = p.read_text(encoding="utf-8")
        for banned in ("sim/truth", "sim\\truth", "truth.json", "data/raw", "data\\raw"):
            assert banned not in text, f"{p.name} mentions {banned}"
        assert not re.search(r"^\s*(from|import)\s+sim\b|importlib", text, re.M), f"{p.name} imports the simulator"
        assert not re.search(r"\b(from|join)\s+(stg_|int_)", text, re.I), f"{p.name} reads staging rows"


@needs_warehouse
def test_export_never_opens_the_answer_key(export):
    _, audit = export
    opened = [Path(p).resolve() for p in audit["opened"]]
    sim_dir = (REPO / "sim").resolve()
    assert not [p for p in opened if p.is_relative_to(sim_dir) or p.name == "truth.json"]
    assert not [m for m in audit["modules"] if m == "sim" or m.startswith("sim.")]
    # the hook works: the grader's output and the MMM outputs were seen being read
    assert (REPO / "mmm" / "grading" / "grade_holdout.json").resolve() in opened
    assert (REPO / "mmm" / "outputs" / "channels.json").resolve() in opened


@needs_warehouse
def test_one_row_per_grain(export):
    out, _ = export
    keys = {
        "weekly_channel_market.csv": ["week_start", "region_id", "channel_id"],
        "controls_weekly_market.csv": ["week_start", "region_id"],
        "mmm_channel_views.csv": ["channel_id", "view_id"],
        "mmm_response_curves.csv": ["channel_id", "spend_multiplier"],
        "mmm_optimizer_plan.csv": ["channel_id"],
    }
    for name, cols in keys.items():
        df = pd.read_csv(out / name)
        assert not df.duplicated(cols).any(), name
    weekly = pd.read_csv(out / "weekly_channel_market.csv")
    assert len(weekly) == 156 * 20 * 13  # every week x market x lead source, paid or not
    assert weekly["week_start"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert weekly[["latitude", "longitude"]].notna().all().all()
    assert (weekly.loc[weekly["is_paid"] == 0, "spend"] == 0).all()
    views = pd.read_csv(out / "mmm_channel_views.csv")
    assert (views["is_answer_key"] == (views["view_id"] == "truth")).all()


@needs_warehouse
def test_2025_totals_match_the_governed_metrics(export, tmp_path):
    out, _ = export
    weekly = pd.read_csv(out / "weekly_channel_market.csv")
    y2025 = weekly[weekly["week_start"].between("2025-01-01", "2025-12-31")]

    _child(GOVERNED_2025, tmp_path / "governed.json")
    governed = json.loads((tmp_path / "governed.json").read_text(encoding="utf-8"))
    for metric, column in (("spend", "spend"), ("leads", "leads"), ("closed_won_deals", "won_deals")):
        rows = governed[metric]
        assert len(rows) == 1
        assert y2025[column].sum() == pytest.approx(float(rows[0][1]), rel=1e-9), metric


@needs_warehouse
def test_committed_csvs_match_a_fresh_export(export):
    out, _ = export
    for name in FILES:
        assert (COMMITTED / name).read_bytes() == (out / name).read_bytes(), f"re-run python -m tableau.export ({name})"
