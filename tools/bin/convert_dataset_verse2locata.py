#!/usr/bin/env python3

import os
import argparse
import yaml
import subprocess
import json
import shutil
import time
import re
import logging
import tempfile
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed, TimeoutError
from tqdm import tqdm
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
import numpy as np
import pandas as pd
import soundfile as sf
import webrtcvad
import scipy.signal


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
_RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../../", "resources")
_DATASET_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../../", "datasets")

_FFPROBE_EXE = "/usr/bin/ffprobe"
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_MKVEXTRACT_EXE = "/usr/bin/mkvextract"
_MKVMERGE_EXE = "/usr/bin/mkvmerge"

_LOCATA_TASK_TYPES={'task1':"task1",'task2':"task2",'task3':"task3",'task4':"task4",'task5':"task5",'task6':"task6"}


class ColoredFormatter(logging.Formatter):

    # ANSI escape codes
    COLORS = {
        logging.DEBUG: "\033[90m",      # light gray
        logging.INFO: "\033[92m",       # green
        logging.WARNING: "\033[93m",    # yellow
        logging.ERROR: "\033[91m",      # red
        logging.CRITICAL: "\033[1;91m", # bold red
    }

    RESET = "\033[0m"

    def format(self, record):

        color = self.COLORS.get(
            record.levelno,
            self.RESET
        )

        message = super().format(record)

        return f"{color}{message}{self.RESET}"


# --- LOGGING SETUP ---
def setup_logging_simple(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    #logging.FileHandler("run.log")
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler()

    formatter = ColoredFormatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    )

    handler.setFormatter(formatter)

    logger = logging.getLogger()

    logger.setLevel(level)

    # Remove duplicated handlers
    logger.handlers.clear()

    logger.addHandler(handler)

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

#
# --- VAD: VOICE ACTIVATION DETECTION
#

def speed_of_sound_mps(
    temperature_celsius
):

    #
    # c(T) = 331.3 + 0.606*T
    #

    return 331.3 + 0.606 * temperature_celsius

def adjust_peak_dbfs(audio, target_peak_dbfs):

    # Current peak amplitude
    peak = np.max(np.abs(audio))

    if peak <= 0:
        return audio

    # Current peak dBFS
    current_peak_dbfs = 20.0 * np.log10(peak)

    # Gain needed
    gain_db = target_peak_dbfs - current_peak_dbfs

    # Linear gain
    gain = 10.0 ** (gain_db / 20.0)

    audio_out = audio * gain

    # Prevent clipping
    audio_out = np.clip(audio_out, -1.0, 1.0)

    return audio_out


def resample_if_needed(audio, sr, target_sr=16000):

    if sr == target_sr:
        return audio, sr

    n_samples = int(len(audio) * target_sr / sr)

    audio_rs = scipy.signal.resample(audio, n_samples)

    return audio_rs, target_sr


def float_to_pcm16(audio):

    audio = np.clip(audio, -1.0, 1.0)

    return (audio * 32767).astype(np.int16)


def remap_vad_mask_to_original_sr(
    vad_mask,
    original_num_samples,
    original_sr,
    vad_sr=16000
):

    scale = vad_sr / original_sr

    indices = (
        np.arange(original_num_samples) * scale
    ).astype(np.int64)

    indices = np.clip(
        indices,
        0,
        len(vad_mask) - 1
    )

    return vad_mask[indices]


def compute_vad_mask(
    wav_path,
    target_peak_dbfs=-6.0,
    target_sr=16000,
    vad_mode=2,
    vad_frame_ms=10,
    hop_ms=5,
    tolerance_ms=50
):

    import numpy as np
    import soundfile as sf
    import webrtcvad

    # ========================================================
    # LOAD AUDIO
    # ========================================================

    audio, input_sr = sf.read(wav_path)

    if audio.ndim != 1:
        raise ValueError("compute_vad_mask: input WAV must be mono")

    input_samples = len(audio)

    logger.debug(f"Compute VAD mask: {wav_path}")

    # ========================================================
    # RESAMPLE (ONLY FOR VAD DECISION)
    # ========================================================

    audio_vad, vad_sr = resample_if_needed(
        audio, input_sr, target_sr=target_sr
    )

    pcm16 = float_to_pcm16(audio_vad)

    # ========================================================
    # VAD SETUP
    # ========================================================

    vad = webrtcvad.Vad(vad_mode)

    frame_samples = int(vad_sr * vad_frame_ms / 1000)
    hop_samples = int(vad_sr * hop_ms / 1000)

    accumulator = np.zeros(len(pcm16), dtype=np.float32)
    frame_events = []

    # ========================================================
    # FRAME LOOP (CENTER SYNCED)
    # ========================================================

    for start in range(0, len(pcm16) - frame_samples, hop_samples):

        stop = start + frame_samples

        frame = pcm16[start:stop]

        is_speech = vad.is_speech(frame.tobytes(), vad_sr)

        # ----------------------------------------------------
        # FRAME CENTER (canonical index in VAD domain)
        # ----------------------------------------------------

        center_vad = start + frame_samples // 2

        # map center to original sample index (NO rounding drift)
        center_ratio = center_vad / vad_sr
        center_orig = int(center_ratio * input_sr)

        frame_events.append({
            "center_orig": center_orig,
            "is_speech": bool(is_speech)
        })

        # accumulate in VAD domain first
        if is_speech:
            accumulator[start:stop] += 1.0

    # ========================================================
    # BINARY MASK (still in VAD domain)
    # ========================================================

    vad_mask = (accumulator > 0).astype(np.uint8)

    # ========================================================
    # CAUSAL EXPANSION (still VAD domain)
    # ========================================================

    tolerance_samples = int(tolerance_ms * vad_sr / 1000)

    if tolerance_samples > 0:

        kernel = np.ones(tolerance_samples + 1, dtype=np.uint8)

        expanded = np.convolve(vad_mask, kernel, mode="full")[:len(vad_mask)]

        vad_mask = (expanded > 0).astype(np.uint8)

    # ========================================================
    # FINAL REMAP (single consistent mapping step)
    # ========================================================

    final_vad_mask = remap_vad_mask_to_original_sr(
        vad_mask,
        original_num_samples=input_samples,
        original_sr=input_sr,
        vad_sr=vad_sr
    )

    return final_vad_mask, input_sr, frame_events

#
# --- VAD: VOICE ACTIVATION DETECTION with DISTANCE DELAY COMPENSATION
#


