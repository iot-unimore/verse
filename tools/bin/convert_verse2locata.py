#!/usr/bin/env python3

import os
import argparse
import yaml
import subprocess
import json
import time
import re
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from tqdm import tqdm
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path

# --- GLOBALS ---
manager = multiprocessing.Manager()
stop_event = manager.Event()

LOCATA_DATA_TYPES={"train":"dev","test":"eval","validate":"eval"}

REQUIRED_SYNTAX_NAMES = {
    "audio_rendering_scene",
    "verse_audio_mkv"
}


####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../", "resources")
_DATASET_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../", "datasets")

_FFPROBE_EXE = "/usr/bin/ffprobe"

_LOCATA_TASK_TYPES={'task1':"task1",'task2':"task2",'task3':"task3",'task4':"task4",'task5':"task5",'task6':"task6"}


# --- LOGGING SETUP ---
def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    #logging.FileHandler("run.log")


logger = logging.getLogger(__name__)


# --- YAML HELPERS ---
def safe_load_yaml(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        logger.debug(f"Failed to read YAML: {file_path} -> {e}")
        return None


def extract_syntax_name(yaml_data):
    try:
        return yaml_data["syntax"]["name"]
    except (TypeError, KeyError):
        return None


# --- VALIDATION ---
def is_measurement_folder(idx, folder_path, **kwargs):
    if stop_event.is_set():
        return None

    logger.debug(f"Checking folder: {folder_path}")

    try:
        files = os.listdir(folder_path)
    except OSError:
        return None

    mkv_files = [f for f in files if f.lower().endswith(".mkv")]
    yaml_files = [f for f in files if f.lower().endswith(".yaml")]

    if len(mkv_files) != 1 or len(yaml_files) < len(REQUIRED_SYNTAX_NAMES):
        return None

    found_syntax = set()

    for yf in yaml_files:
        if stop_event.is_set():
            return None

        yaml_path = os.path.join(folder_path, yf)
        data = safe_load_yaml(yaml_path)
        if data is None:
            continue

        syntax_name = extract_syntax_name(data)
        if syntax_name:
            found_syntax.add(syntax_name)

    logger.debug(f"Found syntax {found_syntax} in {folder_path}")

    if REQUIRED_SYNTAX_NAMES.issubset(found_syntax):
        return folder_path

    return None


def check_folder_exists(path_str):
    path = Path(path_str)
    
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    
    return path.exists()    


# --- YAML SEARCH ---
def find_yaml_by_syntax(folder_path, target_syntax_name):
    logger.debug(f"Searching for '{target_syntax_name}' in {folder_path}")

    try:
        files = os.listdir(folder_path)
    except OSError:
        return ("", None)

    for f in files:
        if not f.lower().endswith(".yaml"):
            continue

        yaml_path = os.path.join(folder_path, f)
        data = safe_load_yaml(yaml_path)
        if data is None:
            continue

        if extract_syntax_name(data) == target_syntax_name:
            return (f, data)

    return ("", None)


# --- FOLDER DISCOVERY ---
def find_measurement_folders(base_path):
    try:
        first_level = [
            os.path.join(base_path, d)
            for d in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, d))
        ]
    except OSError:
        return []

    measurement_folders = []

    for folder in first_level:
        try:
            subfolders = [
                os.path.join(folder, d)
                for d in os.listdir(folder)
                if os.path.isdir(os.path.join(folder, d))
            ]
        except OSError:
            continue

        if subfolders:
            measurement_folders.extend(subfolders)

    return measurement_folders or first_level


# --- GENERIC PARALLEL EXECUTION ---
def run_parallel(folders, worker_fn, num_workers, timeout, verbose, **kwargs):
    results = []

    try:

        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(worker_fn, idx, f, **kwargs): f for idx, f in enumerate(folders)}

            iterator = as_completed(futures)

            if not verbose:
                iterator = tqdm(iterator, total=len(futures), desc=worker_fn.__name__)

            for future in iterator:
                folder = futures[future]

                try:
                    result = future.result(timeout=timeout)
                    if result:
                        results.append(result)

                except TimeoutError:
                    logger.warning(f"Timeout processing: {folder}")

                except Exception as e:
                    logger.error(f"Error processing {folder}: {e}")

    except KeyboardInterrupt:
        logger.warning("CTRL-C received: stopping gracefully...")
        stop_event.set()
        executor.shutdown(wait=True, cancel_futures=True)

    return results


