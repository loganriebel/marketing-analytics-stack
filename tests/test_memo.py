"""Step 5 funding memo: facts pack, grounding check, and what memo/ may read."""

import builtins
import json
import pathlib
import re

import pytest

from memo import facts as F
from memo import grounding as G
from memo import writer as W

REPO = pathlib.Path(__file__).resolve().parents[1]
MEMO = REPO / "memo"


@pytest.fixture(scope="module")
def pack():
    return json.loads(F.FACTS_PATH.read_text(encoding="utf-8"))


def _pack(*facts):
    return {"facts": [{"id": f"f{i}", "low": None, "high": None, **f} for i, f in enumerate(facts)]}


SMALL = _pack(
    {"value": 1491622.59, "unit": "USD"},
    {"value": 166.325, "low": 10.139, "high": 333.68, "unit": "deals"},
    {"value": 472477.77, "low": 28801.76, "high": 947882.58, "unit": "USD"},
    {"value": 29.8157, "low": 22.366, "high": 37.989, "unit": "percent"},
    {"value": 8, "unit": "weeks"},
    {"value": None, "low": 6, "high": 8, "unit": "weeks"},
    {"value": 4, "unit": "markets"},
    {"value": -42.1384, "unit": "percent"},
    {"value": 11.7899, "low": 8.7622, "high": 20.096, "unit": "months"},
)


# --- an invented number fails ---------------------------------------------------

def test_committed_memo_passes_and_matches_committed_grounding(pack):
    memo = G.MEMO_PATH.read_text(encoding="utf-8")
    result = G.check(memo, pack)
    assert result["pass"], result["unmatched"]
    assert result["checked"] >= 20
    committed = json.loads(G.GROUNDING_PATH.read_text(encoding="utf-8"))
    assert committed["pass"] and committed["score"] == 1.0
    assert committed["numbers"] == json.loads(json.dumps(result["numbers"]))


@pytest.mark.parametrize("invented", ["We also expect $7.3M in savings.", "It adds 412 deals.",
                                      "Payback is 3 months.", "Spend rises 17%.", "It needs nine markets."])
def test_invented_number_fails(pack, invented):
    memo = G.MEMO_PATH.read_text(encoding="utf-8") + "\n" + invented + "\n"
    result = G.check(memo, pack)
    assert not result["pass"]
    assert result["score"] < 1.0
    assert len(result["unmatched"]) == 1


def test_changed_number_fails(pack):
    memo = G.MEMO_PATH.read_text(encoding="utf-8")
    assert "166" in memo
    result = G.check(memo.replace("166", "176", 1), pack)
    assert [u["text"] for u in result["unmatched"]] == ["176"]


def test_grounding_cli_fails_below_100(tmp_path, pack):
    memo = tmp_path / "memo.md"
    memo.write_text("Move $1.5M a year for 900 deals.\n", encoding="utf-8")
    assert G.main(["--memo", str(memo), "--facts", str(F.FACTS_PATH), "--out", str(tmp_path / "g.json")]) == 1
    out = json.loads((tmp_path / "g.json").read_text(encoding="utf-8"))
    assert out["score"] == 0.5 and not out["pass"]


# --- allowed rounding passes, and only that -----------------------------------------

@pytest.mark.parametrize("text", [
    "$1.5M", "$1.49M", "$1,491,623", "$1.492 million", "1.5 million dollars",
    "166 deals", "170 more deals", "166.3 deals",
    "$472K", "$470K", "$0.47M",
    "30%", "29.8%", "30 percent",
    "8 weeks", "an 8-week test", "4 markets",
    "42%", "-42%", "12 months", "11.8 months", "eight weeks", "four markets",
])
def test_allowed_rounding_passes(text):
    result = G.check(text + "\n", SMALL)
    assert result["pass"] and result["checked"] == 1, result


@pytest.mark.parametrize("text", [
    "$1M",          # one significant figure
    "$2M",
    "$1.4M",        # wrong at the digit shown
    "$473K",        # 472,478 rounds to $472K
    "200 deals",    # two significant figures means 170
    "31%",
    "9 weeks",
    "$8",           # a weeks fact is not dollars
    "8%",           # nor a percent
    "4 deals",      # a markets fact is not deals
    "4 channels",
    "nine weeks",   # number words are numbers too
    "twice",
])
def test_bad_rounding_or_units_fail(text):
    result = G.check(text + "\n", SMALL)
    assert not result["pass"], result


@pytest.mark.parametrize("text", [
    "166 deals (90% range: 10 to 334)", "10 to 334 deals", "between 10 and 334 deals",
    "$29K to $948K", "$28,802 to $948K", "$0.029M to $0.95M", "22.4% to 38%", "6 to 8 weeks", "6-8 weeks",
    "8.8 to 20 months",
])
def test_ranges_must_match_one_facts_interval(text):
    small = {"facts": SMALL["facts"] + [{"id": "p", "value": 90, "low": None, "high": None, "unit": "percent"}]}
    result = G.check(text + "\n", small)
    assert result["pass"], result
    assert any(n["kind"] == "range" for n in result["numbers"])


