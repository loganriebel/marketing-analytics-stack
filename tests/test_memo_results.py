"""The January 2027 results memo: grounded, in form, and built only from what the team wrote in 2026."""

import builtins
import json
import pathlib

import pytest

from memo import grounding as G
from memo import results as R
from memo import writer as W

REPO = pathlib.Path(__file__).resolve().parents[1]
ALLOWED = {(REPO / p).resolve() for p in ("geotest/outputs/readout.json", "rollout/outputs/plan.json",
                                          "rollout/outputs/results.json")}


@pytest.fixture(scope="module")
def pack():
    return json.loads(R.FACTS_PATH.read_text(encoding="utf-8"))


def test_committed_results_memo_is_fully_grounded(pack):
    result = G.check(R.MEMO_PATH.read_text(encoding="utf-8"), pack)
    assert result["pass"], result["unmatched"]
    assert result["checked"] >= 20
    committed = json.loads(R.GROUNDING_PATH.read_text(encoding="utf-8"))
    assert committed["pass"] and committed["numbers"] == json.loads(json.dumps(result["numbers"]))


def test_committed_results_memo_meets_style():
    assert W.style_problems(R.MEMO_PATH.read_text(encoding="utf-8"), R.RESULTS) == []


def test_invented_number_fails(pack):
    memo = R.MEMO_PATH.read_text(encoding="utf-8") + "\nThe rollout added 1,234 deals.\n"
    assert not G.check(memo, pack)["pass"]


def test_pack_reads_only_the_teams_2026_records(monkeypatch):
    seen = []
    real_open, real_read = builtins.open, pathlib.Path.read_text
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (seen.append(pathlib.Path(f).resolve()),
                                                                real_open(f, *a, **k))[1])
    monkeypatch.setattr(pathlib.Path, "read_text", lambda self, *a, **k: (seen.append(self.resolve()),
                                                                          real_read(self, *a, **k))[1])
    R.build()
    assert seen and set(seen) <= ALLOWED, seen


def test_pack_is_deterministic_and_matches_committed():
    a = json.dumps(R.build(), indent=2) + "\n"
    assert a == json.dumps(R.build(), indent=2) + "\n"
    assert a == R.FACTS_PATH.read_text(encoding="utf-8")


def test_pack_sources_and_prose(pack):
    for f in pack["facts"]:
        assert f["source"] in {"geotest/outputs/readout.json", "rollout/outputs/plan.json",
                               "rollout/outputs/results.json"}, f["id"]
    text = json.dumps(pack).lower()
    assert "truth" not in text and "grading" not in text
    prose = list(pack["test_readout"].values()) + [v for k, v in pack["rollout"].items()
                                                    if k not in ("verdict", "against_forecast")] + pack["next"]
    for t in prose:
        assert G.check(t, {"facts": []})["checked"] == 0, t


def test_chart_plots_only_facts(tmp_path, pack):
    drawn = R.draw(pack, tmp_path / "c.png")
    facts = {f["id"]: f for f in pack["facts"]}
    for row in drawn["plotted"]:
        f = facts[row["fact"]]
        assert (row["value"], row["low"], row["high"]) == (f["value"], f["low"], f["high"])
    assert R.CHART_PATH.exists()


def test_memo_states_the_holdouts_power(pack):
    power = next(f for f in pack["facts"] if f["id"] == "rollout_power")
    memo = R.MEMO_PATH.read_text(encoding="utf-8")
    assert f"{round(power['value'])}%" in memo
