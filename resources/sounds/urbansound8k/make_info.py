#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
generate_wav_descriptors.py

Scan WAV files and generate YAML descriptor files.

For each WAV file:
    - scan audio properties with ffprobe
    - read corresponding JSON recipe
    - extract classes
    - write YAML descriptor

Requirements:
    ffmpeg
    ffprobe
    pyyaml
"""

from pathlib import Path
import subprocess
import json
import argparse
import sys

import yaml
from concurrent.futures import ProcessPoolExecutor


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FOLDER = BASE_DIR / "files_wav/"
OUTPUT_FOLDER = BASE_DIR / "info/"


SOURCE_NAME = "urbansound8k"


DEFAULT_SAMPLERATE = "16000 Hz"


# ============================================================
# FFMPEG / FFPROBE
# ============================================================


def check_ffprobe():

    result = subprocess.run(
        ["which", "ffprobe"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode != 0:
        raise RuntimeError("ffprobe not found in PATH")


def get_wav_info(filename):
    """
    Return samplerate, channels, duration
    """

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(filename),
    ]

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    data = json.loads(result.stdout)

    audio_stream = None

    for stream in data["streams"]:
        if stream.get("codec_type") == "audio":
            audio_stream = stream

            break

    if audio_stream is None:
        raise RuntimeError("No audio stream found")

    samplerate = int(audio_stream.get("sample_rate", 0))

    channels = int(audio_stream.get("channels", 0))

    duration = float(data["format"]["duration"])

    return {"samplerate": samplerate, "channels": channels, "duration": duration}


# ============================================================
# JSON RECIPE METADATA
# ============================================================


def get_classes_from_recipe(wav_file):
    """
    Read the JSON recipe associated with
    the WAV file and return classes as CSV.

    Example:

        [
            "dog_bark",
            "car_horn"
        ]

    becomes:

        dog_bark,car_horn
    """

    json_file = wav_file.with_suffix(".json")

    if not json_file.exists():
        return "unknown"

    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        classes = data.get("classes", [])

        if not classes:
            return "unknown"

        return ",".join(classes)

    except Exception as e:
        print(f"WARNING: cannot read {json_file}: {e}", file=sys.stderr)

        return "unknown"


# ============================================================
# TIME FORMAT
# ============================================================


def seconds_to_timestamp(seconds):
    """
    Convert seconds to:

        HH:MM:SS.xx

    """

    hours = int(seconds // 3600)

    minutes = int((seconds % 3600) // 60)

    secs = seconds % 60

    return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"


# ============================================================
# YAML GENERATION
# ============================================================


def create_descriptor(wav_file, info, description):

    name = wav_file.stem

    duration = info["duration"]

    descriptor = {
        "syntax": {
            "name": "sound_file",
            "version": {"major": 0, "minor": 1, "revision": 0},
        },
        "description": description,
        "copyright": SOURCE_NAME,
        "source": SOURCE_NAME,
        "name": name,
        # "file": str(wav_file).replace("\\", "/"),
        "file": str(wav_file.relative_to(BASE_DIR)).replace("\\", "/"),
        "speaker": {"count": 1},
        "format": {
            "type": "wav",
            "samplerate": f"{info['samplerate']} Hz",
            "channels": info["channels"],
            "duration": seconds_to_timestamp(duration),
        },
        "playback": {"begin": "00:00:00.00", "end": seconds_to_timestamp(duration)},
    }

    return descriptor


# def write_yaml(wav_file, descriptor):

#     yaml_file = wav_file.with_suffix(".yaml")

#     with open(yaml_file, "w", encoding="utf-8") as f:
#         f.write("---\n")

#         yaml.dump(descriptor, f, sort_keys=False, allow_unicode=True)

#         f.write("#EOF\n")


def write_yaml(wav_file, descriptor):

    # preserve relative folder structure
    relative_path = wav_file.relative_to(SOURCE_FOLDER)

    yaml_file = (OUTPUT_FOLDER / relative_path).with_suffix(".yaml")

    # create output folder if needed
    yaml_file.parent.mkdir(parents=True, exist_ok=True)

    with open(yaml_file, "w", encoding="utf-8") as f:
        f.write("---\n")

        yaml.dump(descriptor, f, sort_keys=False, allow_unicode=True)

        f.write("#EOF\n")


# ============================================================
# SCANNING
# ============================================================


def scan_wav_files(folder):

    return sorted(folder.rglob("*.wav"))


# ============================================================
# MAIN PROCESS
# ============================================================


def process_single_wav(wav):

    try:
        print(f"Processing {wav}")

        info = get_wav_info(wav)

        description = get_classes_from_recipe(wav)

        descriptor = create_descriptor(wav, info, description)

        write_yaml(wav, descriptor)

        return True

    except Exception as e:
        print(f"ERROR {wav}: {e}", file=sys.stderr)

        return False


def process_folder(folder, jobs=1):

    wav_files = scan_wav_files(folder)

    if not wav_files:
        print("No WAV files found")

        return

    print(f"Found {len(wav_files)} WAV files")

    if jobs <= 1:
        for wav in wav_files:
            process_single_wav(wav)

    else:
        print(f"Running with {jobs} parallel jobs")

        with ProcessPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(process_single_wav, wav_files))

        success = sum(results)

        print(f"Completed {success}/{len(wav_files)} files")


def process_folder_serial(folder):

    wav_files = scan_wav_files(folder)

    if not wav_files:
        print("No WAV files found")

        return

    print(f"Found {len(wav_files)} WAV files")

    for wav in wav_files:
        try:
            print(f"Processing {wav}")

            info = get_wav_info(wav)

            description = get_classes_from_recipe(wav)

            descriptor = create_descriptor(wav, info, description)

            write_yaml(wav, descriptor)

        except Exception as e:
            print(f"ERROR {wav}: {e}", file=sys.stderr)


# ============================================================
# CLI
# ============================================================


def main():

    parser = argparse.ArgumentParser(
        description="Generate YAML descriptors for WAV files"
    )

    parser.add_argument(
        "-j", "--jobs", type=int, default=1, help="Number of parallel processes"
    )

    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        default=str(SOURCE_FOLDER),
        help="Folder containing WAV files",
    )

    args = parser.parse_args()

    check_ffprobe()

    process_folder(Path(args.folder), args.jobs)


if __name__ == "__main__":
    main()
