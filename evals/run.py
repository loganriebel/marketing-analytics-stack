"""Ask headless Claude every eval question, through one of two MCP servers.

  governed: servers.governed (MetricFlow metrics only)
  raw:      servers.raw_sql (read-only SQL over the raw exports)

Each answer is appended to evals/results/<arm>__<model>.jsonl as soon as it
lands, and questions already answered there are skipped, so a cut-off run
resumes where it stopped. Claude runs from an empty folder with every
built-in tool off, so the MCP server is its only way to see data.

  python -m evals.run --arm both --model claude-sonnet-5-5
  python -m evals.run --arm both --set 2026     # the 2026 test and rollout questions

A question set other than the default (evals/questions_<set>.yml) names its own data cut:
both MCP servers read that cut, and its answers go to <arm>__<model>__<set>.jsonl.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "evals" / "questions.yml"
BASE_WEEKS = ("2023-01-02", "2025-12-22")
RESULTS_DIR = REPO / "evals" / "results"
DEFAULT_MODEL = "claude-sonnet-5-5"

ARMS = {
    "governed": {"server": "metrics", "module": "servers.governed",
                 "tools": ["mcp__metrics__list_metrics", "mcp__metrics__query_metric"]},
    "raw": {"server": "rawsql", "module": "servers.raw_sql",
            "tools": ["mcp__rawsql__list_tables", "mcp__rawsql__run_sql"]},
}

SYSTEM = """You are a marketing analyst at Fernhook Software, a B2B software company. Answer the question using only your tools.
House rules:
- Weekly data runs from the week of {first} through the week of {last}.
- A week belongs to the month, quarter and year that contain its Monday.
- Spend and revenue are in USD.
- If your tools and data cannot answer the question, or would need a definition you do not have, say so instead of estimating.
Finish with exactly one line of JSON and nothing after it:
{"answer": <a number, or text for a name, or null>, "refused": <true if you could not answer, else false>}
Write percentages as numbers like 12.5 for 12.5%. Do not put units, commas or currency symbols inside the number."""

ANSWER_RE = re.compile(r"\{[^{}]*\"answer\"[^{}]*\}", re.S)


def load_set(name: str | None = None) -> dict:
    """A question set: its questions, and for a later data cut its warehouse, raw folder and weeks."""
    path = QUESTIONS if not name else REPO / "evals" / f"questions_{name}.yml"
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {"name": name, "questions": d["questions"], "warehouse": d.get("warehouse"),
            "raw_dir": d.get("raw_dir"), "weeks": tuple(str(w) for w in d.get("weeks", BASE_WEEKS))}


def load_questions(name: str | None = None) -> list[dict]:
    return load_set(name)["questions"]


def results_path(arm: str, model: str, name: str | None = None) -> Path:
    return RESULTS_DIR / (f"{arm}__{model}.jsonl" if not name else f"{arm}__{model}__{name}.jsonl")


def system_prompt(qset: dict) -> str:
    return SYSTEM.replace("{first}", qset["weeks"][0]).replace("{last}", qset["weeks"][1])


def server_env(qset: dict) -> dict[str, str]:
    """Point both MCP servers at the set's data cut (paths relative to the repo root)."""
    env = {}
    if qset.get("warehouse"):
        env["FERNHOOK_WAREHOUSE"] = qset["warehouse"]
    if qset.get("raw_dir"):
        env["FERNHOOK_RAW_DIR"] = qset["raw_dir"]
    return env


def done_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not row.get("error"):
            ids.add(row["id"])
    return ids


def parse_answer(text: str) -> tuple[object, bool | None]:
    matches = ANSWER_RE.findall(text or "")
    if not matches:
        return None, None
    try:
        obj = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None, None
    return obj.get("answer"), bool(obj.get("refused"))


def ask(question: str, arm: str, model: str, workdir: Path, timeout: int, qset: dict | None = None) -> dict:
    spec = ARMS[arm]
    qset = qset or load_set()
    cfg = {"mcpServers": {spec["server"]: {
        "command": sys.executable, "args": ["-m", spec["module"]],
        "env": {"PYTHONPATH": str(REPO), **server_env(qset)}}}}
    cfg_path = workdir / f"mcp_{arm}.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    cmd = ["claude", "-p", question, "--output-format", "json", "--model", model,
           "--tools", "", "--strict-mcp-config", "--mcp-config", str(cfg_path),
           "--allowedTools", ",".join(spec["tools"]), "--setting-sources", "",
           "--append-system-prompt", system_prompt(qset),
           "--max-turns", "20", "--no-session-persistence"]
    # Load MCP tools up front; with tool search on, they stay deferred behind ToolSearch,
    # which --tools "" removes, so Claude would see no tools at all.
    env = {**os.environ, "ENABLE_TOOL_SEARCH": "false"}
    started = time.time()
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout, shell=False, env=env)
    elapsed = round(time.time() - started, 1)
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"error": f"exit {proc.returncode}: {(proc.stderr or proc.stdout)[-400:]}", "seconds": elapsed}
    text = out.get("result") or ""
    answer, refused = parse_answer(text)
    return {
        "answer": answer, "refused": refused, "final_text": text[-1500:],
        "turns": out.get("num_turns"), "cost_usd": out.get("total_cost_usd"), "seconds": elapsed,
        "models_used": sorted((out.get("modelUsage") or {}).keys()),
        "error": None if not out.get("is_error") else f"claude error: {text[-400:]}",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=["governed", "raw", "both"], default="both")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--ids", help="comma-separated question ids, e.g. q01,q43")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per question")
    ap.add_argument("--set", dest="qset", help="a question set other than the default, e.g. 2026")
    args = ap.parse_args()

    qset = load_set(args.qset)
    questions = qset["questions"]
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    arms = ["governed", "raw"] if args.arm == "both" else [args.arm]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="fernhook_eval_") as tmp:
        workdir = Path(tmp)
        for arm in arms:
            path = results_path(arm, args.model, args.qset)
            skip = done_ids(path)
            todo = [q for q in questions if q["id"] not in skip]
            print(f"[{arm}] {len(skip)} already answered, {len(todo)} to go", flush=True)
            for q in todo:
                try:
                    row = ask(q["question"], arm, args.model, workdir, args.timeout, qset)
                except subprocess.TimeoutExpired:
                    row = {"error": f"timeout after {args.timeout}s"}
                row = {"id": q["id"], "arm": arm, "model": args.model, **row}
                with path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(row) + "\n")
                status = "ERROR" if row.get("error") else ("refused" if row.get("refused") else row.get("answer"))
                print(f"[{arm}] {q['id']}: {status} ({row.get('seconds')}s)", flush=True)


if __name__ == "__main__":
    main()
