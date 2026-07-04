#!/usr/bin/env python3

import argparse
import csv
import os
import sys


####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))


def clamp_angle(x: int) -> int:
    return max(0, min(359, x))


def validate_audio_path_file(lines):
    """
    Ensures first non-empty line is '#audio_path'
    """
    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped != "#audio_path":
            print("[ERROR] Invalid file format.")
            print("First non-empty line must be: #audio_path")
            print(f"Line {i + 1}: {stripped}")
            sys.exit(1)

        return  # valid

    print("[ERROR] Empty file or missing #audio_path header")
    sys.exit(1)


def process_file(input_path: str, output_path: str):
    processed_rows = []

    last_az = None
    last_el = None

    # -----------------------------
    # Read file once
    # -----------------------------
    with open(input_path, "r", newline="") as f:
        lines = f.readlines()

    # -----------------------------
    # Validate format early
    # -----------------------------
    validate_audio_path_file(lines)

    # -----------------------------
    # CSV parsing
    # -----------------------------
    reader = csv.reader(lines)

    header_lines = []

    for row in reader:
        if not row:
            continue

        # keep header/comment lines
        if row[0].startswith("#"):
            header_lines.append(row)
            continue

        # strict column check (important for stability)
        if len(row) < 6:
            continue

        try:
            time = float(row[0])
            volume = int(row[1])
            az = float(row[2])
            el = float(row[3])
            dist = float(row[4])
            mode = row[5].strip()
        except ValueError:
            continue

        # round + clamp
        az_i = clamp_angle(int(round(az)))
        el_i = clamp_angle(int(round(el)))

        # skip consecutive duplicates (az, el only)
        if last_az == az_i and last_el == el_i:
            continue

        last_az = az_i
        last_el = el_i

        processed_rows.append([
            f"{time:.6f}",
            str(volume),
            str(az_i),
            str(el_i),
            f"{dist:.6f}",
            mode
        ])

    # -----------------------------
    # Write output
    # -----------------------------
    with open(output_path, "w", newline="") as f:
        for h in header_lines:
            f.write(",".join(h) + "\n")

        writer = csv.writer(f)
        writer.writerows(processed_rows)


def main():
    parser = argparse.ArgumentParser(description="Process audio CSV file")

    parser.add_argument("-i", "--input", required=True, help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file (optional)")

    args = parser.parse_args()

    output_path = args.output if args.output else args.input

    process_file(args.input, output_path)


if __name__ == "__main__":
    main()