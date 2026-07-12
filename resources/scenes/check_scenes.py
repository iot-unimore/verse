#!/usr/bin/env python3

import argparse
from pathlib import Path
from collections import defaultdict

import yaml


def load_footprint(filename):
    """
    Compute a unique footprint for a scene.

    The footprint consists of:

        sources_count

        for each source:

            Dynamic:
                (idx, "dynamic", path_file)

            Static:
                (idx, "static", coord_type, coord_value)
    """

    with open(filename, "r") as f:
        data = yaml.safe_load(f)

    setup = data["setup"]

    sources_count = setup["sources_count"]
    sources = setup["sources"]

    footprint = []

    ordered_keys = sorted(sources.keys(), key=int)

    for key in ordered_keys:
        src = sources[key]

        position = src.get("position", {})

        position_type = position.get("type", "")

        if position_type == "dynamic":
            path_info = position.get("value", {}).get("info", None)

            footprint.append(
                (
                    int(key),
                    "dynamic",
                    path_info,
                )
            )

        elif position_type == "static":
            coord = position.get("coord", {})

            coord_type = coord.get("type", "")

            coord_value = tuple(coord.get("value", []))

            footprint.append(
                (
                    int(key),
                    "static",
                    coord_type,
                    coord_value,
                )
            )

        else:
            footprint.append(
                (
                    int(key),
                    position_type,
                )
            )

    return (
        sources_count,
        tuple(footprint),
    )


def print_footprint(fp):

    print(f"sources_count = {fp[0]}")

    for src in fp[1]:
        if src[1] == "dynamic":
            idx, _, path = src

            print(f"  {idx},dynamic,{path}")

        elif src[1] == "static":
            idx, _, coord_type, coord_value = src

            print(f"  {idx},static,{coord_type},{list(coord_value)}")

        else:
            print(" ", src)


def main():

    parser = argparse.ArgumentParser(
        description="Find dynamic scene YAML files with identical source footprints."
    )

    parser.add_argument(
        "folder",
        nargs="?",
        default="./info/",
        help="Folder containing dynamic_*.yaml files",
    )

    args = parser.parse_args()

    folder = Path(args.folder)

    files = sorted(folder.glob("dynamic_*.yaml"))

    if not files:
        print("No dynamic_*.yaml files found.")
        return

    footprints = defaultdict(list)

    for file in files:
        try:
            fp = load_footprint(file)

            footprints[fp].append(file.name)

        except Exception as e:
            print(f"Error reading {file}: {e}")

    found = False

    for fp, names in footprints.items():
        if len(names) < 2:
            continue

        found = True

        print("=" * 70)

        print("\nMatching footprint:\n")

        for n in names:
            print(f"  {n}")

        print()

        print_footprint(fp)

        print()

    if not found:
        print("No duplicate footprints found.")


if __name__ == "__main__":
    main()
