"""The eval set, its scorer, and the governed layer's agreement with plain SQL."""

from pathlib import Path

import duckdb
import pytest

from evals.run import load_questions, parse_answer
from evals.score import is_correct

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "data" / "warehouse.duckdb"
needs_warehouse = pytest.mark.skipif(not DB.exists(), reason="run python -m sim and dbt build first")


def test_eval_set_shape():
    qs = load_questions()
    assert len(qs) == 50
    assert len({q["id"] for q in qs}) == 50
    assert sum(q["answer_type"] == "refusal" for q in qs) == 8
    assert all(q.get("sql") for q in qs if q["answer_type"] != "refusal")


def test_parse_answer_takes_the_last_json_line():
    text = 'Spend was high.\n{"answer": 1, "refused": false}\nActually:\n{"answer": 1331.27, "refused": false}'
    assert parse_answer(text) == (1331.27, False)
    assert parse_answer("no json here") == (None, None)


def test_scoring_rules():
    num = {"answer_type": "number"}
    pct = {"answer_type": "percent"}
    assert is_correct(num, {"answer": "1,331.3", "refused": False}, 1331.27)
    assert not is_correct(num, {"answer": 1400, "refused": False}, 1331.27)
    assert is_correct(pct, {"answer": 0.1589, "refused": False}, 15.891)
    assert is_correct({"answer_type": "text"}, {"answer": "paid_search_nonbrand", "refused": False}, "Paid Search Non-Brand")
    assert is_correct({"answer_type": "refusal"}, {"answer": None, "refused": True}, None)
    assert not is_correct(num, {"answer": None, "refused": True}, 5.0)


@needs_warehouse
def test_every_ground_truth_query_returns_one_value():
    con = duckdb.connect(str(DB), read_only=True)
    try:
        for q in load_questions():
            if q["answer_type"] != "refusal":
                rows = con.execute(q["sql"]).fetchall()
                assert len(rows) == 1 and rows[0][0] is not None, q["id"]
    finally:
        con.close()


@needs_warehouse
def test_semantic_layer_matches_plain_sql():
    con = duckdb.connect(str(DB), read_only=True)
    truth = {q["id"]: con.execute(q["sql"]).fetchone()[0] for q in load_questions() if q["id"] in ("q01", "q19", "q24", "q40")}
    con.close()

    from servers.semantic_layer import SemanticLayer

    layer = SemanticLayer()

    def one(metric, start, end):
        rows = layer.query([metric], grain="year", start_date=start, end_date=end)["rows"]
        assert len(rows) == 1
        return rows[0][1]

    assert one("spend", "2024-01-01", "2024-12-31") == pytest.approx(float(truth["q01"]), rel=1e-6)
    assert 100 * one("win_rate", "2024-01-01", "2024-12-31") == pytest.approx(float(truth["q19"]), rel=1e-4)
    assert one("cost_per_acquisition", "2025-01-01", "2025-12-31") == pytest.approx(float(truth["q24"]), rel=1e-4)
    assert one("ae_headcount", "2024-01-01", "2024-12-31") == pytest.approx(float(truth["q40"]))
