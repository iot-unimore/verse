#!/usr/bin/env python3

"""
modify_spatial_csv.py

Modify spherical spatial coordinates in a CSV file.

Supported modifications:
    --azimuth     add offset to azimuth [deg]
    --elevation   add offset to elevation [deg]
    --distance    add offset to distance [m]
    --translate   apply Cartesian translation (x y z)

Processing order:
    1. spherical modifications
    2. spherical -> Cartesian conversion
    3. Cartesian translation
    4. Cartesian -> spherical conversion

Output format remains identical to the input.

Example:
    python modify_spatial_csv.py \
        --input input.csv \
        --output output.csv \
        --azimuth 30 \
        --translate 1.0 0.0 -0.5
"""

import argparse
import numpy as np
import pandas as pd


# ============================================================
# Helpers
# ============================================================

def wrap_azimuth_360(azimuth):
    """
    Wrap azimuth into [0, 360).
    """
    return azimuth % 360.0


def clamp_elevation(elevation):
    """
    Clamp elevation into [-90, 90].
    """
    return elevation.clip(-90.0, 90.0)


def clamp_distance(distance):
    """
    Prevent negative distances.
    """
    return distance.clip(lower=0.0)


# ============================================================
# Spherical <-> Cartesian
# ============================================================

def spherical_to_cartesian(azimuth_deg, elevation_deg, distance):
    """
    Convert spherical coordinates to Cartesian.

    Azimuth:
        0°   -> +x
        90°  -> +y

    Elevation:
        0°   -> horizontal plane
        +90° -> +z
    """

    azimuth_rad = np.radians(azimuth_deg)
    elevation_rad = np.radians(elevation_deg)

    x = distance * np.cos(elevation_rad) * np.cos(azimuth_rad)
    y = distance * np.cos(elevation_rad) * np.sin(azimuth_rad)
    z = distance * np.sin(elevation_rad)

    return x, y, z


def cartesian_to_spherical(x, y, z):
    """
    Convert Cartesian coordinates to spherical.
    """

    distance = np.sqrt(x**2 + y**2 + z**2)

    azimuth_rad = np.arctan2(y, x)
    azimuth_deg = np.degrees(azimuth_rad)
    azimuth_deg = wrap_azimuth_360(azimuth_deg)

    horizontal_dist = np.sqrt(x**2 + y**2)

    elevation_rad = np.arctan2(z, horizontal_dist)
    elevation_deg = np.degrees(elevation_rad)

    return azimuth_deg, elevation_deg, distance


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Modify spherical coordinates in a spatial CSV file."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Input CSV file"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output CSV file"
    )

    parser.add_argument(
        "--azimuth",
        type=float,
        default=None,
        help="Azimuth offset in degrees"
    )

    parser.add_argument(
        "--elevation",
        type=float,
        default=None,
        help="Elevation offset in degrees"
    )

    parser.add_argument(
        "--distance",
        type=float,
        default=None,
        help="Distance offset in meters"
    )

    parser.add_argument(
        "--translate",
        nargs=3,
        type=float,
        metavar=("X", "Y", "Z"),
        default=None,
        help="Cartesian translation vector"
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Read comment/header lines manually
    # --------------------------------------------------------

    header_lines = []

    with open(args.input, "r") as f:

        while True:

            pos = f.tell()
            line = f.readline()

            if not line.startswith("#"):
                f.seek(pos)
                break

            header_lines.append(line)

        df = pd.read_csv(
            f,
            header=None,
            names=[
                "time_percent",
                "volume_percent",
                "azimuth_deg",
                "elevation_deg",
                "distance_m",
                "coord_type"
            ]
        )

    # --------------------------------------------------------
    # Apply spherical modifications
    # --------------------------------------------------------

    if args.azimuth is not None:
        df["azimuth_deg"] += args.azimuth
        df["azimuth_deg"] = wrap_azimuth_360(df["azimuth_deg"])

    if args.elevation is not None:
        df["elevation_deg"] += args.elevation
        df["elevation_deg"] = clamp_elevation(df["elevation_deg"])

    if args.distance is not None:
        df["distance_m"] += args.distance
        df["distance_m"] = clamp_distance(df["distance_m"])

    # --------------------------------------------------------
    # Apply Cartesian translation
    # --------------------------------------------------------

    if args.translate is not None:

        tx, ty, tz = args.translate

        # spherical -> Cartesian
        x, y, z = spherical_to_cartesian(
            df["azimuth_deg"].values,
            df["elevation_deg"].values,
            df["distance_m"].values
        )

        # Apply translation
        x += tx
        y += ty
        z += tz

        # Cartesian -> spherical
        azimuth_deg, elevation_deg, distance_m = (
            cartesian_to_spherical(x, y, z)
        )

        df["azimuth_deg"] = azimuth_deg
        df["elevation_deg"] = elevation_deg
        df["distance_m"] = distance_m

    # --------------------------------------------------------
    # Final safety normalization
    # --------------------------------------------------------

    df["azimuth_deg"] = wrap_azimuth_360(df["azimuth_deg"])
    df["elevation_deg"] = clamp_elevation(df["elevation_deg"])
    df["distance_m"] = clamp_distance(df["distance_m"])

    # --------------------------------------------------------
    # Write output
    # --------------------------------------------------------

    with open(args.output, "w") as f:

        # Preserve original headers/comments
        for line in header_lines:
            f.write(line)

        # Write CSV data
        df.to_csv(
            f,
            index=False,
            header=False,
            sep=",",
            float_format="%.6f"
        )

    print(f"Modified CSV written to: {args.output}")


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":
    main()
