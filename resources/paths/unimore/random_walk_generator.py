#!/usr/bin/env python3

import argparse
import csv
import random


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

POINTS = 101  # 0% to 100%

ELEVATION_MIN = -45
ELEVATION_MAX = 45

DISTANCE_MIN = 1.0
DISTANCE_MAX = 3.0


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def normalize_azimuth(value):
    """
    Keep azimuth continuous.

    No wrapping is performed because multiple rotations
    are allowed and useful for spatial audio paths.
    """
    return value


# ---------------------------------------------------------
# Random walk generator
# ---------------------------------------------------------


def generate_walk(continuity, azimuth_begin=None, azimuth_end=None):
    """
    Generate a spherical-coordinate random walk.

    continuity:
        0  -> highly random, folded paths
        10 -> smooth continuous motion

    azimuth_begin:
        Optional forced initial azimuth.

    azimuth_end:
        Optional forced final azimuth.
    """

    # -----------------------------------------------------
    # Initial position
    # -----------------------------------------------------

    if azimuth_begin is not None:
        azimuth = azimuth_begin
    else:
        azimuth = random.uniform(0, 360)

    elevation = random.uniform(-20, 20)
    distance = random.uniform(DISTANCE_MIN, DISTANCE_MAX)

    # -----------------------------------------------------
    # Initial velocities
    # -----------------------------------------------------

    az_velocity = random.uniform(-3, 3)
    el_velocity = random.uniform(-1, 1)
    dist_velocity = random.uniform(-0.02, 0.02)

    result = []

    # -----------------------------------------------------
    # Continuity model
    #
    # low continuity:
    #   weak inertia -> direction changes often
    #
    # high continuity:
    #   strong inertia -> smooth movement
    # -----------------------------------------------------

    inertia = 0.15 + (continuity / 10.0) * 0.80

    # Probability of changing direction

    turn_probability = 1.0 - (continuity / 10.0)

    for percentage in range(POINTS):
        if percentage > 0:
            # -------------------------------------------------
            # AZIMUTH
            # -------------------------------------------------

            if azimuth_end is not None:
                # Forced destination mode

                remaining = POINTS - percentage

                target_velocity = (azimuth_end - azimuth) / remaining

                az_velocity = inertia * az_velocity + (1 - inertia) * target_velocity

            else:
                # Free random walk

                if random.random() < turn_probability:
                    # Sudden direction change
                    # creates folded trajectories

                    az_velocity += random.uniform(-20, 20)

                else:
                    # Small perturbation

                    az_velocity += random.uniform(-5, 5)

                az_velocity = clamp(az_velocity, -15, 15)

                # Apply inertia

                az_velocity *= inertia

            azimuth += az_velocity

            # -------------------------------------------------
            # ELEVATION
            # -------------------------------------------------

            if random.random() < turn_probability:
                el_velocity += random.uniform(-8, 8)

            else:
                el_velocity += random.uniform(-2, 2)

            el_velocity = clamp(el_velocity, -6, 6)

            el_velocity *= inertia

            elevation += el_velocity

            # -------------------------------------------------
            # DISTANCE
            # -------------------------------------------------

            if random.random() < turn_probability:
                dist_velocity += random.uniform(-0.15, 0.15)

            else:
                dist_velocity += random.uniform(-0.05, 0.05)

            dist_velocity = clamp(dist_velocity, -0.1, 0.1)

            dist_velocity *= inertia

            distance += dist_velocity

            # -------------------------------------------------
            # Constraints
            # -------------------------------------------------

            elevation = clamp(elevation, ELEVATION_MIN, ELEVATION_MAX)

            distance = clamp(distance, DISTANCE_MIN, DISTANCE_MAX)

        result.append(
            {
                "time": percentage,
                "volume": 100,
                "azimuth": normalize_azimuth(azimuth),
                "elevation": elevation,
                "distance": distance,
            }
        )

    # -----------------------------------------------------
    # Force exact final azimuth
    # -----------------------------------------------------

    if azimuth_end is not None:
        result[-1]["azimuth"] = azimuth_end

    return result


# ---------------------------------------------------------
# CSV writer
# ---------------------------------------------------------


def write_csv(filename, walk):

    with open(filename, "w", newline="") as f:
        f.write("#audio_path\n")
        f.write("#syntax_ver:1.0\n")

        f.write(
            "#time[%], volume[%], azimuth[degree], "
            "elevation[degree], distance[metre], "
            "spherical(s)/cartesian(c)\n"
        )

        writer = csv.writer(f)

        for p in walk:
            writer.writerow(
                [
                    f"{p['time']:05.2f}",
                    p["volume"],
                    int(round(p["azimuth"])),
                    int(round(p["elevation"])),
                    f"{p['distance']:.3f}",
                    "s",
                ]
            )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------


def main():

    parser = argparse.ArgumentParser(
        description="Generate a 3D spherical-coordinate random walk audio path."
    )

    parser.add_argument(
        "-o", "--output", default="./mywalk.csv", help="Output CSV filename"
    )

    parser.add_argument(
        "-c",
        "--continuity",
        type=int,
        choices=range(0, 11),
        default=6,
        help="Continuity level from 0 (folded/random) to 10 (smooth)",
    )

    parser.add_argument(
        "-b",
        "--begin",
        type=float,
        default=None,
        help="Starting azimuth angle in degrees",
    )

    parser.add_argument(
        "-e", "--end", type=float, default=None, help="Ending azimuth angle in degrees"
    )

    args = parser.parse_args()

    walk = generate_walk(args.continuity, args.begin, args.end)

    write_csv(args.output, walk)

    print(f"Generated {len(walk)} points in {args.output}")


if __name__ == "__main__":
    main()
