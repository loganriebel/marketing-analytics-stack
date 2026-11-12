"""Guards that keep the sim useful for the MMM step: enough spend variation, one
near-zero channel, and platforms that over-claim."""

import numpy as np
import pandas as pd
import pytest

from sim import config as C
from sim import simulate


@pytest.fixture(scope="module")
def sim():
    return simulate(C.DEFAULT_SEED)


def _national_weekly_spend(t: dict[str, pd.DataFrame]) -> pd.DataFrame:
    g = t["ads_google_weekly"]
    parts = [
        pd.DataFrame({"week": g.week_start_date, "ch": g.campaign_type.map({"SEARCH": "paid_search", "VIDEO": "youtube"}),
                      "spend": g.cost_micros / 1e6}),
        pd.DataFrame({"week": t["ads_meta_weekly"].date_start, "ch": "meta", "spend": t["ads_meta_weekly"].spend}),
        pd.DataFrame({"week": t["ads_linkedin_weekly"].start_date, "ch": "linkedin", "spend": t["ads_linkedin_weekly"].cost_usd}),
        pd.DataFrame({"week": t["ads_display_weekly"].week, "ch": "display", "spend": t["ads_display_weekly"].media_cost}),
    ]
    ev = t["webinar_events"]
    d = pd.to_datetime(ev.event_date)
    week = (d - pd.to_timedelta(d.dt.day_of_week, unit="D")).dt.strftime("%Y-%m-%d")
    parts.append(pd.DataFrame({"week": week, "ch": "webinars", "spend": ev.total_cost}))
    return pd.concat(parts).pivot_table(index="week", columns="ch", values="spend", aggfunc="sum").fillna(0.0)


def test_grid_size(sim):
    spend = _national_weekly_spend(sim.tables)
    assert spend.shape == (C.N_WEEKS, len(C.PAID_CHANNELS))
    assert len(sim.tables["regions"]) == 20


def test_channel_spend_is_not_collinear(sim):
    corr = _national_weekly_spend(sim.tables).corr().to_numpy()
    off_diag = np.abs(corr[~np.eye(len(corr), dtype=bool)])
    assert off_diag.max() < 0.6


def test_display_is_the_near_zero_channel(sim):
    roi = {c: v["roi_pipeline"] for c, v in sim.truth["channels"].items()}
    assert sim.truth["near_zero_channel"] == "display"
    others = [v for c, v in roi.items() if c != "display"]
    assert roi["display"] < 0.1 * min(others)


def test_platforms_over_claim(sim):
    t = sim.tables
    claimed = {
        "paid_search": t["ads_google_weekly"].query("campaign_type == 'SEARCH'").conversions.sum(),
        "youtube": t["ads_google_weekly"].query("campaign_type == 'VIDEO'").conversions.sum(),
        "meta": t["ads_meta_weekly"].leads.sum(),
        "linkedin": t["ads_linkedin_weekly"].conversions.sum(),
        "display": (t["ads_display_weekly"].post_click_conversions + t["ads_display_weekly"].post_view_conversions).sum(),
        "webinars": t["webinar_events"].registrants.sum(),
    }
    for ch, n in claimed.items():
        assert n > 1.2 * sim.truth["channels"][ch]["incremental_leads"], ch
