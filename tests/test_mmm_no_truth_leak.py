"""The MMM must learn from the marts only.

Only mmm/grade.py may read the answer key. No model module may import the
simulator or read the raw exports. Runs in either environment (text checks only).
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MMM = REPO / "mmm"
GRADER = "grade.py"
SIM_IMPORT = re.compile(r"^\s*(from|import)\s+sim\b|^\s*from\s+\.\.\s*sim\b|importlib", re.M)


def _model_modules():
    files = sorted(p for p in MMM.glob("*.py") if p.name != GRADER)
    assert files, "mmm package missing"
    return files


def test_no_model_module_mentions_the_answer_key():
    for p in _model_modules():
        text = p.read_text(encoding="utf-8").lower()
        assert "truth" not in text, p.name
        assert "sim/" not in text and "sim\\\\" not in text, p.name


def test_no_model_module_imports_the_simulator():
    for p in _model_modules():
        assert not SIM_IMPORT.search(p.read_text(encoding="utf-8")), p.name


def test_no_model_module_reads_raw_exports():
    for p in _model_modules():
        text = p.read_text(encoding="utf-8")
        assert "data/raw" not in text and "data\\raw" not in text, p.name
        assert "read_csv" not in text, p.name


def test_grader_is_the_only_reader_and_writes_outside_outputs():
    text = (MMM / GRADER).read_text(encoding="utf-8")
    assert "truth.json" in text
    assert "OUTPUT_DIR /" not in text and 'outputs" /' not in text
    assert not SIM_IMPORT.search(text)


def test_committed_outputs_hold_no_truth():
    out = MMM / "outputs"
    for p in out.glob("*") if out.exists() else []:
        assert "truth" not in p.read_text(encoding="utf-8").lower(), p.name
