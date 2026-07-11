#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
make_dataset.py

Audio dataset generator based on WAV concatenation recipes.

Features implemented in this part:
- WAV database creation
- recipe generation
- random repetitions
- recipe validation
- JSON persistence
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import os

from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FOLDER = BASE_DIR / "files/UrbanSound8K/audio/"
OUTPUT_FOLDER = BASE_DIR / "files_wav/"

# Number of generated wav files in normal generation mode
NUMBER_OF_FILES = 100

# Audio parameters
TARGET_SR = 16000
TARGET_LENGTH = 60.0

# Normal silence between different clips
PAUSE_MIN = 0.0
PAUSE_MAX = 3.0

# Repetition parameters
#
# Example:
#
# REPEAT_N = 3
#
# means:
#
# clip can appear:
#
# 1 time
# 2 times
# 3 times
# 4 times
#
# because this is the number of ADDITIONAL repetitions
REPEAT_N = 2
# Maximum silence seconds between repetitions
REPEAT_SILENCE_S = 2.0


# Stop condition tolerance
STOP_TOLERANCE = 5.0

# Safety limit
MAX_CLIPS_PER_FILE = 200


# Recipe identifier
#
# This is the "magic number" used to validate JSON files.
RECIPE_MAGIC = "AUDIO_CONCAT_GENERATION_RECIPE_V1"


# ============================================================
# DATA STRUCTURES
# ============================================================


@dataclass
class RecipeItem:
    file: str

    duration: float

    pause_after: float

    # same value means that these clips came from
    # the same repetition decision

    repeat_group: int


@dataclass
class Recipe:
    recipe_is: str

    version: int

    sample_rate: int

    target_length: float

    repeat_max: int

    repeat_silence_max: float

    output_file: str

    items: List[RecipeItem]


# ============================================================
# SYSTEM UTILITIES
# ============================================================


def run_command(cmd):

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result.stdout.strip()


def check_dependencies():

    for exe in (
        "ffmpeg",
        "ffprobe",
    ):
        if shutil.which(exe) is None:
            raise RuntimeError(f"{exe} not found in PATH")


# ============================================================
# WAV DATABASE
# ============================================================


def scan_wavs(folder: Path):

    files = sorted(folder.rglob("*.wav"))

    if not files:
        raise RuntimeError(f"No wav files found in {folder}")

    return files


def wav_duration(filename: Path):

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(filename),
    ]

    return float(run_command(cmd))


# def build_database(files):

#     database = []

#     for filename in files:
#         database.append({"file": filename, "duration": wav_duration(filename)})

#     return database


def build_database(files):

    database = []


    for filename in tqdm(
        files,
        desc="Reading WAV durations",
        unit="file"
    ):

        try:

            duration = wav_duration(
                filename
            )


            database.append(
                {
                    "file": filename,

                    "duration": duration
                }
            )


        except Exception as e:

            print(
                f"Skipping {filename}: {e}",
                file=sys.stderr
            )


    if not database:

        raise RuntimeError(
            "No valid WAV files found"
        )


    return database

# ============================================================
# RECIPE GENERATION
# ============================================================


