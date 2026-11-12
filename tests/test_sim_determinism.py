import hashlib
import json
from pathlib import Path

import pytest

from sim import config as C
from sim import simulate, write_outputs
from sim.generate import DEFAULT_TRUTH_PATH

RAW_FILES = {
    "regions.csv", "ads_google_weekly.csv", "ads_meta_weekly.csv", "ads_linkedin_weekly.csv",
    "ads_display_weekly.csv", "ctv_weekly.csv", "partners_weekly.csv", "webinar_events.csv",
    "crm_leads.csv", "crm_opportunities.csv", "sales_capacity_monthly.csv", "email_weekly.csv",
    "promo_calendar.csv", "media_plan_changes.csv", "fleet_activity_index_weekly.csv",
}


def _run(folder: Path, seed: int) -> dict[str, str]:
    write_outputs(simulate(seed), folder / "raw", folder / "truth.json")
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.fixture(scope="module")
def default_seed_runs(tmp_path_factory):
    return [_run(tmp_path_factory.mktemp(f"run{i}"), C.DEFAULT_SEED) for i in range(2)]


def test_same_seed_gives_byte_identical_files(default_seed_runs):
    first, second = default_seed_runs
    assert {Path(k).name for k in first} == RAW_FILES | {"truth.json"}
    assert first == second


def test_different_seed_gives_different_data(default_seed_runs, tmp_path):
    other = _run(tmp_path, C.DEFAULT_SEED + 1)
    changed = {k for k in other if other[k] != default_seed_runs[0][k]}
    assert changed >= {"raw/crm_leads.csv", "raw/ads_meta_weekly.csv", "truth.json"}


def test_committed_truth_matches_default_seed():
    # If this fails, the sim or a pinned library changed: regenerate and commit truth.json.
    committed = json.loads(DEFAULT_TRUTH_PATH.read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(simulate(C.DEFAULT_SEED).truth))
