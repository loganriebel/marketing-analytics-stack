"""Run the whole Fernhook story in order with one command.

Each stage calls the repo's own entry points (python -m ... and dbt). Main-environment
steps run with --python (default .venv), MMM steps with --mmm-python (default
.venv-mmm), and dbt runs from the main environment's folder.
"""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Must equal dates.readout_snapshot in geotest/outputs/design.json; the readout finds its
# data cut by that date, and tests/test_stack.py checks the two agree.
CUT_DATE = "2026-05-31"
CUT_DIR = f"data/cut_{CUT_DATE}"
TEST_PLAN = "plans/2026_test.yaml"


@dataclass(frozen=True)
class Step:
    env: str                              # "main" or "mmm"
    cmd: tuple[str, ...]                  # starts with "python" or "dbt"
    cwd: str = "."
    env_vars: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Stage:
    name: str
    about: str
    steps: tuple[Step, ...]
    opt_in: bool = False


def py(env: str, module: str, *args: str, env_vars: tuple[tuple[str, str], ...] = ()) -> Step:
    return Step(env, ("python", "-m", module, *args), env_vars=env_vars)


def dbt(*args: str, cwd: str = ".") -> Step:
    return Step("main", ("dbt", *args), cwd=cwd)


STAGES: tuple[Stage, ...] = (
    Stage("sim", "Write the 2023 to 2025 world: raw CSVs and the hidden answer key.",
          (py("main", "sim"),)),
    Stage("dbt", "Build the golden marts and run every dbt test.",
          (dbt("build", "--project-dir", "warehouse", "--profiles-dir", "warehouse"),)),
    Stage("eda", "Write the EDA and data validation report.",
          (py("main", "eda"),)),
    Stage("evals", "Ask Claude 50 questions two ways (governed metrics and raw SQL) and score them. "
                   "Needs the claude CLI signed in. Costs about $7. Opt in with --with-evals.",
          (py("main", "evals.run", "--arm", "both"), py("main", "evals.score")), opt_in=True),
    Stage("mmm", "Fit the MMM with the last 13 weeks held out, then grade it against the answer key. "
                 "About 10 minutes.",
          (py("mmm", "mmm"), py("mmm", "mmm.grade"))),
    Stage("design", "Design the 2026 market test from the MMM.",
          (py("mmm", "geotest.design"),)),
    Stage("memo", "Write the proposal memo, check that every number is grounded, then grade its claims. "
                  "Calls the claude CLI, about $0.36 a draft.",
          (py("main", "memo", "--retries", "4"), py("mmm", "mmm.grade"))),
    Stage("test", "Run the world through May 2026 with the test plan, then build that data cut's marts.",
          (py("main", "sim", "--through", CUT_DATE, "--plan", TEST_PLAN, "--out", CUT_DIR),
           # dbt reads --target-path from the project folder, so this keeps the cut's
           # artifacts in the cut instead of over the base build's warehouse/target.
           dbt("build", "--project-dir", "../../warehouse", "--profiles-dir", "../../warehouse",
               "--no-partial-parse", "--target-path", f"../{CUT_DIR}/target", cwd=CUT_DIR))),
    Stage("readout", "Read out the test as pre-registered, then cross-check it with a synthetic control.",
          (py("main", "geotest.readout"), py("mmm", "geotest.crosscheck"), py("main", "geotest.readout"))),
    Stage("refit", "Refit the MMM with the test's lift results, then regrade it. About 15 minutes.",
          (py("mmm", "mmm", "--name", "refit", "--market-tests", "geotest/outputs/readout.json",
              "--estimands-through", "2025-12-22",
              env_vars=(("MMM_WAREHOUSE", f"{CUT_DIR}/data/warehouse.duckdb"),
                        ("MMM_OUTPUT_DIR", "mmm/outputs/refit"))),
           py("mmm", "mmm.grade", "--outputs", "mmm/outputs/refit",
              "--compare", "mmm/grading/grade_holdout.json"))),
    Stage("tableau", "Export the CSVs behind the Tableau dashboards.",
          (py("main", "tableau.export"),)),
)
NAMES = tuple(s.name for s in STAGES)