def create_recipe(database, output_file, clip_rng, repeat_rng, pause_rng):

    items = []

    total_length = 0.0

    repeat_group = 0

    while len(items) < MAX_CLIPS_PER_FILE:
        source = clip_rng.choice(database)

        #
        # Random repetition count
        #
        # 0 means:
        #   only original clip
        #
        # 3 means:
        #   original + 3 copies
        #

        repeat_count = repeat_rng.randint(0, REPEAT_N)

        for repetition in range(repeat_count + 1):
            if repetition < repeat_count:
                pause = pause_rng.uniform(0, REPEAT_SILENCE_S)

            else:
                pause = pause_rng.uniform(PAUSE_MIN, PAUSE_MAX)

            new_length = total_length + source["duration"]

            if items:
                new_length += pause

            #
            # stop before exceeding target
            #

            if (
                total_length >= TARGET_LENGTH - STOP_TOLERANCE
                and new_length > TARGET_LENGTH + STOP_TOLERANCE
            ):
                break

            items.append(
                RecipeItem(
                    file=str(source["file"].resolve()),
                    duration=source["duration"],
                    pause_after=pause,
                    repeat_group=repeat_group,
                )
            )

            total_length = new_length

            if abs(total_length - TARGET_LENGTH) <= STOP_TOLERANCE:
                break

        repeat_group += 1

        if abs(total_length - TARGET_LENGTH) <= STOP_TOLERANCE:
            break

    return Recipe(
        recipe_is=RECIPE_MAGIC,
        version=1,
        sample_rate=TARGET_SR,
        target_length=TARGET_LENGTH,
        repeat_max=REPEAT_N,
        repeat_silence_max=REPEAT_SILENCE_S,
        output_file=str(output_file.resolve()),
        items=items,
    )


# ============================================================
# RECIPE JSON
# ============================================================


def save_recipe(recipe: Recipe):

    filename = Path(recipe.output_file).with_suffix(".json")

    with open(filename, "w", encoding="utf8") as f:
        json.dump(asdict(recipe), f, indent=4)


def load_recipe(filename):

    with open(filename, encoding="utf8") as f:
        data = json.load(f)

    if data.get("recipe_is") != RECIPE_MAGIC:
        raise ValueError(f"Invalid recipe file: {filename}")

    items = [RecipeItem(**item) for item in data["items"]]

    return Recipe(
        recipe_is=data["recipe_is"],
        version=data["version"],
        sample_rate=data["sample_rate"],
        target_length=data["target_length"],
        repeat_max=data.get("repeat_max", 0),
        repeat_silence_max=data.get("repeat_silence_max", 0),
        output_file=data["output_file"],
        items=items,
    )


# ============================================================
# FFMPEG RENDERING
# ============================================================


def build_ffmpeg_command(recipe: Recipe):

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]

    filters = []

    concat_inputs = []

    input_index = 0

    for i, item in enumerate(recipe.items):
        #
        # input wav
        #

        cmd.extend(["-i", item.file])

        #
        # convert:
        # - target samplerate
        # - mono
        # - 16 bit PCM
        #

        filters.append(
            f"[{input_index}:a]"
            f"aresample={recipe.sample_rate},"
            f"aformat="
            f"sample_fmts=s16:"
            f"channel_layouts=mono"
            f"[a{i}]"
        )

        concat_inputs.append(f"[a{i}]")

        input_index += 1

        #
        # silence after clip
        #

        if i < len(recipe.items) - 1:
            filters.append(
                f"anullsrc="
                f"channel_layout=mono:"
                f"sample_rate={recipe.sample_rate},"
                f"atrim="
                f"duration={item.pause_after:.6f}"
                f"[s{i}]"
            )

            concat_inputs.append(f"[s{i}]")

    #
    # concatenate all streams
    #

    filters.append(
        "".join(concat_inputs) + f"concat=n={len(concat_inputs)}:v=0:a=1[out]"
    )

    cmd.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            recipe.output_file,
        ]
    )

    return cmd


# ============================================================
# WAV GENERATION
# ============================================================


def render_recipe(recipe: Recipe, overwrite=False):

    output = Path(recipe.output_file)

    #
    # avoid accidental overwrite
    #

    if output.exists() and not overwrite:
        print(f"Skipping existing file: {output}")

        return

    output.parent.mkdir(parents=True, exist_ok=True)

    #
    # write recipe first
    #

    save_recipe(recipe)

    cmd = build_ffmpeg_command(recipe)

    subprocess.run(cmd, check=True)


# ============================================================
# MULTIPROCESSING WORKER
# ============================================================


_WORKER_OVERWRITE = False


def init_worker(overwrite):

    global _WORKER_OVERWRITE

    _WORKER_OVERWRITE = overwrite