# --- PIPELINE STEPS ---

def _run_ffprobe(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def _parse_duration_to_seconds(duration_str):
    # supports "HH:MM:SS.micro"
    h, m, s = duration_str.split(":")
    return float(h) * 3600 + float(m) * 60 + float(s)


def get_audio_info(mkv_path):
    # 1. Get global container duration (more reliable)
    fmt_cmd = [
        _FFPROBE_EXE,
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        mkv_path
    ]
    fmt_data = _run_ffprobe(fmt_cmd)

    duration = float(fmt_data["format"]["duration"])

    # 2. Get ALL audio streams
    stream_cmd = [
        _FFPROBE_EXE,
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=sample_rate,channels,codec_name",
        "-of", "json",
        mkv_path
    ]
    stream_data = _run_ffprobe(stream_cmd)

    streams = stream_data.get("streams", [])
    if not streams:
        raise ValueError("No audio streams found")

    # 3. Choose a “best” stream (prefer highest sample rate)
    best_stream = None
    best_sr = -1

    for s in streams:
        sr = int(s.get("sample_rate", 0))
        if sr > best_sr:
            best_sr = sr
            best_stream = s

    if best_stream is None or best_sr <= 0:
        raise ValueError("Could not determine sample rate")

    sample_rate = best_sr

    # 4. Compute total samples (robust)
    total_samples = int(round(sample_rate * duration))

    return sample_rate, duration, total_samples


def generate_required_time_file(mkv_path, start_datetime, output_path="/tmp/", output_file="required_time.txt"):
    try:
        Fs, duration, total_samples = get_audio_info(mkv_path)
    except:
        logger.error(f"Invalid audio file: {mkv_path}")
        return 0
    
    # --- ALIGNMENT on 8ms boundaries for locata 8ms (120Hz) ---
    target_step_sec = 0.008
    samples_per_step = round(Fs * target_step_sec)
    step_duration = samples_per_step / Fs
    
    logger.debug(f"Sample rate: {Fs} Hz")
    logger.debug(f"Samples per step: {samples_per_step}")
    logger.debug(f"Actual step duration: {step_duration:.9f} s")
    
    current_sample = 0

    data_file = os.path.join(output_path, output_file)
    
    with open(data_file, "w") as f:
        f.write("year \tmonth \tday \thour \tminute \tsecond \tvalid_flag\n")
        
        while current_sample < total_samples:
            current_time = current_sample / Fs
            dt = start_datetime + timedelta(seconds=current_time)
            
            seconds = dt.second + dt.microsecond / 1e6
            
            row = [
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                f"{seconds:.3f}",
                1
            ]
            
            f.write("\t".join(map(str, row)) + "\n")
            
            current_sample += samples_per_step
    
    return total_samples


def find_verse_dataset(path, output_path, num_workers, timeout, verbose ):
    folders = find_measurement_folders(path)
    logger.info(f"Found {len(folders)} candidate folders")
    return run_parallel(folders, is_measurement_folder, num_workers, timeout, verbose, output_path=output_path)


def verse_to_locata(idx, path, **kwargs):
    if stop_event.is_set():
        return None

    output_path = ""
    if "output_path" in kwargs:
        output_path = kwargs["output_path"]
    else:
        return None

    logger.debug(f"Processing folder: {path}")

    # search mkv_descriptor

    mkv_descriptor, mkv_yaml = find_yaml_by_syntax(path, "verse_audio_mkv")
    if not mkv_descriptor or mkv_yaml is None:
        return None

    # try:
    #     source = mkv_yaml["sources"][0]
    # except (KeyError, IndexError, TypeError):
    #     logger.warning(f"Invalid YAML structure in {path}")
    #     return None


    # search scene descriptor

    scene_descriptor, scene_yaml = find_yaml_by_syntax(path, "audio_rendering_scene")
    if not scene_descriptor or scene_yaml is None:
        return None

    try:
        source = scene_yaml["setup"]["sources"][0]
    except (KeyError, IndexError, TypeError):
        logger.warning(f"Invalid YAML structure in {path}")
        return None

    # sanity check
    if( len(scene_yaml["setup"]["sources"]) != scene_yaml["setup"]["sources_count"] ):
        return None
    if( len(scene_yaml["setup"]["listeners"]) != scene_yaml["setup"]["listeners_count"] ):
        return None

    # select the locata task type

    task_type=""
    
    if(scene_yaml["setup"]["sources_count"] == 1):
        if ((scene_yaml["setup"]["sources"][0]["position"]["type"] == "static")):
            task_type = _LOCATA_TASK_TYPES["task1"]
        else:
            task_type = _LOCATA_TASK_TYPES["task3"]
    else:
        task_type = _LOCATA_TASK_TYPES["task2"]

        for s in scene_yaml["setup"]["sources"]:
            if scene_yaml["setup"]["sources"][s]["position"]["type"] == "dynamic":
               task_type = _LOCATA_TASK_TYPES["task4"]

    # select the locata data type

    data_type=""
    tmp_list = os.path.normpath(mkv_yaml["file"]).lstrip(os.path.sep).split(os.path.sep)
    for d in LOCATA_DATA_TYPES:
        if d in tmp_list:
            data_type = LOCATA_DATA_TYPES[d]

    output_locata_path = ""
    if "datasets" in tmp_list:
        output_locata_path = os.path.join(output_path, "locata", tmp_list[tmp_list.index("datasets")+1])
    else:
        for d in LOCATA_DATA_TYPES:
            if d in tmp_list:
                output_locata_path = os.path.join(output_path, "locata", tmp_list[tmp_list.index("datasets")+1])

    # mic array name from head definition in audio scene
    mic_array_name=scene_yaml["setup"]["listeners"][0]["subtype"]+"_"+scene_yaml["setup"]["listeners"][0]["info"]

    # additional locata data structure
    output_locata_path = os.path.join(output_locata_path, task_type, "recording"+str(idx), mic_array_name)

    # create output folder as per Locata syntax
    if not ( check_folder_exists(output_locata_path) ):
        return None

    # print("===")
    # print(idx)
    # print(output_locata_path)
    # print(len(scene_yaml["setup"]["sources"]))
    # print(task_type)
    # # print(scene_yaml)

    start_dt = datetime.now()

    total_audio_samples = generate_required_time_file(mkv_yaml["file"], start_dt, output_path=output_locata_path, output_file="required_time.txt")

    time.sleep(1)  # simulate work

    return (path, mkv_descriptor, source)


def export_to_locata(folders, output_path, num_workers, timeout, verbose):
    return run_parallel(folders, verse_to_locata, num_workers, timeout, verbose, output_path=output_path)


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Dataset pipeline")
    parser.add_argument("-p", "--input_path", required=True)
    parser.add_argument("-o", "--output_path", required=True)
    parser.add_argument("-m", "--max-workers", type=int, default=os.cpu_count())
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout per task (seconds)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (disables progress bar)")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not os.path.isdir(args.input_path):
        logger.error(f"Invalid path: {args.path}")
        return

    if not os.path.isdir(args.output_path):
        logger.error(f"Invalid path: {args.path}")
        return

    results = find_verse_dataset(args.input_path, args.output_path, args.max_workers, args.timeout, args.verbose)
    logger.info(f"Valid folders: {len(results)}")

    results = export_to_locata(results, args.output_path, args.max_workers, args.timeout, args.verbose)
    logger.info(f"Processed results: {len(results)}")


if __name__ == "__main__":
    main()