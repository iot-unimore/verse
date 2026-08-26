#!/usr/bin/env python3
"""
Scan a LOCATA-format dataset and report the min/max elevation angle found
across every position_source*.txt file, expressed in two conventions:

  - "from Z axis" (polar angle theta): 0deg = +Z (straight up),
    90deg = horizontal (xy plane), 180deg = -Z (straight down).
  - "from XY plane" (AES69-2022 elevation): -90deg = -Z (straight down),
    0deg = horizontal (xy plane), +90deg = +Z (straight up).

Elevation is computed relative to the listener/array, taken as the origin:
for each position_source_*.txt, x/y/z is read alongside the sibling
position_array_<array_folder>.txt (same recording folder), and the array's
position is subtracted row-by-row before the elevation angle is derived.


Reports min/max and the 1-sigma (mean +/- std) range over every valid data
point (not per-file averages), plus an ASCII histogram of the "from XY plane" elevation --
VERSE's own native elevation convention (see spherical_to_cartesian() in
convert_dataset_verse2locata.py) -- over a configurable range/step.

Also reports min/max/avg duration of the audio_array*.wav files (one per
array folder, probed with ffprobe).
"""

import argparse
import glob
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

_FFPROBE_EXE = "/usr/bin/ffprobe"


def elevation_from_xyz(x, y, z):
    """Return (elevation_from_z_axis_deg, elevation_from_xy_plane_deg) arrays.

    Rows where the source sits exactly at the listener (r == 0, elevation
    undefined) come back as NaN.
    """

    r = np.sqrt(x**2 + y**2 + z**2)

    cos_theta = np.full_like(r, np.nan)
    valid = r > 0
    cos_theta[valid] = np.clip(z[valid] / r[valid], -1.0, 1.0)

    elevation_from_z = np.degrees(np.arccos(cos_theta))
    elevation_from_xy = 90.0 - elevation_from_z

    return elevation_from_z, elevation_from_xy