def compute_average_distance_vad_frame(
    source_positions_df,
    receiver_positions_df,
    start_sample,
    stop_sample
):

    src_xyz = source_positions_df[
        start_sample:stop_sample
    ][["x", "y", "z"]].values

    rx_xyz = receiver_positions_df[
        start_sample:stop_sample
    ][["x", "y", "z"]].values

    distances = np.linalg.norm(
        src_xyz - rx_xyz,
        axis=1
    )

    return np.mean(distances)


def compute_propagation_aware_vad_mask(
    wav_path,
    source_position_file,
    receiver_position_file,
    air_temperature_celsius=20.0,
    target_peak_dbfs=-6.0,
    target_sr=16000,
    vad_mode=2,
    vad_frame_ms=10,
    hop_ms=5,
    tolerance_ms=50
):

    import numpy as np
    import pandas as pd
    import soundfile as sf
    import webrtcvad

    # ========================================================
    # LOAD AUDIO
    # ========================================================

    audio, input_sr = sf.read(wav_path)

    if audio.ndim != 1:
        raise ValueError("compute_propagation_aware_vad_mask: input WAV must be mono")

    input_samples = len(audio)

    # ========================================================
    # LOAD POSITION DATA
    # ========================================================

    src_df = pd.read_csv(source_position_file, sep="\t")
    rx_df = pd.read_csv(receiver_position_file, sep="\t")

    if (len(src_df) != len(rx_df)) or (len(src_df)!=input_samples) or (len(rx_df)!=input_samples):
        raise ValueError("compute_propagation_aware_vad_mask: input files invalid length")


    logger.debug(f"Compute propagation-aware VAD mask: {wav_path}")

    # ========================================================
    # RESAMPLE ONLY FOR VAD DECISION
    # ========================================================

    audio_vad, vad_sr = resample_if_needed(
        audio, input_sr, target_sr=target_sr
    )

    pcm16 = float_to_pcm16(audio_vad)

    vad = webrtcvad.Vad(vad_mode)

    frame_samples = int(vad_sr * vad_frame_ms / 1000)
    hop_samples = int(vad_sr * hop_ms / 1000)

    accumulator = np.zeros(input_samples, dtype=np.float32)
    frame_events = []

    c = speed_of_sound_mps(air_temperature_celsius)

    # ========================================================
    # FRAME LOOP (STRICT FRAME SYNC)
    # ========================================================

    for start in range(0, len(pcm16) - frame_samples, hop_samples):

        stop = start + frame_samples

        frame = pcm16[start:stop]

        is_speech = vad.is_speech(frame.tobytes(), vad_sr)

        # ----------------------------------------------------
        # FRAME CENTER (single canonical time index)
        # ----------------------------------------------------

        center_vad = start + frame_samples // 2

        center_time = center_vad / vad_sr
        center_orig = int(center_time * input_sr)

        # ====================================================
        # GEOMETRY AT SAME TIME INDEX
        # ====================================================

        src = src_df.iloc[center_orig][["x", "y", "z"]].values
        rx = rx_df.iloc[center_orig][["x", "y", "z"]].values

        distance = np.linalg.norm(src - rx)

        delay_samples = int((distance / c) * input_sr)

        # ====================================================
        # APPLY PROPAGATION IN SAME FRAME DOMAIN
        # ====================================================

        if is_speech:

            # correct physical propagation direction
            arrival_center = center_orig + delay_samples

            half = int((frame_samples / vad_sr) * input_sr / 2)

            start_orig = arrival_center - half
            stop_orig = arrival_center + half

            start_orig = max(0, start_orig)
            stop_orig = min(input_samples, stop_orig)

            if stop_orig > start_orig:
                accumulator[start_orig:stop_orig] += 1.0

        frame_events.append({
            "center_orig": center_orig,
            "delay_samples": delay_samples,
            "distance_m": distance,
            "is_speech": bool(is_speech)
        })

    # ========================================================
    # FINAL MASK (SAME DOMAIN AS BASELINE)
    # ========================================================

    vad_mask = (accumulator > 0).astype(np.uint8)

    return vad_mask, input_sr, frame_events



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

    codec_name = str(s.get("codec_name",0))

    # 4. Compute total samples 
    total_samples = int(round(sample_rate * duration))

    return sample_rate, duration, total_samples, codec_name


def generate_timestamps_file(file_path, start_datetime, output_path="/tmp/", output_file="required_time.txt", target_time_step_seconds=0.008):
    try:
        Fs, duration, total_samples, codec_name = get_audio_info(file_path)
    except:
        logger.error(f"Invalid audio file: {file_path}")
        return 0
    
    if(target_time_step_seconds < 0):
        logger.error(f"Invalid time_step for: {file_path}")
        return 0

    # note: if target_time_step is zero we want ALL samples
    if(target_time_step_seconds > 0):
        # --- ALIGNMENT on 8ms boundaries for locata 8ms (120Hz) ---
        target_step_sec = target_time_step_seconds
        samples_per_step = round(Fs * target_step_sec)
        step_duration = samples_per_step / Fs
        
        logger.debug(f"Sample rate: {Fs} Hz")
        logger.debug(f"Samples per step: {samples_per_step}")
        logger.debug(f"Actual step duration: {step_duration:.9f} s")
    else:
        samples_per_step = 1
    
    current_sample = 0

    data_file = os.path.join(output_path, output_file)

    logger.debug(f"Generating timestamp file for: {file_path}")

    timestamps=[]

    while current_sample < total_samples:

        current_time = current_sample / Fs
        dt = start_datetime + timedelta(seconds=current_time)
        
        seconds = dt.second + dt.microsecond / 1e6

        if(target_time_step_seconds > 0):
            row = [
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                seconds,
                1
            ]
        else:
            row = [
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
                dt.minute,
                seconds
            ]

        timestamps.append(row) 

        current_sample += samples_per_step

    # check for early exit
    if stop_event.is_set():
        return -1

    # save to file
    if(target_time_step_seconds > 0):
        log_header = "\t".join(["year","month","day","hour","minute","second","valid_flag"])
        np.savetxt(data_file, timestamps, fmt=["%d", "%d", "%d", "%d", "%d", "%.3f", "%d"], delimiter="\t", header=log_header, comments="")
    else:
        log_header = "\t".join(["year","month","day","hour","minute","second"])
        np.savetxt(data_file, timestamps, fmt=["%d", "%d", "%d", "%d", "%d", "%.13f"], delimiter="\t", header=log_header, comments="")

    return total_samples