def render_worker(recipe):

    try:
        render_recipe(recipe, _WORKER_OVERWRITE)

        return True

    except Exception as e:
        print(f"ERROR: {recipe.output_file}", file=sys.stderr)

        print(e, file=sys.stderr)

        return False


# ============================================================
# EXECUTION ENGINE
# ============================================================


def execute_recipes(recipes, jobs=1, overwrite=False):

    if jobs <= 1:
        for recipe in recipes:
            render_recipe(recipe, overwrite)

    else:
        with ProcessPoolExecutor(
            max_workers=jobs, initializer=init_worker, initargs=(overwrite,)
        ) as pool:
            list(
                tqdm(
                    pool.map(render_worker, recipes),
                    total=len(recipes),
                    desc="Generating",
                )
            )


# ============================================================
# RECIPE FOLDER GENERATION (-g)
# ============================================================


def scan_recipe_folder(folder):

    folder = Path(folder)

    json_files = sorted(folder.rglob("*.json"))

    if not json_files:
        raise RuntimeError(f"No JSON files found in {folder}")

    recipes = []

    print(f"Scanning {len(json_files)} JSON files")

    for filename in json_files:
        try:
            recipe = load_recipe(filename)

            recipes.append(recipe)

            print(f"Accepted recipe: {filename}")

        except Exception as e:
            print(f"Ignored {filename}: {e}")

    if not recipes:
        raise RuntimeError("No valid audio generation recipes found")

    return recipes


# ============================================================
# GENERATION MODES
# ============================================================


def generate_from_recipe_folder(folder, jobs, overwrite):

    recipes = scan_recipe_folder(folder)

    print(f"Generating {len(recipes)} files")

    execute_recipes(recipes, jobs, overwrite)


def recreate_from_files(filenames, jobs, overwrite):

    recipes = []

    for filename in filenames:
        recipes.append(load_recipe(filename))

    execute_recipes(recipes, jobs, overwrite)


# ============================================================
# RANDOM GENERATION MODE
# ============================================================


def generate_random_dataset(jobs, overwrite, seed=None):

    print("Scanning WAV files...")

    wav_files = scan_wavs(SOURCE_FOLDER)

    print(f"Found {len(wav_files)} WAV files")

    database = build_database(wav_files)

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    #
    # Separate random generators:
    #
    # - clip selection
    # - repetitions
    # - pauses
    #
    # This avoids one random process influencing another.
    #

    if seed is None:
        seed = random.randrange(1_000_000_000)

    clip_rng = random.Random(seed)

    repeat_rng = random.Random(seed + 1)

    pause_rng = random.Random(seed + 2)

    recipes = []

    for i in range(NUMBER_OF_FILES):
        output_file = OUTPUT_FOLDER / f"sample_{i:06d}.wav"

        recipe = create_recipe(database, output_file, clip_rng, repeat_rng, pause_rng)

        recipes.append(recipe)

    print(f"Created {len(recipes)} recipes")

    execute_recipes(recipes, jobs, overwrite)


# ============================================================
# CLI
# ============================================================


def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Generate WAV datasets from audio recipes"
    )

    parser.add_argument(
        "-p",
        "--param-file",
        nargs="+",
        help="Generate audio from specific recipe JSON files",
    )

    parser.add_argument(
        "-g",
        "--generate",
        type=str,
        help="Scan a folder recursively for recipe JSON files and generate them",
    )

    parser.add_argument(
        "-j", "--jobs", type=int, default=1, help="Number of parallel ffmpeg jobs"
    )

    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible dataset generation",
    )

    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing WAV files"
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================


def main():

    args = parse_arguments()

    check_dependencies()

    #
    # Priority:
    #
    # 1) -g recipe folder
    # 2) -p recipe files
    # 3) random generation
    #

    if args.generate:
        generate_from_recipe_folder(args.generate, args.jobs, args.overwrite)

    elif args.param_file:
        recreate_from_files(args.param_file, args.jobs, args.overwrite)

    else:
        generate_random_dataset(args.jobs, args.overwrite, args.seed)


if __name__ == "__main__":
    main()
    os.system("tset")
