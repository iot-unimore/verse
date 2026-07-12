#!/usr/bin/env python3
"""
Analyze the 3D spatial coverage of audio sources (voices/sounds) used by a
dataset recipe, per set (train/validate/test), and report whether that
coverage overlaps between sets.

check_recipe.py already verifies that resource files exist and that voice/
scene *identifiers* are not reused across sets. This script goes one level
deeper: it opens every scene referenced by the recipe, reads the actual
static positions and dynamic path trajectories of its sources/sounds, bins
them into an azimuth/elevation "sky map", and reports per-set coverage plus
cross-set overlap -- both at the identifier level (same static coordinate or
same dynamic path reused in more than one set: hard error) and at the sky
cell level (sets landing in the same region of space: informational).
"""

import argparse
import os
from collections import defaultdict
from pathlib import Path

import yaml

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

# default sky-map / distance grid resolution
_DEFAULT_AZ_BINS = 24  # 15 degrees/bin over 0-360
_DEFAULT_EL_BINS = 6  # 30 degrees/bin over -90..90
_DEFAULT_DIST_MIN = 0.0
_DEFAULT_DIST_MAX = 6.0
_DEFAULT_DIST_BINS = 6  # 1 metre/bin

# default sanity-check thresholds for audio source positions
_DEFAULT_MIN_SOURCE_DISTANCE_M = 1.0
_DEFAULT_MIN_ELEVATION_DEG = -45.0
_DEFAULT_MAX_ELEVATION_DEG = 45.0


def load_yaml(filename):
    """Load and return a YAML file's content, or None if it cannot be read/parsed."""
    try:
        with open(filename, "r") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None


def iter_recipe_scenes(recipe):
    """Walk every set/task/scene entry of a loaded ds_recipe dict and yield
    (set_name, task_id, subtype, scene_name) tuples for every scene reference."""
    for set_name, set_data in (recipe.get("sets") or {}).items():
        tasks = set_data.get("tasks") or {}
        for task_id, task in tasks.items():
            scenes = task.get("scenes") or {}
            for _, group in scenes.items():
                if not isinstance(group, dict):
                    continue
                subtype = group.get("subtype")
                info = group.get("info") or []
                if not subtype or not info:
                    continue
                for scene_name in info:
                    yield set_name, task_id, subtype, scene_name


def cartesian_to_spherical(x, y, z):
    """Convert a cartesian (x, y, z) point to (azimuth_deg, elevation_deg, distance),
    using the same axis convention as the rest of the scene coordinate system
    (azimuth measured in the XY plane, elevation from that plane towards Z)."""
    import math

    dist = math.sqrt(x * x + y * y + z * z)
    az = math.degrees(math.atan2(y, x))
    el = math.degrees(math.atan2(z, math.sqrt(x * x + y * y)))
    return az, el, dist


def read_static_position(entry):
    """Extract (azimuth_deg, elevation_deg, distance_m) from a scene source/sound
    entry whose position type is 'static'. Supports both spherical and cartesian
    coord encodings. Returns None if the entry is malformed."""
    coord = entry.get("position", {}).get("coord", {})
    value = coord.get("value")
    coord_type = coord.get("type")

    if not value or len(value) != 3:
        return None

    if coord_type == "spherical":
        return float(value[0]), float(value[1]), float(value[2])
    if coord_type == "cartesian":
        return cartesian_to_spherical(float(value[0]), float(value[1]), float(value[2]))
    return None