def generate_vad_file(file_path, start_datetime, output_path="/tmp/", output_file="required_time.txt", target_time_step_seconds=0.008, source_position_file="", array_position_file=""):
    try:
        Fs, duration, total_samples, codec_name = get_audio_info(file_path)
    except:
        logger.error(f"Invalid audio file: {file_path}")
        return 0
    
    if(target_time_step_seconds < 0):
        logger.error(f"Invalid time_step for: {file_path}")
        return 0

    # note: if target_time_step is zero we want ALL samples
    if(target_time_step_seconds > 0):
        # --- ALIGNMENT on 8ms boundaries for locata 8ms (120Hz) ---
        target_step_sec = target_time_step_seconds
        samples_per_step = round(Fs * target_step_sec)
        step_duration = samples_per_step / Fs
        
        logger.debug(f"Sample rate: {Fs} Hz")
        logger.debug(f"Samples per step: {samples_per_step}")
        logger.debug(f"Actual step duration: {step_duration:.9f} s")
    else:
        samples_per_step = 1
    
    if stop_event.is_set():
        return -1

    # run VAD with position aware computation if we have info
    if ( (source_position_file!="") and (array_position_file!="") ):
        vad_mask, sr, frame_events = compute_propagation_aware_vad_mask(
            wav_path = file_path,
            source_position_file = source_position_file,
            receiver_position_file = array_position_file,
            air_temperature_celsius=23.0,
            target_peak_dbfs=-6.0,
            vad_mode=2,
            vad_frame_ms=10,
            hop_ms=5,
            tolerance_ms=50
        )
    else:
        vad_mask, sr, frame_events = compute_vad_mask(
            wav_path = file_path,
            target_peak_dbfs = -6.0,
            vad_mode = 2,
            vad_frame_ms = 10,
            hop_ms=5,
            tolerance_ms = 50
        )

    if stop_event.is_set():
        return -1

    data_file = os.path.join(output_path, output_file)

    logger.debug(f"Generating VAD file for: {file_path}")

    np.savetxt(data_file, vad_mask.reshape(-1, 1), fmt="%d",header="VAD", comments="")
    
    return len(vad_mask)

# ----------------------------------------------------
# 2. SPHERICAL -> CARTESIAN
# LOCATA-like convention:
#
# azimuth:
#   0 deg  -> +x
#   +90    -> +y
#
# elevation:
#   0 deg  -> xy plane
#   +90    -> +z
#
# ----------------------------------------------------

def spherical_to_cartesian(az_deg, el_deg, r, convention="locata"):

    conventions=["locata","verse"]

    x=0
    y=0
    z=0

    if(str(convention).lower() == "locata"):
        az = np.deg2rad(az_deg)
        el = np.deg2rad(el_deg)

        x = r * np.cos(el) * np.cos(az)
        y = r * np.cos(el) * np.sin(az)
        z = r * np.sin(el)

    elif(str(convention).lower() == "verse"):
        az = np.deg2rad(az_deg)
        el = np.deg2rad(el_deg)

        x = r * np.cos(el) * np.sin(az) * -1.0
        y = r * np.cos(el) * np.cos(az)
        z = r * np.sin(el)
    else:
        logger.error(f"Invalid convention type for spherical_to_cartesian: {convention}")
        x=-99
        y=-99
        z=-99

    return x, y, z


def read_trajectory_csv(filename):
    err=0
    cols = [
        'time_percent',
        'volume',
        'azimuth_deg',
        'elevation_deg',
        'distance',
        'coord_type'
    ]

    try:
        df = pd.read_csv(
            filename,
            comment='#',
            header=None,
            names=cols,
            skipinitialspace=True
        )
    except:
        err=-1

    return err, df

import numpy as np
import pandas as pd


def compute_reference_frame(
    trajectory_df,
    target_xyz,
    world_up=(0.0, 0.0, 1.0),
    singularity_threshold=0.9999,
):
    """
    Computation of reference vectors and rotation matrices.

    Coordinate convention
    ---------------------
    +Y : look / forward
    +Z : up
    +X : right

    Rotation matrix columns:
        col1 = right   (+X local axis)
        col2 = forward (+Y local axis)
        col3 = up      (+Z local axis)

    Parameters
    ----------
    trajectory_df : pandas.DataFrame
        Must contain columns:
            x, y, z

    target_xyz : iterable
        Target world coordinates:
            (tx, ty, tz)

    world_up : iterable
        Global up vector

    singularity_threshold : float
        Threshold for detecting parallelism between
        forward vector and world_up

    Returns
    -------
    pandas.DataFrame
        Original dataframe plus:

        ref_vec_x
        ref_vec_y
        ref_vec_z

        rotation_11 ... rotation_33
    """

    df = trajectory_df.copy()

    # -----------------------------------------------------
    # POSITIONS
    # -----------------------------------------------------

    positions = df[["x", "y", "z"]].to_numpy(dtype=np.float64)

    target = np.asarray(target_xyz, dtype=np.float64)

    world_up = np.asarray(world_up, dtype=np.float64)

    # -----------------------------------------------------
    # FORWARD / LOOK VECTOR
    # -----------------------------------------------------

    forward = target - positions

    norms = np.linalg.norm(forward, axis=1, keepdims=True)

    # avoid division by zero
    norms = np.where(norms < 1e-12, 1.0, norms)

    forward = forward / norms

    # -----------------------------------------------------
    # HANDLE SINGULARITIES
    #
    # if forward almost parallel to world_up
    # use temporary up = X axis
    # -----------------------------------------------------

    dot_fw_up = np.abs(forward @ world_up)

    tmp_up = np.tile(world_up, (len(df), 1))

    singular_mask = dot_fw_up > singularity_threshold

    tmp_up[singular_mask] = np.array([1.0, 0.0, 0.0])

    # -----------------------------------------------------
    # RIGHT VECTOR
    #
    # right = forward x up
    # -----------------------------------------------------

    right = np.cross(forward, tmp_up)

    right_norms = np.linalg.norm(right, axis=1, keepdims=True)

    right_norms = np.where(right_norms < 1e-12, 1.0, right_norms)

    right = right / right_norms

    # -----------------------------------------------------
    # TRUE UP VECTOR
    #
    # up = right x forward
    # -----------------------------------------------------

    up = np.cross(right, forward)

    up_norms = np.linalg.norm(up, axis=1, keepdims=True)

    up_norms = np.where(up_norms < 1e-12, 1.0, up_norms)

    up = up / up_norms

    # -----------------------------------------------------
    # ROTATION MATRICES
    #
    # columns = [right, forward, up]
    # -----------------------------------------------------

    R = np.stack((right, forward, up), axis=2)

    # -----------------------------------------------------
    # OUTPUT REFERENCE VECTOR
    #
    # forward direction
    # -----------------------------------------------------

    df["ref_vec_x"] = forward[:, 0]
    df["ref_vec_y"] = forward[:, 1]
    df["ref_vec_z"] = forward[:, 2]

    # -----------------------------------------------------
    # OUTPUT ROTATION MATRIX
    # -----------------------------------------------------

    for i in range(3):
        for j in range(3):
            df[f"rotation_{i+1}{j+1}"] = R[:, i, j]

    return df

