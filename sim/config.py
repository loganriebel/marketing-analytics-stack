"""Every knob of the simulated company lives here.

Fernhook Software is fictional. It sells fleet-maintenance and work-order software
to small and mid-size fleets (5 to 200 vehicles): local delivery, HVAC and plumbing
service vans, landscaping crews. Sales-assisted motion with a 14-day trial, so a
lead usually closes in 7 to 30 days. Nothing here describes a real company.

The story baked into the numbers: the CRM credits every deal to its last UTM touch,
so budget reviews kept rewarding search and retargeting. Performance channels took
70% of spend in 2023 and 76% by 2025. In truth, search is saturated, display
retargeting does almost nothing, and YouTube and Meta are underfunded.
"""

from datetime import date

DEFAULT_SEED = 2026

COMPANY = "Fernhook Software (fictional)"

# Analysis window: 156 Monday-start weeks. The burn-in weeks before it warm up
# adstock and the sales funnel so week 0 is in steady state; only the CRM keeps
# rows from the burn-in, the same way a CRM holds more history than ad exports.
WINDOW_START = date(2023, 1, 2)
N_WEEKS = 156
BURN_IN_WEEKS = 26
L_MAX = 12  # adstock memory in weeks

# (code, name, sales_area, target_accounts). Target accounts set market size.
REGIONS = [
    ("US_NE", "US Northeast", "NA", 3100),
    ("US_MA", "US Mid-Atlantic", "NA", 2700),
    ("US_SE", "US Southeast", "NA", 2500),
    ("US_FL", "US Florida", "NA", 1800),
    ("US_GL", "US Great Lakes", "NA", 2900),
    ("US_MW", "US Midwest", "NA", 2200),
    ("US_PL", "US Plains", "NA", 1100),
    ("US_TX", "US Texas", "NA", 3600),
    ("US_MT", "US Mountain", "NA", 1300),
    ("US_SW", "US Southwest", "NA", 1500),
    ("US_CA", "US California", "NA", 4000),
    ("US_PNW", "US Pacific Northwest", "NA", 1600),
    ("CA_E", "Canada East", "NA", 1700),
    ("CA_W", "Canada West", "NA", 1000),
    ("EU_UKI", "UK and Ireland", "EMEA", 2300),
    ("EU_DACH", "DACH", "EMEA", 2000),
    ("EU_BNL", "Benelux", "EMEA", 900),
    ("EU_NOR", "Nordics", "EMEA", 800),
    ("AP_ANZ", "Australia and New Zealand", "APAC", 1200),
    ("AP_SEA", "Southeast Asia", "APAC", 700),
]

AREA = {
    # base_leads: organic demand per account; amount: deal size multiplier
    "NA": {"base_leads": 1.00, "amount": 1.00},
    "EMEA": {"base_leads": 0.90, "amount": 0.92},
    "APAC": {"base_leads": 0.80, "amount": 0.85},
}

PAID_CHANNELS = ["paid_search", "meta", "linkedin", "youtube", "display", "webinars"]
AD_CHANNELS = ["paid_search", "meta", "linkedin", "youtube", "display"]
ORIGINS = ["base"] + PAID_CHANNELS  # what truly caused a lead
CRM_CHANNELS = PAID_CHANNELS + ["organic_search", "direct", "referral"]

# --- Spend plan -------------------------------------------------------------
# weekly_budget: national $/week at window start. growth: log budget growth per
# year; the signs carry the drift (last-touch reviews feed search and retargeting,
# starve YouTube and Meta). flight: always_on | bursts | flights. dark_rate:
# expected regional pauses per region over the horizon (natural geo holdouts).
# tilt_sigma: how unevenly a channel is spread across regions beyond market size.
SPEND = {
    "paid_search": {"weekly_budget": 92_000, "growth": 0.15, "quarter_sigma": 0.12,
                    "weekly_sigma": 0.08, "flight": "always_on", "season_follow": 0.5,
                    "dark_rate": 0.25, "dark_len": (4, 6), "tilt_sigma": 0.30,
                    "region_sigma": 0.12},
    "meta": {"weekly_budget": 40_000, "growth": -0.12, "quarter_sigma": 0.25,
             "weekly_sigma": 0.12, "flight": "bursts", "season_follow": 0.0,
             "dark_rate": 0.9, "dark_len": (6, 10), "tilt_sigma": 0.40,
             "region_sigma": 0.18},
    "linkedin": {"weekly_budget": 30_000, "growth": 0.05, "quarter_sigma": 0.20,
                 "weekly_sigma": 0.10, "flight": "bursts", "season_follow": 0.0,
                 "dark_rate": 0.7, "dark_len": (6, 10), "tilt_sigma": 0.45,
                 "region_sigma": 0.15},
    "youtube": {"weekly_budget": 27_000, "growth": -0.20, "quarter_sigma": 0.20,
                "weekly_sigma": 0.10, "flight": "flights", "season_follow": 0.0,
                "dark_rate": 0.6, "dark_len": (6, 10), "tilt_sigma": 0.35,
                "region_sigma": 0.15},
    "display": {"weekly_budget": 24_000, "growth": 0.14, "quarter_sigma": 0.30,
                "weekly_sigma": 0.20, "flight": "always_on", "season_follow": 0.0,
                "dark_rate": 0.9, "dark_len": (6, 10), "tilt_sigma": 0.35,
                "region_sigma": 0.20},
}

