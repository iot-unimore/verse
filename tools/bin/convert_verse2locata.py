#!/usr/bin/env python3

import os
import argparse
import yaml
import time
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from tqdm import tqdm


# --- GLOBALS ---
manager = multiprocessing.Manager()
stop_event = manager.Event()

LOCATA_TASK_TYPES={'task1':"task1",'task2':"task2",'task3':"task3",'task4':"task4",'task5':"task5",'task6':"task6"}

REQUIRED_SYNTAX_NAMES = {
    "audio_rendering_scene",
    "verse_audio_mkv"
}


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
def is_measurement_folder(folder_path):
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
def run_parallel(folders, worker_fn, num_workers, timeout, verbose):
    results = []

    try:
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            futures = {executor.submit(worker_fn, f): f for f in folders}

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
def find_verse_dataset(path, num_workers, timeout, verbose):
    folders = find_measurement_folders(path)
    logger.info(f"Found {len(folders)} candidate folders")
    return run_parallel(folders, is_measurement_folder, num_workers, timeout, verbose)


def verse_to_locata(path):
    if stop_event.is_set():
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

    task_type=None
    
    if(scene_yaml["setup"]["sources_count"] == 1):
        if ((scene_yaml["setup"]["sources"][0]["position"]["type"] == "static")):
            task_type = LOCATA_TASK_TYPES["task1"]
        else:
            task_type = LOCATA_TASK_TYPES["task3"]
    else:
        task_type = LOCATA_TASK_TYPES["task2"]

        for s in scene_yaml["setup"]["sources"]:
            if scene_yaml["setup"]["sources"][s]["position"]["type"] == "dynamic":
               task_type = LOCATA_TASK_TYPES["task4"]


    print(len(scene_yaml["setup"]["sources"]))
    print(task_type)
    print(scene_yaml)

    time.sleep(1)  # simulate work

    return (path, mkv_descriptor, source)


def export_to_locata(folders, num_workers, timeout, verbose):
    return run_parallel(folders, verse_to_locata, num_workers, timeout, verbose)


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Dataset pipeline")
    parser.add_argument("-p", "--path", required=True)
    parser.add_argument("-m", "--max-workers", type=int, default=os.cpu_count())
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout per task (seconds)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (disables progress bar)")

    args = parser.parse_args()

    setup_logging(args.verbose)

    if not os.path.isdir(args.path):
        logger.error(f"Invalid path: {args.path}")
        return

    results = find_verse_dataset(args.path, args.max_workers, args.timeout, args.verbose)
    logger.info(f"Valid folders: {len(results)}")

    results = export_to_locata(results, args.max_workers, args.timeout, args.verbose)
    logger.info(f"Processed results: {len(results)}")


if __name__ == "__main__":
    main()