def compute_position_dynamic(yaml_info="", start_datetime=0, duration_seconds=0, sample_rate=48000, total_samples=0, offset_xyz=[0,0,0], target_xyz=(0,0,0), rotation_matrix=[], source_wav=None):
    position=[]
    err=0

    if( duration_seconds==0 ):
        err=-1

    if(total_samples<1):
        err=-1

    try:
        if( yaml_info["position"]["type"].lower() != "dynamic" ):
            err=-1
    except:
        err=-1

    yaml_data=[]

    # --------------------------------------------------------
    # read the original .wav file and compute source duration from incoming sample_rate, extend position file if needed
    # --------------------------------------------------------

    # source_yaml = os.path.join(_RESOURCES_DIR, yaml_info["type"], yaml_info["subtype"], "info", yaml_info["info"]+".yaml" )
    # source_yaml_data = safe_load_yaml(source_yaml)
    # source_wav = os.path.join(_RESOURCES_DIR, yaml_info["type"], yaml_info["subtype"], source_yaml_data["file"])

    if source_wav is None:
        s_duration = duration_seconds
        s_Fs = sample_rate
        s_total_samples = total_samples    
    else:
        s_Fs, s_duration, s_total_samples, s_codec_name = get_audio_info(source_wav)


    if(err==0):

        path_file=os.path.join(_RESOURCES_DIR,yaml_info["position"]["value"]["type"],yaml_info["position"]["value"]["subtype"],"info",yaml_info["position"]["value"]["info"])

        try:
            yaml_data = safe_load_yaml(path_file)
            if yaml_data is None:
                logger.error(f"Cannot open dynamic path file: {path_file}")
                err = -1
            else:
                if (yaml_data["syntax"]["name"]!="path_map"):
                    logger.error(f"Invalid dynamic path file: {path_file}")
                    err = -1

                if (yaml_data["path_count"]!=1):
                    logger.error(f"Invalid dynamic path file: {path_file}")
                    err = -1
        except:
            err = -1

    if(err==0):
        path_csv = os.path.join(_RESOURCES_DIR,yaml_info["position"]["value"]["type"],yaml_info["position"]["value"]["subtype"],yaml_data["path"][0]["file"])

        # --------------------------------------------------------
        # Read CSV
        # --------------------------------------------------------

        err , df = read_trajectory_csv(path_csv)

        # --------------------------------------------------------
        # Convert anchor points to Cartesian
        # --------------------------------------------------------

        coord_type = df['coord_type'].iloc[0].strip().lower()

        if coord_type == 's':

            x, y, z = spherical_to_cartesian(
                df['azimuth_deg'].to_numpy(),
                df['elevation_deg'].to_numpy(),
                df['distance'].to_numpy(),
                convention="verse"
            )

            x = x + offset_xyz[0]
            y = y + offset_xyz[1]
            z = z + offset_xyz[2]

        elif coord_type == 'c':

            # assuming:
            # azimuth_deg -> x
            # elevation_deg -> y
            # distance -> z

            x = df['azimuth_deg'].to_numpy()
            y = df['elevation_deg'].to_numpy()
            z = df['distance'].to_numpy()

            x = x + offset_xyz[0]
            y = y + offset_xyz[1]
            z = z + offset_xyz[2]
        else:
            raise ValueError("Unknown coordinate type")

        # --------------------------------------------------------
        # Anchor timestamps (seconds)
        # --------------------------------------------------------

        anchor_times = (
            df['time_percent'].to_numpy() / 100.0
        ) * s_duration #duration_seconds

        # --------------------------------------------------------
        # Uniform sample timeline
        # --------------------------------------------------------

        n_samples = int((s_total_samples / s_Fs) * sample_rate)

        sample_times = np.arange(n_samples) / sample_rate

        # --------------------------------------------------------
        # Linear interpolation
        # --------------------------------------------------------

        x_interp = np.interp(sample_times, anchor_times, x)
        y_interp = np.interp(sample_times, anchor_times, y)
        z_interp = np.interp(sample_times, anchor_times, z)

        # --------------------------------------------------------
        # Datetime generation
        # --------------------------------------------------------

        timestamps = [
            start_datetime + timedelta(seconds=float(t))
            for t in sample_times
        ]

        # --------------------------------------------------------
        # Build final dataframe
        # --------------------------------------------------------
        position = pd.DataFrame({
            'year':   [t.year for t in timestamps],
            'month':  [t.month for t in timestamps],
            'day':    [t.day for t in timestamps],
            'hour':   [t.hour for t in timestamps],
            'minute': [t.minute for t in timestamps],

            # fractional seconds
            'second': [
                t.second + t.microsecond / 1e6
                for t in timestamps
            ],

            'x': x_interp,
            'y': y_interp,
            'z': z_interp
        })

        # --------------------------------------------------------
        # extend the position file if the duration is shorter than required
        # --------------------------------------------------------
        if ( n_samples > total_samples):
            err = -1
            logger.error(f"compute_position_dynamic: source file duration {n_samples} is bigger than the requested {total_samples}")
        elif ( n_samples < total_samples ):
            
            e_sample_times = np.arange(
                n_samples,
                total_samples,
            ) / sample_rate

            e_timestamps = [
                start_datetime + timedelta(seconds=float(t))
                for t in e_sample_times
            ]

            e_position = pd.DataFrame({
                'year':   [t.year for t in e_timestamps],
                'month':  [t.month for t in e_timestamps],
                'day':    [t.day for t in e_timestamps],
                'hour':   [t.hour for t in e_timestamps],
                'minute': [t.minute for t in e_timestamps],

                # fractional seconds
                'second': [
                    t.second + t.microsecond / 1e6
                    for t in e_timestamps
                ],

                'x': np.repeat(x_interp[-1], len(e_timestamps)),
                'y': np.repeat(y_interp[-1], len(e_timestamps)),
                'z': np.repeat(z_interp[-1], len(e_timestamps))
            })


            position = pd.concat([position, e_position], ignore_index=True)


        # --------------------------------------------------------
        # in VERSE each speaker is pointing to the listener HEAD position
        # --------------------------------------------------------
        position_with_refvec = compute_reference_frame(
            position,
            target_xyz=target_xyz
        )

    return err, position_with_refvec

