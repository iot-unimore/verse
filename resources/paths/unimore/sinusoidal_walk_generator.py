#!/usr/bin/env python3

import argparse
import csv
import math
import random


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

POINTS = 101

ELEVATION_MIN = -45
ELEVATION_MAX = 45

DISTANCE_MIN = 1.0
DISTANCE_MAX = 3.0


# ---------------------------------------------------------
# Utility
# ---------------------------------------------------------


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


# ---------------------------------------------------------
# Harmonic generator
# ---------------------------------------------------------


def harmonic_signal(t, amplitudes, frequencies, phases):
    """
    Superposition of sinusoidal components.
    """

    value = 0

    for a, f, p in zip(amplitudes, frequencies, phases):
        value += a * math.sin(2 * math.pi * f * t + p)

    return value


# ---------------------------------------------------------
# Generate path
# ---------------------------------------------------------


def generate_walk(continuity, azimuth_begin=None, azimuth_end=None):
    """
    Generate a sinusoidal spatial trajectory.

    continuity:
        0  -> faster oscillations
        10 -> very slow smooth movement
    """

    # -----------------------------------------------------
    # Continuity controls frequency bandwidth
    # -----------------------------------------------------

    smoothness = continuity / 10.0

    # Number of oscillations over the complete path

    min_frequency = 0.5 + continuity * 0.05

    max_frequency = 8 - continuity * 0.5

    # -----------------------------------------------------
    # Azimuth waveform
    # -----------------------------------------------------

    az_components = random.randint(2, 5)

    az_amplitudes = [random.uniform(10, 60) for _ in range(az_components)]

    az_frequencies = [
        random.uniform(min_frequency, max_frequency) for _ in range(az_components)
    ]

    az_phases = [random.uniform(0, 2 * math.pi) for _ in range(az_components)]

    # -----------------------------------------------------
    # Elevation waveform
    # -----------------------------------------------------

    el_components = random.randint(2, 4)

    el_amplitudes = [random.uniform(15, 45) for _ in range(el_components)]

    el_frequencies = [
        random.uniform(min_frequency, max_frequency) for _ in range(el_components)
    ]

    el_phases = [random.uniform(0, 2 * math.pi) for _ in range(el_components)]

    # Random center position

    az_center = azimuth_begin if azimuth_begin is not None else random.uniform(0, 360)

    el_center = random.uniform(-15, 15)

    result = []

    # -----------------------------------------------------
    # Distance random walk
    # -----------------------------------------------------

    distance = random.uniform(DISTANCE_MIN, DISTANCE_MAX)

    distance_speed = 0

    for percentage in range(POINTS):
        t = percentage / 100.0

        # ---------------------------------------------
        # Azimuth
        # ---------------------------------------------

        azimuth = az_center + harmonic_signal(
            t, az_amplitudes, az_frequencies, az_phases
        )

        # Optional endpoint constraint

        if azimuth_end is not None:
            correction = (azimuth_end - azimuth) * t

            azimuth += correction

        # ---------------------------------------------
        # Elevation
        # ---------------------------------------------

        elevation = el_center + harmonic_signal(
            t, el_amplitudes, el_frequencies, el_phases
        )

        elevation = clamp(elevation, ELEVATION_MIN, ELEVATION_MAX)

        # ---------------------------------------------
        # Distance random walk
        # ---------------------------------------------

        distance_speed += random.uniform(-0.02, 0.02)

        # Continuity controls distance smoothness

        distance_speed *= 0.5 + smoothness * 0.45

        distance += distance_speed

        distance = clamp(distance, DISTANCE_MIN, DISTANCE_MAX)

        result.append(
            {
                "time": percentage,
                "volume": 100,
                "azimuth": azimuth,
                "elevation": elevation,
                "distance": distance,
            }
        )

    # Force exact final azimuth

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
        description="Generate a sinusoidal 3D spherical audio path."
    )

    parser.add_argument("-o", "--output", default="./mywalk.csv")

    parser.add_argument("-c", "--continuity", type=int, choices=range(0, 11), default=6)

    parser.add_argument(
        "-b", "--begin", type=float, default=None, help="Starting azimuth"
    )

    parser.add_argument("-e", "--end", type=float, default=None, help="Ending azimuth")

    args = parser.parse_args()

    walk = generate_walk(args.continuity, args.begin, args.end)

    write_csv(args.output, walk)

    print(f"Generated {len(walk)} points in {args.output}")


if __name__ == "__main__":
    main()
