#!/usr/bin/env python3
"""Normalize a VERSE dynamic path trajectory CSV (the 'audio_path' format used
under resources/paths/{subtype}/files/*.csv, referenced by scene 'dynamic'
positions via a path_map yaml).

Raw trajectory CSVs can contain unwrapped azimuth values outside the nominal
[0, 360) range (e.g. produced by motion-capture/unwrapping upstream, values
observed as low as -174 deg and as high as 529 deg) and sub-degree precision
that is not meaningful for downstream rendering. This script rewrites the
file so that:
  - azimuth is wrapped into [0, 359] (it is a circular quantity),
  - elevation is clamped into [-90, 90] (it is not circular),
  - both are rounded to whole degrees,
  - consecutive rows that round to the same (azimuth, elevation) are
    collapsed to the first occurrence, to drop redundant near-static samples.

Rows that are malformed (wrong column count or non-numeric fields) are
dropped silently. Comment/header lines ('#...') are preserved as-is.

Two optional caps can be applied on top of the above:
  -d/--distance-range: a minimum distance (metres); points closer to the
    origin than this are pushed out to this value. Unset by default, in
    which case distance is left untouched.
  -e/--elevation-range: a symmetric elevation range in degrees (e.g. 45
    caps elevation into [-45, 45]) applied in addition to the always-on
    physical [-90, 90] bound. Unset by default.

Every time a point's distance or elevation is actually changed by capping
(whether from the always-on physical elevation bound or from -d/-e), a
[WARN] line is printed identifying the affected row. After processing, a
summary [INFO] line reports the resulting azimuth/elevation/distance ranges.

By default the output overwrites the input file in place; pass -o/--output
to write to a different file instead, or --dry-run to parse and report
without writing anything.
"""

import argparse
import csv
import os
import sys


####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))


def wrap_azimuth(x: int) -> int:
    """Azimuth is circular: wrap into [0, 359] instead of clamping, so values
    outside the nominal range (e.g. from unwrapped trajectory data) land on
    their true angle rather than being flattened to the boundary."""
    return x % 360


def clamp_elevation(x: int, max_abs: float = None) -> int:
    """Elevation is not circular: always clamp into the physical [-90, 90]
    range. If `max_abs` is given (e.g. 45), further clamp into the
    symmetric [-max_abs, max_abs] range on top of the physical bound;
    if `max_abs` is None, only the physical bound applies."""
    x = max(-90, min(90, x))
    if max_abs is not None:
        x = max(-max_abs, min(max_abs, x))
    return int(x)


def cap_min_distance(dist: float, min_distance: float = None) -> float:
    """Cap the path point's distance-from-origin to a floor: if
    `min_distance` is given and `dist` is below it, return `min_distance`
    instead; if `min_distance` is None, return `dist` unchanged (no
    capping)."""
    if min_distance is None:
        return dist
    return max(dist, min_distance)


def validate_audio_path_file(lines):
    """Validate that `lines` (as returned by file.readlines()) is a well-formed
    audio_path file: the first non-empty line must be exactly '#audio_path'.
    Exits the process with status 1 and an [ERROR] message if the file is
    empty or the header is missing/incorrect; returns None on success."""
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


def process_file(
    input_path: str,
    output_path: str,
    min_distance: float = None,
    elevation_range: float = None,
    dry_run: bool = False,
):
    """Read the audio_path CSV at `input_path`, normalize it (wrap azimuth,
    clamp elevation, round both to whole degrees, drop malformed rows and
    consecutive (azimuth, elevation) duplicates -- see module docstring for
    the full rationale), and write the result to `output_path`. Comment/
    header lines are copied through unchanged. `output_path` may be the same
    as `input_path`, in which case the file is overwritten in place.

    `min_distance`, if given, floors every point's distance to that value
    (no capping if None). `elevation_range`, if given, additionally clamps
    elevation into [-elevation_range, elevation_range] on top of the
    physical [-90, 90] bound (no extra capping if None). Whenever a point's
    distance or elevation is actually changed by capping, a [WARN] line is
    printed identifying the offending row. After processing, an [INFO]
    summary line reports the min/max azimuth, elevation and distance of the
    kept (post-dedup) rows. If `dry_run` is True, the file is parsed and
    these messages are still printed, but the output is not written."""
    processed_rows = []

    last_az = None
    last_el = None
    data_row_num = 0

    az_values = []
    el_values = []
    dist_values = []

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

        data_row_num += 1

        # round + wrap/clamp
        az_i = wrap_azimuth(int(round(az)))

        el_rounded = int(round(el))
        el_i = clamp_elevation(el_rounded, elevation_range)
        if el_i != el_rounded:
            print(
                f"[WARN] row {data_row_num} (time={time:.3f}): elevation {el_rounded}deg "
                f"capped to {el_i}deg"
            )

        dist_capped = cap_min_distance(dist, min_distance)
        if dist_capped != dist:
            print(
                f"[WARN] row {data_row_num} (time={time:.3f}): distance {dist:.3f}m "
                f"capped to {dist_capped:.3f}m (minimum {min_distance:.3f}m)"
            )
        dist = dist_capped

        # skip consecutive duplicates (az, el only)
        if last_az == az_i and last_el == el_i:
            continue

        last_az = az_i
        last_el = el_i

        az_values.append(az_i)
        el_values.append(el_i)
        dist_values.append(dist)

        processed_rows.append([
            f"{time:.6f}",
            str(volume),
            str(az_i),
            str(el_i),
            f"{dist:.6f}",
            mode
        ])

    # -----------------------------
    # Summary
    # -----------------------------
    if az_values:
        print(
            f"[INFO] azimuth range: {min(az_values)}..{max(az_values)}deg, "
            f"elevation range: {min(el_values)}..{max(el_values)}deg, "
            f"distance range: {min(dist_values):.1f}..{max(dist_values):.1f}m"
        )
    else:
        print("[INFO] no valid data rows to summarize")

    # -----------------------------
    # Write output
    # -----------------------------
    if dry_run:
        print(f"[INFO] dry-run: skipped writing {output_path} ({len(processed_rows)} row(s) would be written)")
        return

    with open(output_path, "w", newline="") as f:
        for h in header_lines:
            f.write(",".join(h) + "\n")

        writer = csv.writer(f)
        writer.writerows(processed_rows)


def main():
    """CLI entry point: parse -i/--input (required), -o/--output (optional,
    defaults to overwriting the input file), -d/--distance-range,
    -e/--elevation-range and --dry-run, then normalize the given audio_path
    CSV via process_file()."""
    parser = argparse.ArgumentParser(description="Process audio CSV file")

    parser.add_argument("-i", "--input", required=True, help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file (optional)")
    parser.add_argument(
        "-d",
        "--distance-range",
        type=float,
        default=None,
        help="minimum distance in metres; points closer to the origin than this are "
        "pushed out to this value. If not set, distance is not capped (default: %(default)s)",
    )
    parser.add_argument(
        "-e",
        "--elevation-range",
        type=float,
        default=None,
        help="symmetric elevation range in degrees, e.g. 45 caps elevation into [-45, 45]. "
        "If not set, only the physical [-90, 90] bound is applied (default: %(default)s)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="parse and report (including capping warnings) without writing the output file "
        "(default: %(default)s)",
    )

    args = parser.parse_args()

    output_path = args.output if args.output else args.input

    process_file(args.input, output_path, args.distance_range, args.elevation_range, args.dry_run)


if __name__ == "__main__":
    main()