def compute_position_static(yaml_info="", start_datetime=0, duration_seconds=0, sample_rate=48000, total_samples=0, offset_xyz=[0,0,0], target_xyz=(0,0,0), rotation_matrix=[]):
    position=[]
    err=0

    if( duration_seconds==0 ):
        err=-1
    try:
        if( yaml_info["position"]["type"].lower() != "static" ):
            err=-1
    except:
        err=-1

    if(err==0):

        # --------------------------------------------------------
        # Convert anchor points to Cartesian
        # --------------------------------------------------------

        coord_type = yaml_info["position"]["coord"]["type"].strip().lower()

        if coord_type == 'spherical':

            x, y, z = spherical_to_cartesian(
                yaml_info["position"]["coord"]["value"][0],
                yaml_info["position"]["coord"]["value"][1],
                yaml_info["position"]["coord"]["value"][2],
                convention="verse"
            )

            x = x + offset_xyz[0]
            y = y + offset_xyz[1]
            z = z + offset_xyz[2]

        elif coord_type == 'cartesian':

            # assuming:
            # azimuth_deg -> x
            # elevation_deg -> y
            # distance -> z

            x = yaml_info["position"]["coord"]["value"][0] + offset_xyz.x
            y = yaml_info["position"]["coord"]["value"][1] + offset_xyz.y
            z = yaml_info["position"]["coord"]["value"][2] + offset_xyz.z

            x = x + offset_xyz[0]
            y = y + offset_xyz[1]
            z = z + offset_xyz[2]

        else:
            raise ValueError("Unknown coordinate type")

        # --------------------------------------------------------
        # Uniform sample timeline
        # --------------------------------------------------------

        # dt = 1.0 / sample_rate

        # sample_times = np.arange(
        #     0,
        #     duration_seconds,
        #     dt
        # )

        sample_times = np.arange(total_samples) / sample_rate

        # fixed position -> repeat anchor times
        anchor_times = sample_times

        # --------------------------------------------------------
        # Datetime generation
        # --------------------------------------------------------

        timestamps = [
            start_datetime + timedelta(seconds=float(t))
            for t in sample_times
        ]

        # --------------------------------------------------------
        # Build final dataframe
        # --------------------------------------------------------
        position = pd.DataFrame({
            'year':   [t.year for t in timestamps],
            'month':  [t.month for t in timestamps],
            'day':    [t.day for t in timestamps],
            'hour':   [t.hour for t in timestamps],
            'minute': [t.minute for t in timestamps],

            # fractional seconds
            'second': [
                t.second + t.microsecond / 1e6
                for t in timestamps
            ],

            # copy position (fixed)
            'x': x,
            'y': y,
            'z': z,
        })

        # --------------------------------------------------------
        # in VERSE each speaker is pointing to the listener HEAD position
        # --------------------------------------------------------
        position_with_refvec = compute_reference_frame(
            position,
            target_xyz=target_xyz
        )


    return err, position_with_refvec

def save_locata_position(position, output_filename):
    log_header = "\t".join(["year","month","day","hour","minute","second",
                  "x","y","z"])

    log_header_locata = "\t".join(["year","month","day","hour","minute","second",
                  "x","y","z",
                  "ref_vec_x","ref_vec_y","ref_vec_z",
                  "rotation_11","rotation_12","rotation_13",
                  "rotation_21","rotation_22","rotation_23",
                  "rotation_31","rotation_32","rotation_33"])

    try:
        if(len(position.columns)==9):
            np.savetxt(output_filename, position, fmt=["%d", "%d", "%d", "%d", "%d", "%.13f", "%.4f", "%.4f", "%.4f"], delimiter="\t", header=log_header, comments="")
        elif(len(position.columns)==21):
            np.savetxt(output_filename, position, fmt=["%d", "%d", "%d", "%d", "%d", "%.13f", # datetime
                                                       "%.4f", "%.4f", "%.4f",                # x,y,z
                                                       "%.4f", "%.4f", "%.4f",                # ref_vec
                                                       "%.4f", "%.4f", "%.4f",                # rotation matrix
                                                       "%.4f", "%.4f", "%.4f", 
                                                       "%.4f", "%.4f", "%.4f"], delimiter="\t", header=log_header_locata, comments="")
    except:
        logger.error(f"Error while saving position file: {output_filename}")


def generate_position_file(mkv_path, start_datetime, output_path="/tmp/", output_prefix="", output_postfix="loudspeaker_", scene="", offset_xyz=(0,0,0), target_xyz=(0,0,0)):

    err = 0

    if(scene==""):
        return -1

    yaml_scene = scene

    # check for mkv presence
    try:
        Fs, duration, total_samples, codec_name = get_audio_info(mkv_path)
    except:
        logger.error(f"Invalid audio file: {mkv_path}")
        err = -1
        return err

    # check for mkv descriptor presence
    tmp_path = Path(mkv_path)
    yaml_path = tmp_path.with_name(f"{tmp_path.stem}_{tmp_path.suffix.lstrip('.')}.yaml")
    yaml_data = safe_load_yaml(yaml_path)
    if yaml_data is None:
        logger.error(f"Invalid mkv_descriptor file: {yaml_path}")
        err = -1
        return err

    if stop_event.is_set():
        return -1

    for source_number, source_info in yaml_scene["setup"]["sources"].items():
        filename = f"position_source_{output_postfix}{str(source_number)}.txt"
        output_filename = os.path.join(output_path, filename)

        logger.debug(f"Compute position file for source: {output_filename}")

        if( source_info["position"]["type"].lower() not in ["static", "dynamic"] ):
            err=-1
            logger.error(f"Invalid source position type in file: {yaml_path}")
        else:
            if(source_info["position"]["type"]=="dynamic"):

                with tempfile.TemporaryDirectory() as tmpdir:            

                    # demux the audio source file
                    source_wav = "source_"+str(source_number)+"*.wav"
                    source_wav = os.path.join(tmpdir, source_wav)

                    try:
                        cmd = [
                            _FFMPEG_EXE,
                            "-v", "error",
                            "-y",                           # overwrite output
                            "-i", mkv_path,                 # input mkv
                            "-map", f"0:{source_number}",   # select track
                            "-c", "copy",            # no re-encoding
                            source_wav
                        ]
    
                        subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                        err,position = compute_position_dynamic(source_info, start_datetime, duration, Fs, total_samples, offset_xyz, target_xyz, source_wav)

                    except:
                       logger.error(f"compute_position_dynamic, cannot extract source wav: track {source_number} {mkv_path}")
                       err = -1                        
            else:
                err,position = compute_position_static(source_info, start_datetime, duration, Fs, total_samples, offset_xyz, target_xyz)

            if(err==0):
                save_locata_position(position, output_filename)
            else:
                logger.error(f"Error while computing source position in file: {yaml_path}{output_filename}")                

    for listener_number, listener_info in yaml_scene["setup"]["listeners"].items():
        if(listener_number > 0):
            err=-1
            logger.error(f"Invalid scene (listener count is > 1) for file: {mkv_path}")
        else:
            filename = f"position_array_{output_prefix}.txt"
            output_filename = os.path.join(output_path, filename)

            logger.debug(f"Compute position file for array: {output_filename}")

            if( listener_info["position"]["type"].lower() not in ["static", "dynamic"] ):
                err=-1
                logger.error(f"Invalid listener position type in file: {yaml_path}")
            else:
                if(listener_info["position"]["type"]=="dynamic"):
                    # ToDo: dynamic listener to be verified, verse has static listener for now.
                    err,position = compute_position_dynamic(listener_info, start_datetime, duration, Fs, total_samples, offset_xyz, target_xyz)
                else:
                    err,position = compute_position_static(listener_info, start_datetime, duration, Fs, total_samples, offset_xyz, target_xyz)
 
                if(err==0):
                    save_locata_position(position, output_filename)
                else:
                    logger.error(f"Error while computing listener position in file: {yaml_path}")
    return err


