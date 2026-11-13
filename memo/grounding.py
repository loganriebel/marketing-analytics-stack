"""Grounding check: every number in the memo must match a fact in the facts pack.

    python -m memo.grounding        # checks memo/outputs/proposal_memo.md

Writes memo/outputs/grounding.json and exits 1 unless every number matches.

What counts as a number:
  dollars ($2,841, $1.5M, $473K, 2 million dollars), percents (5.4%, 30 percent,
  2 percentage points), multipliers (1.5x), counts (166 deals, 4 markets),
  durations (8 weeks, an 8-week test, 12 months), ranges (10 to 334, $29K to
  $948K, 6-8 weeks, between 6 and 8), and number words (two to ninety, hundred,
  thousand, million, billion, dozen, zero, half, double, twice, triple).

What is exempt:
  years (a bare 1990 to 2099 with no comma, $, % or scale), ISO dates
  (2025-12-22), month-day dates (June 1), section and list numbering at the
  start of a line (1. or 2) ), digits glued to letters (Q1, B2B, FY26), ordinals
  (3rd), and the word "one".

Units must agree:
  $ or "dollars" matches only USD facts; % or "percent" only percent facts; x
  only multipliers. A count or duration takes the unit of the next word (deals,
  markets, channels, weeks, months, years), skipping filler like "more" or
  "extra". A bare number with no unit word may match any fact that is not USD or
  percent, so the check cannot tell what a bare number means, only that it exists.

Rounding:
  A number matches a fact when the fact, rounded to the digits the memo shows,
  equals it, and the memo keeps at least two significant figures. So 166.3 deals
  may be 166 or 170 deals, $1,491,623 may be $1.5M or $1.49M but not $1M, and
  8 weeks must be a fact between 7.95 and 8.05. Trailing zeros in a whole number
  are not significant ($500K means 495K to 505K). Signs are ignored: the words
  carry the direction ("cut $540K" matches a -540,098 fact).

Ranges:
  A range must match one fact's own low and high (its 90% range), in either
  order. Two ends taken from different facts fail. A single number may match a
  fact's value, low or high.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "memo" / "outputs"
MEMO_PATH = OUT_DIR / "proposal_memo.md"
FACTS_PATH = OUT_DIR / "facts.json"
GROUNDING_PATH = OUT_DIR / "grounding.json"

SCALES = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}
NUMBER = re.compile(r"""
    (?<![\w.,$])
    (?P<dollar>\$)?
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)
    (?:\s?(?P<scale>[KMB]|thousand|million|billion)(?![A-Za-z]))?
    (?:\s?(?P<pct>%|percent(?!age)|percentage\s+points?))?
    (?P<x>[x\u00d7](?![A-Za-z]))?
    (?![A-Za-z\d])
