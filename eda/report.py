"""EDA and data validation on the golden tables, written to docs/eda/.

Reads only the dbt warehouse (data/warehouse.duckdb): marts plus a few staging
views. It never imports the simulator or opens its answer key, so everything here
is what an analyst at Fernhook could see before building an MMM.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
DB_PATH = REPO / "data" / "warehouse.duckdb"
OUT_DIR = REPO / "docs" / "eda"
IMG_DIR = OUT_DIR / "img"

# Reference palette (light mode). Three categorical slots validated all-pairs.
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, BAND = "#e1e0d9", "#c3c2b7", "#f0efec"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
SEQ = LinearSegmentedColormap.from_list(
    "seq_blue", ["#fcfcfb", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.sans-serif": ["Segoe UI", "DejaVu Sans", "Arial"],
    "font.size": 9.5, "text.color": INK, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "axes.grid.axis": "y",
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 10.5, "axes.titleweight": "semibold", "axes.titlelocation": "left",
    "lines.linewidth": 1.5, "legend.frameon": False,
})


def _q(con, sql: str) -> pd.DataFrame:
    return con.sql(sql).df()


def _save(fig, name: str) -> str:
    fig.savefig(IMG_DIR / name, dpi=150, bbox_inches="tight", metadata={"Software": None})
    plt.close(fig)
    return f"img/{name}"


def _money(x: float) -> str:
    return f"${x / 1e6:.1f}M" if abs(x) >= 1e5 else f"${x:,.0f}"


def _weeks(n: float) -> str:
    n = int(round(n))
    return f"{n} week" if n == 1 else f"{n} weeks"


def _runs(on: np.ndarray) -> tuple[list[int], list[int]]:
    """Lengths of consecutive on-runs and the off-gaps between them."""
    on_runs, off_runs, n, cur = [], [], 0, None
    for v in on:
        if v == cur:
            n += 1
        else:
            if cur is not None:
                (on_runs if cur else off_runs).append(n)
            cur, n = v, 1
    (on_runs if cur else off_runs).append(n)
    if len(on) and not on[0] and off_runs:
        off_runs = off_runs[1:]  # leading off-stretch is not a gap between flights
    if len(on) and not on[-1] and off_runs:
        off_runs = off_runs[:-1]
    return on_runs, off_runs


def _table(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in cols) + " |")
    return "\n".join(lines)


# --- data ------------------------------------------------------------------

def load(con) -> dict[str, pd.DataFrame]:
    d = {}
    d["channels"] = _q(con, "select * from dim_channel order by sort_order")
    d["regions"] = _q(con, "select region_id, target_accounts from stg_regions")
    d["spend"] = _q(con, """
        select week_start, channel_id, sum(spend)::double as spend,
               count(*) filter (where spend > 0) as regions_on
        from fct_channel_weekly group by 1, 2 order by 1, 2""")
    d["region_spend"] = _q(con, """
        select week_start, region_id, channel_id, spend::double as spend
        from fct_channel_weekly order by 1, 2, 3""")
    d["outcome"] = _q(con, """
        select week_start, sum(leads) as leads, sum(won_deals) as deals, sum(won_revenue)::double as revenue
        from fct_funnel group by 1 order by 1""")
    d["by_channel"] = _q(con, """
        select channel_id, year(week_start) as yr, sum(spend)::double as spend,
               sum(platform_conversions) as claims, sum(sourced_leads) as crm_leads
        from fct_channel_weekly group by 1, 2 order by 1, 2""")
    d["controls"] = _q(con, """
        select week_start, sum(sdr_headcount) as sdrs, sum(ae_headcount) as aes,
               sum(emails_sent) as emails, bool_or(is_discount_promo) as promo,
               max(list_price_index) as price_index, avg(fleet_activity_index) as fleet_index
        from fct_controls_weekly group by 1 order by 1""")
    d["plan_changes"] = _q(con, """
        select change_date, channel_id, budget_change_pct, reason
        from stg_media_plan_changes order by change_date, channel_id""")
    for k in ("spend", "region_spend", "outcome", "controls"):
        d[k]["week_start"] = pd.to_datetime(d[k]["week_start"])
    d["plan_changes"]["change_date"] = pd.to_datetime(d["plan_changes"]["change_date"])
    return d


def validate(con) -> list[tuple[str, str, bool]]:
    checks = []
    weeks, regions = _q(con, "select count(*) w, min(week_start) a, max(week_start) b from int_week_spine"), \
        int(_q(con, "select count(*) n from stg_regions").n[0])
    n_w = int(weeks.w[0])
    checks.append(("Reporting window", f"{n_w} weeks, {weeks.a[0]:%Y-%m-%d} to {weeks.b[0]:%Y-%m-%d}, {regions} regions", n_w == 156))

    paid = int(_q(con, "select count(*) n from dim_channel where is_paid").n[0])
    alls = int(_q(con, "select count(*) n from dim_channel").n[0])
    for model, expect in (("fct_channel_weekly", n_w * regions * paid), ("fct_funnel", n_w * regions * alls),
                          ("fct_controls_weekly", n_w * regions)):
        n = int(_q(con, f"select count(*) n from {model}").n[0])
        checks.append((f"{model} is a full grid", f"{n:,} rows (expected {expect:,})", n == expect))

    rec = _q(con, """
        with m as (select channel_id, sum(spend) s from fct_channel_weekly group by 1),
             p as (select channel_id, sum(spend) s from int_paid_media_weekly group by 1)
        select sum(abs(m.s - p.s))::double as diff, sum(p.s)::double as total from m join p using (channel_id)""")
    checks.append(("Spend matches the platform exports", f"{_money(rec.total[0])} in both; difference ${rec['diff'][0]:,.2f}",
                   rec["diff"][0] == 0))

    bad = int(_q(con, """select count(*) n from fct_channel_weekly
                         where spend < 0 or platform_conversions < 0 or sourced_leads < 0 or impressions < clicks""").n[0])
    checks.append(("No negative values; clicks never exceed impressions", f"{bad} bad rows", bad == 0))

    utm = _q(con, """select count(*) filter (where channel_id is null) unmapped,
                            count(*) filter (where channel_id = 'direct') direct, count(*) n from stg_crm_leads""")
    checks.append(("Every lead maps to a channel", f"{int(utm.unmapped[0])} unmapped of {int(utm.n[0]):,}; "
                   f"{utm.direct[0] / utm.n[0]:.0%} recorded as direct", utm.unmapped[0] == 0))

    lag = _q(con, """select quantile_cont(o.close_date - l.created_date, [0.1, 0.5, 0.9]) q
                     from stg_crm_opportunities o join stg_crm_leads l using (lead_id) where o.is_won""").q[0]
    checks.append(("Lead to close (won deals)", f"median {lag[1]:.0f} days; 80% between {lag[0]:.0f} and {lag[2]:.0f}",
                   lag[1] <= 30))

    open_late = _q(con, """select avg(case when not is_closed then 1 else 0 end) r from stg_crm_opportunities
                           where created_date >= (select max(week_start) - 21 from int_week_spine)""").r[0]
    checks.append(("Censoring at the end of the window", f"{open_late:.0%} of opportunities from the last 4 weeks are still open; "
                   "treat the final weeks of deals as incomplete", None))

    tests = _q(con, "select count(*) n from stg_promo_calendar").n[0]
    checks.append(("Promo and price calendar loaded", f"{int(tests)} entries", tests > 0))
    return checks


# --- charts ----------------------------------------------------------------

def chart_flighting(d) -> str:
    ch = d["channels"].query("is_paid")
    piv = d["spend"].pivot(index="channel_id", columns="week_start", values="regions_on").reindex(ch.channel_id) / 20
    fig, ax = plt.subplots(figsize=(10, 3.6))
    im = ax.imshow(piv.to_numpy(), aspect="auto", cmap=SEQ, vmin=0, vmax=1, interpolation="nearest")
    ax.set_yticks(range(len(ch)), ch.channel_name)
    xt = [i for i, w in enumerate(piv.columns) if w.month in (1, 4, 7, 10) and w.day <= 7]
    ax.set_xticks(xt, [f"{piv.columns[i]:%b %Y}" for i in xt], fontsize=8)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.outline.set_visible(False)
    cb.ax.tick_params(length=0, labelsize=8)
    cb.set_label("Share of 20 regions with spend", color=INK2, fontsize=8.5)
    ax.set_title("When each channel was on: share of regions with spend, by week")
    return _save(fig, "flighting_calendar.png")


def chart_spend_small_multiples(d) -> str:
    ch = d["channels"].query("is_paid").reset_index(drop=True)
    piv = d["spend"].pivot(index="week_start", columns="channel_id", values="spend")
    fig, axes = plt.subplots(3, 3, figsize=(11, 7), sharex=True)
    for ax, (_, row) in zip(axes.ravel(), ch.iterrows()):
        s = piv[row.channel_id] / 1000
        ax.plot(s.index, s.to_numpy(), color=S1, linewidth=1.2)
        for dt in d["plan_changes"].query("channel_id == @row.channel_id").change_date:
            ax.axvline(dt, color=MUTED, linewidth=0.8)
        ax.set_title(row.channel_name, fontsize=9.5)
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(lambda v, _: f"${v:,.0f}k")
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.suptitle("Weekly national spend by channel ($ thousands). Gray lines mark plan changes. Each panel has its own scale.",
                 x=0.01, ha="left", fontsize=10.5, fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return _save(fig, "spend_by_channel.png")


def seasonal_index(d) -> pd.DataFrame:
    o = d["outcome"].copy()
    o["yr"] = o.week_start.dt.isocalendar().year.astype(int)
    o["woy"] = o.week_start.dt.isocalendar().week.astype(int)
    o = o[o.woy <= 52]
    for col in ("deals", "leads"):
        o[f"{col}_idx"] = 100 * o[col] / o.groupby("yr")[col].transform("mean")
    last = o.week_start.max()
    o = o[o.week_start < last - pd.Timedelta(weeks=3)]  # drop censored final weeks
    return o.groupby("woy")[["deals_idx", "leads_idx"]].mean()


def chart_seasonality(si: pd.DataFrame) -> str:
    fig, ax = plt.subplots(figsize=(10, 3.6))
    for lo, hi, label in ((19, 25, "Spring switchover"), (29, 37, "Summer lull"), (40, 45, "Fall switchover")):
        ax.axvspan(lo, hi, color=BAND, linewidth=0)
        ax.text((lo + hi) / 2, 47, label, ha="center", color=INK2, fontsize=8.5)
    ax.axhline(100, color=AXIS, linewidth=0.8)
    ax.plot(si.index, si.leads_idx, color=S1, label="Leads")
    ax.plot(si.index, si.deals_idx, color=S2, label="Closed-won deals")
    ax.text(52.6, si.leads_idx.iloc[-1], "Leads", color=INK2, va="center", fontsize=8.5)
    ax.text(52.6, si.deals_idx.iloc[-1] - 4, "Deals", color=INK2, va="center", fontsize=8.5)
    ax.set_xlim(1, 55)
    ax.set_ylim(45, 130)
    ax.set_xlabel("ISO week of year")
    ax.legend(loc="lower left", ncol=2, fontsize=8.5)
    ax.set_title("Seasonality: each week as an index of its year's average (100 = average week), 2023 to 2025")
    return _save(fig, "seasonality.png")


def chart_spend_and_deals(d) -> str:
    s = d["spend"].groupby("week_start").spend.sum() / 1000
    o = d["outcome"].set_index("week_start").deals
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True)
    for ax, ser, title, fmt in ((a1, s, "Total paid media spend per week ($ thousands)", lambda v, _: f"${v:,.0f}k"),
                                (a2, o, "Closed-won deals per week", lambda v, _: f"{v:,.0f}")):
        ax.plot(ser.index, ser.to_numpy(), color=AXIS, linewidth=1.0, label="Weekly")
        ax.plot(ser.index, ser.rolling(13, center=True).mean().to_numpy(), color=S1, linewidth=1.8, label="13-week average")
        ax.set_title(title)
        ax.yaxis.set_major_formatter(fmt)
        ax.set_ylim(bottom=0)
    a1.legend(loc="lower right", ncol=2, fontsize=8.5)
    a2.xaxis.set_major_locator(mdates.YearLocator())
    a2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.tight_layout()
    return _save(fig, "spend_and_deals.png")


def chart_mix(mix: pd.DataFrame) -> str:
    roles = [("performance", "Performance", S1), ("brand", "Brand", S2), ("events", "Events", S3)]
    fig, ax = plt.subplots(figsize=(10, 2.4))
    years = list(mix.index)
    left = np.zeros(len(years))
    for key, label, color in roles:
        vals = mix[key].to_numpy()
        ax.barh(range(len(years)), vals, left=left, color=color, edgecolor=SURFACE, linewidth=2, height=0.62, label=label)
        for i, v in enumerate(vals):
            if v >= 0.08:
                ax.text(left[i] + v / 2, i, f"{v:.0%}", ha="center", va="center", fontsize=8.5,
                        color="#ffffff")
        left += vals
    ax.set_yticks(range(len(years)), [str(y) for y in years])
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=8.5)
    ax.set_title("Spend mix by marketing role")
    return _save(fig, "mix_by_year.png")


def chart_claims(claims: pd.DataFrame) -> str:
    c = claims.sort_values("claims")
    y = np.arange(len(c))
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.set_axisbelow(True)
    ax.barh(y + 0.19, c.claims, height=0.36, color=S1, label="Platform-reported conversions")
    ax.barh(y - 0.19, c.crm_leads, height=0.36, color=S2, label="CRM last-touch leads")
    ax.set_yticks(y, c.channel_name)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v / 1000:,.0f}k")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("Two reporting sources, 2023 to 2025: what each platform claims vs what the CRM credits")
    return _save(fig, "claims_vs_crm.png")


def chart_controls(d) -> str:
    c = d["controls"].set_index("week_start")
    panels = [("sdrs", "SDR headcount (all regions)", lambda v, _: f"{v:,.0f}"),
              ("aes", "AE headcount (all regions)", lambda v, _: f"{v:,.0f}"),
              ("emails", "Emails sent per week", lambda v, _: f"{v / 1000:,.0f}k"),
              ("fleet_index", "Fleet activity index", lambda v, _: f"{v:,.0f}")]
    fig, axes = plt.subplots(2, 2, figsize=(10, 5), sharex=True)
    for ax, (col, title, fmt) in zip(axes.ravel(), panels):
        ax.plot(c.index, c[col].to_numpy(), color=S1, linewidth=1.3)
        ax.set_title(title, fontsize=9.5)
        ax.yaxis.set_major_formatter(fmt)
        if col in ("sdrs", "aes"):
            ax.axvspan(pd.Timestamp("2024-07-01"), pd.Timestamp("2025-01-31"), color=BAND, linewidth=0)
            ax.set_ylim(bottom=0)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[0, 0].text(pd.Timestamp("2024-10-15"), 5, "Hiring freeze", ha="center", color=INK2, fontsize=8.5)
    fig.suptitle("Controls over time", x=0.01, ha="left", fontsize=10.5, fontweight="semibold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return _save(fig, "controls.png")


# --- channel stories --------------------------------------------------------

def channel_profiles(d) -> pd.DataFrame:
    rs = d["region_spend"]
    nat = d["spend"]
    rows = []
    for _, ch in d["channels"].query("is_paid").iterrows():
        cid = ch.channel_id
        n = nat[nat.channel_id == cid].sort_values("week_start")
        on_nat = (n.spend > 0).to_numpy()
        r = rs[rs.channel_id == cid].pivot(index="week_start", columns="region_id", values="spend")
        used = [c for c in r.columns if (r[c] > 0).any()]
        on_lengths, off_lengths = [], []
        for c in used:
            a, b = _runs((r[c] > 0).to_numpy())
            on_lengths += a
            off_lengths += b
        on_w = n[n.spend > 0]
        q = n.assign(q=n.week_start.dt.quarter).groupby("q").spend.mean()
        by_region = r.sum().sort_values(ascending=False)
        top5 = list(by_region.index[:5])
        acc = d["regions"].set_index("region_id").target_accounts
        rows.append({
            "channel_id": cid,
            "weeks_on": int(on_nat.sum()),
            "regions_used": len(used),
            "avg_regions_on": float(on_w.regions_on.mean()) if len(on_w) else 0.0,
            "median_on_run": float(np.median(on_lengths)) if on_lengths else 0.0,
            "median_off_gap": float(np.median(off_lengths)) if off_lengths else 0.0,
            "pauses": len(off_lengths),
            "busiest_quarter": int(q.idxmax()),
            "quietest_quarter": int(q.idxmin()),
            "peak_to_median": float(on_w.spend.max() / on_w.spend.median()) if len(on_w) else 0.0,
            "top5_spend_share": float(by_region.iloc[:5].sum() / by_region.sum()),
            "top5_account_share": float(acc[top5].sum() / acc.sum()),
        })
    return pd.DataFrame(rows).set_index("channel_id")


def channel_section(ch, prof, by_year, changes, extra: str) -> str:
    p = prof.loc[ch.channel_id]
    y = by_year[by_year.channel_id == ch.channel_id].set_index("yr")
    spend_line = ", ".join(f"{yr}: {_money(v)}" for yr, v in y.spend.items())
    claims, crm = y.claims.sum(), y.crm_leads.sum()
    lines = [f"### {ch.channel_name}", "",
             f"*{ch.marketing_role.capitalize()} channel.* {ch.buying_model}", ""]
    on = int(p.weeks_on)
    timing = "On every week of the window" if on == 156 else f"On {on} of 156 weeks nationally"
    region_part = (f"used in {int(p.regions_used)} of 20 regions, with about {p.avg_regions_on:.0f} active in a typical on-week")
    if p.pauses == 0:
        rhythm = "Always on in every region it uses."
    elif p.median_on_run >= 26:
        rhythm = (f"Always on within each region, apart from {int(p.pauses)} regional pauses of about "
                  f"{_weeks(p.median_off_gap)}.")
    elif p.median_on_run <= 1:
        rhythm = f"Spend comes in single weeks; a region typically goes {_weeks(p.median_off_gap)} between them."
    else:
        rhythm = (f"Within a region it typically runs {_weeks(p.median_on_run)} on, then pauses for "
                  f"{_weeks(p.median_off_gap)} ({int(p.pauses)} regional pauses in all).")
    lines.append(f"- **When it ran:** {timing}; {region_part}. {rhythm}")
    lines.append(f"- **Spend:** {spend_line}. Highest in Q{int(p.busiest_quarter)}, lowest in Q{int(p.quietest_quarter)}; "
                 f"the biggest week was {p.peak_to_median:.1f} times a typical on-week. The top 5 regions take "
                 f"{p.top5_spend_share:.0%} of its spend and hold {p.top5_account_share:.0%} of target accounts.")
    if len(changes):
        ch_txt = "; ".join(f"{r.change_date:%b %Y} {r.budget_change_pct:+d}% ({r.reason})" for r in changes.itertuples())
        lines.append(f"- **Plan changes:** {ch_txt}.")
    else:
        lines.append("- **Plan changes:** none between annual plans.")
    if claims > 0 or crm > 0:
        ratio = f"{claims / crm:.1f} times" if crm > 0 else "with no CRM credit to compare against"
        cpl = (y.spend / y.crm_leads.replace(0, np.nan)).round(0)
        cpl_txt = ", ".join(f"{yr}: ${v:,.0f}" for yr, v in cpl.dropna().items())
        lines.append(f"- **Reporting:** the platform claims {claims:,.0f} conversions; the CRM credits {crm:,.0f} last-touch leads "
                     f"({ratio}). Last-touch cost per lead: {cpl_txt or 'not defined (no CRM credit)'}.")
    if extra:
        lines.append(f"- **What to watch in the MMM:** {extra}")
    return "\n".join(lines)


def watch_notes(d, prof) -> dict[str, str]:
    nat = d["spend"].pivot(index="week_start", columns="channel_id", values="spend")
    leads = d["outcome"].set_index("week_start").leads
    corr_brand = float(np.corrcoef(nat["paid_search_brand"], leads)[0, 1])
    corr_nb = float(np.corrcoef(nat["paid_search_nonbrand"], leads)[0, 1])
    return {
        "paid_search_brand": f"its weekly spend tracks total leads closely (correlation {corr_brand:.2f}). Spend that follows demand "
                             "can look like it causes demand. The regional pauses are the cleanest evidence of what it adds.",
        "paid_search_nonbrand": f"always on and seasonal (correlation with total leads {corr_nb:.2f}), so most of its signal comes "
                                "from the regional budget tests and pauses, not from week-to-week swings.",
        "meta": "pushes land on the busy seasons, so spend rises when demand does. Each market's push comes on its own "
                "week and at its own size, and that is the contrast to learn from; the June 2025 retest adds a late step up.",
        "linkedin": "always on with no pauses, so its signal comes from quarterly market re-splits and plan changes.",
        "youtube": "flights are national and run ahead of each busy season, so they line up with the run-up in demand; "
                   "long carryover means effects can land in the busy weeks after a flight ends.",
        "ctv": f"runs in only {int(prof.loc['ctv'].regions_used)} regions. The other 12 regions are a natural comparison group, and "
               "each test market times its own flights.",
        "display": "always on and retargets people who already visited, so it overlaps with demand from every other channel.",
        "affiliates": (f"fees change only when each market's contracts renew, so there are few distinct spend levels to "
                       "learn from, and "
                       f"the top 5 regions take {prof.loc['affiliates'].top5_spend_share:.0%} of spend against "
                       f"{prof.loc['affiliates'].top5_account_share:.0%} of accounts."),
        "webinars": "spend lands in one region and one week at a time, a strong natural experiment.",
    }


# --- report -------------------------------------------------------------------

def build(con) -> str:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    d = load(con)
    checks = validate(con)
    chans = d["channels"].query("is_paid")
    names = dict(zip(d["channels"].channel_id, d["channels"].channel_name))

    nat = d["spend"].pivot(index="week_start", columns="channel_id", values="spend")[list(chans.channel_id)]
    corr = nat.corr()
    pairs = [(names[a], names[b], corr.loc[a, b]) for i, a in enumerate(corr.columns) for b in corr.columns[i + 1:]]
    pairs.sort(key=lambda t: -abs(t[2]))
    x = nat.to_numpy()
    vif = {}
    for j, cid in enumerate(nat.columns):
        others = np.column_stack([np.ones(len(x)), np.delete(x, j, axis=1)])
        coef, *_ = np.linalg.lstsq(others, x[:, j], rcond=None)
        resid = x[:, j] - others @ coef
        r2 = 1 - resid.var() / x[:, j].var()
        vif[names[cid]] = 1 / (1 - r2)
    checks.append(("Channels are not collinear", f"largest correlation {abs(pairs[0][2]):.2f} ({pairs[0][0]} and {pairs[0][1]}); "
                   f"largest VIF {max(vif.values()):.1f}", abs(pairs[0][2]) < 0.6 and max(vif.values()) < 5))

    si = seasonal_index(d)
    season = [  # (period, expectation, seen, holds)
        ("Holiday weeks (51, 52, 1)", "well below 100", si.loc[[51, 52, 1], "leads_idx"].mean(), lambda v: v < 90),
        ("Thanksgiving week (47)", "below 100", si.loc[47, "leads_idx"], lambda v: v < 100),
        ("Winter after the holidays (weeks 3 to 9)", "below 100", si.loc[3:9, "leads_idx"].mean(), lambda v: v < 100),
        ("Spring switchover, AC on (weeks 19 to 25)", "above 100", si.loc[19:25, "leads_idx"].mean(), lambda v: v > 102),
        ("Summer lull into early fall (weeks 29 to 37)", "below 100", si.loc[29:37, "leads_idx"].mean(), lambda v: v < 98),
        ("Fall switchover, heat on (weeks 40 to 45)", "above 100", si.loc[40:45, "leads_idx"].mean(), lambda v: v > 102),
    ]
    season_rows = [{"Period": n, "Expected": e, "Leads index (100 = average week)": f"{v:.0f}",
                    "Holds": "Yes" if f(v) else "No"} for n, e, v, f in season]
    misses = [r["Period"].split(" (")[0].lower() for r in season_rows if r["Holds"] == "No"]
    season_note = (f"{len(season_rows) - len(misses)} of {len(season_rows)} expectations hold. "
                   + (f"Not seen: {', '.join(misses)}. The MMM should learn seasonality from the data rather than "
                      "impose the planning calendar." if misses else "The data matches the planning calendar."))
    promo_lift = si.loc[46:50, "deals_idx"].mean() / si.loc[46:50, "leads_idx"].mean()

    by_year = d["by_channel"].copy()
    role = dict(zip(d["channels"].channel_id, d["channels"].marketing_role))
    by_year["role"] = by_year.channel_id.map(role)
    mix = by_year.groupby(["yr", "role"]).spend.sum().unstack().fillna(0)
    mix = mix.div(mix.sum(axis=1), axis=0)

    claims = by_year.groupby("channel_id")[["claims", "crm_leads", "spend"]].sum().reset_index()
    claims["channel_name"] = claims.channel_id.map(names)

    prof = channel_profiles(d)
    notes = watch_notes(d, prof)
    img = {
        "flight": chart_flighting(d), "spend": chart_spend_small_multiples(d), "season": chart_seasonality(si),
        "trend": chart_spend_and_deals(d), "mix": chart_mix(mix), "claims": chart_claims(claims),
        "controls": chart_controls(d),
    }

    yearly = d["outcome"].assign(yr=d["outcome"].week_start.dt.year).groupby("yr")[["leads", "deals", "revenue"]].sum()
    yearly["spend"] = d["spend"].assign(yr=d["spend"].week_start.dt.year).groupby("yr").spend.sum()
    yearly["cost_per_deal"] = yearly.spend / yearly.deals

    ok = sum(bool(c[2]) for c in checks if c[2] is not None)
    md = ["# EDA and data validation", "",
          "Built by `python -m eda` from the dbt warehouse only: the golden tables plus a few staging views. "
          "Nothing here reads the simulator or its answer key, so this is what an analyst at Fernhook would see before an MMM.", "",
          "## 1. Validation checks", "",
          f"{ok} of {sum(c[2] is not None for c in checks)} checks pass; notes flag known limits. The dbt tests (`dbt build`) cover row-level rules; these are the checks an analyst "
          "reads before trusting the data.", "",
          _table(pd.DataFrame([{"Check": c, "Result": r, "Status": "Note" if s is None else ("Pass" if s else "Review")} for c, r, s in checks])), "",
          "## 2. Outcome and spend over time", "",
          f"![Spend and deals]({img['trend']})", "",
          _table(pd.DataFrame({
              "Year": yearly.index,
              "Paid spend": [_money(v) for v in yearly.spend],
              "Leads": [f"{v:,.0f}" for v in yearly.leads],
              "Closed-won deals": [f"{v:,.0f}" for v in yearly.deals],
              "New contract value": [_money(v) for v in yearly.revenue],
              "Spend per deal": [f"${v:,.0f}" for v in yearly.cost_per_deal],
          })), "",
          "The last few weeks of 2025 are undercounted for deals, because those leads have not had time to close.", "",
          "## 3. Seasonality", "",
          "Expected pattern for Midwest service fleets: busy when the season turns (AC switching on in late spring, heat "
          "switching on in late fall), a lull from mid-July into September, a soft winter, a deep holiday dip in late "
          "December and early January, and a smaller dip at Thanksgiving.", "",
          f"![Seasonality]({img['season']})", "",
          _table(pd.DataFrame(season_rows)), "",
          f"{season_note} During the year-end promo (weeks 46 to 50), deals run {promo_lift - 1:+.0%} relative to leads, "
          "which is what a discount on annual plans should do.", "",
          "## 4. How the media was flighted", "",
          f"![Flighting calendar]({img['flight']})", "",
          f"![Spend by channel]({img['spend']})", "",
          _table(pd.DataFrame({
              "Channel": [names[c] for c in prof.index],
              "Weeks on (of 156)": prof.weeks_on.astype(int),
              "Regions used": prof.regions_used.astype(int),
              "Typical run in a region (weeks)": prof.median_on_run.map(lambda v: f"{v:.0f}"),
              "Typical pause (weeks)": prof.median_off_gap.map(lambda v: f"{v:.0f}" if v else "none"),
          })), "",
          "Media plan changes logged between annual plans:", "",
          _table(d["plan_changes"].assign(
              Date=d["plan_changes"].change_date.dt.strftime("%Y-%m-%d"),
              Channel=d["plan_changes"].channel_id.map(names),
              Change=d["plan_changes"].budget_change_pct.map(lambda v: f"{v:+d}%"),
              Reason=d["plan_changes"].reason)[["Date", "Channel", "Change", "Reason"]]), "",
          "## 5. Spend mix", "",
          f"![Mix by year]({img['mix']})", "",
          _table(pd.DataFrame({"Year": mix.index, **{r.capitalize(): [f"{v:.0%}" for v in mix[r]] for r in ("performance", "brand", "events")}})), "",
          "## 6. Reporting sources disagree", "",
          f"![Claims vs CRM]({img['claims']})", "",
          f"Platforms claim {claims.claims.sum():,.0f} conversions in total; the CRM credits {claims.crm_leads.sum():,.0f} leads to paid "
          f"channels. Connected TV gets {int(claims.set_index('channel_id').loc['ctv', 'crm_leads'])} last-touch leads because nobody "
          "clicks a TV ad. Neither source measures what a channel adds; that is the MMM's job.", "",
          "## 7. Controls", "",
          f"![Controls]({img['controls']})", "",
          "- **Sales headcount** grows each Q1 hiring wave, then falls through the July 2024 to January 2025 freeze.",
          "- **Email** volume grows with the list, with blasts in promo weeks.",
          "- **Fleet activity index** moves a few points either way; it is the market-demand control.",
          f"- **Promo and price:** year-end discount weeks are flagged each year; list price rose 10% in July 2024 "
          f"(index {d['controls'].price_index.max():.2f} after).", "",
          "## 8. Channel by channel", "",
          "What the data shows about how each channel was bought and reported. These are observations, not effects.", ""]
    for _, ch in chans.iterrows():
        md += [channel_section(ch, prof, by_year, d["plan_changes"].query("channel_id == @ch.channel_id"),
                               notes.get(ch.channel_id, "")), ""]
    md += ["## 9. Strongest spend correlations", "",
           _table(pd.DataFrame([{"Channel A": a, "Channel B": b, "Correlation": f"{v:.2f}"} for a, b, v in pairs[:5]])), "",
           "Variance inflation (VIF) of national weekly spend: " +
           ", ".join(f"{k} {v:.1f}" for k, v in sorted(vif.items(), key=lambda kv: -kv[1])) + ".", ""]
    return "\n".join(md)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit("data/warehouse.duckdb not found: run `python -m sim` and `dbt build` first")
    con = duckdb.connect(str(DB_PATH), read_only=True)
    text = build(con)
    (OUT_DIR / "EDA.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT_DIR / 'EDA.md'} and {len(list(IMG_DIR.glob('*.png')))} charts")