def venv_python(folder: str) -> str:
    for rel in ("Scripts/python.exe", "bin/python"):
        if (REPO / folder / rel).exists():
            return str(REPO / folder / rel)
    return sys.executable


def dbt_program(python: str) -> str:
    beside = Path(python).parent / ("dbt.exe" if os.name == "nt" else "dbt")
    return str(beside) if beside.exists() else (shutil.which("dbt") or "dbt")


def select(only: list[str] | None, start: str | None, with_evals: bool) -> list[Stage]:
    if only and start:
        raise SystemExit("Use --only or --from, not both.")
    if only:
        unknown = sorted(set(only) - set(NAMES))
        if unknown:
            raise SystemExit(f"Unknown stage(s): {', '.join(unknown)}. Stages: {', '.join(NAMES)}.")
        if "evals" in only and not with_evals:
            raise SystemExit("The evals cost about $7 in Claude usage. Add --with-evals to run them.")
        chosen = [s for s in STAGES if s.name in only]
    elif start:
        chosen = list(STAGES[NAMES.index(start):])
    else:
        chosen = list(STAGES)
    return [s for s in chosen if with_evals or not s.opt_in]


def command(step: Step, python: str, mmm_python: str) -> list[str]:
    head = {"python": mmm_python if step.env == "mmm" else python, "dbt": dbt_program(python)}[step.cmd[0]]
    return [head, *step.cmd[1:]]


def show(cmd: list[str], cwd: str) -> str:
    here = REPO / cwd
    short = [os.path.relpath(a, here) if os.path.isabs(a) and Path(a).is_relative_to(REPO) else a for a in cmd]
    return subprocess.list2cmdline(short) if os.name == "nt" else shlex.join(short)


def run(stages: list[Stage], python: str, mmm_python: str, dry_run: bool) -> int:
    total = time.monotonic()
    for stage in stages:
        print(f"\n== {stage.name}: {stage.about}", flush=True)
        began = time.monotonic()
        for step in stage.steps:
            cmd = command(step, python, mmm_python)
            print(f"   {show(cmd, step.cwd)}", flush=True)
            if step.cwd != ".":
                print(f"     in {step.cwd}", flush=True)
            for key, value in step.env_vars:
                print(f"     with {key}={value}", flush=True)
            if dry_run:
                continue
            rc = subprocess.run(cmd, cwd=REPO / step.cwd, env={**os.environ, **dict(step.env_vars)}).returncode
            if rc:
                print(f"\n!! {stage.name} failed (exit {rc}). Fix it, then rerun with --from {stage.name}.",
                      flush=True)
                return rc
        if not dry_run:
            print(f"   {stage.name} done in {time.monotonic() - began:.0f}s", flush=True)
    if not dry_run:
        print(f"\nAll {len(stages)} stage(s) done in {time.monotonic() - total:.0f}s.")
    return 0


def parser() -> argparse.ArgumentParser:
    stage_list = "\n".join(f"  {s.name:8s} {s.about}" for s in STAGES)
    ap = argparse.ArgumentParser(
        prog="python -m stack.run",
        description="Run the Fernhook story end to end, in order, with the repo's own commands.",
        epilog=f"Stages, in order:\n{stage_list}\n\n"
               "The evals cost about $7 in Claude usage, so they run only with --with-evals.\n"
               "The memo stage and the evals need the claude CLI signed in (claude auth login).",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", type=lambda s: [x.strip() for x in s.split(",") if x.strip()], action="extend",
                    metavar="STAGE[,STAGE]", help="run just these stages, in chain order")
    ap.add_argument("--from", dest="start", choices=NAMES, metavar="STAGE",
                    help="start at this stage and run to the end")
    ap.add_argument("--with-evals", action="store_true",
                    help="include the Claude evals (about $7 in Claude usage)")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    ap.add_argument("--python", default=venv_python(".venv"),
                    help="Python for the main environment (default: .venv if present)")
    ap.add_argument("--mmm-python", default=venv_python(".venv-mmm"),
                    help="Python for the MMM environment (default: .venv-mmm if present)")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    stages = select(args.only, args.start, args.with_evals)
    return run(stages, args.python, args.mmm_python, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
