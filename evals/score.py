"""Score eval results against SQL ground truth and write evals/RESULTS.md.

  python -m evals.score --model claude-sonnet-5-5
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import duckdb

from .run import DEFAULT_MODEL, REPO, load_questions, results_path

DB_PATH = REPO / "data" / "warehouse.duckdb"
OUT = REPO / "evals" / "RESULTS.md"
REL_TOL = 0.005  # 0.5%
ABS_TOL = {"number": 0.01, "percent": 0.05}


def ground_truth(questions: list[dict]) -> dict[str, object]:
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        return {q["id"]: con.execute(q["sql"]).fetchone()[0] for q in questions if q["answer_type"] != "refusal"}
    finally:
        con.close()


def _norm(s: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _to_float(v: object) -> float | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").replace("$", "").replace("%", "").strip())
    except ValueError:
        return None


def is_correct(q: dict, row: dict, truth: object) -> bool:
    kind = q["answer_type"]
    if kind == "refusal":
        return row.get("refused") is True
    if row.get("refused") or row.get("answer") is None:
        return False
    if kind == "text":
        a, e = _norm(row["answer"]), _norm(truth)
        return bool(a) and (a == e or e in a)
    a, e = _to_float(row["answer"]), float(truth)
    if a is None:
        return False
    tol = max(REL_TOL * abs(e), ABS_TOL[kind])
    candidates = [a, a * 100] if kind == "percent" else [a]  # accept 0.125 for 12.5%
    return any(abs(c - e) <= tol for c in candidates)


def load_rows(arm: str, model: str) -> dict[str, dict]:
    path = results_path(arm, model)
    rows = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if not r.get("error"):
                rows[r["id"]] = r
    return rows


def score(model: str) -> str:
    questions = load_questions()
    truth = ground_truth(questions)
    answerable = [q for q in questions if q["answer_type"] != "refusal"]
    refusals = [q for q in questions if q["answer_type"] == "refusal"]
    table, detail = [], []
    for arm, label in (("governed", "Claude + governed metrics (MCP)"), ("raw", "Claude + raw tables (SQL)")):
        rows = load_rows(arm, model)
        if not rows:
            continue
        ok = {q["id"]: is_correct(q, rows[q["id"]], truth.get(q["id"])) for q in questions if q["id"] in rows}
        acc = sum(ok[q["id"]] for q in answerable if q["id"] in ok)
        ref = sum(ok[q["id"]] for q in refusals if q["id"] in ok)
        false_ref = sum(1 for q in answerable if q["id"] in rows and rows[q["id"]].get("refused"))
        n_ans = sum(q["id"] in rows for q in answerable)
        n_ref = sum(q["id"] in rows for q in refusals)
        cost = sum(r.get("cost_usd") or 0 for r in rows.values())
        secs = [r.get("seconds") or 0 for r in rows.values()]
        table.append(f"| {label} | {acc}/{n_ans} ({acc / max(n_ans, 1):.0%}) | {ref}/{n_ref} ({ref / max(n_ref, 1):.0%}) | "
                     f"{false_ref} | {sum(ok.values())}/{len(rows)} | ${cost:.2f} | {sum(secs) / max(len(secs), 1):.0f}s |")
        for q in questions:
            if q["id"] in rows:
                r = rows[q["id"]]
                got = "refused" if r.get("refused") else r.get("answer")
                want = "refuse" if q["answer_type"] == "refusal" else truth[q["id"]]
                if isinstance(want, float):
                    want = round(want, 3)
                detail.append(f"| {arm} | {q['id']} | {q['category']} | {got} | {want} | {'yes' if ok[q['id']] else 'no'} |")
    md = [
        "# Eval results", "",
        f"Model: `{model}`, one pass per arm, same system prompt. 42 questions have a SQL ground truth "
        "(0.5% tolerance); 8 should be refused. Built-in tools are off, so each arm sees data only through its "
        "MCP server.", "",
        "| Arm | Answerable correct | Correct refusals | Wrong refusals | Overall | Cost | Avg time |",
        "|---|---|---|---|---|---|---|",
        *table, "",
        "## Per question", "",
        "| Arm | Id | Category | Answer | Truth | Correct |",
        "|---|---|---|---|---|---|",
        *detail, "",
    ]
    return "\n".join(md)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    text = score(args.model)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print("\n".join(text.splitlines()[:8]))


if __name__ == "__main__":
    main()