def find_locata_position_files(
    audio_wav_path
):
    """
    Given a LOCATA audio source path, find:

    - matching source position file
    - matching array position file

    """

    err=0

    audio_path = Path(audio_wav_path)

    # Parent directory

    base_dir = audio_path.parent

    #
    # Example:
    # audio_source_talker0.wav

    audio_name = audio_path.stem

    # SOURCE POSITION FILE

    if not audio_name.startswith( "audio_source_" ):
        logger.error(
            f"Unexpected source audio filename: "
            f"{audio_name}"
            )
        return -1

    source_suffix = audio_name.replace(
        "audio_source_",
        "",
        1
    )

    source_position_filename = (
        f"position_source_{source_suffix}.txt"
    )

    source_position_path = (
        base_dir / source_position_filename
    )

    # MIC ARRAY POSITION FILE

    array_name = base_dir.name

    array_position_filename = (
        f"position_array_{array_name}.txt"
    )

    array_position_path = (
        base_dir / array_position_filename
    )

    # ========================================================
    # OPTIONAL EXISTENCE CHECKS
    # ========================================================

    if not source_position_path.exists():
        logger.error(
            f"Missing source position file:\n"
            f"{source_position_path}"
            )
        return -1

    if not array_position_path.exists():
        logger.error(
            f"Missing array position file:\n"
            f"{array_position_path}"
            )
        return -1

    return err, str(source_position_path), str(array_position_path)

    # return {
    #     "source_position_file":
    #         str(source_position_path),

    #     "array_position_file":
    #         str(array_position_path)
    # }


