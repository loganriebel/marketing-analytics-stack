"""Ask headless Claude every eval question, through one of two MCP servers.

  governed: servers.governed (MetricFlow metrics only)
  raw:      servers.raw_sql (read-only SQL over the raw exports)

Each answer is appended to evals/results/<arm>__<model>.jsonl as soon as it
lands, and questions already answered there are skipped, so a cut-off run
resumes where it stopped. Claude runs from an empty folder with every
built-in tool off, so the MCP server is its only way to see data.

  python -m evals.run --arm both --model claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
QUESTIONS = REPO / "evals" / "questions.yml"
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
- Weekly data runs from the week of 2023-01-02 through the week of 2025-12-22.
- A week belongs to the month, quarter and year that contain its Monday.
- Spend and revenue are in USD.
- If your tools and data cannot answer the question, or would need a definition you do not have, say so instead of estimating.
Finish with exactly one line of JSON and nothing after it:
{"answer": <a number, or text for a name, or null>, "refused": <true if you could not answer, else false>}
Write percentages as numbers like 12.5 for 12.5%. Do not put units, commas or currency symbols inside the number."""

ANSWER_RE = re.compile(r"\{[^{}]*\"answer\"[^{}]*\}", re.S)


def load_questions() -> list[dict]:
    return yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))["questions"]


def results_path(arm: str, model: str) -> Path:
    return RESULTS_DIR / f"{arm}__{model}.jsonl"


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


def ask(question: str, arm: str, model: str, workdir: Path, timeout: int) -> dict:
    spec = ARMS[arm]
    cfg = {"mcpServers": {spec["server"]: {
        "command": sys.executable, "args": ["-m", spec["module"]], "env": {"PYTHONPATH": str(REPO)}}}}
    cfg_path = workdir / f"mcp_{arm}.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    cmd = ["claude", "-p", question, "--output-format", "json", "--model", model,
           "--tools", "", "--strict-mcp-config", "--mcp-config", str(cfg_path),
           "--allowedTools", ",".join(spec["tools"]), "--setting-sources", "",
           "--append-system-prompt", SYSTEM, "--max-turns", "20", "--no-session-persistence"]
    started = time.time()
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, encoding="utf-8",
                          timeout=timeout, shell=False)
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
    args = ap.parse_args()

    questions = load_questions()
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    arms = ["governed", "raw"] if args.arm == "both" else [args.arm]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="fernhook_eval_") as tmp:
        workdir = Path(tmp)
        for arm in arms:
            path = results_path(arm, args.model)
            skip = done_ids(path)
            todo = [q for q in questions if q["id"] not in skip]
            print(f"[{arm}] {len(skip)} already answered, {len(todo)} to go", flush=True)
            for q in todo:
                try:
                    row = ask(q["question"], arm, args.model, workdir, args.timeout)
                except subprocess.TimeoutExpired:
                    row = {"error": f"timeout after {args.timeout}s"}
                row = {"id": q["id"], "arm": arm, "model": args.model, **row}
                with path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(json.dumps(row) + "\n")
                status = "ERROR" if row.get("error") else ("refused" if row.get("refused") else row.get("answer"))
                print(f"[{arm}] {q['id']}: {status} ({row.get('seconds')}s)", flush=True)


if __name__ == "__main__":
    main()
