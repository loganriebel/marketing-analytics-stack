"""python -m sim [--seed N] [--raw-dir DIR] [--truth-path FILE]
python -m sim --through 2026-05-31 --plan plans/2026_test.yaml --out data/cut_2026-05-31

With no --through the sim writes the 2023 to 2025 world, byte for byte as always.
--through runs the world on into 2026 up to that snapshot date, with spend from the
plan files (applied in order). --out DIR writes DIR/data/raw/, DIR/truth.json and
DIR/truth_2026.json, so dbt can build DIR/data/warehouse.duckdb from DIR.
"""

import argparse
from datetime import date
from pathlib import Path

from . import config as C
from .extend import BASE_SNAPSHOT, simulate_through
from .generate import DEFAULT_RAW_DIR, DEFAULT_TRUTH_PATH, simulate, write_outputs


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Fernhook's synthetic marketing data.")
    ap.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    ap.add_argument("--truth-path", type=Path, default=DEFAULT_TRUTH_PATH)
    ap.add_argument("--through", type=date.fromisoformat, default=None,
                    help="snapshot date; after 2025-12-28 the world runs on into 2026")
    ap.add_argument("--plan", type=Path, action="append", default=[],
                    help="2026 plan file (repeatable, applied in order)")
    ap.add_argument("--out", type=Path, default=None,
                    help="write DIR/data/raw, DIR/truth.json and DIR/truth_2026.json")
    args = ap.parse_args()

    raw_dir, truth_path, truth_2026 = args.raw_dir, args.truth_path, None
    if args.out:
        raw_dir, truth_path, truth_2026 = args.out / "data" / "raw", args.out / "truth.json", args.out / "truth_2026.json"
    if args.through and args.through > BASE_SNAPSHOT:
        result = simulate_through(args.seed, args.through, args.plan)
    else:
        if args.plan:
            ap.error("--plan needs --through after 2025-12-28")
        result = simulate(args.seed)
    write_outputs(result, raw_dir, truth_path, truth_2026)
    for name, df in result.tables.items():
        print(f"{name:28s} {len(df):>9,d} rows")
    if result.truth_2026 is None:
        print("true CPA:", {c: round(v["cpa"]) for c, v in result.truth["channels"].items()})


if __name__ == "__main__":
    main()