def generate_source_audio_files(mkv_path, start_datetime, output_path="/tmp/", output_prefix="audio_source_", output_postfix="loudspeaker_", audio_samples=0):
    err = 0

    # check for mkv presence
    try:
        Fs, duration, total_samples, codec_name = get_audio_info(mkv_path)
    except:
        logger.error(f"Invalid audio file: {mkv_path}")
        err = -1
        return err

    # check for mkv descriptor presence
    tmp_path = Path(mkv_path)
    yaml_path = tmp_path.with_name(f"{tmp_path.stem}_{tmp_path.suffix.lstrip('.')}.yaml")
    yaml_data = safe_load_yaml(yaml_path)
    if yaml_data is None:
        logger.error(f"Invalid mkv_descriptor file: {yaml_path}")
        err = -1
        return err

    for source_number, source_info in yaml_data["sources"].items():

        if stop_event.is_set():
            return -1

        channels = source_info.get("channels")
        track_id = source_info.get("track_id")

        filename = f"{output_prefix}{output_postfix}{str(track_id)}.wav"
        output_filename = os.path.join(output_path, filename)

        # demux the audio source file
        cmd = [
            _FFMPEG_EXE,
            "-v", "error",
            "-y",                      # overwrite output
            "-i", mkv_path,            # input mkv
            "-map", f"0:{track_id}",   # select track
            "-c", "copy",            # no re-encoding
            output_filename
        ]

        try:
            subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            try:
                Fs, duration, total_samples, codec_name = get_audio_info(output_filename)
            except:
                logger.error(f"Invalid audio file: {output_filename}")
                err = -1

            if(audio_samples != total_samples):
                if(audio_samples > total_samples):

                    p = Path(output_filename)
                    output_filename_orig = str(p.with_name(f"{p.stem}_orig{p.suffix}"))
                    shutil.copy2(p, output_filename_orig)

                    logger.debug(f"Padding audio track for {audio_samples}!={total_samples} on audio file: {output_filename} [{mkv_path}]")
                    cmd = [
                        _FFMPEG_EXE,
                        "-v", "error",
                        "-y",
                        "-i", output_filename_orig,
                        "-af",
                        f"apad=whole_len={audio_samples}", 
                        "-c", f"{codec_name}",
                        output_filename
                    ]

                    try:
                        subprocess.run(
                            cmd,
                            check=True,
                            stdin=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        os.remove(output_filename_orig)
                    except:
                        logger.error(f"Error while executing: {cmd}")
                        err = -1
                else:
                    logger.error(f"1 Invalid audio_samples count {audio_samples}!={total_samples} on audio file: {output_filename} [{mkv_path}]")
                    err=-1

                try:
                    Fs, duration, total_samples, codec_name = get_audio_info(output_filename)

                    if(total_samples != audio_samples):
                        logger.error(f"Invalid sample_count after padding audio file: {output_filename}")
                        err=-1
                except:
                    logger.error(f"Invalid audio file: {output_filename}")
                    err = -1                    

        except:
            logger.error(f"Cannot extrace track #{track_id} from {mkv_path}")
            err = -1
            return err


        # generate timestamps for source audio file
        if stop_event.is_set():
            return -1

        filename = f"{output_prefix}timestamps_{output_postfix}{str(track_id)}.txt"
        audio_samples = generate_timestamps_file(output_filename, start_datetime, output_path, output_file=filename, target_time_step_seconds=0)
        if(audio_samples != total_samples):
            logger.error(f"2 Invalid audio_samples count {audio_samples}!={total_samples} on audio file timestamps: {output_filename} [{mkv_path}]")
            err=-1

        # generate VAD timestamps for source audio file
        if stop_event.is_set():
            return -1

        filename = f"VAD_source_{output_postfix}{str(track_id)}.txt"
        audio_samples = generate_vad_file(output_filename, start_datetime, output_path, output_file=filename, target_time_step_seconds=0)
        if(audio_samples != total_samples):
            logger.error(f"3 Invalid audio_samples count {audio_samples}!={total_samples} on audio file VAD: {output_filename} [{mkv_path}]")
            err=-1

        if stop_event.is_set():
            return -1

    return err


def generate_array_audio_files(mkv_path, start_datetime, output_path="/tmp/", output_prefix="audio_array_", output_postfix="loudspeaker_",audio_samples=0, source_postfix="loudspeaker_"):
    err = 0

    # check for mkv presence
    try:
        Fs, duration, total_samples, codec_name = get_audio_info(mkv_path)
    except:
        logger.error(f"Invalid audio file: {mkv_path}")
        err = -1
        return err

    # check for mkv descriptor presence
    tmp_path = Path(mkv_path)

    yaml_path = tmp_path.with_name(f"{tmp_path.stem}_{tmp_path.suffix.lstrip('.')}.yaml")
    
    yaml_data = safe_load_yaml(yaml_path)
    
    if yaml_data is None:
        logger.error(f"Invalid mkv_descriptor file: {yaml_path}")
        err = -1
        return err

    # output filename for merged wav
    filename = f"{output_prefix}{output_postfix}.wav"
    
    output_filename = os.path.join(output_path, filename)        

    with tempfile.TemporaryDirectory() as tmpdir:

        extracted_wavs = []

        for receiver_number, receiver_info in yaml_data["receivers"].items():
            channels = receiver_info.get("channels")
            track_id = receiver_info.get("track_id")

            # extract audio tracks into mono files (ordered list)

            track_wav = os.path.join(tmpdir, f"receiver_{receiver_number}.wav")

            cmd = [
                _MKVEXTRACT_EXE,
                "-q",
                str(mkv_path),
                "tracks",
                f"{track_id}:{track_wav}"
            ]

            try:
                subprocess.run(
                    cmd,
                    check=True,
                    stdin=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except:
                err = -1

            # add to the list if no errors
            if err==0:

                if channels == 1:
                    extracted_wavs.append(track_wav)
                else:
                    for channel_number in range(channels):

                        tmp_wav = os.path.join(tmpdir, f"receiver_{receiver_number}_{channel_number}.wav")

                        pan_filter = f"pan=mono|c0=c{channel_number}"
            
                        cmd = [
                            _FFMPEG_EXE,
                            "-v", "error",
                            "-y",
                            "-i", str(track_wav),
                            "-filter:a", pan_filter,                    
                            "-c:a", codec_name,
                            str(tmp_wav)
                        ]

                        try:
                            subprocess.run(
                                cmd,
                                check=True,
                                stdin=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )

                            # check if we need to do zero padding on the wav file
                            tmp_Fs, tmp_duration, tmp_total_samples, tmp_codec_name = get_audio_info(tmp_wav)


                            if(total_samples != tmp_total_samples):
                                logger.warning(f"Different audio track length for {total_samples}!={tmp_total_samples} on audio file: {tmp_wav} [{mkv_path}]")

                                if(total_samples > tmp_total_samples):

                                    p = Path(tmp_wav)
                                    tmp_wav_orig = str(p.with_name(f"{p.stem}_orig{p.suffix}"))
                                    shutil.copy2(p, tmp_wav_orig)

                                    logger.debug(f"Padding audio track for {audio_samples}!={total_samples} on audio file: {output_filename} [{mkv_path}]")
                                    cmd = [
                                        _FFMPEG_EXE,
                                        "-v", "error",
                                        "-y",
                                        "-i", tmp_wav_orig,
                                        "-af",
                                        f"apad=whole_len={audio_samples}", 
                                        #"-c", f"{codec_name}",
                                        tmp_wav
                                    ]

                                    try:
                                        subprocess.run(
                                            cmd,
                                            check=True,
                                            stdin=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL
                                        )

                                        os.remove(tmp_wav_orig)

                                    except:
                                        logger.error(f"Error while executing: {cmd}")
                                        err = -1

                            try:
                                tmp_Fs, tmp_duration, tmp_total_samples, tmp_codec_name = get_audio_info(tmp_wav)

                                if(tmp_total_samples != audio_samples):
                                    logger.error(f"Invalid sample_count after padding audio file: {output_filename}")
                                    err = -1
                                else:
                                    extracted_wavs.append(tmp_wav)

                            except:
                                logger.error(f"Invalid audio file: {output_filename}")
                                err = -1
                        except:
                            err = -1

        # now mux all track in one single .wav file as per locata sintax
        if(err == 0):
            n_inputs = len(extracted_wavs)
            filter_complex = f"amerge=inputs={n_inputs}"

            cmd = [
                _FFMPEG_EXE,
                "-v", "error",
                "-y",
            ]

            # add all inputs
            for wav in extracted_wavs:
                cmd += ["-i", str(wav)]

            cmd += [
                "-filter_complex", filter_complex,
                "-c:a", codec_name,
                str(output_filename)
            ]

            logger.debug(f"Extracting array audio file: {output_filename}")

            subprocess.run(
                cmd,
                check=True,
                stdin=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            try:
                Fs, duration, total_samples, codec_name = get_audio_info(output_filename)
            except:
                logger.error(f"Invalid audio file: {output_filename}")
                err = -1

            if(audio_samples != total_samples):
                logger.error(f"4 Invalid audio_samples count {audio_samples}!={total_samples} on audio file: {output_filename}")
                err=-1



        # generate array timestamps for array audio file
        if stop_event.is_set():
            return -1

        if(err == 0):
            filename = f"{output_prefix}timestamps_{output_postfix}.txt"
            audio_samples = generate_timestamps_file(output_filename, start_datetime, output_path, output_file=filename, target_time_step_seconds=0)
            if(audio_samples != total_samples):
                logger.error(f"5 Invalid audio_samples count {audio_samples}!={total_samples} on audio file timestamps: {output_filename}")
                err=-1

        #
        # now generate array timestamps and VAD for each received array-source pair
        #

        with tempfile.TemporaryDirectory() as tmpdir:

            # ToDo: IMPORTANT we need to extract source audio AND compensate for the source-destination distance (free air)
            for source_number, source_info in yaml_data["sources"].items():

                if stop_event.is_set():
                    return -1

                channels = source_info.get("channels")
                track_id = source_info.get("track_id")

                filename = f"{output_prefix}{output_postfix}{str(track_id)}.wav"
                output_filename = os.path.join(tmpdir, filename)

                # demux the audio source file
                cmd = [
                    _FFMPEG_EXE,
                    "-v", "error",
                    "-y",                      # overwrite output
                    "-i", mkv_path,            # input mkv
                    "-map", f"0:{track_id}",   # select track
                    "-c", "copy",            # no re-encoding
                    output_filename
                ]

                try:
                    subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                    try:
                        Fs, duration, total_samples, codec_name = get_audio_info(output_filename)
                    except:
                        logger.error(f"Invalid audio file: {output_filename}")
                        err = -1

                    if(audio_samples != total_samples):
                        if(audio_samples > total_samples):

                            p = Path(output_filename)
                            output_filename_orig = str(p.with_name(f"{p.stem}_orig{p.suffix}"))
                            shutil.copy2(p, output_filename_orig)

                            logger.debug(f"Padding audio track for {audio_samples}!={total_samples} on audio file: {output_filename} [{mkv_path}]")
                            cmd = [
                                _FFMPEG_EXE,
                                "-v", "error",
                                "-y",
                                "-i", output_filename_orig,
                                "-af",
                                f"apad=whole_len={audio_samples}", 
                                "-c", f"{codec_name}",
                                output_filename
                            ]

                            try:
                                subprocess.run(
                                    cmd,
                                    check=True,
                                    stdin=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL
                                )
                                os.remove(output_filename_orig)
                            except:
                                logger.error(f"Error while executing: {cmd}")
                                err = -1
                        else:                        
                            logger.error(f"6 Invalid audio_samples count {audio_samples}!={total_samples} on audio file: {output_filename} [{mkv_path}]")
                            err=-1

                        try:
                            Fs, duration, total_samples, codec_name = get_audio_info(output_filename)

                            if(total_samples != audio_samples):
                                logger.error(f"Invalid sample_count after padding audio file: {output_filename}")
                                err=-1
                        except:
                            logger.error(f"Invalid audio file: {output_filename}")
                            err = -1


                except:
                    logger.error(f"Cannot extrace track #{track_id} from {mkv_path}")
                    err = -1
                    return err

                if(err == 0):

                    source_filename = "audio_source_"+str(source_postfix)+str(track_id)+".wav"
                    source_filename = os.path.join(output_path, source_filename)

                    # search if we have position information for source and array
                    source_position_file="" 
                    array_position_file=""
                    position_err, source_position_file, array_position_file = find_locata_position_files( audio_wav_path=source_filename )

                    filename = f"VAD_{output_postfix}_{source_postfix}{str(track_id)}.txt"
                    audio_samples = generate_vad_file(  output_filename, start_datetime, output_path, output_file=filename, 
                                                        target_time_step_seconds=0, source_position_file=source_position_file, array_position_file=array_position_file)
                    if(audio_samples != total_samples):
                        logger.error(f"7 Invalid audio_samples count {audio_samples}!={total_samples} on audio file VAD: {output_filename} [{mkv_path}]")
                        err=-1

    return err


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

    # retrieve the listener target position from command line

    array_pos_x, array_pos_y, array_pos_z = kwargs["position"]

    array_pos = (array_pos_x, array_pos_y, array_pos_z)

    # search mkv_descriptor

    mkv_descriptor, mkv_yaml = find_yaml_by_syntax(path, "verse_audio_mkv")
    if not mkv_descriptor or mkv_yaml is None:
        return None

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
    output_locata_path = os.path.join(output_locata_path, data_type, task_type, "recording"+str(idx), mic_array_name)

    # STEP-1: create output folder as per Locata syntax

    if stop_event.is_set():
        return None

    if not ( check_folder_exists(output_locata_path) ):
        return None

    start_dt = datetime.now()
    total_audio_samples = generate_timestamps_file(mkv_yaml["file"], start_dt, output_path=output_locata_path, output_file="required_time.txt", target_time_step_seconds=0.008)

    # STEP-2: create audio source and mic-array files

    if stop_event.is_set():
        return None

    # setting output_postfix as per LOCATA naming convention, but for VERSE this is always a loudspeaker since we have no "real life" speaker person in the room.
    output_postfix = "loudspeaker"
    if(task_type==_LOCATA_TASK_TYPES["task3"] or task_type==_LOCATA_TASK_TYPES["task4"]):
        output_postfix = "talker"

    err = generate_position_file(mkv_yaml["file"], start_dt, output_path=output_locata_path, output_prefix=mic_array_name, output_postfix=output_postfix, scene=scene_yaml, offset_xyz=array_pos, target_xyz=array_pos)
    if ( err != 0):
        return None

    # check for early exit
    if stop_event.is_set():
        return None

    err = generate_source_audio_files(mkv_yaml["file"], start_dt, output_path=output_locata_path, audio_samples=total_audio_samples, output_postfix=output_postfix)
    if ( err != 0):
        return None

    # check for early exit
    if stop_event.is_set():
        return None

    err = generate_array_audio_files(mkv_yaml["file"], start_dt, output_path=output_locata_path, output_postfix=mic_array_name, source_postfix=output_postfix, audio_samples=total_audio_samples)
    if ( err != 0):
        return None

    return (path, mkv_descriptor, source)


def export_to_locata(folders, output_path, num_workers, timeout, verbose, position):
    return run_parallel(folders, verse_to_locata, num_workers, timeout, verbose, position=position, output_path=output_path)


# --- MAIN ---
def main():
    parser = argparse.ArgumentParser(description="Dataset pipeline")
    parser.add_argument("-i", "--input_path", required=True)
    parser.add_argument("-o", "--output_path", required=True)
    parser.add_argument("-m", "--max-workers", type=int, default=os.cpu_count())
    parser.add_argument("-t", "--timeout", type=int, default=10, help="Timeout per task (seconds)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (disables progress bar)")
    parser.add_argument("-p", "--position", nargs=3, type=float, metavar=("X", "Y", "Z"), default=(0,0,1), required=False, help="mic array coord (x,y,z) static" )

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

    results = export_to_locata(results, args.output_path, args.max_workers, args.timeout, args.verbose, args.position)
    logger.info(f"Processed results: {len(results)}")


if __name__ == "__main__":
    main()