""", re.X | re.I)
WORDS = {w: i for i, w in enumerate(
    "zero _ two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split()) if w != "_"}
TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split(), 0)
        if w != "_"}
ONES = {**{w: v for w, v in WORDS.items() if 0 < v < 10}, "one": 1}
BIG = {"hundred": 100, "thousand": 1e3, "million": 1e6, "billion": 1e9, "dozen": 12}
LOOSE = {"half": 0.5, "double": 2, "twice": 2, "triple": 3}
NUMBER_WORD = re.compile(
    r"\b(?:(?P<tens>" + "|".join(TENS) + r")(?:-(?P<unit>" + "|".join(ONES) + r"))?"
    r"|(?P<word>" + "|".join(list(WORDS) + list(BIG) + list(LOOSE)) + r"))\b", re.I)
UNIT_WORDS = {"deal": "deals", "deals": "deals", "market": "markets", "markets": "markets",
              "week": "weeks", "weeks": "weeks", "month": "months", "months": "months",
              "year": "years", "years": "years", "channel": "channels", "channels": "channels",
              "dollar": "USD", "dollars": "USD"}
FILLER = {"more", "extra", "new", "added", "additional", "fewer", "incremental", "test", "control", "matched",
          "paid", "won", "closed", "other", "average", "full", "held-out", "hidden", "lost"}
RANGE_GAP = re.compile(r"^\s*(?:to|through|-|\u2013)\s*$", re.I)
BETWEEN_GAP = re.compile(r"^\s+and\s+$", re.I)
MONTHS = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
EXEMPT = [
    ("iso_date", re.compile(r"\b\d{4}-\d{2}-\d{2}\b")),
    ("date", re.compile(r"\b" + MONTHS + r"\.?\s+\d{1,2}(?:st|nd|rd|th)?\b")),
    ("numbering", re.compile(r"^[ \t>]*(?:#+[ \t]*)?\d+[.)](?=\s)", re.M)),
]
SYMBOL_UNIT = {"dollar": "USD", "pct": "percent", "x": "multiplier"}
OPEN_UNITS = {"USD", "percent"}  # a bare number never matches these


def _sig_digits(num: str) -> int:
    s = num.replace(",", "")
    if "." in s:
        return max(len(s.replace(".", "").lstrip("0")), 1)
    return max(len(s.lstrip("0").rstrip("0")), 1)


def _precision(value: float, digits: int) -> float:
    """Place value of the last digit that must agree: what the memo shows, and never
    coarser than two significant figures."""
    if value == 0:
        return 1.0
    return 10 ** (math.floor(math.log10(abs(value))) - max(digits, 2) + 1)


def _close(fact: float | None, value: float, precision: float) -> bool:
    if fact is None:
        return False
    return abs(abs(fact) - abs(value)) <= precision / 2 * (1 + 1e-9) + 1e-12


def _unit_after(text: str, end: int) -> str | None:
    rest = text[end:end + 60]
    m = re.match(r"-(week|month|year|market|deal)s?\b", rest, re.I)
    if m:
        return UNIT_WORDS[m.group(1).lower()]
    for w in re.findall(r"[A-Za-z][A-Za-z-]*", rest)[:3]:
        w = w.lower()
        if w in UNIT_WORDS:
            return UNIT_WORDS[w]
        if w not in FILLER:
            return None
    return None


def _mask(text: str) -> tuple[str, list[dict]]:
    exempt = []
    chars = list(text)
    for kind, rx in EXEMPT:
        for m in rx.finditer(text):
            exempt.append({"text": m.group(0).strip(), "line": text.count("\n", 0, m.start()) + 1, "why": kind})
            for i in range(m.start(), m.end()):
                if chars[i] != "\n":
                    chars[i] = " "
    return "".join(chars), exempt


def extract(text: str) -> tuple[list[dict], list[dict]]:
    """Every number in the memo as checkable items (scalars and ranges), plus exempt ones."""
    masked, exempt = _mask(text)
    toks = []
    for m in NUMBER.finditer(masked):
        num = m.group("num")
        scale = SCALES[m.group("scale").lower()] if m.group("scale") else 1.0
        unit = next((u for g, u in SYMBOL_UNIT.items() if m.group(g)), None)
        if unit is None and m.group("scale") is None and "," not in num and "." not in num \
                and len(num) == 4 and 1990 <= int(num) <= 2099:
            exempt.append({"text": num, "line": masked.count("\n", 0, m.start()) + 1, "why": "year"})
            continue
        toks.append({"start": m.start(), "end": m.end(), "text": m.group(0).strip(), "num": num,
                     "value": float(num.replace(",", "")) * scale, "scale": scale, "unit": unit,
                     "digits": _sig_digits(num), "has_scale": m.group("scale") is not None})
    spans = [(t["start"], t["end"]) for t in toks]
    for m in NUMBER_WORD.finditer(masked):
        if any(a <= m.start() < b for a, b in spans):
            continue
        if m.group("tens"):
            v = TENS[m.group("tens").lower()] + (ONES[m.group("unit").lower()] if m.group("unit") else 0)
        else:
            w = m.group("word").lower()
            v = WORDS.get(w, BIG.get(w, LOOSE.get(w)))
        toks.append({"start": m.start(), "end": m.end(), "text": m.group(0), "num": m.group(0), "value": float(v),
                     "scale": 1.0, "unit": None, "digits": len(str(int(v)).rstrip("0")) or 1,
                     "has_scale": False, "word": True})
    toks.sort(key=lambda t: t["start"])
    for t in toks:
        if t["unit"] is None:
            t["unit"] = _unit_after(masked, t["end"])

    items, i = [], 0
    while i < len(toks):
        a = toks[i]
        b = toks[i + 1] if i + 1 < len(toks) else None
        if b is not None and not a.get("word") and not b.get("word"):
            gap = masked[a["end"]:b["start"]]
            between = BETWEEN_GAP.match(gap) and re.search(r"between\s*$", masked[max(0, a["start"] - 12):a["start"]], re.I)
            units = {a["unit"], b["unit"]} - {None}
            if (RANGE_GAP.match(gap) or between) and len(units) <= 1:
                unit = units.pop() if units else None
                # "$1.2 to $1.5 million": the scale on the high end covers the low end too
                if not a["has_scale"] and b["has_scale"] and a["value"] < b["value"] / b["scale"]:
                    a = {**a, "value": a["value"] * b["scale"], "scale": b["scale"]}
                items.append(_item("range", text[a["start"]:b["end"]], masked, a["start"], unit, [a, b]))
                i += 2
                continue
        items.append(_item("number", a["text"], masked, a["start"], a["unit"], [a]))
        i += 1
    return items, exempt


def _item(kind, text, masked, start, unit, ends):
    a = masked.rfind("\n", 0, start) + 1
    b = masked.find("\n", start)
    lo = max(a, start - 50)
    return {"kind": kind, "text": text.strip(), "line": masked.count("\n", 0, start) + 1, "unit": unit,
            "context": " ".join(masked[lo:min(b if b >= 0 else len(masked), lo + 110)].split()),
            "values": [e["value"] for e in ends],
            "precisions": [_precision(e["value"], e["digits"]) for e in ends]}


def _candidates(facts: list[dict], unit: str | None) -> list[dict]:
    if unit is None:
        return [f for f in facts if f["unit"] not in OPEN_UNITS]
    return [f for f in facts if f["unit"] == unit]


def match(item: dict, facts: list[dict]) -> list[str]:
    cands = _candidates(facts, item["unit"])
    if item["kind"] == "range":
        (lo, hi), (plo, phi) = item["values"], item["precisions"]
        return [f["id"] for f in cands
                if (_close(f.get("low"), lo, plo) and _close(f.get("high"), hi, phi))
                or (_close(f.get("low"), hi, phi) and _close(f.get("high"), lo, plo))]
    v, pv = item["values"][0], item["precisions"][0]
    return [f["id"] for f in cands if any(_close(f.get(k), v, pv) for k in ("value", "low", "high"))]


def check(memo_text: str, pack: dict) -> dict:
    facts = pack["facts"]
    items, exempt = extract(memo_text)
    for it in items:
        it["matched"] = match(it, facts)
        it["ok"] = bool(it["matched"])
    ok = sum(it["ok"] for it in items)
    return {
        "checked": len(items),
        "matched": ok,
        "score": ok / len(items) if items else 1.0,
        "pass": ok == len(items),
        "unmatched": [{k: it[k] for k in ("text", "line", "unit", "context")} for it in items if not it["ok"]],
        "numbers": items,
        "exempt": sorted(exempt, key=lambda e: e["line"]),
    }


def run(memo: Path = MEMO_PATH, facts: Path = FACTS_PATH, out: Path | None = GROUNDING_PATH) -> dict:
    pack = json.loads(facts.read_text(encoding="utf-8"))
    result = {"memo": _rel(memo), "facts": _rel(facts), **check(memo.read_text(encoding="utf-8"), pack)}
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    return result


def _rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def summary(result: dict) -> str:
    lines = [f"grounding: {result['matched']} of {result['checked']} numbers match a fact "
             f"({100 * result['score']:.0f}%), {len(result['exempt'])} exempt: {'PASS' if result['pass'] else 'FAIL'}"]
    for u in result["unmatched"]:
        lines.append(f"  line {u['line']}: {u['text']!r} ({u['unit'] or 'no unit'}) matches no fact, in: "
                     f"{u['context']}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--memo", type=Path, default=MEMO_PATH)
    ap.add_argument("--facts", type=Path, default=FACTS_PATH)
    ap.add_argument("--out", type=Path, default=GROUNDING_PATH)
    args = ap.parse_args(argv)
    result = run(args.memo, args.facts, args.out)
    print(summary(result))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