@pytest.mark.parametrize("text", ["10 to 400 deals", "$29K to $472K", "22% to 30%", "4 to 8 weeks"])
def test_range_with_ends_from_different_facts_fails(text):
    assert not G.check(text + "\n", SMALL)["pass"]


def test_dates_years_numbering_and_labels_are_exempt():
    memo = ("# Memo\n## 1. The ask\n1. Fund it in Q1.\n2) Data from 2023 to 2025, through 2025-12-22.\n"
            "Decide by June 1. Our B2B fleet buyers.\n")
    result = G.check(memo, SMALL)
    assert result["checked"] == 0 and result["pass"]
    assert {e["why"] for e in result["exempt"]} == {"numbering", "year", "iso_date", "date"}


# --- memo/ never reads the answer key or the grader's output ------------------------

def test_memo_code_never_mentions_answer_key_or_grading():
    for p in sorted(MEMO.glob("*.py")):
        text = p.read_text(encoding="utf-8").lower()
        assert "truth" not in text, p.name
        assert "grading" not in text and "mmm.grade" not in text and "import grade" not in text, p.name
        assert "sim/" not in text and "sim\\\\" not in text, p.name
        assert not re.search(r"^\s*(from|import)\s+sim\b", text, re.M), p.name


def _audit_reads(monkeypatch):
    seen = []
    real_open, real_read, real_popen = builtins.open, pathlib.Path.read_text, pathlib.Path.open

    def rec(p):
        seen.append(pathlib.Path(p).resolve())

    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (rec(f), real_open(f, *a, **k))[1])
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, *a, **k: (rec(self), real_read(self, *a, **k))[1])
    monkeypatch.setattr(pathlib.Path, "open", lambda self, *a, **k: (rec(self), real_popen(self, *a, **k))[1])
    return seen


def test_facts_pack_reads_only_mmm_outputs(monkeypatch):
    seen = _audit_reads(monkeypatch)
    F.build()
    out = (REPO / "mmm" / "outputs").resolve()
    assert seen and all(out in p.parents for p in seen), seen


def test_grounding_reads_only_memo_outputs(monkeypatch, tmp_path):
    seen = _audit_reads(monkeypatch)
    G.run(out=None)
    out = (REPO / "memo" / "outputs").resolve()
    assert seen and all(out in p.parents for p in seen), seen


def test_facts_sources_are_model_outputs_or_the_test_design(pack):
    for f in pack["facts"]:
        assert f["source"].startswith("mmm/outputs/") or f["kind"] == "design", f["id"]
        assert "truth" not in json.dumps(f).lower() and "grading" not in json.dumps(f).lower(), f["id"]
    assert all(r.startswith("mmm/outputs/") for r in pack["meta"]["reads"])


def test_memo_outputs_hold_no_answer_key():
    for p in (MEMO / "outputs").glob("*"):
        assert "truth" not in p.read_text(encoding="utf-8").lower(), p.name


# --- the facts pack is deterministic -----------------------------------------------

def test_facts_pack_is_deterministic_and_matches_committed():
    a = json.dumps(F.build(), indent=2) + "\n"
    b = json.dumps(F.build(), indent=2) + "\n"
    assert a == b
    assert a == F.FACTS_PATH.read_text(encoding="utf-8")


def test_fact_ids_unique_and_complete(pack):
    ids = [f["id"] for f in pack["facts"]]
    assert len(ids) == len(set(ids))
    for f in pack["facts"]:
        assert f["unit"] in {"USD", "deals", "percent", "weeks", "months", "markets", "channels", "years", "multiplier"}, f["id"]
        assert f["value"] is not None or (f["low"] is not None and f["high"] is not None), f["id"]
    for v in pack["variants"].values():
        claim = next(f for f in pack["facts"] if f["id"] == v["deals_fact"])
        assert claim["low"] < claim["value"] < claim["high"]


def test_pack_prose_has_no_numbers(pack):
    """Numbers live in facts. The prose the writer reads carries none, so it cannot pass one on."""
    texts = [r["text"] for r in pack["risks"]] + pack["recommendation"] + \
        [pack["test"][k] for k in ("what", "decision_rule", "limits")] + [v["what"] for v in pack["variants"].values()]
    for t in texts:
        assert G.check(t, {"facts": []})["checked"] == 0, t


# --- the writer ------------------------------------------------------------------

def test_writer_runs_headless_with_no_tools():
    cmd = W.command(W.DEFAULT_MODEL)
    assert W.DEFAULT_MODEL == "claude-sonnet-5-5"
    assert cmd[:2] == ["claude", "-p"]
    assert cmd[cmd.index("--model") + 1] == "claude-sonnet-5-5"
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd


def test_committed_memo_meets_style():
    memo = G.MEMO_PATH.read_text(encoding="utf-8")
    assert W.style_problems(memo) == []
