#!/usr/bin/env python3

import argparse
from pathlib import Path
import yaml
import os
from collections import defaultdict

GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

RESOURCE_TYPES = ("voices", "heads", "rooms", "scenes")

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

def iter_resources(task, resource_type):
    resources = task.get(resource_type)

    if not resources:
        return

    for _, group in resources.items():
        if not isinstance(group, dict):
            continue

        subtype = group.get("subtype")
        info = group.get("info", [])

        if not subtype or not info:
            continue

        for item in info:
            yield subtype, item

# def print_duplicates(counter, label, set_name):

#     duplicates = {k: v for k, v in counter.items() if v > 1}

#     if duplicates:
#         print(f"\n{RED}DUPLICATES in {set_name} ({label}):{RESET}")
#         for item, count in duplicates.items():
#             print(f"{RED}  {item} -> {count} times{RESET}")

def check_recipe(recipe_file: Path, resource_dir: Path):

    with recipe_file.open("r") as f:
        recipe = yaml.safe_load(f)

    global_total = 0
    global_missing = 0

    sets = recipe.get("sets", {})

    # CROSS-SET TRACKING
    voice_to_sets = defaultdict(set)
    scene_to_sets = defaultdict(set)    

    for set_name, set_data in sets.items():

        print(f"\n{CYAN}=============================={RESET}")
        print(f"{CYAN}{set_name.upper()}{RESET}")
        print(f"{CYAN}=============================={RESET}")

        tasks = set_data.get("tasks", {})

        for resource_type in RESOURCE_TYPES:

            print(f"\n{YELLOW}Checking {resource_type}{RESET}")

            any_found = False

            for task_id, task in tasks.items():

                items = list(iter_resources(task, resource_type))

                if not items:
                    continue

                any_found = True

                for subtype, resource in items:

                   # CROSS-SET REGISTRATION
                    if resource_type == "voices":
                        voice_to_sets[resource].add(set_name)

                    if resource_type == "scenes":
                        scene_to_sets[resource].add(set_name)

                    filename = (
                        resource_dir
                        / resource_type
                        / subtype
                        / "info"
                        / f"{resource}.yaml"
                    )

                    filename_log = filename.relative_to(resource_dir)

                    global_total += 1

                    label = f"[task {task_id}]"

                    if filename.exists():
                        print(f"{GREEN}[OK]{RESET}   {label} {filename_log}")
                    else:
                        global_missing += 1
                        print(f"{RED}[MISS]{RESET} {label} {filename_log}")

            if not any_found:
                print("none")

    # ============================
    # CROSS-SET VALIDATION REPORT
    # ============================

    def print_cross_duplicates(mapping, label):
        print(f"\n{RED}CROSS-SET DUPLICATES ({label}):{RESET}")

        found = False

        for item, sets_used in mapping.items():
            if len(sets_used) > 1:
                found = True
                sets_list = ", ".join(sorted(sets_used))
                print(f"{RED}{item} -> {sets_list}{RESET}")

        if not found:
            print(f"{GREEN}none{RESET}")

    print_cross_duplicates(voice_to_sets, "voices")
    print_cross_duplicates(scene_to_sets, "scenes")

    print("\n===================================")
    print("FINAL SUMMARY")
    print("===================================")
    print(f"Checked : {global_total}")
    print(f"Present : {global_total - global_missing}")
    print(f"Missing : {global_missing}")


def main():

    parser = argparse.ArgumentParser(
        description="Verify dataset resources from recipe YAML"
    )

    parser.add_argument(
        "--i",
        type=Path,
        help="YAML recipe file",
    )

    parser.add_argument(
        "--resource_dir",
        type=Path,
        default=os.path.join(_ROOT_DIR,"../"),
        help="Root resource directory",
    )

    args = parser.parse_args()

    check_recipe(args.recipe, args.resource_dir)


if __name__ == "__main__":
    main()
