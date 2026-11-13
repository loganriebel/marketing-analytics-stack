"""Plan files that drive 2026 spend.

A plan is a decision, not an outcome: it says what to buy, where and when. The sim
buys it with each channel's usual habits and the true world decides what happens.

    name: 2026 market test
    approved: 2026-01-26
    budget: hold_2025_exit        # first plan only: the 2026 budget basis
    test:                         # optional: market test arms
      id: MT2026
      start: 2026-02-02           # Monday of the first test week
      end: 2026-04-20             # Monday of the last test week
      arms:
        - id: youtube_up
          markets: [CHI, MSP]
          moves:
            youtube: {add_per_week_per_size: 3000}
        - id: cuts_dark
          markets: [CLE, CMH]
          moves:
            linkedin: {multiplier: 0.0}
    national:                     # optional: moves in every market
      start: 2026-06-01
      end: 2026-12-28
      moves:
        youtube: {multiplier: 1.5}

Moves apply to the weeks whose Monday falls between start and end. A multiplier
scales the planned spend; add_per_week_per_size adds dollars per week per unit of
market size (target accounts over the market average), so a market twice the
average size gets twice the dollars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from . import config as C

BUDGET_BASES = ("hold_2025_exit",)
MOVE_KEYS = ("multiplier", "add_per_week_per_size")


@dataclass
class Move:
    channel: str
    multiplier: float | None = None
    add_per_week_per_size: float | None = None


@dataclass
class Arm:
    id: str
    markets: list[str]
    moves: list[Move]


@dataclass
class Test:
    id: str
    start: date
    end: date
    arms: list[Arm]


@dataclass
class National:
    start: date
    end: date
    moves: list[Move]


@dataclass
class Plan:
    name: str
    approved: date
    path: str
    budget: str | None = None
    test: Test | None = None
    national: National | None = None
    raw: dict = field(default_factory=dict)


def _date(v) -> date:
    return v if isinstance(v, date) else date.fromisoformat(str(v))


def _monday(d: date, what: str) -> date:
    if d.weekday() != 0:
        raise ValueError(f"{what} must be a Monday, got {d}")
    return d


def _moves(raw: dict, where: str) -> list[Move]:
    out = []
    for ch, mv in (raw or {}).items():
        if ch not in C.PLANNED_CHANNELS:
            raise ValueError(f"{where}: {ch} is not a planned channel ({C.PLANNED_CHANNELS})")
        keys = [k for k in MOVE_KEYS if k in mv]
        if len(keys) != 1 or set(mv) - set(MOVE_KEYS):
            raise ValueError(f"{where}: {ch} needs exactly one of {MOVE_KEYS}, got {mv}")
        val = float(mv[keys[0]])
        if val < 0:
            raise ValueError(f"{where}: {ch} {keys[0]} must be >= 0")
        out.append(Move(ch, **{keys[0]: val}))
    return out


def load(path: Path) -> Plan:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    codes = {r[0] for r in C.REGIONS}
    budget = raw.get("budget")
    if budget is not None and budget not in BUDGET_BASES:
        raise ValueError(f"{path}: budget must be one of {BUDGET_BASES}")
    test = None
    if raw.get("test"):
        t = raw["test"]
        arms = []
        seen: set[tuple[str, str]] = set()
        for a in t["arms"]:
            bad = set(a["markets"]) - codes
            if bad:
                raise ValueError(f"{path}: unknown markets {sorted(bad)}")
            moves = _moves(a["moves"], f"{path} arm {a['id']}")
            for mv in moves:
                for m in a["markets"]:
                    if (mv.channel, m) in seen:
                        raise ValueError(f"{path}: {mv.channel} moves twice in {m}")
                    seen.add((mv.channel, m))
                if mv.channel == "ctv" and mv.add_per_week_per_size and set(a["markets"]) - set(C.CTV_REGIONS):
                    raise ValueError(f"{path}: CTV can only be bought in {C.CTV_REGIONS}")
            arms.append(Arm(a["id"], list(a["markets"]), moves))
        test = Test(t["id"], _monday(_date(t["start"]), "test start"), _monday(_date(t["end"]), "test end"), arms)
    national = None
    if raw.get("national"):
        n = raw["national"]
        national = National(_monday(_date(n["start"]), "national start"), _monday(_date(n["end"]), "national end"),
                            _moves(n["moves"], f"{path} national"))
    return Plan(raw["name"], _date(raw["approved"]), Path(path).as_posix(), budget, test, national, raw)


def load_all(paths) -> list[Plan]:
    plans = [load(p) for p in paths]
    if plans and plans[0].budget is None:
        plans[0].budget = BUDGET_BASES[0]
    if any(p.budget for p in plans[1:]):
        raise ValueError("only the first plan sets the budget basis")
    return plans
