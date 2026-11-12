"""Guards that keep the sim true to its scenario: enough spend variation for an MMM,
the planned search split, one near-zero channel, platforms that over-claim, and CTV
that last touch never sees."""

import numpy as np
import pandas as pd
import pytest

from sim import config as C
from sim import simulate


@pytest.fixture(scope="module")
def sim():
    return simulate(C.DEFAULT_SEED)


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


def test_grid_size(sim):
    national = _spend_long(sim.tables).pivot_table(index="week", columns="ch", values="spend", aggfunc="sum")
    assert national.shape == (C.N_WEEKS, len(C.PAID_CHANNELS))
    assert len(sim.tables["regions"]) == 20


def test_channel_spend_is_not_collinear(sim):
    national = _spend_long(sim.tables).pivot_table(index="week", columns="ch", values="spend", aggfunc="sum").fillna(0.0)
    corr = national.corr().to_numpy()
    assert np.abs(corr[~np.eye(len(corr), dtype=bool)]).max() < 0.6


def test_nonbrand_is_about_65_percent_of_search(sim):
    # Brand spend follows demand, so the split lands near the 65/35 plan, not on it.
    assert sim.truth["summary"]["nonbrand_share_of_search_spend"] == pytest.approx(0.65, abs=0.03)


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
