#!/usr/bin/env python3

import argparse
import os
import sys
import subprocess
from pathlib import Path


####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# Path to your processing script
_CHECK_PATH = os.path.join(_ROOT_DIR, "check_path.py")


def run_batch(input_folder: str):
    folder = Path(input_folder)

    # 1. check folder exists
    if not folder.exists() or not folder.is_dir():
        print(f"[ERROR] Folder not found: {input_folder}")
        sys.exit(1)

    # 2. find csv files
    csv_files = list(folder.glob("*.csv"))

    if not csv_files:
        print(f"[WARNING] No CSV files found in: {input_folder}")
        return

    print(f"[INFO] Found {len(csv_files)} CSV files")

    # 3. process each file
    for csv_file in csv_files:
        print(f"[INFO] Processing: {csv_file}")

        try:
            result = subprocess.run(
                ["python", _CHECK_PATH, "-i", str(csv_file)],
                check=True,
                capture_output=True,
                text=True
            )

            # result = subprocess.run(
            #     ["python", _CHECK_PATH, "-i", str(csv_file), "-d", str("1"), "-e", str("45"), "--dry-run"],
            #     check=True,
            #     capture_output=True,
            #     text=True
            # )

            # optional: print script output
            if result.stdout:
                print(result.stdout)

        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed on {csv_file}")
            print(e.stderr)


def main():
    parser = argparse.ArgumentParser(description="Batch CSV processor")
    parser.add_argument("-i", "--input", required=True, help="Input folder containing CSV files")

    args = parser.parse_args()

    run_batch(args.input)


if __name__ == "__main__":
    main()
