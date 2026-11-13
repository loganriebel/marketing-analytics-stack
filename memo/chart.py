"""The proposal memo's one chart, drawn from the facts pack and nothing else.

    python -m memo.chart

Cost per extra deal from the next dollar, by channel, with the MMM's 90% range.
The channel the test grows and the channels it cuts carry color; the rest are gray.
Every plotted number is a fact in memo/outputs/facts.json, so the chart cannot show
a number the memo's grounding check would reject.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FixedLocator, NullLocator  # noqa: E402

from . import facts as F  # noqa: E402

CHART_PATH = F.OUT_DIR / "proposal_chart.png"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
GROW, CUT, OTHER = "#2a78d6", "#eb6834", "#a3a29c"   # validated pair (dataviz palette slots 1 and 2)


def draw(pack: dict | None = None, path=CHART_PATH) -> dict:
    pack = pack or json.loads(F.FACTS_PATH.read_text(encoding="utf-8"))
    facts = {f["id"]: f for f in pack["facts"]}
    names = pack["channel_names"]
    grow = pack["channels"]["grow"][0]
    cuts = set(pack["channels"]["cut"])
    rows = sorted(names, key=lambda c: facts[f"{c}_mcpa"]["value"])
    plotted = []

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
    fig, ax = plt.subplots(figsize=(6.4, 3.3), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for i, c in enumerate(rows):
        f = facts[f"{c}_mcpa"]
        color = GROW if c == grow else CUT if c in cuts else OTHER
        y = len(rows) - 1 - i
        ax.plot([f["low"], f["high"]], [y, y], color=color, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([f["value"]], [y], s=42, color=color, edgecolor=SURFACE, linewidth=2, zorder=3)
        plotted.append({"channel": c, "fact": f"{c}_mcpa", "value": f["value"], "low": f["low"], "high": f["high"]})
        if c == grow or c in cuts:
            ax.annotate(f"${f['value'] / 1000:,.1f}K", (f["value"], y), xytext=(0, 7), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.5, color=INK_2)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([names[c][0].upper() + names[c][1:] for c in reversed(rows)], color=INK)
    ax.set_xscale("log")
    ticks = [1_000, 3_000, 10_000, 30_000, 100_000]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xticklabels([f"${t // 1000:,}K" for t in ticks], color=INK_2)
    ax.set_xlim(900, 200_000)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.grid(axis="x", color=GRID, lw=0.8, zorder=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="both", length=0, pad=6)
    ax.set_xlabel("Cost per extra deal from the next dollar (dot: model's estimate; line: its 90% range)",
                  color=INK_2, fontsize=8)
    cut = sorted(cuts)[0]
    pricier = facts[f"{cut}_mcpa"]["value"] >= 2 * facts[f"{grow}_mcpa"]["value"]
    title = (f"{names[grow][0].upper() + names[grow][1:]}'s next dollar looks cheapest"
             + (f"; {names[cut]}'s costs far more" if pricier else ""))
    fig.suptitle(title,
                 x=0.02, y=0.985, ha="left", fontsize=10.5, color=INK, fontweight="bold")
    handles = [plt.Line2D([], [], color=GROW, marker="o", lw=2, label="Test grows it"),
               plt.Line2D([], [], color=CUT, marker="o", lw=2, label="Test pulls it back"),
               plt.Line2D([], [], color=OTHER, marker="o", lw=2, label="Not in the test")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.01, 0.93), ncol=3, frameon=False,
               fontsize=7.5, labelcolor=INK_2, handlelength=1.6, columnspacing=1.4)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(path, facecolor=SURFACE, metadata={"Software": None})
    plt.close(fig)
    return {"path": str(path), "plotted": plotted}


def main() -> int:
    out = draw()
    print(f"wrote {CHART_PATH.relative_to(F.REPO).as_posix()}: {len(out['plotted'])} channels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
