"""Every knob of the simulated company lives here.

Fernhook Software is fictional. It sells fleet-maintenance and work-order software
to small and mid-size fleets (5 to 200 vehicles): local delivery, HVAC and plumbing
service vans, landscaping crews. Sales-assisted motion with a 14-day trial, so a
lead usually closes in 7 to 30 days. Nothing here describes a real company.

The story baked into the numbers: the CRM credits every deal to its last UTM touch,
so budget reviews kept rewarding search and retargeting while CTV, YouTube and Meta
got cut. In truth, non-brand search is saturated, brand search mostly buys clicks
that would have come anyway, display retargeting does almost nothing, and CTV,
YouTube and Meta are underfunded.

Model frame: the dependent variable is closed-won deals by region and week. Paid
channel spend is the independent variable set. Sales headcount, email volume, the
promo and price calendar, a market-activity index, seasonality and trend are controls.
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
    ("US_NE", "US Northeast", "NA", 31_000),
    ("US_MA", "US Mid-Atlantic", "NA", 27_000),
    ("US_SE", "US Southeast", "NA", 25_000),
    ("US_FL", "US Florida", "NA", 18_000),
    ("US_GL", "US Great Lakes", "NA", 29_000),
    ("US_MW", "US Midwest", "NA", 22_000),
    ("US_PL", "US Plains", "NA", 11_000),
    ("US_TX", "US Texas", "NA", 36_000),
    ("US_MT", "US Mountain", "NA", 13_000),
    ("US_SW", "US Southwest", "NA", 15_000),
    ("US_CA", "US California", "NA", 40_000),
    ("US_PNW", "US Pacific Northwest", "NA", 16_000),
    ("CA_E", "Canada East", "NA", 17_000),
    ("CA_W", "Canada West", "NA", 10_000),
    ("EU_UKI", "UK and Ireland", "EMEA", 23_000),
    ("EU_DACH", "DACH", "EMEA", 20_000),
    ("EU_BNL", "Benelux", "EMEA", 9_000),
    ("EU_NOR", "Nordics", "EMEA", 8_000),
    ("AP_ANZ", "Australia and New Zealand", "APAC", 12_000),
    ("AP_SEA", "Southeast Asia", "APAC", 7_000),
]
# CTV runs as a market test, only in these US regions.
CTV_REGIONS = ["US_NE", "US_SE", "US_FL", "US_GL", "US_MW", "US_TX", "US_SW", "US_CA"]

AREA = {
    # base_leads: organic demand per account; amount: deal size multiplier
    "NA": {"base_leads": 1.00, "amount": 1.00},
    "EMEA": {"base_leads": 0.90, "amount": 0.92},
    "APAC": {"base_leads": 0.80, "amount": 0.85},
}

PAID_CHANNELS = ["paid_search_brand", "paid_search_nonbrand", "meta", "linkedin",
                 "youtube", "ctv", "display", "affiliates", "webinars"]
# Channels whose budget comes from a plan. Brand search spend follows demand instead,
# and webinars are events.
PLANNED_CHANNELS = ["paid_search_nonbrand", "meta", "linkedin", "youtube", "ctv", "display", "affiliates"]
PLATFORM_CHANNELS = ["paid_search_brand", "paid_search_nonbrand", "meta", "linkedin",
                     "youtube", "ctv", "display", "affiliates"]
ORIGINS = ["base", "email"] + PAID_CHANNELS  # what truly caused a lead
CRM_CHANNELS = PAID_CHANNELS + ["email", "organic_search", "direct", "referral"]

# --- Spend plan for planned channels ----------------------------------------
# weekly_budget: national $/week at window start. growth: log budget growth per
# year; the signs carry the drift (last-touch reviews feed non-brand search,
# retargeting and affiliates, and starve CTV, YouTube and Meta).
# flight: always_on | bursts | flights | regional_flights. dark_rate: expected
# regional pauses per region over the horizon (natural geo holdouts). tilt_sigma:
# how unevenly a channel is spread across regions beyond market size.
SPEND = {
    # Always-on, saturated search moves with the baseline, so the team runs regional
    # budget tests (pauses and uneven regional budgets) to keep it measurable.
    "paid_search_nonbrand": {"weekly_budget": 65_000, "growth": 0.20, "quarter_sigma": 0.18,
                             "weekly_sigma": 0.08, "flight": "always_on", "season_follow": 0.3,
                             "dark_rate": 0.6, "dark_len": (4, 8), "tilt_sigma": 0.30,
                             "region_sigma": 0.22},
    "meta": {"weekly_budget": 30_000, "growth": -0.20, "quarter_sigma": 0.15,
             "weekly_sigma": 0.12, "flight": "bursts", "season_follow": 0.0,
             "dark_rate": 0.9, "dark_len": (6, 10), "tilt_sigma": 0.40,
             "region_sigma": 0.18},
    "linkedin": {"weekly_budget": 26_000, "growth": 0.05, "quarter_sigma": 0.20,
                 "weekly_sigma": 0.10, "flight": "bursts", "season_follow": 0.0,
                 "dark_rate": 0.7, "dark_len": (6, 10), "tilt_sigma": 0.45,
                 "region_sigma": 0.15},
    "youtube": {"weekly_budget": 22_000, "growth": -0.25, "quarter_sigma": 0.20,
                "weekly_sigma": 0.10, "flight": "flights", "season_follow": 0.0,
                "dark_rate": 0.6, "dark_len": (6, 10), "tilt_sigma": 0.35,
                "region_sigma": 0.15},
    "ctv": {"weekly_budget": 22_000, "growth": -0.25, "quarter_sigma": 0.15,
           "weekly_sigma": 0.05, "flight": "regional_flights", "season_follow": 0.0,
           "dark_rate": 0.0, "dark_len": (0, 0), "tilt_sigma": 0.25,
           "region_sigma": 0.08, "on_weeks": (3, 6), "off_weeks": (4, 10)},
    "display": {"weekly_budget": 22_000, "growth": 0.15, "quarter_sigma": 0.20,
                "weekly_sigma": 0.20, "flight": "always_on", "season_follow": 0.0,
                "dark_rate": 0.9, "dark_len": (6, 10), "tilt_sigma": 0.35,
                "region_sigma": 0.20},
    # Partner placement and sponsor fees, set at quarterly contract renewals.
    # Per-deal commissions are cost of sale and stay out of media spend.
    "affiliates": {"weekly_budget": 12_000, "growth": 0.12, "quarter_sigma": 0.25,
                   "weekly_sigma": 0.04, "flight": "always_on", "season_follow": 0.0,
                   "dark_rate": 0.2, "dark_len": (6, 12), "tilt_sigma": 0.50,
                   "region_sigma": 0.05},
}

# Brand search buys clicks from people already searching "Fernhook", so its spend
# follows demand: baseline plus the searches CTV, YouTube and Meta create. Its total
# is set so non-brand is 65% of search spend over the window. Regional pauses are
# the brand-search holdout tests a cautious team would run.
BRAND_SEARCH = {
    "share_of_search": 0.35,
    "demand_from": {"ctv": 0.6, "youtube": 0.5, "meta": 0.3},
    "noise_sigma": 0.10,
    "dark_rate": 0.5,
    "dark_len": (4, 8),
}

# Webinars are regional field events, not an ad platform.
WEBINARS = {
    "events_per_week_national": 1.5,
    "cost_median": 9_000,
    "cost_sigma": 0.35,
    "cost_per_registrant": 44.0,
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

HOLIDAY_SPEND_CUT = 0.7  # every planned channel trims spend in the last and first ISO weeks

# --- True media effect -----------------------------------------------------
# Leads caused by channel c in region r, week t:
#   beta_c * size_r * hill(adstock_c(spend_rc)(t) / size_r; K_c, S_c)
# adstock is geometric and normalized (weights sum to 1) over L_MAX weeks.
# K_c is in $/week of adstocked spend for an average-size region (size 1.0).
# target_cpa sets beta: in-window spend / expected closed-won deals it causes.
EFFECT = {
    "paid_search_brand": {"alpha": 0.10, "K": 600, "S": 1.0, "target_cpa": 5_600},
    "paid_search_nonbrand": {"alpha": 0.25, "K": 1_800, "S": 1.4, "target_cpa": 1_600},
    "meta": {"alpha": 0.45, "K": 3_000, "S": 1.2, "target_cpa": 1_360},
    "linkedin": {"alpha": 0.40, "K": 1_300, "S": 1.2, "target_cpa": 2_720},
    "youtube": {"alpha": 0.70, "K": 3_000, "S": 1.3, "target_cpa": 1_440},
    "ctv": {"alpha": 0.75, "K": 6_000, "S": 1.5, "target_cpa": 1_920},
    "display": {"alpha": 0.30, "K": 1_000, "S": 1.0, "target_cpa": 36_000},
    "affiliates": {"alpha": 0.50, "K": 900, "S": 1.1, "target_cpa": 1_200},
    "webinars": {"alpha": 0.20, "K": 6_000, "S": 1.0, "target_cpa": 1_120},
}

# --- Organic baseline ------------------------------------------------------
BASE = {
    "leads_per_week_avg_region": 82.5,  # at window start, size 1.0, NA, season 1.0
    "growth_per_year": 0.08,            # log growth
    "region_week_sigma": 0.07,
    "national_shock_sigma": 0.04,       # the part the market-activity index tracks
    "national_shock_rho": 0.6,
}
# Fourier terms on ISO week of year plus holiday dips.
SEASON = {
    "fourier": [(1, 0.08, 0.05), (2, 0.04, 0.0)],  # (harmonic, sin_coef, cos_coef)
    "holiday_weeks": {52: 0.55, 53: 0.55, 1: 0.60, 51: 0.80, 47: 0.85},
    "summer_weeks": (27, 34),
    "summer_mult": 0.92,
}
# Fleet activity index: a public-style weekly index of commercial fleet miles.
# Baseline demand moves one for one with it in logs; it is published with a
# little measurement noise.
MACRO = {"index_level": 100.0, "measurement_sigma": 0.01}

# --- Controls that move conversion -------------------------------------------
# Sales capacity: more SDRs per account book more calls (MQL to SQL), more AEs
# close more trials (opportunity to won). Multiplier = coverage ** elasticity.
SALES = {
    "sdr_per_1k_accounts": 0.14,
    "ae_per_1k_accounts": 0.19,
    "start_coverage": 0.88,
    "hiring_months": (1, 2, 3),
    "hiring_gain_per_month": 0.045,
    "attrition_per_month": 0.006,
    "freeze": (date(2024, 7, 1), date(2025, 1, 31)),  # hiring freeze
    "freeze_attrition_per_month": 0.02,
    "area_offset": {"NA": 0.0, "EMEA": -0.10, "APAC": -0.14},
    "region_sigma": 0.06,
    "month_sigma": 0.03,
    "sdr_elasticity": 0.40,
    "ae_elasticity": 0.30,
    "mult_bounds": (0.75, 1.12),
}
# Email is owned media: nurture and newsletter sends reactivate known contacts.
EMAIL = {
    "list_per_avg_region": 2_500,
    "list_growth_per_year": 0.20,
    "sends_per_contact_week": 1.3,
    "blast_prob": 0.15,          # national promo blast weeks
    "blast_extra": 1.0,
    "open_rate_start": 0.31,
    "open_rate_drift_per_year": -0.012,
    "click_rate_of_opens": 0.09,
    "alpha": 0.30,
    "K": 6_000,
    "S": 1.0,
    "leads_per_week_avg_region": 5.0,
}
# Year-end offer: 15% off annual plans for trials started in ISO weeks 46 to 50.
# List price rises 10% for leads created on or after the change date.
PROMO = {
    "year_end_weeks": (46, 50),
    "year_end_discount_pct": 15,
    "year_end_win_mult": 1.20,
    "price_change_date": date(2024, 7, 1),
    "price_change_pct": 10,
    "price_win_mult": 0.94,
}

# --- Funnel ------------------------------------------------------------------
# lead -> MQL (fits the profile) -> SQL (SDR call booked) -> opportunity (demo and
# trial) -> closed won. Lead quality depends on the true origin, not the recorded
# source. amount_mult scales the first-year contract median.
FUNNEL = {
    "base": {"p_mql": 0.60, "p_sql": 0.45, "p_opp": 0.70, "p_won": 0.36, "amount_mult": 1.00},
    "email": {"p_mql": 0.65, "p_sql": 0.45, "p_opp": 0.70, "p_won": 0.36, "amount_mult": 1.00},
    "paid_search_brand": {"p_mql": 0.62, "p_sql": 0.46, "p_opp": 0.72, "p_won": 0.38, "amount_mult": 1.00},
    "paid_search_nonbrand": {"p_mql": 0.56, "p_sql": 0.42, "p_opp": 0.70, "p_won": 0.33, "amount_mult": 1.00},
    "meta": {"p_mql": 0.45, "p_sql": 0.35, "p_opp": 0.62, "p_won": 0.28, "amount_mult": 0.85},
    "linkedin": {"p_mql": 0.62, "p_sql": 0.45, "p_opp": 0.70, "p_won": 0.32, "amount_mult": 1.25},
    "youtube": {"p_mql": 0.55, "p_sql": 0.40, "p_opp": 0.68, "p_won": 0.32, "amount_mult": 1.00},
    "ctv": {"p_mql": 0.55, "p_sql": 0.40, "p_opp": 0.68, "p_won": 0.33, "amount_mult": 1.05},
    "display": {"p_mql": 0.40, "p_sql": 0.30, "p_opp": 0.60, "p_won": 0.25, "amount_mult": 0.90},
    "affiliates": {"p_mql": 0.60, "p_sql": 0.44, "p_opp": 0.70, "p_won": 0.35, "amount_mult": 1.05},
    "webinars": {"p_mql": 0.70, "p_sql": 0.40, "p_opp": 0.65, "p_won": 0.34, "amount_mult": 1.10},
}
AMOUNT_MEDIAN = 2_400.0  # first-year contract value at list price, USD
AMOUNT_SIGMA = 0.45
# Stage lags in days, gamma(shape, scale) floored to whole days. Lead to close
# averages about two weeks; nine in ten close inside 7 to 30 days.
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
# CTV, YouTube or Meta often search the brand name later, so brand search takes the
# credit. CTV never shows up as a last touch at all.
CRM_ATTRIBUTION = {
    "base": {"organic_search": 0.36, "direct": 0.25, "referral": 0.12, "paid_search_brand": 0.18,
             "display": 0.05, "meta": 0.02, "affiliates": 0.02},
    "email": {"email": 0.85, "direct": 0.15},
    "paid_search_brand": {"paid_search_brand": 0.92, "direct": 0.05, "organic_search": 0.03},
    "paid_search_nonbrand": {"paid_search_nonbrand": 0.85, "paid_search_brand": 0.05,
                             "organic_search": 0.04, "direct": 0.06},
    "meta": {"meta": 0.42, "paid_search_brand": 0.25, "direct": 0.20, "organic_search": 0.10, "display": 0.03},
    "linkedin": {"linkedin": 0.75, "direct": 0.13, "paid_search_brand": 0.10, "display": 0.02},
    "youtube": {"youtube": 0.10, "paid_search_brand": 0.40, "organic_search": 0.22, "direct": 0.25,
                "display": 0.03},
    "ctv": {"paid_search_brand": 0.45, "direct": 0.35, "organic_search": 0.18, "display": 0.02},
    "display": {"display": 0.40, "direct": 0.35, "paid_search_brand": 0.25},
    "affiliates": {"affiliates": 0.70, "paid_search_brand": 0.15, "direct": 0.15},
    "webinars": {"webinars": 0.95, "direct": 0.05},
}
# Raw UTM (source, medium, campaign) per recorded channel, with messy casing like a
# real CRM. Only search campaigns carry the brand or non-brand split.
UTM_VARIANTS = {
    "paid_search_brand": [(("google", "cpc", "search_brand"), 0.90), (("Google", "cpc", "search_brand"), 0.10)],
    "paid_search_nonbrand": [(("google", "cpc", "search_nonbrand"), 0.90),
                             (("Google", "cpc", "search_nonbrand"), 0.10)],
    "meta": [(("facebook", "paid_social", "prospecting"), 0.60), (("instagram", "paid_social", "prospecting"), 0.30),
             (("Facebook", "Paid_Social", "prospecting"), 0.10)],
    "linkedin": [(("linkedin", "paid_social", "lead_gen_forms"), 0.85),
                 (("LinkedIn", "paid_social", "lead_gen_forms"), 0.15)],
    "youtube": [(("youtube", "video", "prospecting"), 0.95), (("YouTube", "video", "prospecting"), 0.05)],
    "ctv": [],
    "display": [(("dsp", "display", "retargeting"), 0.70), (("programmatic", "display", "retargeting"), 0.30)],
    "affiliates": [(("partner_network", "affiliate", ""), 0.70), (("reseller", "affiliate", ""), 0.20),
                   (("Partner_Network", "affiliate", ""), 0.10)],
    "webinars": [(("webinar", "event", ""), 1.00)],
    "email": [(("newsletter", "email", ""), 0.45), (("nurture", "email", ""), 0.55)],
    "organic_search": [(("google", "organic", ""), 0.88), (("bing", "organic", ""), 0.12)],
    "direct": [(("(direct)", "(none)", ""), 0.85), (("", "", ""), 0.15)],
    "referral": [(("customer_referral", "referral", ""), 0.60), (("review_site", "referral", ""), 0.40)],
}

# --- Platform-reported conversions -----------------------------------------
# reported ~ Poisson(noise * (claim_mult * true incremental leads
#                             + halo * baseline leads * reach
#                             + sum over halo_from of share * leads caused by that channel))
# reach = 1 - exp(-spend / (reach_spend * size)). Halo is credit for leads the
# channel did not cause (brand search, view-through, cookie-based partner credit).
PLATFORM = {
    "paid_search_brand": {"claim_mult": 1.10, "halo": 0.20, "reach_spend": 800,
                          "halo_from": {"ctv": 0.45, "youtube": 0.40, "meta": 0.25}, "noise_sigma": 0.0},
    "paid_search_nonbrand": {"claim_mult": 1.20, "halo": 0.03, "reach_spend": 3_000,
                             "halo_from": {}, "noise_sigma": 0.0},
    "meta": {"claim_mult": 1.60, "halo": 0.08, "reach_spend": 2_000, "halo_from": {}, "noise_sigma": 0.0},
    "linkedin": {"claim_mult": 1.30, "halo": 0.05, "reach_spend": 1_500, "halo_from": {}, "noise_sigma": 0.0},
    "youtube": {"claim_mult": 1.80, "halo": 0.04, "reach_spend": 1_500, "halo_from": {}, "noise_sigma": 0.0},
    # The CTV platform only credits weeks it served ads, so CTV's long carryover is
    # partly missed; its in-flight household-match claim over-claims overall anyway.
    "ctv": {"claim_mult": 2.40, "halo": 0.05, "reach_spend": 4_000, "halo_from": {}, "noise_sigma": 0.30},
    "display": {"claim_mult": 2.00, "halo": 0.20, "reach_spend": 1_300, "halo_from": {}, "noise_sigma": 0.0},
    "affiliates": {"claim_mult": 1.80, "halo": 0.04, "reach_spend": 600, "halo_from": {}, "noise_sigma": 0.0},
}
DISPLAY_POST_VIEW_SHARE = 0.85
# CPM in $ and click-through rate per impression (None = not reported).
MEDIA = {
    "paid_search_brand": {"cpm": 450.0, "ctr": 0.22},
    "paid_search_nonbrand": {"cpm": 250.0, "ctr": 0.035},
    "meta": {"cpm": 12.0, "ctr": 0.010},
    "linkedin": {"cpm": 45.0, "ctr": 0.006},
    "youtube": {"cpm": 10.0, "ctr": 0.002},
    "ctv": {"cpm": 35.0, "completion_rate": 0.95},
    "display": {"cpm": 4.0, "ctr": 0.0015},
    "affiliates": {"cpc": 3.5},
}
Q4_CPM_LIFT = 0.25
