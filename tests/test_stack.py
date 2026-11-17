"""python -m stack.run: every stage points at a real entry point, and the flags pick the right stages."""

import json
import re
from pathlib import Path

import pytest

from stack import run as R

REPO = Path(__file__).resolve().parents[1]
STEPS = [(stage.name, step) for stage in R.STAGES for step in stage.steps]


def _module_file(module: str) -> Path | None:
    base = REPO / module.replace(".", "/")
    for path in (base / "__main__.py", base.with_suffix(".py")):
        if path.exists():
            return path
    return None


@pytest.mark.parametrize("stage, step", [(n, s) for n, s in STEPS if s.cmd[0] == "python"],
                         ids=lambda x: x if isinstance(x, str) else " ".join(x.cmd[2:4]))
def test_python_steps_run_real_modules_with_real_flags(stage, step):
    assert step.cmd[1] == "-m"
    module = step.cmd[2]
    path = _module_file(module)
    assert path is not None, f"{stage}: no module {module} in the repo"
    assert path.name == "__main__.py" or '__name__ == "__main__"' in path.read_text(encoding="utf-8")
    package_source = "\n".join(p.read_text(encoding="utf-8") for p in (REPO / module.split(".")[0]).rglob("*.py"))
    for flag in (a for a in step.cmd[3:] if a.startswith("--")):
        assert f'"{flag}"' in package_source, f"{stage}: {module} has no {flag} flag"


@pytest.mark.parametrize("stage, step", [(n, s) for n, s in STEPS if s.cmd[0] == "dbt"],
                         ids=lambda x: x if isinstance(x, str) else "dbt")
def test_dbt_steps_point_at_the_dbt_project(stage, step):
    args = step.cmd
    assert args[1] == "build"
    for flag in ("--project-dir", "--profiles-dir"):
        folder = (REPO / step.cwd / args[args.index(flag) + 1]).resolve()
        assert folder == (REPO / "warehouse").resolve()
    if "--target-path" in args:
        # dbt resolves it from the project folder; it must land inside the step's own folder
        target = (REPO / "warehouse" / args[args.index("--target-path") + 1]).resolve()
        assert target == (REPO / step.cwd / "target").resolve()
    assert (REPO / "warehouse" / "dbt_project.yml").exists()
    assert (REPO / "warehouse" / "profiles.yml").exists()


def test_dbt_program_is_found_beside_the_main_python():
    pytest.importorskip("dbt.cli.main")
    import sys
    assert Path(R.dbt_program(sys.executable)).name.startswith("dbt")


def test_every_step_names_a_known_environment():
    assert {step.env for _, step in STEPS} <= {"main", "mmm"}
    assert all(step.cmd[0] in ("python", "dbt") for _, step in STEPS)


def test_the_data_cut_matches_the_readout_snapshot():
    design = json.loads((REPO / "geotest" / "outputs" / "design.json").read_text(encoding="utf-8"))
    assert R.CUT_DATE == design["dates"]["readout_snapshot"]
    assert (REPO / R.TEST_PLAN).exists()


def test_inputs_named_on_the_command_line_are_committed():
    for path in ("geotest/outputs/readout.json", "mmm/grading/grade_holdout.json", R.TEST_PLAN):
        assert (REPO / path).exists(), path


def test_chain_order():
    assert R.NAMES == ("sim", "dbt", "eda", "evals", "mmm", "design", "memo", "test", "readout",
                       "refit", "tableau")


def test_evals_are_opt_in():
    names = lambda stages: [s.name for s in stages]
    assert "evals" not in names(R.select(None, None, with_evals=False))
    assert names(R.select(None, None, with_evals=True)) == list(R.NAMES)
    assert "evals" not in names(R.select(None, "dbt", with_evals=False))
    with pytest.raises(SystemExit, match="--with-evals"):
        R.select(["evals"], None, with_evals=False)
    assert names(R.select(["evals"], None, with_evals=True)) == ["evals"]


def test_only_and_from():
    assert [s.name for s in R.select(["tableau", "sim"], None, False)] == ["sim", "tableau"]
    assert [s.name for s in R.select(None, "readout", False)] == ["readout", "refit", "tableau"]
    with pytest.raises(SystemExit, match="Unknown"):
        R.select(["nope"], None, False)
    with pytest.raises(SystemExit, match="not both"):
        R.select(["sim"], "dbt", False)


def test_dry_run_prints_every_stage_and_runs_nothing(monkeypatch, capsys):
    def no_run(*a, **k):
        raise AssertionError("dry run started a process")
    monkeypatch.setattr(R.subprocess, "run", no_run)
    assert R.main(["--dry-run", "--with-evals", "--python", "py-main", "--mmm-python", "py-mmm"]) == 0
    out = capsys.readouterr().out
    assert [m for m in re.findall(r"^== (\w+):", out, re.M)] == list(R.NAMES)
    assert "py-mmm -m mmm.grade" in out
    assert "py-main -m sim --through" in out
    assert "with MMM_WAREHOUSE=" in out


def test_help_says_what_the_evals_cost(capsys):
    with pytest.raises(SystemExit):
        R.main(["--help"])
    out = capsys.readouterr().out
    assert "$7" in out and "--with-evals" in out