def read_dynamic_path_trajectory(resource_dir, subtype, path_name):
    """Resolve a scene source/sound entry's dynamic 'path' reference (paths/{subtype}/
    info/{path_name}.yaml) and read its associated CSV trajectory. Returns a list of
    (azimuth_deg, elevation_deg, distance_m) points, or None if the path/CSV file is
    missing or malformed."""
    path_yaml_file = resource_dir / "paths" / subtype / "info" / f"{path_name}.yaml"
    path_info = load_yaml(path_yaml_file)

    if not path_info or path_info.get("format") != "csv":
        return None

    path_entries = path_info.get("path") or {}
    main_idx = path_info.get("path_main_idx", 0)
    csv_entry = path_entries.get(main_idx) or next(iter(path_entries.values()), None)

    if not csv_entry:
        return None

    csv_file = resource_dir / "paths" / subtype / csv_entry["file"]

    if not csv_file.is_file():
        return None

    points = []
    with open(csv_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            az, el, dist = float(parts[2]), float(parts[3]), float(parts[4])
            points.append((az % 360.0, el, dist))

    return points


def iter_scene_object_positions(resource_dir, scene_subtype, scene_name):
    """Load a scene file and yield one position record per source/sound entry it
    defines: {"kind": "static"|"dynamic", "az", "el", "dist"} for static entries,
    or {"kind": "dynamic", "path_id": (subtype, name), "points": [...]} for dynamic
    ones. Both 'sources' (voices) and optional 'sounds' groups are covered."""
    scene_file = resource_dir / "scenes" / scene_subtype / "info" / f"{scene_name}.yaml"
    scene = load_yaml(scene_file)

    if not scene:
        return

    setup = scene.get("setup", {})

    for group_key in ("sources", "sounds"):
        group = setup.get(group_key) or {}
        if not isinstance(group, dict):
            continue

        for entry_key, entry in group.items():
            position = entry.get("position", {})
            pos_type = position.get("type")

            if pos_type == "static":
                static_pos = read_static_position(entry)
                if static_pos is None:
                    continue
                az, el, dist = static_pos
                yield {
                    "kind": "static",
                    "group": group_key,
                    "entry": entry_key,
                    "az": az % 360.0,
                    "el": el,
                    "dist": dist,
                }

            elif pos_type == "dynamic":
                value = position.get("value", {})
                path_subtype = value.get("subtype")
                path_name = value.get("info")
                if not path_subtype or not path_name:
                    continue
                points = read_dynamic_path_trajectory(resource_dir, path_subtype, path_name)
                if not points:
                    continue
                yield {
                    "kind": "dynamic",
                    "group": group_key,
                    "entry": entry_key,
                    "path_id": (path_subtype, path_name),
                    "points": points,
                }


def check_object_sanity(scene_label, obj, min_distance, el_min, el_max):
    """Check a single source/sound position record (as yielded by
    iter_scene_object_positions) against the physical sanity thresholds: distance
    must stay >= min_distance, elevation must stay within [el_min, el_max]. For a
    static entry this checks the one point; for a dynamic entry it checks every
    point of the trajectory and reports the worst offender. Returns a list of
    warning strings (empty if the entry is within bounds)."""
    label = f"{scene_label} [{obj['group']} {obj['entry']}]"
    warnings = []

    if obj["kind"] == "static":
        points = [(obj["az"], obj["el"], obj["dist"])]
    else:
        points = obj["points"]

    min_dist_point = min(points, key=lambda p: p[2])
    if min_dist_point[2] < min_distance:
        n_bad = sum(1 for p in points if p[2] < min_distance)
        warnings.append(
            f"{label}: [{obj['kind']}] distance {min_dist_point[2]:.3f}m below minimum {min_distance:.3f}m "
            f"({n_bad}/{len(points)} point(s))"
        )

    worst_el_point = max(points, key=lambda p: max(el_min - p[1], p[1] - el_max))
    if worst_el_point[1] < el_min or worst_el_point[1] > el_max:
        n_bad = sum(1 for p in points if p[1] < el_min or p[1] > el_max)
        warnings.append(
            f"{label}: elevation {worst_el_point[1]:.3f}deg outside [{el_min:.1f}, {el_max:.1f}] "
            f"({n_bad}/{len(points)} point(s))"
        )

    return warnings


def check_recipe_sanity(recipe, resource_dir, min_distance, el_min, el_max):
    """Check every unique scene referenced anywhere in the recipe (regardless of
    which set(s) use it) against the physical sanity thresholds, and return the
    flat list of warning strings produced by check_object_sanity."""
    seen_scenes = set()
    warnings = []

    for _set_name, _task_id, subtype, scene_name in iter_recipe_scenes(recipe):
        scene_key = (subtype, scene_name)
        if scene_key in seen_scenes:
            continue
        seen_scenes.add(scene_key)

        scene_label = f"{subtype}/{scene_name}"
        for obj in iter_scene_object_positions(resource_dir, subtype, scene_name):
            warnings.extend(check_object_sanity(scene_label, obj, min_distance, el_min, el_max))

    return warnings


def print_sanity_report(warnings):
    print(f"\n{CYAN}=============================={RESET}")
    print(f"{CYAN}SANITY CHECKS (distance / elevation){RESET}")
    print(f"{CYAN}=============================={RESET}")

    if not warnings:
        print(f"{GREEN}none{RESET}")
        return

    for w in warnings:
        print(f"{YELLOW}[WARN]{RESET} {w}")


class SetStats:
    """Accumulates spatial-coverage stats for a single dataset set (train/validate/test)."""

    def __init__(self):
        self.scene_count = 0
        self.static_count = 0
        self.dynamic_count = 0
        self.unique_paths = set()
        self.static_coords = set()
        self.az_values = []
        self.el_values = []
        self.dist_values = []
        self.sky_cells = set()  # (az_bin, el_bin)
        self.space_cells = set()  # (az_bin, el_bin, dist_bin)

    def add_point(self, az, el, dist, az_bins, el_bins, dist_min, dist_max, dist_bins):
        self.az_values.append(az)
        self.el_values.append(el)
        self.dist_values.append(dist)

        az_bin = min(int((az % 360.0) / (360.0 / az_bins)), az_bins - 1)
        el_clamped = max(-90.0, min(90.0, el))
        el_bin = min(int((el_clamped + 90.0) / (180.0 / el_bins)), el_bins - 1)
        dist_clamped = max(dist_min, min(dist_max, dist))
        dist_bin = min(int((dist_clamped - dist_min) / ((dist_max - dist_min) / dist_bins)), dist_bins - 1)

        self.sky_cells.add((az_bin, el_bin))
        self.space_cells.add((az_bin, el_bin, dist_bin))


def analyze_recipe(recipe, resource_dir, az_bins, el_bins, dist_min, dist_max, dist_bins):
    """Resolve every scene's source/sound positions per set of an already-loaded
    ds_recipe dict, and return a dict {set_name: SetStats} with spatial-coverage
    stats aggregated over the set's *unique* scenes (a scene's spatial layout is
    independent of which task/voice combination renders it, so repeats are only
    counted once)."""
    seen_scenes_per_set = defaultdict(set)
    stats = defaultdict(SetStats)

    for set_name, _task_id, subtype, scene_name in iter_recipe_scenes(recipe):
        scene_key = (subtype, scene_name)
        if scene_key in seen_scenes_per_set[set_name]:
            continue
        seen_scenes_per_set[set_name].add(scene_key)

        stat = stats[set_name]
        stat.scene_count += 1

        for obj in iter_scene_object_positions(resource_dir, subtype, scene_name):
            if obj["kind"] == "static":
                stat.static_count += 1
                stat.static_coords.add((round(obj["az"], 3), round(obj["el"], 3), round(obj["dist"], 3)))
                stat.add_point(obj["az"], obj["el"], obj["dist"], az_bins, el_bins, dist_min, dist_max, dist_bins)
            else:
                stat.dynamic_count += 1
                stat.unique_paths.add(obj["path_id"])
                for az, el, dist in obj["points"]:
                    stat.add_point(az, el, dist, az_bins, el_bins, dist_min, dist_max, dist_bins)

    return stats


def fmt_range(values):
    if not values:
        return "n/a"
    return f"{min(values):.0f}..{max(values):.0f}"


def overall_sky_cells(stats):
    """Union of the sky cells touched by every set -- i.e. how much of the sky map
    the recipe uses at all, regardless of which set. This is the context needed to
    judge cross-set sky cell overlap: if the recipe already covers most of the sky,
    sets overlapping heavily is close to unavoidable; if overall coverage is low,
    the same overlap instead signals room to spread sets into unused regions."""
    cells = set()
    for s in stats.values():
        cells |= s.sky_cells
    return cells


def print_summary_table(stats, az_bins, el_bins):
    from tabulate import tabulate

    total_sky_cells = az_bins * el_bins
    rows = []
    for set_name in sorted(stats.keys()):
        s = stats[set_name]
        coverage_pct = 100.0 * len(s.sky_cells) / total_sky_cells
        rows.append(
            [
                set_name,
                s.scene_count,
                s.static_count,
                s.dynamic_count,
                len(s.unique_paths),
                fmt_range(s.az_values),
                fmt_range(s.el_values),
                fmt_range(s.dist_values),
                f"{len(s.sky_cells)}/{total_sky_cells} ({coverage_pct:.1f}%)",
            ]
        )

    union_cells = overall_sky_cells(stats)
    union_pct = 100.0 * len(union_cells) / total_sky_cells
    rows.append(
        [
            f"{CYAN}ALL (union){RESET}",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            f"{CYAN}{len(union_cells)}/{total_sky_cells} ({union_pct:.1f}%){RESET}",
        ]
    )

    print(f"\n{CYAN}=============================={RESET}")
    print(f"{CYAN}PER-SET SPATIAL COVERAGE{RESET}")
    print(f"{CYAN}=============================={RESET}")
    print(
        tabulate(
            rows,
            headers=[
                "set",
                "scenes",
                "static pos",
                "dyn paths",
                "unique paths",
                "az range",
                "el range",
                "dist range",
                "sky coverage",
            ],
            tablefmt="psql",
        )
    )
    print(
        f"\nOverall sky coverage (union of all sets): {len(union_cells)}/{total_sky_cells} ({union_pct:.1f}%) "
        f"-- low overall coverage means there is room to spread sets further apart; "
        f"high overall coverage means some cross-set overlap is close to unavoidable."
    )


def print_overlap_report(stats, az_bins, el_bins):
    set_names = sorted(stats.keys())
    had_error = False

    total_sky_cells = az_bins * el_bins
    union_cells = overall_sky_cells(stats)
    union_pct = 100.0 * len(union_cells) / total_sky_cells

    print(f"\n{CYAN}=============================={RESET}")
    print(f"{CYAN}CROSS-SET OVERLAP{RESET}")
    print(f"{CYAN}=============================={RESET}")
    print(f"(for reference, overall sky coverage across all sets is {union_pct:.1f}% -- see above)")

    for i in range(len(set_names)):
        for j in range(i + 1, len(set_names)):
            a, b = set_names[i], set_names[j]
            sa, sb = stats[a], stats[b]

            shared_paths = sa.unique_paths & sb.unique_paths
            shared_coords = sa.static_coords & sb.static_coords
            shared_cells = sa.sky_cells & sb.sky_cells

            smaller_cells = min(len(sa.sky_cells), len(sb.sky_cells)) or 1
            cell_overlap_pct = 100.0 * len(shared_cells) / smaller_cells

            print(f"\n{YELLOW}{a} <-> {b}{RESET}")

            if shared_paths:
                had_error = True
                print(f"{RED}  duplicate dynamic paths ({len(shared_paths)}):{RESET}")
                for subtype, name in sorted(shared_paths):
                    print(f"{RED}    {subtype}/{name}{RESET}")
            else:
                print(f"{GREEN}  duplicate dynamic paths: none{RESET}")

            if shared_coords:
                had_error = True
                print(f"{RED}  duplicate static coordinates ({len(shared_coords)}):{RESET}")
                for az, el, dist in sorted(shared_coords):
                    print(f"{RED}    az={az} el={el} dist={dist}{RESET}")
            else:
                print(f"{GREEN}  duplicate static coordinates: none{RESET}")

            print(
                f"  sky cell overlap: {len(shared_cells)} cells "
                f"({cell_overlap_pct:.1f}% of the smaller set's coverage) -- informational only"
            )

    return had_error


def main():
    parser = argparse.ArgumentParser(description="Analyze 3D positioning coverage/overlap of a ds_recipe YAML")

    parser.add_argument("-i", "--recipe", type=Path, required=True, help="dataset recipe YAML file")
    parser.add_argument(
        "--resource_dir",
        type=Path,
        default=os.path.join(_ROOT_DIR, "../"),
        help="root resource directory (default: %(default)s)",
    )
    parser.add_argument("--az-bins", type=int, default=_DEFAULT_AZ_BINS, help="azimuth bins over 0-360 (default: %(default)s)")
    parser.add_argument("--el-bins", type=int, default=_DEFAULT_EL_BINS, help="elevation bins over -90..90 (default: %(default)s)")
    parser.add_argument("--dist-min", type=float, default=_DEFAULT_DIST_MIN, help="distance grid lower bound, metres (default: %(default)s)")
    parser.add_argument("--dist-max", type=float, default=_DEFAULT_DIST_MAX, help="distance grid upper bound, metres (default: %(default)s)")
    parser.add_argument("--dist-bins", type=int, default=_DEFAULT_DIST_BINS, help="distance bins (default: %(default)s)")
    parser.add_argument(
        "--min-source-distance",
        type=float,
        default=_DEFAULT_MIN_SOURCE_DISTANCE_M,
        help="sanity check: minimum allowed source distance, metres (default: %(default)s)",
    )
    parser.add_argument(
        "--min-elevation",
        type=float,
        default=_DEFAULT_MIN_ELEVATION_DEG,
        help="sanity check: minimum allowed source elevation, degrees (default: %(default)s)",
    )
    parser.add_argument(
        "--max-elevation",
        type=float,
        default=_DEFAULT_MAX_ELEVATION_DEG,
        help="sanity check: maximum allowed source elevation, degrees (default: %(default)s)",
    )

    args = parser.parse_args()

    resource_dir = args.resource_dir.resolve()

    recipe = load_yaml(args.recipe)
    if not recipe:
        raise SystemExit(f"{RED}cannot read/parse recipe: {args.recipe}{RESET}")

    stats = analyze_recipe(
        recipe,
        resource_dir,
        args.az_bins,
        args.el_bins,
        args.dist_min,
        args.dist_max,
        args.dist_bins,
    )

    if not stats:
        print(f"{RED}no sets/scenes found in recipe{RESET}")
        raise SystemExit(1)

    sanity_warnings = check_recipe_sanity(recipe, resource_dir, args.min_source_distance, args.min_elevation, args.max_elevation)

    print_summary_table(stats, args.az_bins, args.el_bins)
    print_sanity_report(sanity_warnings)
    had_error = print_overlap_report(stats, args.az_bins, args.el_bins)

    print("\n===================================")
    print("FINAL SUMMARY")
    print("===================================")
    print(f"Sanity warnings : {len(sanity_warnings)}")
    if had_error:
        print(f"{RED}FAIL: duplicate static positions and/or dynamic paths reused across sets{RESET}")
    else:
        print(f"{GREEN}PASS: no duplicate static positions or dynamic paths across sets{RESET}")


if __name__ == "__main__":
    main()
