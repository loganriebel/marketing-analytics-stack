"""Guards that keep the sim true to its scenario: enough spend variation for an MMM,
seasonal brand pushes a model can still separate from demand, always-on channels
that never pause, budgets that drift from brand to non-brand search, search that
saturates, one near-zero channel, platforms that over-claim, CTV that last touch never
sees, and the README story on more than one seed."""

import numpy as np
import pandas as pd
import pytest

from sim import config as C
from sim import simulate
from sim.generate import _adstock, _hill

BRAND_PUSH = ["meta", "youtube", "ctv"]
PERFORMANCE = ["paid_search_brand", "paid_search_nonbrand", "display", "affiliates"]
BRAND = ["meta", "youtube", "ctv", "linkedin"]
OTHER_SEEDS = [C.DEFAULT_SEED + i for i in (1, 2, 3)]


@pytest.fixture(scope="module")
def sim():
    return simulate(C.DEFAULT_SEED)


@pytest.fixture(scope="module")
def other_seeds():
    return {s: simulate(s) for s in OTHER_SEEDS}


def _week(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates)
    return (d - pd.to_timedelta(d.dt.day_of_week, unit="D")).dt.strftime("%Y-%m-%d")


def _spend_long(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    g = t["ads_google_weekly"]
    google_channel = g.campaign_name.map({"FH_Search_Brand": "paid_search_brand",
                                          "FH_Search_NonBrand": "paid_search_nonbrand",
                                          "FH_YouTube_Prospecting": "youtube"})
    meta, li, dsp = t["ads_meta_weekly"], t["ads_linkedin_weekly"], t["ads_display_weekly"]
    ctv, partners, ev = t["ctv_weekly"], t["partners_weekly"], t["webinar_events"]
    region_by_name = dict(zip(t["regions"].region_name, t["regions"].region_code))
    parts = [
        pd.DataFrame({"week": g.week_start_date, "region": g.geo_target_region, "ch": google_channel, "spend": g.cost_micros / 1e6}),
        pd.DataFrame({"week": meta.date_start, "region": meta.region.map(region_by_name), "ch": "meta", "spend": meta.spend}),
        pd.DataFrame({"week": li.start_date, "region": li.region_code, "ch": "linkedin", "spend": li.cost_usd}),
        pd.DataFrame({"week": dsp.week, "region": dsp.region_code, "ch": "display", "spend": dsp.media_cost}),
        pd.DataFrame({"week": ctv.week_start, "region": ctv.geo_region, "ch": "ctv", "spend": ctv.spend}),
        pd.DataFrame({"week": partners.week_start, "region": partners.region_code, "ch": "affiliates", "spend": partners.partner_fees}),
        pd.DataFrame({"week": _week(ev.event_date), "region": ev.region_code, "ch": "webinars", "spend": ev.total_cost}),
    ]
    return pd.concat(parts, ignore_index=True)


def _national(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return _spend_long(t).pivot_table(index="week", columns="ch", values="spend", aggfunc="sum").fillna(0.0)


def _grid(t: dict[str, pd.DataFrame], ch: str) -> pd.DataFrame:
    """Week x market spend for one channel, zeros filled."""
    sl = _spend_long(t)
    weeks = sorted(t["fleet_activity_index_weekly"].week_start)
    return (sl[sl.ch == ch].pivot_table(index="week", columns="region", values="spend", aggfunc="sum")
            .reindex(index=weeks, columns=list(t["regions"].region_code)).fillna(0.0))


def _woy(weeks) -> np.ndarray:
    return pd.to_datetime(pd.Series(list(weeks))).dt.isocalendar().week.to_numpy().astype(int)


def test_grid_size(sim):
    assert _national(sim.tables).shape == (C.N_WEEKS, len(C.PAID_CHANNELS))
    regions = sim.tables["regions"]
    assert len(regions) == 20
    assert set(regions.sales_area) == set(C.AREA)
    assert set(regions.state) == {"IL", "IA", "MN", "ND", "OH", "SD", "WI"}


def test_channel_spend_moves_apart_within_each_year(sim):
    # Budgets drift on purpose (search up, brand down), so yearly levels move together.
    # Inside each year, week-to-week spend on the planned channels still moves apart, or
    # no model could tell them apart. Brand search follows demand and the upper funnel;
    # the lockstep test below covers it.
    nat = _national(sim.tables)[C.PLANNED_CHANNELS + ["webinars"]]
    yr = pd.to_datetime(pd.Series(nat.index, index=nat.index)).dt.year
    dev = nat / nat.groupby(yr).transform("mean")
    corr = dev.corr().to_numpy()
    assert np.abs(corr[~np.eye(len(corr), dtype=bool)]).max() < 0.6


def test_seasonal_brand_pushes_do_not_move_in_lockstep(sim, other_seeds):
    # Meta, YouTube and CTV all push into the same seasons, and brand search follows the
    # demand those seasons bring. Staggered timing keeps them apart on every seed.
    pairs = BRAND_PUSH + ["paid_search_brand"]
    for seed, result in {C.DEFAULT_SEED: sim, **other_seeds}.items():
        corr = _national(result.tables)[pairs].corr().to_numpy()
        off = corr[~np.eye(len(pairs), dtype=bool)]
        assert off.mean() < 0.45, seed
        assert np.abs(off).max() < 0.7, seed


def test_brand_channels_push_into_busy_seasons(sim):
    nat = _national(sim.tables)
    woy = _woy(nat.index)
    pl = C.PLANNING
    slow = ((woy >= 3) & (woy <= 9)) | ((woy >= 29) & (woy <= 31))
    for ch in BRAND_PUSH:
        f = C.SPEND[ch]["push"]
        push = np.zeros(len(woy), dtype=bool)
        for peak in (pl["spring_peak_week"], pl["fall_peak_week"]):
            push |= (woy >= peak - f["lead"]) & (woy < peak - f["lead"] + f["len"][0])
        assert nat[ch][push].mean() > 1.15 * nat[ch][slow].mean(), ch


def test_brand_spend_is_not_just_the_calendar(sim):
    # A market's average week-of-year pattern explains part of each brand channel's
    # spend, not all of it: push timing and size change from year to year.
    for ch in BRAND_PUSH:
        x = _grid(sim.tables, ch)
        x = x.loc[:, x.sum() > 0]
        fit = x.groupby(_woy(x.index)).transform("mean").to_numpy()
        v = x.to_numpy()
        r2 = 1 - ((v - fit) ** 2).sum() / ((v - v.mean(axis=0)) ** 2).sum()
        assert r2 < 0.8, ch


def _oracle_bias(result, market_season: bool) -> dict[str, float]:
    """Fit leads on each channel's true adstock-and-saturation curve with OLS, plus a
    market-year level, holiday weeks and (optionally) market-level Fourier seasonality.
    Brand search enters at its true effect: it never pauses and its spend follows
    demand, so nothing in the data separates it (that is its own trap).
    Returns the relative error of each other channel's recovered effect."""
    t, tr = result.tables, result.truth
    codes = list(t["regions"].region_code)
    size = np.array([tr["region_size_index"][c] for c in codes])
    weeks = sorted(t["fleet_activity_index_weekly"].week_start)
    leads = t["crm_leads"]
    y = (leads.assign(week=_week(leads.created_date)).query("week in @weeks")
         .groupby(["week", "region_code"]).size().unstack().reindex(index=weeks, columns=codes).fillna(0.0).to_numpy())
    n_t, n_r = y.shape
    curves = {}
    for ch in C.PAID_CHANNELS:
        e = tr["channels"][ch]
        a = _adstock(_grid(t, ch).to_numpy(), e["adstock"]["alpha"], C.L_MAX)
        curves[ch] = size * _hill(a / size, e["saturation"]["half_saturation"], e["saturation"]["slope"])
    fitted = [ch for ch in C.PAID_CHANNELS if ch != "paid_search_brand"]
    y = y - tr["channels"]["paid_search_brand"]["beta_leads_per_week_per_size_unit"] * curves["paid_search_brand"]
    feats = [curves[ch] for ch in fitted]
    woy = _woy(weeks).astype(float)
    yr = pd.to_datetime(pd.Series(weeks)).dt.year.to_numpy()
    ctrl = [(yr == v).astype(float) for v in np.unique(yr)] + [(woy == w).astype(float) for w in (47, 51, 52, 1)]
    if market_season:
        ctrl += [fn(2 * np.pi * h * woy / 52) for h in (1, 2, 3) for fn in (np.sin, np.cos)]
    ctrl = np.column_stack(ctrl)
    k = len(feats)
    x = np.zeros((n_t * n_r, k + ctrl.shape[1] * n_r))
    for j in range(n_r):
        rows = slice(j * n_t, (j + 1) * n_t)
        x[rows, :k] = np.column_stack([f[:, j] for f in feats])
        x[rows, k + j * ctrl.shape[1]: k + (j + 1) * ctrl.shape[1]] = ctrl * size[j]
    keep = np.tile(np.arange(n_t) >= C.L_MAX, n_r)  # adstock warm-up
    w = np.repeat(1 / np.sqrt(size), n_t)  # lead counts are Poisson, so variance grows with size
    coef, *_ = np.linalg.lstsq(x[keep] * w[keep, None], y.T.ravel()[keep] * w[keep], rcond=None)
    return {ch: coef[i] / tr["channels"][ch]["beta_leads_per_week_per_size_unit"] - 1
            for i, ch in enumerate(fitted)}


def test_market_seasonality_separates_brand_pushes_from_demand(sim):
    # Spend timed to demand is a built-in trap. Even knowing every curve's true shape,
    # a fit without seasonality misreads at least one brand channel; adding
    # market-level seasonality recovers all of them.
    naive = _oracle_bias(sim, market_season=False)
    seasonal = _oracle_bias(sim, market_season=True)
    assert max(abs(naive[ch]) for ch in BRAND_PUSH) > 0.1
    for ch in BRAND_PUSH + ["paid_search_nonbrand", "webinars"]:
        assert abs(seasonal[ch]) < 0.2, ch


def test_always_on_channels_never_go_dark(sim):
    # Paid search, LinkedIn, display and affiliates run every week in every market.
    for ch in ("paid_search_brand", "paid_search_nonbrand", "linkedin", "display", "affiliates"):
        assert (_grid(sim.tables, ch).to_numpy() > 0).all(), ch


def test_upper_funnel_creates_brand_searches(sim, other_seeds):
    # Meta, YouTube and CTV create brand searches, so brand-search spend rises with them
    # and each channel gets deals through brand search on top of its direct deals.
    for seed, result in {C.DEFAULT_SEED: sim, **other_seeds}.items():
        tr = result.truth
        assert 0.08 < tr["summary"]["upper_funnel_share_of_brand_searches"] < 0.3, seed
        for ch in BRAND_PUSH:
            v = tr["channels"][ch]
            via, direct = v["incremental_deals_via_brand_search"], v["incremental_deals"]
            assert via > 0, (seed, ch)
            assert v["incremental_deals_total"] == pytest.approx(direct + via, abs=0.02)
            assert v["cpa_total"] < v["cpa"]
            total_curve = v["response_curve_total"]["incremental_deals"]
            direct_curve = v["response_curve"]["incremental_deals"]
            assert total_curve[0] == 0 and all(b > a for a, b in zip(total_curve, total_curve[1:]))
            assert all(t >= d for t, d in zip(total_curve, direct_curve))
            at_one = v["response_curve_total"]["spend_multiplier"].index(1.0)
            assert total_curve[at_one] == pytest.approx(v["incremental_deals_total"], abs=0.01)


def _yearly(t):
    sl = _spend_long(t).assign(yr=lambda d: pd.to_datetime(d.week).dt.year)
    return sl.pivot_table(index="yr", columns="ch", values="spend", aggfunc="sum").fillna(0.0)


def test_budgets_land_on_plan(sim, other_seeds):
    # Every channel is paced to its annual budget: performance against brand goes 60/40,
    # 70/30, 80/20 and total spend rises 10% and then 16%, on every seed.
    for seed, result in {C.DEFAULT_SEED: sim, **other_seeds}.items():
        by = _yearly(result.tables)
        perf = by[PERFORMANCE].sum(axis=1) / by[PERFORMANCE + BRAND].sum(axis=1)
        for y, share in ((2023, 0.60), (2024, 0.70), (2025, 0.80)):
            assert perf[y] == pytest.approx(share, abs=0.005), (seed, y)
        total = by.sum(axis=1)
        assert total[2024] / total[2023] - 1 == pytest.approx(0.10, abs=0.005), seed
        assert total[2025] / total[2024] - 1 == pytest.approx(0.16, abs=0.005), seed
        for ch in C.PLANNED_CHANNELS:
            for y, b in C.SPEND[ch]["annual_budget"].items():
                assert by.loc[y, ch] == pytest.approx(b, rel=0.001), (seed, ch, y)
        for y, b in C.BRAND_SEARCH["annual_budget"].items():
            assert by.loc[y, "paid_search_brand"] == pytest.approx(b, rel=0.001), (seed, y)


def test_readme_story_holds_on_several_seeds(sim, other_seeds):
    # Spend climbs while non-brand search runs out of steam: its cost per click and cost
    # per lead rise every year, its leads close less often, closed-won deals fall in
    # 2025, and the blended cost per deal jumps.
    for seed, result in {C.DEFAULT_SEED: sim, **other_seeds}.items():
        t = result.tables
        by = _yearly(t)
        leads = t["crm_leads"].assign(yr=lambda d: pd.to_datetime(_week(d.created_date)).dt.year)
        nb = leads[leads.utm_campaign == "search_nonbrand"]
        cpl = by["paid_search_nonbrand"] / nb.groupby("yr").size()
        g = t["ads_google_weekly"]
        g = g[g.campaign_name == "FH_Search_NonBrand"].assign(yr=lambda d: pd.to_datetime(d.week_start_date).dt.year)
        cpc = g.groupby("yr").cost_micros.sum() / 1e6 / g.groupby("yr").clicks.sum()
        opps = t["crm_opportunities"].merge(nb[["lead_id", "yr"]], on="lead_id")
        closed = opps[opps.stage != "Open"]
        win_rate = (closed.stage == "Closed Won").groupby(closed.yr).mean()
        for a, b in ((2023, 2024), (2024, 2025)):
            assert cpl[b] > cpl[a] and cpc[b] > cpc[a] and win_rate[b] < win_rate[a], (seed, a, b)
        won = t["crm_opportunities"].query("stage == 'Closed Won'")
        won_year = pd.to_datetime(_week(won.close_date)).dt.year.value_counts()
        assert won_year[2025] < won_year[2024], seed
        cpa = by.sum(axis=1) / won_year
        assert cpa[2025] > 1.15 * cpa[2024] and cpa[2025] > 1.15 * cpa[2023], seed


def test_nonbrand_search_saturates(sim, other_seeds):
    # Each channel's true cost per deal is anchored at its 2023 spend. Non-brand search
    # starts near half-saturation, so its true cost per deal climbs every year.
    for seed, result in {C.DEFAULT_SEED: sim, **other_seeds}.items():
        ch = result.truth["channels"]["paid_search_nonbrand"]
        by = ch["by_year"]
        assert by["2023"]["cpa"] == pytest.approx(ch["cpa_2023_reference"], rel=0.25), seed
        assert by["2023"]["cpa"] < by["2024"]["cpa"] < by["2025"]["cpa"], seed
        assert by["2025"]["cpa"] > 1.5 * by["2023"]["cpa"], seed


def test_display_is_the_near_zero_channel(sim):
    cpa = {c: v["cpa"] for c, v in sim.truth["channels"].items()}
    assert sim.truth["summary"]["highest_cpa_channel"] == "display"
    assert cpa["display"] > 2 * max(v for c, v in cpa.items() if c != "display")


def test_ctv_runs_only_in_ctv_regions_and_never_wins_last_touch(sim):
    ctv_regions = set(sim.tables["ctv_weekly"].geo_region)
    assert ctv_regions == set(C.CTV_REGIONS)
    leads = sim.tables["crm_leads"]
    assert not leads.utm_source.str.lower().isin(["tv", "ctv"]).any()


def test_platforms_over_claim(sim):
    t = sim.tables
    g = t["ads_google_weekly"]
    claimed = {
        "paid_search_brand": g.query("campaign_name == 'FH_Search_Brand'").conversions.sum(),
        "paid_search_nonbrand": g.query("campaign_name == 'FH_Search_NonBrand'").conversions.sum(),
        "youtube": g.query("campaign_type == 'VIDEO'").conversions.sum(),
        "meta": t["ads_meta_weekly"].leads.sum(),
        "linkedin": t["ads_linkedin_weekly"].conversions.sum(),
        "display": (t["ads_display_weekly"].post_click_conversions + t["ads_display_weekly"].post_view_conversions).sum(),
        "ctv": t["ctv_weekly"].attributed_leads.sum(),
        "affiliates": t["partners_weekly"].referred_signups.sum(),
        "webinars": t["webinar_events"].registrants.sum(),
    }
    for ch, n in claimed.items():
        assert n > 1.2 * sim.truth["channels"][ch]["incremental_leads"], ch