# Webinars are regional field events, not an ad platform.
WEBINARS = {
    "events_per_week_national": 1.5,
    "cost_median": 9_000,
    "cost_sigma": 0.35,
    "cost_per_registrant": 110.0,
    "attend_rate": 0.42,
    "topics": [
        "Preventive maintenance playbook",
        "Cutting fleet downtime",
        "Parts inventory on a budget",
        "Telematics for small fleets",
        "Audit-ready inspection records",
        "Scheduling techs without spreadsheets",
    ],
}

HOLIDAY_SPEND_CUT = 0.7  # every channel trims spend in the last and first ISO weeks

# --- True media effect -----------------------------------------------------
# Leads caused by channel c in region r, week t:
#   beta_c * size_r * hill(adstock_c(spend_rc)(t) / size_r; K_c, S_c)
# adstock is geometric and normalized (weights sum to 1) over L_MAX weeks.
# K_c is in $/week of adstocked spend for an average-size region (size 1.0).
# target_roi_pipeline sets beta: expected pipeline $ per in-window $ of spend.
# Search runs far past its half-saturation point, so its next dollar is weak;
# YouTube and Meta run well below theirs, so their next dollar is strong.
EFFECT = {
    "paid_search": {"alpha": 0.25, "K": 2_800, "S": 1.4, "target_roi_pipeline": 3.2},
    "meta": {"alpha": 0.45, "K": 3_500, "S": 1.2, "target_roi_pipeline": 2.6},
    "linkedin": {"alpha": 0.40, "K": 1_500, "S": 1.2, "target_roi_pipeline": 1.8},
    "youtube": {"alpha": 0.70, "K": 3_500, "S": 1.3, "target_roi_pipeline": 2.4},
    "display": {"alpha": 0.30, "K": 1_000, "S": 1.0, "target_roi_pipeline": 0.08},
    "webinars": {"alpha": 0.20, "K": 6_000, "S": 1.0, "target_roi_pipeline": 3.5},
}

# --- Organic baseline ------------------------------------------------------
BASE = {
    "leads_per_week_avg_region": 27.0,  # at window start, size 1.0, NA, season 1.0
    "growth_per_year": 0.08,            # log growth
    "region_week_sigma": 0.07,
    "national_shock_sigma": 0.04,
    "national_shock_rho": 0.5,
}
# Fourier terms on ISO week of year plus holiday dips.
SEASON = {
    "fourier": [(1, 0.08, 0.05), (2, 0.04, 0.0)],  # (harmonic, sin_coef, cos_coef)
    "holiday_weeks": {52: 0.55, 53: 0.55, 1: 0.60, 51: 0.80, 47: 0.85},
    "summer_weeks": (27, 34),
    "summer_mult": 0.92,
}

# --- Funnel ------------------------------------------------------------------
# lead -> MQL (fits the profile) -> SQL (SDR call booked) -> opportunity (demo and
# trial) -> closed won. Lead quality depends on the true origin, not the recorded
# source. amount_mult scales the first-year contract median.
FUNNEL = {
    "base": {"p_mql": 0.60, "p_sql": 0.45, "p_opp": 0.70, "p_won": 0.36, "amount_mult": 1.00},
    "paid_search": {"p_mql": 0.58, "p_sql": 0.42, "p_opp": 0.70, "p_won": 0.33, "amount_mult": 1.00},
    "meta": {"p_mql": 0.45, "p_sql": 0.35, "p_opp": 0.62, "p_won": 0.28, "amount_mult": 0.85},
    "linkedin": {"p_mql": 0.62, "p_sql": 0.45, "p_opp": 0.70, "p_won": 0.32, "amount_mult": 1.25},
    "youtube": {"p_mql": 0.55, "p_sql": 0.40, "p_opp": 0.68, "p_won": 0.32, "amount_mult": 1.00},
    "display": {"p_mql": 0.40, "p_sql": 0.30, "p_opp": 0.60, "p_won": 0.25, "amount_mult": 0.90},
    "webinars": {"p_mql": 0.70, "p_sql": 0.40, "p_opp": 0.65, "p_won": 0.34, "amount_mult": 1.10},
}
AMOUNT_MEDIAN = 6_000.0  # first-year contract value, USD
AMOUNT_SIGMA = 0.45
# Stage lags in days, gamma(shape, scale) floored to whole days. Lead to close
# averages about 17 days; nine in ten close between 7 and 30.
LAGS = {
    "mql": (1.2, 0.8),
    "sql": (1.5, 1.5),
    "opp": (1.5, 1.2),
    "close_won": (4.0, 3.0),
    "close_lost": (3.0, 4.0),
}
WEEKDAY_WEIGHTS = [0.19, 0.20, 0.20, 0.19, 0.15, 0.035, 0.035]

