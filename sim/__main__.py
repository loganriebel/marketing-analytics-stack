"""python -m sim [--seed N] [--raw-dir DIR] [--truth-path FILE]"""

import argparse
from pathlib import Path

from . import config as C
from .generate import DEFAULT_RAW_DIR, DEFAULT_TRUTH_PATH, simulate, write_outputs


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate Fernhook's synthetic marketing data.")
    ap.add_argument("--seed", type=int, default=C.DEFAULT_SEED)
    ap.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    ap.add_argument("--truth-path", type=Path, default=DEFAULT_TRUTH_PATH)
    args = ap.parse_args()

    result = simulate(args.seed)
    write_outputs(result, args.raw_dir, args.truth_path)
    for name, df in result.tables.items():
        print(f"{name:22s} {len(df):>9,d} rows")
    print("true pipeline ROI:", {c: v["roi_pipeline"] for c, v in result.truth["channels"].items()})


if __name__ == "__main__":
    main()