def _read_xyz(path):
    """Read a LOCATA position file and return its x, y, z columns as float
    numpy arrays, or None (with a warning) if the file can't be used."""

    try:
        df = pd.read_csv(path, sep=r"\s+")
    except Exception as exc:
        print(f"WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return None

    for col in ("x", "y", "z"):
        if col not in df.columns:
            print(f"WARNING: {path} missing column '{col}', skipped", file=sys.stderr)
            return None

    if len(df) == 0:
        return None

    return df[["x", "y", "z"]].to_numpy(dtype=float)


def scan_file(path):
    """Return (elevation_from_z_deg, elevation_from_xy_deg) arrays for one
    position_source*.txt file, with the listener/array position subtracted
    out first, or None if the file could not be used."""

    source_xyz = _read_xyz(path)
    if source_xyz is None:
        return None

    array_folder = os.path.dirname(path)
    array_folder_name = os.path.basename(array_folder)
    array_path = os.path.join(array_folder, f"position_array_{array_folder_name}.txt")

    if not os.path.isfile(array_path):
        print(f"WARNING: {path}: no matching {os.path.basename(array_path)}, skipped", file=sys.stderr)
        return None

    array_xyz = _read_xyz(array_path)
    if array_xyz is None:
        return None

    if len(array_xyz) != len(source_xyz):
        print(
            f"WARNING: {path}: row count ({len(source_xyz)}) does not match "
            f"{os.path.basename(array_path)} ({len(array_xyz)}), skipped",
            file=sys.stderr
        )
        return None

    relative_xyz = source_xyz - array_xyz

    x, y, z = relative_xyz[:, 0], relative_xyz[:, 1], relative_xyz[:, 2]

    r = np.sqrt(x**2 + y**2 + z**2)
    n_origin = int(np.sum(r == 0))
    if n_origin:
        print(
            f"WARNING: {path}: {n_origin} row(s) with source at the listener "
            f"(r=0), elevation undefined there, excluded",
            file=sys.stderr
        )

    return elevation_from_xyz(x, y, z)


def get_wav_duration(path):
    """Return the duration in seconds (float) of a wav file via ffprobe, or
    None (with a warning) if it can't be determined."""

    cmd = [
        _FFPROBE_EXE,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, OSError) as exc:
        print(f"WARNING: cannot probe duration of {path}: {exc}", file=sys.stderr)
        return None


def ascii_histogram(data, lo, hi, step, width=50):
    """Render a fixed-width ASCII bar-chart histogram of `data` over
    [lo, hi] in bins of size `step`. Returns (lines, n_below, n_above),
    where n_below/n_above count values outside [lo, hi] (never silently
    dropped -- the caller reports them separately)."""

    edges = np.arange(lo, hi + step, step)
    counts, edges = np.histogram(data, bins=edges)

    n_below = int(np.sum(data < lo))
    n_above = int(np.sum(data > hi))

    max_count = int(counts.max()) if counts.size else 0

    lines = []
    for i in range(len(counts)):
        bar_len = round(width * counts[i] / max_count) if max_count > 0 else 0
        bar = "#" * bar_len
        lines.append(f"  [{edges[i]:6.1f}, {edges[i + 1]:6.1f}) {bar} ({counts[i]})")

    return lines, n_below, n_above


def main():
    parser = argparse.ArgumentParser(
        description="Report min/max elevation angle (relative to the "
                     "listener/array) across all position_source*.txt "
                     "files found under a LOCATA dataset root, plus "
                     "audio_array*.wav duration stats."
    )

    parser.add_argument(
        "dataset_root",
        help="Root folder of the LOCATA dataset to scan (searched recursively)"
    )

    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Also print min/max elevation for each individual file"
    )

    parser.add_argument(
        "-f", "--filter",
        default=None,
        help="Only consider recordings whose device-prefixed array folder "
             "(the position_source*.txt's parent directory, e.g. "
             "'unimore_head_003_auralys2ch') contains this substring. "
             "E.g. '-f auralys2ch' keeps '..._auralys2ch' folders and "
             "excludes '..._auralys6ch' ones, regardless of the device "
             "prefix."
    )

    parser.add_argument(
        "-j", "--jobs",
        type=int,
        default=os.cpu_count() or 4,
        help="Number of worker threads to scan files with (default: cpu count)"
    )

    parser.add_argument(
        "--no-histogram",
        action="store_true",
        help="Skip the ASCII histogram"
    )

    parser.add_argument(
        "--hist-min", type=float, default=-50.0,
        help="Histogram lower bound in degrees, verse (xy-plane) convention (default: -50)"
    )

    parser.add_argument(
        "--hist-max", type=float, default=50.0,
        help="Histogram upper bound in degrees, verse (xy-plane) convention (default: 50)"
    )

    parser.add_argument(
        "--hist-step", type=float, default=2.0,
        help="Histogram bin width in degrees (default: 2)"
    )

    parser.add_argument(
        "--no-duration",
        action="store_true",
        help="Skip probing audio_array*.wav durations with ffprobe"
    )

    args = parser.parse_args()

    pattern = os.path.join(args.dataset_root, "**", "position_source*.txt")
    files = sorted(glob.glob(pattern, recursive=True))

    if args.filter:
        files = [f for f in files if args.filter in os.path.basename(os.path.dirname(f))]

    if not files:
        filter_msg = f" matching filter '{args.filter}'" if args.filter else ""
        print(f"No position_source*.txt files found under: {args.dataset_root}{filter_msg}", file=sys.stderr)
        sys.exit(1)

    global_min_z, global_max_z = np.inf, -np.inf
    global_min_xy, global_max_xy = np.inf, -np.inf
    min_z_file = max_z_file = min_xy_file = max_xy_file = None

    n_files_used = 0
    all_el_z = []
    all_el_xy = []

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for path, result in zip(files, pool.map(scan_file, files)):
            if result is None:
                continue

            el_z, el_xy = result
            valid = ~np.isnan(el_z)
            if not np.any(valid):
                continue

            el_z, el_xy = el_z[valid], el_xy[valid]

            n_files_used += 1
            all_el_z.append(el_z)
            all_el_xy.append(el_xy)

            file_min_z = el_z.min()
            file_max_z = el_z.max()
            file_min_xy = el_xy.min()
            file_max_xy = el_xy.max()

            if args.per_file:
                print(
                    f"{path}: from_z=[{file_min_z:.2f}, {file_max_z:.2f}]  "
                    f"from_xy=[{file_min_xy:.2f}, {file_max_xy:.2f}]"
                )

            if file_min_z < global_min_z:
                global_min_z, min_z_file = file_min_z, path
            if file_max_z > global_max_z:
                global_max_z, max_z_file = file_max_z, path
            if file_min_xy < global_min_xy:
                global_min_xy, min_xy_file = file_min_xy, path
            if file_max_xy > global_max_xy:
                global_max_xy, max_xy_file = file_max_xy, path

    if n_files_used == 0:
        print("No usable data found in any position_source*.txt file.", file=sys.stderr)
        sys.exit(1)

    all_el_z = np.concatenate(all_el_z)
    all_el_xy = np.concatenate(all_el_xy)

    print()
    print(f"Scanned {n_files_used}/{len(files)} position_source*.txt files "
          f"({all_el_z.size:,} data points) under: {args.dataset_root}")
    print()
    mean_z, std_z = all_el_z.mean(), all_el_z.std()
    mean_xy, std_xy = all_el_xy.mean(), all_el_xy.std()

    print("Elevation from Z axis (0deg=+Z, 90deg=horizontal, 180deg=-Z):")
    print(f"  min      = {global_min_z:8.3f} deg  ({min_z_file})")
    print(f"  max      = {global_max_z:8.3f} deg  ({max_z_file})")
    print(f"  1-sigma  = [{mean_z - std_z:8.3f}, {mean_z + std_z:8.3f}] deg  (mean={mean_z:.3f}, std={std_z:.3f})")
    print()
    print("Elevation from XY plane, AES69-2022 / verse convention (-90deg=-Z, 0deg=horizontal, +90deg=+Z):")
    print(f"  min      = {global_min_xy:8.3f} deg  ({min_xy_file})")
    print(f"  max      = {global_max_xy:8.3f} deg  ({max_xy_file})")
    print(f"  1-sigma  = [{mean_xy - std_xy:8.3f}, {mean_xy + std_xy:8.3f}] deg  (mean={mean_xy:.3f}, std={std_xy:.3f})")

    if not args.no_histogram:
        lines, n_below, n_above = ascii_histogram(
            all_el_xy, args.hist_min, args.hist_max, args.hist_step
        )
        print()
        print(
            f"Histogram of elevation from XY plane (verse/AES69 convention), "
            f"[{args.hist_min:g}, {args.hist_max:g}] deg, {args.hist_step:g} deg bins:"
        )
        for line in lines:
            print(line)
        if n_below:
            print(f"  below {args.hist_min:g} deg: {n_below}")
        if n_above:
            print(f"  above {args.hist_max:g} deg: {n_above}")

    if not args.no_duration:
        # one audio_array_<array_folder>.wav per array folder, shared by every
        # source (talker) in that folder -- probe each folder's wav once
        array_dirs = sorted({os.path.dirname(f) for f in files})
        wav_paths = []
        for d in array_dirs:
            wav_path = os.path.join(d, f"audio_array_{os.path.basename(d)}.wav")
            if os.path.isfile(wav_path):
                wav_paths.append(wav_path)
            else:
                print(f"WARNING: no matching audio_array wav for folder: {d}", file=sys.stderr)

        durations = []
        duration_paths = []
        if wav_paths:
            with ThreadPoolExecutor(max_workers=args.jobs) as pool:
                for path, dur in zip(wav_paths, pool.map(get_wav_duration, wav_paths)):
                    if dur is not None:
                        durations.append(dur)
                        duration_paths.append(path)

        print()
        if durations:
            durations = np.array(durations)
            idx_min = int(np.argmin(durations))
            idx_max = int(np.argmax(durations))
            print(f"Audio array (.wav) duration across {len(durations)}/{len(wav_paths)} recording(s):")
            print(f"  min = {durations[idx_min]:8.3f} s  ({duration_paths[idx_min]})")
            print(f"  max = {durations[idx_max]:8.3f} s  ({duration_paths[idx_max]})")
            print(f"  avg = {durations.mean():8.3f} s")
        else:
            print("No audio_array*.wav durations could be determined.", file=sys.stderr)


if __name__ == "__main__":
    main()
