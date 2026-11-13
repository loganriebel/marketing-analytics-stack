"""Write the CFO proposal memo with headless Claude, from the facts pack only.

    python -m memo                               # facts, memo, grounding
    python -m memo --model claude-sonnet-5-5 --retries 2

Builds memo/outputs/facts.json and the chart, asks `claude -p` for the memo with every built-in
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

from . import chart
from . import facts as F
from . import grounding as G

DEFAULT_MODEL = "claude-sonnet-5-5"
WRITER_LOG = F.OUT_DIR / "writer.json"
SECTIONS = ["The problem", "What we found", "The ask", "What it's worth", "How we'll know",
            "Appendix: the ranges"]
CHART_LINE = "![Cost per extra deal from the next dollar, by channel, with the model's 90% range](proposal_chart.png)"
HEADLINE_MAX_NUMBERS = 3
BODY_WORDS = (230, 400)
APPENDIX_MAX_WORDS = 230
BODY_MAX_NUMBERS = 16

SYSTEM = f"""You write a one-page proposal memo to the CFO of Fernhook Software, a fleet-maintenance software company. It is January 2026. The facts pack in the prompt holds the marketing mix model's (MMM) results, the 2024 and 2025 totals, and a market test designed from 2023 to 2025 data. It is your only source.

Numbers. A script checks every number in your memo against the facts pack, and the memo is thrown out if one fails.
- Use only numbers that are in the facts pack: a fact's value, or its low and high. Never compute a number yourself: no sums, differences, ratios, conversions or "about double".
- Round for a reader (2 or 3 significant figures), never below two, and round correctly: 472,478 is $472K or $470K, never $473K; 1,491,623 is $1.5M, never $1M.
- A range must be one fact's own low and high. Never pair ends from different facts.
- Write every number in digits. Never use number words like two, eight, dozen, half, double or twice. The word "one" is fine.
- Money as $1.5M, $472K or $2,841. Percents with %. Durations as "12 weeks".
- Month names and dates such as February 2 are fine. Years such as 2025 are fine.
- If a sentence needs a number that is not in the pack, rewrite the sentence without it.

Form. Executive style: the CFO reads the headline and the first lines and should be able to decide.
- First line: a # headline that states the ask in plain words, with at most {HEADLINE_MAX_NUMBERS} numbers.
- Then these sections as ## headings, in this order, with these exact names: {", ".join(SECTIONS)}.
- Tell it as a story: the problem, what we found, the ask, what it's worth, how we'll know.
- Put this chart line, exactly as written, on its own line at the end of "What we found": {CHART_LINE}
- Above the appendix: point estimates only. No ranges at all and no "90% range" wording. Every range goes in the appendix, next to its point estimate.
- Above the appendix: {BODY_WORDS[0]} to {BODY_WORDS[1]} words and at most {BODY_MAX_NUMBERS} numbers. Fewer numbers is better. Short paragraphs; a few bullets are fine. No tables.
- The appendix: short bullets, each an estimate with its 90% range, at most {APPENDIX_MAX_WORDS} words. Say once that every range is a 90% range.

Content.
- The problem: deals fell in 2025 while spend rose, and the team cannot say which channels work.
- What we found: the model's view of where the next dollar works, and the plan it suggests. Say plainly what it cannot see, using the pack's risks.
- The ask: follow the pack's recommendation. Approve the market test now; decide the rollout after the readout. Say what the test does in plain words and what it costs net.
- What it's worth: what the plan adds if the model is right, and why testing first protects the budget.
- How we'll know: the rules written down before the test, when the readout comes, and the test's limits, including how likely it is to see each effect.
- No claims the pack does not support. Do not mention how the pack was built.

Style.
- CFO voice: direct, plain words, short sentences. No marketing jargon. Say "cost per deal" for CPA, "cost per extra deal" for marginal CPA, "always-on" for channels that never pause.
- No em dashes or en dashes anywhere. Use commas, periods, colons or parentheses.
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


def _sections(text: str) -> dict[str, tuple[int, int]]:
    """Heading -> (first line, last line), 1-based, for each ## section."""
    lines = text.splitlines()
    heads = [(i + 1, ln[3:].strip()) for i, ln in enumerate(lines) if ln.startswith("## ")]
    out = {}
    for k, (n, name) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        out[name] = (n, end)
    return out


def style_problems(text: str) -> list[dict]:
    """The form the prompt asks for, as far as a script can see it."""
    lines = text.splitlines()
    out = [{"line": i, "text": "em or en dash"} for i, ln in enumerate(lines, 1) if "—" in ln or "–" in ln]
    secs = _sections(text)
    if list(secs) != SECTIONS:
        out.append({"line": 0, "text": f"sections must be exactly {SECTIONS}, got {list(secs)}"})
        return out
    if not lines or not lines[0].startswith("# "):
        out.append({"line": 1, "text": "the first line must be the # headline"})
    items, _ = G.extract(text)
    head_n = sum(1 for it in items if it["line"] == 1)
    if head_n > HEADLINE_MAX_NUMBERS:
        out.append({"line": 1, "text": f"headline has {head_n} numbers; at most {HEADLINE_MAX_NUMBERS}"})
    app = secs[SECTIONS[-1]][0]
    for it in items:
        if it["kind"] == "range" and it["line"] < app:
            out.append({"line": it["line"], "text": f"range {it['text']!r} above the appendix; move it there"})
    for i, ln in enumerate(lines[:app - 1], 1):
        if "90% range" in ln.lower() or "90 percent range" in ln.lower():
            if not ln.strip().startswith("!["):
                out.append({"line": i, "text": "range wording above the appendix"})
    charts = [i for i, ln in enumerate(lines, 1) if ln.strip().startswith("![")]
    found = secs["What we found"]
    if len(charts) != 1 or lines[charts[0] - 1].strip() != CHART_LINE or not found[0] < charts[0] <= found[1]:
        out.append({"line": 0, "text": f"exactly one chart line, as given, at the end of What we found: {CHART_LINE}"})
    body = "\n".join(ln for ln in lines[:app - 1] if not ln.strip().startswith("!["))
    words, n_body = len(body.split()), sum(1 for it in items if it["line"] < app)
    if not BODY_WORDS[0] <= words <= BODY_WORDS[1]:
        out.append({"line": 0, "text": f"{words} words above the appendix; aim for {BODY_WORDS[0]} to {BODY_WORDS[1]}"})
    if n_body > BODY_MAX_NUMBERS:
        out.append({"line": 0, "text": f"{n_body} numbers above the appendix; at most {BODY_MAX_NUMBERS}"})
    app_words = len(" ".join(lines[app:]).split())
    if app_words > APPENDIX_MAX_WORDS:
        out.append({"line": app, "text": f"appendix has {app_words} words; at most {APPENDIX_MAX_WORDS}"})
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
    chart.draw(pack)
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
    return 0 if result["pass"] and not style else 1


if __name__ == "__main__":
    raise SystemExit(main())
