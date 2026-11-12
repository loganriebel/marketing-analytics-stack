"""The answer key in sim/truth/ must never feed the warehouse.

Two layers: a text scan of every file in the dbt project, and a check of the parsed
manifest so paths built by Jinja are caught too.
"""

import re
from pathlib import Path

import pytest
from dbt.cli.main import dbtRunner

REPO = Path(__file__).resolve().parents[1]
WAREHOUSE = REPO / "warehouse"
GENERATED_DIRS = {"target", "logs", "dbt_packages"}
FILE_READERS = re.compile(r"\b(read_csv|read_csv_auto|read_json|read_json_auto|read_parquet|read_text|read_blob|glob)\s*\(", re.I)


def _project_files():
    for p in WAREHOUSE.rglob("*"):
        if p.is_file() and not GENERATED_DIRS & set(p.relative_to(WAREHOUSE).parts):
            yield p


def test_no_dbt_file_mentions_truth():
    hits = [
        p.relative_to(REPO).as_posix()
        for p in _project_files()
        if "truth" in p.read_text(encoding="utf-8").lower()
    ]
    assert hits == []


@pytest.fixture(scope="module")
def manifest(tmp_path_factory):
    out = tmp_path_factory.mktemp("dbt_parse")
    result = dbtRunner().invoke([
        "parse",
        "--project-dir", str(WAREHOUSE),
        "--profiles-dir", str(WAREHOUSE),
        "--target-path", str(out / "target"),
        "--log-path", str(out / "logs"),
        "--quiet",
    ])
    assert result.success, result.exception
    return result.result


def test_every_source_reads_from_data_raw(manifest):
    sources = list(manifest.sources.values())
    assert sources, "no sources parsed"
    for src in sources:
        location = src.meta.get("external_location") or src.config.meta.get("external_location")
        assert location, f"{src.unique_id} has no external_location"
        assert "data/raw/" in location, src.unique_id
        assert "truth" not in location.lower(), src.unique_id


def test_models_only_read_through_sources_and_refs(manifest):
    nodes = [n for n in manifest.nodes.values() if n.package_name == "marketing_analytics_stack"]
    assert any(n.resource_type == "model" for n in nodes)
    for node in nodes:
        code = node.raw_code or ""
        assert "truth" not in code.lower(), node.unique_id
        assert not FILE_READERS.search(code), f"{node.unique_id} reads files directly"
        for dep in getattr(node.depends_on, "nodes", []):  # seeds carry macro deps only
            assert "truth" not in dep.lower(), node.unique_id
