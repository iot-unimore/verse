#!/usr/bin/env python3

"""
locata_relative_coordinates.py

Read two LOCATA position files:
    1. array position file
    2. source position file

Compute the source position relative to the array and output:
    - normalized time [0..1]
    - azimuth (deg)
    - elevation (deg)
    - distance (m)

The script:
    - ignores timestamps in output
    - ignores reference vectors
    - ignores rotation matrices
    - optionally resamples to N uniformly spaced values

Example:
    python locata_relative_coordinates.py \
        --array array_pose.txt \
        --source source_pose.txt \
        --output relative_positions.txt \
        -n 100
"""

import os
import argparse
import numpy as np
import pandas as pd

####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../../", "resources")
_DATASET_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../../", "datasets")

_FFPROBE_EXE = "/usr/bin/ffprobe"
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_MKVEXTRACT_EXE = "/usr/bin/mkvextract"
_MKVMERGE_EXE = "/usr/bin/mkvmerge"

# ============================================================
# Utilities
# ============================================================

def timestamp_to_seconds(df):
    """
    Convert LOCATA timestamps to floating-point seconds.
    """
    return (
        df["hour"] * 3600.0
        + df["minute"] * 60.0
        + df["second"]
    )


def spherical_coordinates(relative_xyz):
    """
    Convert Cartesian coordinates to spherical coordinates.

    Parameters
    ----------
    relative_xyz : ndarray, shape (N, 3)

    Returns
    -------
    azimuth_deg : ndarray
        Azimuth angle in degrees.
        Range: [-180, 180]

    elevation_deg : ndarray
        Elevation angle in degrees.
        Range: [-90, 90]

    distance : ndarray
        Euclidean distance.
    """

    x = relative_xyz[:, 0]
    y = relative_xyz[:, 1]
    z = relative_xyz[:, 2]

    distance = np.sqrt(x**2 + y**2 + z**2)

    azimuth = np.arctan2(y, x)

    horizontal_dist = np.sqrt(x**2 + y**2)
    elevation = np.arctan2(z, horizontal_dist)

    azimuth_deg = np.degrees(azimuth)
    elevation_deg = np.degrees(elevation)

    return azimuth_deg, elevation_deg, distance


def interpolate_positions(times_old, positions_old, times_new):
    """
    Interpolate xyz positions independently.
    """

    x = np.interp(times_new, times_old, positions_old[:, 0])
    y = np.interp(times_new, times_old, positions_old[:, 1])
    z = np.interp(times_new, times_old, positions_old[:, 2])

    return np.column_stack((x, y, z))


# ============================================================
# Main processing
# ============================================================

def process(array_file, source_file, output_file, n_samples=None):

    # --------------------------------------------------------
    # Read files
    # --------------------------------------------------------

    array_df = pd.read_csv(array_file, sep='\s+')
    source_df = pd.read_csv(source_file, sep='\s+')

    # --------------------------------------------------------
    # Extract timestamps
    # --------------------------------------------------------

    array_time = timestamp_to_seconds(array_df)
    source_time = timestamp_to_seconds(source_df)

    # Normalize both timelines to start at 0
    array_time = array_time - array_time.iloc[0]
    source_time = source_time - source_time.iloc[0]

    # --------------------------------------------------------
    # Extract xyz positions
    # --------------------------------------------------------

    array_xyz = array_df[["x", "y", "z"]].values
    source_xyz = source_df[["x", "y", "z"]].values

    # --------------------------------------------------------
    # Determine common timeline
    # --------------------------------------------------------

    t_start = max(array_time.min(), source_time.min())
    t_end = min(array_time.max(), source_time.max())

    if t_end <= t_start:
        raise RuntimeError("No overlapping timestamps between files.")

    # Number of output samples
    if n_samples is None:
        n_samples = min(len(array_df), len(source_df))

    # Uniform time grid
    t_uniform = np.linspace(t_start, t_end, n_samples)

    # --------------------------------------------------------
    # Interpolate positions
    # --------------------------------------------------------

    array_interp = interpolate_positions(
        array_time.values,
        array_xyz,
        t_uniform
    )

    source_interp = interpolate_positions(
        source_time.values,
        source_xyz,
        t_uniform
    )

    # --------------------------------------------------------
    # Relative position: source w.r.t array
    # --------------------------------------------------------

    relative_xyz = source_interp - array_interp

    # --------------------------------------------------------
    # Convert to spherical coordinates
    # --------------------------------------------------------

    azimuth_deg, elevation_deg, distance = spherical_coordinates(relative_xyz)

    # --------------------------------------------------------
    # Normalized time [0..1]
    # --------------------------------------------------------

    normalized_time = (
        (t_uniform - t_uniform[0])
        / (t_uniform[-1] - t_uniform[0])
    )

    # --------------------------------------------------------
    # Save output
    # --------------------------------------------------------

    # Write header manually with "#"
    with open(output_file, "w") as f:
        f.write("#audio_path\n")
        f.write("#syntax_ver:1.0\n")
        f.write("#time[%], volume[%], azimuth[degree], elevation[degree], distance[metre], spherical(s)/cartesian(c)\n")

    output_df = pd.DataFrame({
        "time_percent": normalized_time*100,
        "volume_percent": 100,
        "azimuth_deg": azimuth_deg,
        "elevation_deg": elevation_deg,
        "distance_m": distance,
        "spherical/cartesian": "s"
    })

    output_df.to_csv(
        output_file,
        sep=",",
        index=False,
        header=False,
        mode="a",
        float_format="%.6f"
    )

    print(f"Saved {len(output_df)} samples to: {output_file}")


# ============================================================
# CLI
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Compute relative spherical coordinates "
                    "between LOCATA array and source positions."
    )

    parser.add_argument(
        "--array",
        required=True,
        help="LOCATA array position file"
    )

    parser.add_argument(
        "--source",
        required=True,
        help="LOCATA source position file"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output file"
    )

    parser.add_argument(
        "-n",
        "--num-samples",
        type=int,
        default=None,
        help="Number of uniformly spaced output samples"
    )

    args = parser.parse_args()

    process(
        array_file=args.array,
        source_file=args.source,
        output_file=args.output,
        n_samples=args.num_samples
    )


if __name__ == "__main__":
    main()