# --- How the CRM records a lead's source (last touch UTM) -------------------
# Rows: true origin. Values: probability of each recorded channel. People who see
# a YouTube or Meta ad often search the brand name later, so search takes the credit.
CRM_ATTRIBUTION = {
    "base": {"organic_search": 0.38, "direct": 0.27, "referral": 0.13,
             "paid_search": 0.15, "meta": 0.02, "display": 0.05},
    "paid_search": {"paid_search": 0.90, "organic_search": 0.04, "direct": 0.06},
    "meta": {"meta": 0.45, "paid_search": 0.25, "direct": 0.20, "organic_search": 0.10},
    "linkedin": {"linkedin": 0.75, "direct": 0.15, "paid_search": 0.10},
    "youtube": {"youtube": 0.12, "paid_search": 0.40, "organic_search": 0.23, "direct": 0.25},
    "display": {"display": 0.40, "direct": 0.35, "paid_search": 0.25},
    "webinars": {"webinars": 0.95, "direct": 0.05},
}
# Raw UTM pairs per recorded channel, with messy casing like a real CRM.
UTM_VARIANTS = {
    "paid_search": [(("google", "cpc"), 0.90), (("Google", "cpc"), 0.10)],
    "meta": [(("facebook", "paid_social"), 0.60), (("instagram", "paid_social"), 0.30),
             (("Facebook", "Paid_Social"), 0.10)],
    "linkedin": [(("linkedin", "paid_social"), 0.85), (("LinkedIn", "paid_social"), 0.15)],
    "youtube": [(("youtube", "video"), 0.95), (("YouTube", "video"), 0.05)],
    "display": [(("dsp", "display"), 0.70), (("programmatic", "display"), 0.30)],
    "webinars": [(("webinar", "event"), 1.00)],
    "organic_search": [(("google", "organic"), 0.88), (("bing", "organic"), 0.12)],
    "direct": [(("(direct)", "(none)"), 0.85), (("", ""), 0.15)],
    "referral": [(("partner", "referral"), 0.55), (("review_site", "referral"), 0.45)],
}

# --- Platform-reported conversions -----------------------------------------
# reported ~ Poisson(claim_mult * true incremental leads
#                    + halo * baseline leads * reach
#                    + sum over halo_from of share * leads caused by that channel)
# reach = 1 - exp(-spend / (reach_spend * size)). Halo is credit for leads the
# channel did not cause (brand search, view-through, retargeting people already coming).
PLATFORM = {
    "paid_search": {"claim_mult": 1.15, "halo": 0.15, "reach_spend": 4_000,
                    "halo_from": {"youtube": 0.40, "meta": 0.25}},
    "meta": {"claim_mult": 1.60, "halo": 0.08, "reach_spend": 2_000, "halo_from": {}},
    "linkedin": {"claim_mult": 1.30, "halo": 0.05, "reach_spend": 1_500, "halo_from": {}},
    "youtube": {"claim_mult": 1.50, "halo": 0.04, "reach_spend": 1_500, "halo_from": {}},
    "display": {"claim_mult": 2.00, "halo": 0.20, "reach_spend": 1_300, "halo_from": {}},
}
DISPLAY_POST_VIEW_SHARE = 0.85
# CPM in $ and click-through rate per impression.
MEDIA = {
    "paid_search": {"cpm": 200.0, "ctr": 0.045},
    "meta": {"cpm": 12.0, "ctr": 0.010},
    "linkedin": {"cpm": 45.0, "ctr": 0.006},
    "youtube": {"cpm": 10.0, "ctr": 0.002},
    "display": {"cpm": 4.0, "ctr": 0.0015},
}
Q4_CPM_LIFT = 0.25
