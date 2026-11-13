"""Write the CFO funding memo with headless Claude, from the facts pack only.

    python -m memo                               # facts, memo, grounding
    python -m memo --model claude-sonnet-5-5 --retries 2

Builds memo/outputs/facts.json, asks `claude -p` for the memo with every built-in
tool off and no MCP servers, from an empty folder, so the facts pack in the
prompt is all it sees. Then runs the grounding check. If a number fails, Claude
gets the failures and rewrites, up to --retries times. Exits 1 unless the final
memo passes at 100%.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

from . import facts as F
from . import grounding as G

DEFAULT_MODEL = "claude-sonnet-5-5"
WRITER_LOG = F.OUT_DIR / "writer.json"
SECTIONS = ["The ask", "Expected return", "Payback", "Risk", "The test"]

SYSTEM = """You write a one-page funding memo to the CFO of Fernhook Software, a fleet-maintenance software company. The facts pack in the prompt comes from the marketing mix model (MMM). It is your only source.

Numbers. A script checks every number in your memo against the facts pack, and the memo is thrown out if one fails.
- Use only numbers that are in the facts pack: a fact's value, or its low and high. Never compute a number yourself: no sums, differences, ratios, conversions or "about double".
- Round for a reader (2 or 3 significant figures is usually right), but never below two, and round correctly: 472,478 is $472K or $470K, never $473K; 1,491,623 is $1.5M or $1.49M, never $1M.
- A range must be one fact's own low and high: "166 more deals a year (90% range: 10 to 334)". Never pair ends from different facts.
- Write every number in digits. Never use number words like two, eight, dozen, half, double or twice. The word "one" is fine.
- Money as $1.5M, $472K or $2,841. Percents with %. Durations as "8 weeks" or "12 months".
- Every fact is already "a year" where its id says per_year. Do not use dates or years.
- If a sentence needs a number that is not in the pack, rewrite the sentence without it.

Content.
- Sections, in this order, as ## headings with these exact names: The ask, Expected return, Payback, Risk, The test.
- Start with a # title line, then the ask. The CFO should know what you want in the first two sentences.
- Present both variants in the pack: the same-budget reallocation, and the YouTube ask (new money).
- Early on, give the one comparison that explains the move: YouTube's cost per extra deal against the cut channels', with their ranges.
- Follow the pack's recommendation: the market test comes before the large move. Say why.
- Be honest about uncertainty. Give the 90% range next to every estimate of deals, revenue or payback. Say plainly what the model cannot see, using the pack's risks.
- No claims the pack does not support. Do not mention how the pack was built.

Style.
- CFO voice: direct, plain words, short sentences. No marketing jargon. Say "cost per deal" for CPA, "cost per extra deal" for marginal CPA, "90% range" for an HDI, "always-on" for channels that never pause.
- No em dashes or en dashes anywhere. Use commas, periods, colons or parentheses.
- About one page: 350 to 450 words. Short bullets are fine. No tables.
- Output only the memo in Markdown. No preamble, no closing note."""


def _prompt(pack: dict, previous: str | None = None, failures: list[dict] | None = None) -> str:
    body = "Facts pack:\n```json\n" + json.dumps(pack, indent=1) + "\n```\n\n"
    if previous is None:
        return body + "Write the memo."
    fails = "\n".join(f"- line {f['line']}: {f['text']}" for f in failures)
    return (body + "Your last draft is below. It failed these checks (numbers listed match no fact under "
                   "the rules):\n" + fails
            + "\n\nRewrite the whole memo. Fix each number by using a fact's value or its own range, rounded "
              "correctly, or drop it. Fix any other problem listed. Keep the rest.\n\nLast draft:\n" + previous)


def style_problems(text: str) -> list[dict]:
    """Checks the prompt asks for that a script can see: dashes, sections, length."""
    out = [{"line": i, "text": "em or en dash"} for i, ln in enumerate(text.splitlines(), 1)
           if "\u2014" in ln or "\u2013" in ln]
    heads = [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]
    if heads != SECTIONS:
        out.append({"line": 0, "text": f"sections must be exactly {SECTIONS}, got {heads}"})
    words = len(text.split())
    if not 300 <= words <= 550:
        out.append({"line": 0, "text": f"{words} words; aim for 350 to 450"})
    return out


def command(model: str) -> list[str]:
    return ["claude", "-p", "--output-format", "json", "--model", model, "--tools", "", "--strict-mcp-config",
            "--setting-sources", "", "--append-system-prompt", SYSTEM, "--max-turns", "1",
            "--no-session-persistence"]


def ask(prompt: str, model: str, timeout: int) -> dict:
    with tempfile.TemporaryDirectory(prefix="fernhook_memo_") as tmp:
        started = time.time()
        proc = subprocess.run(command(model), input=prompt, cwd=tmp, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, shell=False)
    out = json.loads(proc.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude error: {(out.get('result') or '')[-400:]}")
    return {"text": (out.get("result") or "").strip() + "\n", "cost_usd": out.get("total_cost_usd"),
            "seconds": round(time.time() - started, 1), "models_used": sorted((out.get("modelUsage") or {}))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--retries", type=int, default=2, help="rewrites allowed after a failed grounding check")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per Claude call")
    args = ap.parse_args(argv)

    pack = F.write()
    print(f"facts: {len(pack['facts'])} in {F.FACTS_PATH.relative_to(F.REPO).as_posix()}")
    attempts, text, problems = [], None, None
    for n in range(args.retries + 1):
        reply = ask(_prompt(pack, text, problems), args.model, args.timeout)
        text = reply["text"]
        G.MEMO_PATH.write_text(text, encoding="utf-8", newline="\n")
        result = G.run()
        style = style_problems(text)
        problems = [{"line": u["line"], "text": f"{u['text']!r} in: {u['context']}"}
                    for u in result["unmatched"]] + style
        attempts.append({"attempt": n + 1, **{k: reply[k] for k in ("cost_usd", "seconds", "models_used")},
                         "grounding_score": result["score"], "unmatched": result["unmatched"], "style": style})
        print(f"attempt {n + 1}: " + G.summary(result) + "".join(f"\n  style: {s['text']}" for s in style))
        if not problems:
            break
    log = {"model": args.model, "attempts": attempts, "grounding_pass": result["pass"],
           "style_pass": not style, "words": len(text.split())}
    WRITER_LOG.write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
