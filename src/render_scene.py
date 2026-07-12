#!/usr/bin/env python3
"""Render audio scene"""

import os
import re
import yaml
import logging
import signal
import argparse
import random
import time
import shutil
import glob

import json
import subprocess
from subprocess import check_output

from multiprocessing import Pool
from setproctitle import setproctitle
from pathlib import Path
from datetime import datetime

#
# Set logger format and color
#
logger = logging.getLogger(__name__)

# short format (default for -v/-vv): no source location
# full format (-vvv only): adds [filename->funcName():lineno] for deep tracing
FORMAT_SHORT = "%(asctime)s [%(levelname)s] %(message)s"
FORMAT_FULL = "%(asctime)s [%(levelname)s] [%(filename)s->%(funcName)s():%(lineno)s] %(message)s"


class ColoredFormatter(logging.Formatter):
    """Same colored console formatter used by tools/bin/convert_dataset_verse2locata.py,
    kept consistent across the VERSE toolchain."""

    # ANSI escape codes
    COLORS = {
        logging.DEBUG: "\033[90m",  # light gray
        logging.INFO: "\033[92m",  # green
        logging.WARNING: "\033[93m",  # yellow
        logging.ERROR: "\033[91m",  # red
        logging.CRITICAL: "\033[1;91m",  # bold red
    }

    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


def setup_logging(verbose, logfile=None, quiet=False, silent=False):
    """Configure logging for the whole process: colored console output, plus an
    optional plain-text file handler when a logfile path is given.

    verbose is a count:
      0 (default) -> WARNING, short format
      1 (-v)      -> INFO, short format
      2 (-vv)     -> DEBUG, short format
      3+ (-vvv)   -> DEBUG, full format (adds [filename->funcName():lineno])

    -q/--quiet and -s/--silent only affect the CONSOLE handler: they silence
    terminal output, but the optional -log FILE still records at the
    verbose-derived level. Kept identical to render_dataset.py's setup_logging()
    for consistent behavior across the toolchain (render_dataset spawns
    render_scene as a subprocess and propagates a matching set of flags).
    """
    if verbose >= 2:
        level = logging.DEBUG
    elif verbose == 1:
        level = logging.INFO
    else:
        level = logging.WARNING

    fmt = FORMAT_FULL if verbose >= 3 else FORMAT_SHORT

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # remove any pre-existing handlers (e.g. from a prior basicConfig call)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(fmt))
    console_handler.setLevel(logging.CRITICAL + 1 if (quiet or silent) else level)
    root_logger.addHandler(console_handler)

    if logfile is not None:
        file_handler = logging.FileHandler(logfile, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(fmt))
        root_logger.addHandler(file_handler)


#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_RESOURCES_DIR = os.path.abspath(os.path.dirname(__file__)) + "/../resources/"
_TOOLS_DIR = _ROOT_DIR + "/../tools/bin/"

_OUTPUT_REF_DIR = "/ref/"
_OUTPUT_TMP_DIR = "/tmp/"

_MIN_CPU_COUNT = 1  # we need at least one CPU for each compute process
_MIN_MEM_GB = 1  # min amount of memory for each compute process


#
# EXECUTABLES / EXTERNAL CMDs
#
_SOFA_PARSE_EXE = _TOOLS_DIR + "/parse_sofa.py"
_SSPAT_EXE = _TOOLS_DIR + "/sspat"
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_FFPROBE_EXE = "/usr/bin/ffprobe"


#
# TOOLS
#
def signal_handler(sig, frame):
    """SIGINT (Ctrl+C) handler: prints a notice and sets the global exit flag."""
    global _CTRL_EXIT_SIGNAL
    print("\npressed Ctrl+C\n")
    _CTRL_EXIT_SIGNAL = 1


def readYamlFile(filename=None):
    """Load and parse a YAML file, returning its content (dict/list).
    Returns an empty list if filename is missing or the file can't be
    opened/parsed (error is logged, not raised)."""
    yaml_params = []
    if filename != None:
        try:
            with open(filename, "r") as file:
                yaml_params = yaml.safe_load(file)
        except:
            logger.error("cannot open/parse yaml file: {}".format(filename))
    else:
        logger.error("missing yaml filename")

    return yaml_params


def get_samplerate(wav_file):
    """Uses ffprobe to read the sample rate (Hz) of a WAV file's first
    audio stream. Returns it as a string (ffprobe's raw JSON value)."""
    cmd = [
        _FFPROBE_EXE,
        "-hide_banner",
        "-loglevel",
        "panic",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate",
        "-of",
        "json",
        str(wav_file),
    ]

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
    info = json.loads(result.stdout)
    return info["streams"][0]["sample_rate"]


def waitFileCompleted(filepath, stable_time=3.0, timeout=120.0, check_interval=0.5):
    """Poll a file's size until it stops changing for `stable_time` seconds,
    to detect that another (parallel) process has finished writing it.
    Returns True once stable, False if `timeout` elapses first."""
    filepath = Path(filepath)

    start_time = time.time()
    last_size = -1
    stable_start = None

    logger.debug("waiting for file complete: {}".format(filepath))

    while True:
        # Timeout check
        if time.time() - start_time > timeout:
            return False

        if not filepath.exists():
            time.sleep(check_interval)
            continue

        size = filepath.stat().st_size

        if size == last_size:
            if stable_start is None:
                stable_start = time.time()
            elif time.time() - stable_start >= stable_time:
                logger.debug("waiting for file complete. DONE.: {}".format(filepath))
                return True  # file stable
        else:
            stable_start = None  # reset stability timer

        last_size = size
        time.sleep(check_interval)


def resampleAudioFile(input_file, output_file, samplerate=0, overwrite=False):
    """Resample a WAV file to `samplerate` via ffmpeg, without re-encoding
    (detects and keeps the source codec). Used to reconcile source/HRTF
    samplerate mismatches before/after running sspat. No-ops if
    output_file already exists and overwrite=False. Raises ValueError on
    any failure (bad args, unreadable input, unsupported codec, ffmpeg error)."""

    codec_types = ["pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le", "pcm_f64le"]

    if not input_file and not output_file:
        raise ValueError("resampleAudioFile: provide in/out files.")

    if samplerate not in [8000, 16000, 32000, 44100, 48000, 96000]:
        raise ValueError("resampleAudioFile: invalid sample rate.")

    if not (Path(input_file).exists()):
        raise ValueError("resampleAudioFile: cannot open input file.")

    # skip unless overwrite requested
    elif (not (Path(output_file).exists())) or (overwrite == True):
        # detect audio file format
        cmd = [
            _FFPROBE_EXE,
            "-hide_banner",
            "-loglevel",
            "panic",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(input_file),
        ]
        try:
            codec_type = check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
        except:
            raise ValueError("resampleAudioFile: cannot detect input codec type.")

        codec_supported = False
        for codec in codec_types:
            if codec in codec_type:
                codec_supported = True
                codec_type = codec

        if not codec_supported:
            raise ValueError("resampleAudioFile: invalid input codec type.")

        # resample without re-encoding
        cmd = [
            _FFMPEG_EXE,
            "-y",
            "-i",
            str(input_file),
            "-ar",
            str(samplerate),
            "-c:a",
            str(codec_type),
            str(output_file),
        ]

        try:
            logger.debug("Running ffmpeg audio_resampling command:")
            logger.debug(" ".join(cmd))
            _ = check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()

        except:
            raise ValueError("resampleAudioFile: cannot resample audio file: {}.".format(input_file))
    else:
        logger.debug("file {} already done, skipping resample".format(str(output_file)))

    if not (Path(output_file).exists()):
        raise ValueError("resampleAudioFile: missing output file {}.".format(output_file))


def muxWavFilesMKV(mono_files, stereo_files, output_file):
    """
    Muxes mono and stereo .wav files into a single multi-track .mp4 file.
    Each file becomes a separate audio stream. No channel splitting is performed.

    Parameters:
    - mono_files: List of mono .wav file paths.
    - stereo_files: List of stereo .wav file paths.
    - output_file: Output multi-track .mkv file path (Matroska).
    """
    if not mono_files and not stereo_files:
        raise ValueError("Provide at least one mono or stereo file.")

    input_args = []
    map_args = []
    title_args = []

    all_inputs = mono_files + stereo_files

    for idx, file in enumerate(all_inputs):
        input_args.extend(["-i", file])
        map_args.extend(["-map", f"{idx}:a"])
        tmp_title = os.path.split(file)[1]
        title_args.append('-metadata:s:a:{} title="{}"'.format(idx, tmp_title))

    # Build FFmpeg command to mux inputs into an MP4 container
    cmd = [
        _FFMPEG_EXE,
        "-y",
        "-loglevel",
        "error",
        "-stats",
        *input_args,
        *map_args,
        *title_args,
        "-movflags",
        "+faststart",
        "-acodec",
        "copy",
        output_file,
        " > /dev/null 2>&1",
    ]

    logger.debug("Running ffmpeg command:")
    logger.debug(" ".join(cmd))

    os.system(" ".join(cmd))


def getSourceFilesSoundSpatializer(cfg_yaml={}, skip_sounds=True):
    """Extract the list of mono source .wav file paths from a sound_spatializer
    task config (cfg_yaml["sources"]), used to build the MKV's dry reference
    tracks. When skip_sounds=True (default), entries marked is_sound=True are
    excluded, per the -is/--include_sounds_output CLI option."""
    source_files = []

    if len(cfg_yaml) > 0:
        if "sources" in cfg_yaml:
            for sidx in cfg_yaml["sources"]:
                if skip_sounds and cfg_yaml["sources"][sidx].get("is_sound", False):
                    continue
                source_files.append(cfg_yaml["sources"][sidx]["file"])

    return source_files


def writeAudioMKVDescriptor(filename=None, mono_files=[], stereo_files=[], mkv_filename=None, scene_filename=None):
    """Write the .yaml descriptor accompanying a rendered MKV file: lists
    each mono source track and each stereo receiver track with their track
    IDs/channel counts, the MKV filename, and a reference back to the scene
    .yaml used to render it."""

    track_id = 0

    yaml_descriptor = {}

    if filename != None:
        yaml_descriptor["syntax"] = {}

        yaml_descriptor["syntax"]["name"] = "verse_audio_mkv"

        if mkv_filename == None:
            yaml_descriptor["file"] = os.path.split(filename)[1][0:-5] + ".mkv"
        else:
            yaml_descriptor["file"] = mkv_filename

        yaml_descriptor["sources_count"] = len(mono_files)
        yaml_descriptor["sources"] = {}
        idx = 0
        for file in mono_files:
            yaml_descriptor["sources"][idx] = {}
            yaml_descriptor["sources"][idx]["file"] = os.path.split(file)[1]
            yaml_descriptor["sources"][idx]["channels"] = 1
            yaml_descriptor["sources"][idx]["track_id"] = track_id
            track_id += 1
            idx += 1

        yaml_descriptor["receivers_count"] = len(stereo_files) * 2
        yaml_descriptor["receivers"] = {}
        idx = 0
        for file in stereo_files:
            yaml_descriptor["receivers"][idx] = {}
            yaml_descriptor["receivers"][idx]["file"] = os.path.split(file)[1]
            yaml_descriptor["receivers"][idx]["channels"] = 2
            yaml_descriptor["receivers"][idx]["track_id"] = track_id
            track_id += 1
            idx += 1

        yaml_descriptor["name"] = "verse rendered audio scene"

        yaml_descriptor["description"] = "none"

        # reference to the rendering scene config
        yaml_descriptor["scene"] = "none"
        if scene_filename != None:
            yaml_descriptor["scene"] = scene_filename

        with open(filename, "w") as file:
            yaml.dump(yaml_descriptor, file)


def writeSoundSpatializerCFG(filename=None, cfg_yaml={}):
    """Build and write the sspat tool's own config .yaml (its "-p" argument)
    from a sound_spatializer_cmd task dict: head/room SOFA/BRIR files, one
    entry per source (file/coord/path_csv plus fixed 3DTI processing flags),
    and the listener entry. Returns 0 on success, -1 on failure."""
    err = -1

    cfg = {}

    if len(cfg_yaml) > 0:
        cfg = {}
        cfg["syntax"] = {}
        cfg["syntax"]["name"] = "sspat_config"
        cfg["syntax"]["version"] = {"major": 0, "minor": 2, "revision": 0}

        #
        # audio setup
        #
        cfg["setup"] = {}

        cfg["setup"]["head"] = {}
        cfg["setup"]["head"]["hrtf_sofa"] = cfg_yaml["head"]

        #
        # room
        #
        cfg["setup"]["room"] = {}
        cfg["setup"]["room"]["brir_sofa"] = cfg_yaml["room"]

        #
        # sources
        #
        cfg["setup"]["sources_count"] = len(cfg_yaml["sources"])
        cfg["setup"]["sources"] = {}
        for sidx in cfg_yaml["sources"]:
            cfg["setup"]["sources"][sidx] = {}
            cfg["setup"]["sources"][sidx]["file_wav"] = cfg_yaml["sources"][sidx]["file"]
            cfg["setup"]["sources"][sidx]["coord"] = cfg_yaml["sources"][sidx]["coord"]
            cfg["setup"]["sources"][sidx]["path_csv"] = cfg_yaml["sources"][sidx]["path_csv"]
            # 3dti extra parameters
            cfg["setup"]["sources"][sidx]["3dti"] = {}
            cfg["setup"]["sources"][sidx]["3dti"]["enableInterpolation"] = "yes"
            cfg["setup"]["sources"][sidx]["3dti"]["enableAnechoicProcess"] = "yes"
            cfg["setup"]["sources"][sidx]["3dti"]["enableDistanceAttenuationAnechoic"] = "no"
            cfg["setup"]["sources"][sidx]["3dti"]["enableDistanceAttenuationSmoothingAnechoic"] = "no"
            if cfg["setup"]["room"]["brir_sofa"] == "none":
                cfg["setup"]["sources"][sidx]["3dti"]["enableReverbProcess"] = "no"
            else:
                cfg["setup"]["sources"][sidx]["3dti"]["enableReverbProcess"] = "yes"
            cfg["setup"]["sources"][sidx]["3dti"]["enableDistanceAttenuationReverb"] = "yes"
            cfg["setup"]["sources"][sidx]["3dti"]["enableFarDistanceEffect"] = "yes"
            cfg["setup"]["sources"][sidx]["3dti"]["enableNearFieldEffect"] = (
                "no"  # "yes" removing since we do not have ILD map
            )
            cfg["setup"]["sources"][sidx]["3dti"]["enablePropagationDelay"] = "yes"

        #
        # listeners
        #

        cfg["setup"]["listeners_count"] = 1
        cfg["setup"]["listeners"] = {}
        cfg["setup"]["listeners"][0] = {}
        cfg["setup"]["listeners"][0]["coord"] = cfg_yaml["listeners"][0]["position"]["coord"]["value"]
        cfg["setup"]["listeners"][0]["path_csv"] = "none"
        cfg["setup"]["listeners"][0]["head"] = {}
        cfg["setup"]["listeners"][0]["head"]["hrtf_sofa"] = cfg_yaml["head"]
        cfg["setup"]["listeners"][0]["3dti"] = {}
        cfg["setup"]["listeners"][0]["3dti"]["head_radius"] = cfg_yaml["head_radius"]
        cfg["setup"]["listeners"][0]["3dti"]["customizedITD"] = "no"
        cfg["setup"]["listeners"][0]["3dti"]["ILDAttenutaion_dB"] = -6
        cfg["setup"]["listeners"][0]["3dti"]["directionality"] = "no"
        cfg["setup"]["listeners"][0]["3dti"]["directionality_L_dB"] = 0
        cfg["setup"]["listeners"][0]["3dti"]["directionality_R_dB"] = 0

    if len(cfg) > 0:
        logger.debug(cfg)

        with open(filename, "w") as file:
            yaml.dump(cfg, file)

        if os.path.isfile(filename):
            err = 0
        else:
            err = -1
            logger.error("cannot write soundSpatializer config file {}".format(filename))

    return err


def get_flag_value(cmd, flag):
    """Return the value following `flag` in a command-line argument list
    `cmd` (e.g. get_flag_value(cmd, "-o") -> the output path), or None if
    the flag isn't present."""
    for i, token in enumerate(cmd):
        if token == flag and i + 1 < len(cmd):
            return cmd[i + 1]
    return None


def executeSoundSpatializerCmd(cmd=""):
    """Run one sspat command (as built in executeSpatializeTasks()). First
    checks whether every source's samplerate matches the HRTF's (parsed from
    the SOFA file via parse_sofa.py); on mismatch, resamples the inputs to
    match, runs sspat, resamples the output back down, then removes the
    temporary resampled files. Returns 0 on success, -1 on any failure."""
    err = 0

    if cmd == "":
        err = -1

    if err == 0:
        out_file = get_flag_value(cmd, "-o")
        param_file = get_flag_value(cmd, "-p")
        yaml_param = readYamlFile(param_file)

        # extract HRTF sampling rate
        head_samplerate = 0
        head_samplerate_match = True

        tmp_cmd = [_SOFA_PARSE_EXE, "-i", str(yaml_param["setup"]["head"]["hrtf_sofa"])]

        try:
            result = check_output(tmp_cmd)
            # print(result)
            text = result.decode("utf-8")
            match = re.search(r"Data_SamplingRate\s*:\s*([0-9.]+)", text)
            head_samplerate = float(match.group(1)) if match else None
        except:
            logger.error(
                "executeSoundSpatializerCmd, could not parse sofa file: {}".format(
                    yaml_param["setup"]["head"]["hrtf_sofa"]
                )
            )
            err = -1

        # extract input files sampling rate
        # check if we have to match samples

        audio_sources = yaml_param["setup"]["sources"]

        for src_id, src in audio_sources.items():
            src_samplerate = get_samplerate(src["file_wav"])
            if int(src_samplerate) != int(head_samplerate):
                head_samplerate_match = False

        #
        # rate sampling adaptation on mismatch
        if not head_samplerate_match:
            logger.warning("sspat samplerate mismatch: will resample inputs (suboptimal) ")
            for src_id, src in audio_sources.items():
                # resampled file
                p = Path(src["file_wav"])
                # f = p.with_name(p.stem + "_" + str(int(head_samplerate)) + p.suffix)
                f = p.with_name(
                    p.stem + "_" + str(datetime.now().microsecond) + "_" + str(random.randint(0, 999999)) + p.suffix
                )

                resampleAudioFile(input_file=src["file_wav"], output_file=f, samplerate=head_samplerate)
                if not (Path(f).exists()):
                    err = -1

                # change input param for sspat config
                yaml_param["setup"]["sources"][src_id]["file_wav"] = str(f).strip()

            # rewrite param file after mods
            with open(param_file, "w") as f:
                yaml.dump(yaml_param, f, default_flow_style=False, sort_keys=False)

        # now execute command
        if err == 0:
            logger.debug("soundSpatializer, executing:" + str(cmd))

            # rename output if needed
            if not head_samplerate_match:
                p = Path(str(out_file))
                f = p.with_name(p.stem + "_" + str(int(head_samplerate)) + p.suffix)
                cmd[4] = str(f)

            # execute sspat
            try:
                _ = check_output(cmd)
            except:
                logger.error("spatializer, could not run cmd: {}".format(cmd))
                err = -1

            if not (os.path.isfile(cmd[4])):
                err = -1
                logger.error("spatializer, missing audio output file: {}".format(cmd[4]))
            else:
                if not head_samplerate_match:
                    logger.warning("sspat samplerate mismatch: will resample output (suboptimal)")
                    resampleAudioFile(input_file=str(cmd[4]), output_file=out_file, samplerate=int(src_samplerate))
                    if not (Path(out_file).exists()):
                        err = -1

                    # remove temporary audio files
                    if Path(str(cmd[4])).exists():
                        Path(str(cmd[4])).unlink()

                    for src_id, src in yaml_param["setup"]["sources"].items():
                        if Path(yaml_param["setup"]["sources"][src_id]["file_wav"]).exists():
                            Path(yaml_param["setup"]["sources"][src_id]["file_wav"]).unlink()

        else:
            logger.error("spatializer, error on input data, rendering skipped: {}".format(cmd))

    return err


def writePostProcessingCFG(cfg_file=None, wav_file=None, cli=[], task_yaml={}, postproc_yaml={}):
    """Write the config .yaml for one post-processing script invocation:
    in-place input/output (post-processing overwrites wav_file), a reference
    to the scene file, and the task/postproc resource descriptors. Returns
    0 on success, -1 on failure (empty task_yaml, bad data, or write error)."""
    err = -1

    cfg = {}

    if len(task_yaml) > 0:
        try:
            cfg = {}
            cfg["syntax"] = {}
            cfg["syntax"]["name"] = "postproc_config"
            cfg["syntax"]["version"] = {"major": 0, "minor": 2, "revision": 0}

            cfg["name"] = task_yaml["name"]

            cfg["scene"] = {}
            cfg["scene"]["file"] = cli["scene_file"]

            # in-place post-processing
            cfg["input"] = {}
            cfg["input"]["file"] = wav_file

            cfg["output"] = {}
            cfg["output"]["file"] = wav_file

            cfg["setup"] = {}
            cfg["setup"]["file"] = postproc_yaml

            cfg["task"] = task_yaml
            err = 0

        except:
            logger.error("invalid post-processing configuration. cannot write cfg file.")
            err = -1

    if (err == 0) and (len(cfg) > 0):
        # logger.info(yaml.dump(cfg))
        logger.debug(cfg)

        with open(cfg_file, "w") as file:
            yaml.dump(cfg, file)

        if os.path.isfile(cfg_file):
            err = 0
        else:
            err = -1
            logger.error("cannot write post-processing config file {}".format(cfg_file))

    return err


def executePostProcessingCmd(cmd=""):
    """Run one post-processing script command (as built in
    executeSpatializeTasks()) and verify its output file was produced.
    Returns 0 on success, -1 on failure."""
    err = 0
    logger.debug("post-processing, executing:" + str(cmd))

    try:
        _ = check_output(cmd)
    except:
        logger.error("post-processing, could not run cmd: {}".format(cmd))
        err = -1

    if not (os.path.isfile(cmd[4])):
        err = -1
        logger.error("post-processing, missing audio output file: {}".format(cmd[4]))

    return err


#
# AUDIO PROCESSING
#
def getMediaInfo(filename, print_result=True):
    """Run ffprobe on `filename` and return its full format+streams info as
    a dict (parsed JSON): result["format"] holds tags/bit rate/etc.,
    result["streams"] holds one dict per stream (sample rate, channels...).
    If print_result=True, also pretty-prints both to stdout."""
    result = check_output(
        [_FFPROBE_EXE, "-hide_banner", "-loglevel", "panic", "-show_format", "-show_streams", "-of", "json", filename]
    )

    result = json.loads(result)

    if print_result:
        print("\nFormat")

        for key, value in result["format"].items():
            print("   ", key, ":", value)

        print("\nStreams")
        for stream in result["streams"]:
            for key, value in stream.items():
                print("   ", key, ":", value)

        print("\n")

    return result


def verifySpericalCoord(source_coord):
    """Validate a "azimuth,elevation,distance" coordinate string: must have
    exactly 3 comma-separated components, and distance must be > 0.1
    (sspat/3DTI requirement). Returns 0 if valid, -1 otherwise (logged)."""
    err = 0
    tmp = str(source_coord).split(",")

    # components
    if 3 != len(tmp):
        err = -1

    # distance
    if float(tmp[2]) < 0.1:
        logger.error("spherical coordinates must have distance >0.1")
        err = -1

    return err


def loadAudioObjectGroup(cli_params, scene_yaml, group_key):
    """
    Load and ffmpeg-convert every entry of a scene "sources" (human voices) or
    "sounds" (non-voice, syntax v0.2.0+) group. Both groups share the identical
    descriptor schema (voice_file / sound_file) and static/dynamic positioning
    syntax, so the loading/validation/conversion logic is shared here.

    group_key is missing/zero-count for scenes written before syntax v0.2.0,
    in which case this returns empty lists (no-op).

    Returns
    -------
    (err, group_yaml, group_wav)
    """
    err = 0
    group_yaml = []
    group_wav = []

    count = scene_yaml["setup"].get(group_key + "_count", 0)
    if count == 0:
        return err, group_yaml, group_wav

    entries = scene_yaml["setup"][group_key]

    # load per-entry descriptor yaml
    for idx in entries:
        tmp_yaml = []
        tmp_filename = ""
        try:
            tmp_filename = os.path.join(
                _RESOURCES_DIR,
                entries[idx]["type"],
                entries[idx]["subtype"],
                "info",
                entries[idx]["info"],
            )
            with open(tmp_filename + ".yaml", "r") as file:
                tmp_yaml = yaml.safe_load(file)
            group_yaml.append(tmp_yaml)
        except:
            err = -1
            logger.error("cannot open/parse {} yaml file: {}".format(group_key, tmp_filename))

    if err == 0:
        for idx in range(count):
            media_filename = os.path.join(
                _RESOURCES_DIR,
                entries[idx]["type"],
                entries[idx]["subtype"],
                group_yaml[idx]["file"],
            )

            media_info = getMediaInfo(media_filename, print_result=False)

            # sanity checks : only one audio stream
            if media_info["format"]["nb_streams"] != 1:
                err = -1
                logger.error("more than one stream in file {}".format(media_filename))

            # sanity checks : position
            tmp_filename = media_filename
            if "position" in entries[idx]:
                if entries[idx]["position"]["type"] == "static":
                    if entries[idx]["position"]["coord"]["type"] != "spherical":
                        err = -1
                        logger.error("invalid position type for {} {} in file {}".format(group_key, idx, tmp_filename))

                    mycoord = list(entries[idx]["position"]["coord"]["value"])

                    if 0 != verifySpericalCoord(str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])):
                        err = -1
                        logger.error(
                            "invalid position coordinates {} for {} {} in file {}".format(
                                entries[idx]["position"]["coord"]["value"], group_key, idx, tmp_filename
                            )
                        )
                elif entries[idx]["position"]["type"] == "dynamic":
                    tmp1_filename = os.path.join(
                        _RESOURCES_DIR,
                        entries[idx]["position"]["value"]["type"],
                        entries[idx]["position"]["value"]["subtype"],
                        "info",
                        entries[idx]["position"]["value"]["info"],
                    )

                    tmp_filename = str(Path(tmp1_filename).with_suffix(".yaml"))

                    if not os.path.isfile(tmp_filename):
                        err = -1
                        logger.error("missing path file {}".format(tmp_filename))
                else:
                    err = -1
                    logger.error("invalid position type for {} {} in file {}".format(group_key, idx, tmp_filename))
            else:
                err = -1
                logger.error("invalid position for {} {} in file {}".format(group_key, idx, tmp_filename))

            if err == 0:
                out_filename = os.path.join(_OUTPUT_REF_DIR, entries[idx]["info"]) + ".wav"

                overwrite_option = "-n"
                if cli_params["force_overwrite"] == True:
                    overwrite_option = "-y"

                os_cmd = [
                    _FFMPEG_EXE,
                    overwrite_option,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    media_filename,
                    "-c:a",
                    str(scene_yaml["setup"]["format"]["subtype"]),
                    "-ar",
                    str(scene_yaml["setup"]["format"]["samplerate"]),
                    "-ac",
                    "1",
                ]

                if "playback" in group_yaml[idx]:
                    os_cmd += [
                        "-ss",
                        str(group_yaml[idx]["playback"]["begin"]),
                        "-to",
                        str(group_yaml[idx]["playback"]["end"]),
                    ]

                if "playback" in entries[idx]:
                    if "padding" in entries[idx]["playback"]:
                        if ("pre" in entries[idx]["playback"]["padding"]) and (
                            "post" in entries[idx]["playback"]["padding"]
                        ):
                            os_cmd += [
                                "-af",
                                "adelay="
                                + str(entries[idx]["playback"]["padding"]["pre"])
                                + ",apad=pad_dur="
                                + str(entries[idx]["playback"]["padding"]["post"]),
                            ]
                        elif "pre" in entries[idx]["playback"]["padding"]:
                            os_cmd += [
                                "-af",
                                "adelay=" + str(entries[idx]["playback"]["padding"]["pre"]) + "s:all_true",
                            ]
                        elif "post" in entries[idx]["playback"]["padding"]:
                            os_cmd += [
                                "-af",
                                "apad=pad_dur=" + str(entries[idx]["playback"]["padding"]["post"]),
                            ]

                os_cmd += [out_filename]

                if not os.path.isfile(out_filename):
                    logger.debug("convert audio file {}".format(out_filename))

                    _ = check_output(os_cmd)
                else:
                    waitFileCompleted(out_filename)
                    logger.debug("audio file already converted {}".format(out_filename))

                group_wav.append(os.path.join(_ROOT_DIR, out_filename))

                if not os.path.isfile(os.path.join(_ROOT_DIR, out_filename)):
                    err = -1
                    logger.error("could not render .wav file {}".format(os.path.join(_ROOT_DIR, out_filename)))

    return err, group_yaml, group_wav


def resolveSpatializerSourceEntry(scene_yaml, group_key, idx, wav_file):
    """
    Resolve the sound_spatializer "sources" entry (file/coord/path_csv) for one
    "sources" or "sounds" entry of a scene, static or dynamic positioning alike.
    sspat itself does not distinguish sources from sounds: both become plain
    point sources to spatialize.

    Returns
    -------
    (err, entry)
    """
    err = 0
    entry = {"file": wav_file}

    position = scene_yaml["setup"][group_key][idx]["position"]

    if position["type"] == "static":
        mycoord = list(position["coord"]["value"])
        if 0 != verifySpericalCoord(str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])):
            err = -1
            logger.error("invalid position coordinates {} for {} {}".format(position["coord"]["value"], group_key, idx))
        entry["coord"] = str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])
        entry["path_csv"] = "none"
    else:
        tmp1_filename = os.path.join(
            _RESOURCES_DIR,
            position["value"]["type"],
            position["value"]["subtype"],
            "info",
            position["value"]["info"],
        )
        tmp_filename = str(Path(tmp1_filename).with_suffix(".yaml"))

        path_yaml = readYamlFile(tmp_filename)
        path_file = ""

        # sanity checks: must be a csv
        if "format" in path_yaml:
            if path_yaml["format"] != "csv":
                err = -1
                logger.error("unsupported path file format: {}".format(tmp_filename))
        else:
            err = -1
            logger.error("missing path file format: {}".format(tmp_filename))

        # sanity checks: must have a path file
        if "path" in path_yaml:
            if (len(path_yaml["path"]) > 1) or (len(path_yaml["path"]) == 0):
                err = -1
                logger.error("more than one path in file: {}".format(tmp_filename))

            if "file" in path_yaml["path"][0]:
                tmp_filename2 = os.path.join(
                    _RESOURCES_DIR,
                    position["value"]["type"],
                    position["value"]["subtype"],
                    path_yaml["path"][0]["file"],
                )
                if os.path.isfile(tmp_filename2):
                    path_file = tmp_filename2
                else:
                    err = -1
                    logger.error("missing path file in folder: {}".format(tmp_filename2))
            else:
                err = -1
                logger.error("missing path filename: {}".format(tmp_filename))
        else:
            err = -1
            logger.error("invalid path file syntax: {}".format(tmp_filename))

        entry["coord"] = "0,0,0"
        entry["path_csv"] = path_file

    return err, entry


def audioSceneRender(cli_params=None):
    """
    Entry point for rendering one scene .yaml file (called from __main__ with
    the parsed CLI args). Loads and validates the scene: syntax check, the
    "sources" (voices) and "sounds" (non-voice, optional) audio groups via
    loadAudioObjectGroup(), the listener (exactly 1 required) and the room
    (0 or 1). On success, hands off to audioSpatialize() to run sspat.
    """

    err = 0

    scene_yaml = []
    sources_yaml = []
    sources_wav = []
    sounds_yaml = []
    sounds_wav = []
    listeners_yaml = []
    rooms_yaml = []

    logger.info("-" * 80)
    logger.info("audioSceneRender:")
    logger.info("-" * 80)

    if cli_params["scene_file"] != None:
        try:
            with open(cli_params["scene_file"], "r") as file:
                scene_yaml = yaml.safe_load(file)
        except:
            err = -1
            logger.error("cannot open/parse scene yaml file: {}".format(cli_params["scene_file"]))

        try:
            _ = scene_yaml["setup"]["listeners"][0]["position"]
        except:
            err = -1

    # check syntax
    if (err == 0) and (scene_yaml["syntax"]["name"] != "audio_rendering_scene"):
        err = -1
        logger.error("invalid audio scene file.")

    if "scene" not in scene_yaml:
        err = -1
        logger.error("invalid audio scene file, missing scene details")

    if "name" not in scene_yaml["scene"]:
        err = -1
        logger.error("invalid audio scene file, missing scene name")

    # override scene name if needed
    if cli_params["scene_name"] != None:
        scene_yaml["scene"]["name"] = cli_params["scene_name"] + "_" + scene_yaml["scene"]["name"]

    #
    # load & convert audio sources: "sources" (human voices) and "sounds"
    # (non-voice, optional, syntax v0.2.0+). Both share identical loading,
    # validation and ffmpeg-conversion logic, see loadAudioObjectGroup().
    #
    if err == 0:
        err, sources_yaml, tmp_sources_wav = loadAudioObjectGroup(cli_params, scene_yaml, "sources")
        sources_wav.append(tmp_sources_wav)

    if err == 0:
        err, sounds_yaml, tmp_sounds_wav = loadAudioObjectGroup(cli_params, scene_yaml, "sounds")
        sounds_wav.append(tmp_sounds_wav)

    #
    # loop over listeners
    #
    if (scene_yaml["setup"]["listeners_count"] > 1) or (scene_yaml["setup"]["listeners_count"] < 1):
        err = -1
        logger.error("invalid listeners count")

    if err == 0:
        for idx in scene_yaml["setup"]["listeners"]:
            tmp_yaml = []
            tmp_filename = ""
            try:
                tmp_filename = os.path.join(
                    _RESOURCES_DIR,
                    scene_yaml["setup"]["listeners"][idx]["type"],
                    scene_yaml["setup"]["listeners"][idx]["subtype"],
                    "info",
                    scene_yaml["setup"]["listeners"][idx]["info"],
                )

                with open(tmp_filename + ".yaml", "r") as file:
                    tmp_yaml = yaml.safe_load(file)
                listeners_yaml.append(tmp_yaml)
            except:
                err = -1
                logger.error("cannot open/parse listener yaml file: {}".format(tmp_filename))

    #
    # loop over rooms
    #
    if scene_yaml["setup"]["rooms_count"] > 1:
        err = -1
        logger.error("invalid rooms count, should be rooms_count <=1")

    if (err == 0) and (scene_yaml["setup"]["rooms_count"] == 1):
        for idx in scene_yaml["setup"]["rooms"]:
            tmp_yaml = []
            tmp_filename = ""
            try:
                tmp_filename = os.path.join(
                    _RESOURCES_DIR,
                    scene_yaml["setup"]["rooms"][idx]["type"],
                    scene_yaml["setup"]["rooms"][idx]["subtype"],
                    "info",
                    scene_yaml["setup"]["rooms"][idx]["info"],
                )

                with open(tmp_filename + ".yaml", "r") as file:
                    tmp_yaml = yaml.safe_load(file)
                rooms_yaml.append(tmp_yaml)
            except:
                err = -1
                logger.error("cannot open/parse room yaml file: {}".format(tmp_filename))

    try:
        _ = scene_yaml["setup"]["listeners"][0]["position"]
    except:
        err = -1

    #
    # render scene or exit on error
    #
    if err != 0:
        logger.error("could not render audio scene: {}".format(cli_params["scene_file"]))
    else:
        audioSpatialize(
            cli_params, scene_yaml, sources_yaml, sources_wav, listeners_yaml, rooms_yaml, sounds_yaml, sounds_wav
        )


def audioSpatialize(
    cli_params=None,
    scene_yaml=None,
    sources_yaml=None,
    sources_wav=None,
    listeners_yaml=None,
    rooms_yaml=None,
    sounds_yaml=None,
    sounds_wav=None,
):
    """
    Build one sspat task per listener HRTF entry: resolves the room BRIR and
    head SOFA files (matching on samplerate/name, falling back to defaults
    with a warning on mismatch), then appends every "sources" (voice) and
    "sounds" (non-voice) entry as a spatializer source via
    resolveSpatializerSourceEntry(). Hands the resulting task list to
    executeSpatializeTasks() for execution.
    """

    err = 0

    logger.info("-" * 80)
    logger.info("audioSpatialize:")
    logger.info("-" * 80)

    sound_spatializer_tasks = []

    if (len(listeners_yaml) != 1) or (scene_yaml["setup"]["listeners_count"] != 1):
        err = -1
        logger.error("invalid listener count (must be 1)")

    if err == 0:
        for listener in listeners_yaml:
            # clear sound spatializer command line for this listener
            sound_spatializer_cmd = {}
            sound_spatializer_cmd["scene"] = {}
            sound_spatializer_cmd["scene"]["name"] = scene_yaml["scene"]["name"]
            # add syntax identifier
            sound_spatializer_cmd["syntax"] = {}
            sound_spatializer_cmd["syntax"]["name"] = "audioSpatialize"
            sound_spatializer_cmd["syntax"]["version"] = {"major": 0, "minor": 1, "revision": 0}

            # redundant but preferred
            scene_listener_idx = scene_yaml["setup"]["listeners_count"] - 1

            if err == 0:
                for lidx in listener["hrtf"]:
                    #
                    # room
                    #
                    rooms_brir_file = ""
                    if scene_yaml["setup"]["rooms_count"] > 1:
                        err = -1
                        logger.error("invalid rooms count (must be 1)")
                    else:
                        rooms_brir_file = "none"

                        if scene_yaml["setup"]["rooms_count"] == 1:
                            # check for BRIR samplerate
                            if scene_yaml["setup"]["format"]["samplerate"] in rooms_yaml[0]["brir_samplerates"]:
                                # index match
                                sr_idx = rooms_yaml[0]["brir_samplerates"].index(
                                    scene_yaml["setup"]["format"]["samplerate"]
                                )

                                # check for BRIR name match
                                names = [k for k in rooms_yaml[0]["brir"][0].keys() if k != "audio"]

                                if (listener["hrtf"][lidx]["name"]) in names:
                                    rooms_brir_file = rooms_yaml[0]["brir"][sr_idx][listener["hrtf"][lidx]["name"]][
                                        "file"
                                    ]
                                else:
                                    logger.warning("render_scene: missing match on room BRIR name, fallback on default")
                                    rooms_brir_file = rooms_yaml[0]["brir"][sr_idx]["default"]["file"]

                                rooms_brir_file = os.path.join(
                                    _RESOURCES_DIR,
                                    scene_yaml["setup"]["rooms"][scene_listener_idx]["type"],
                                    scene_yaml["setup"]["rooms"][scene_listener_idx]["subtype"],
                                    rooms_brir_file,
                                )

                    logger.info("==============================")
                    logger.info("LISTENER IDX: " + str(lidx))
                    logger.info("==============================")

                    sound_spatializer_cmd["name"] = listener["hrtf"][lidx]["name"]
                    sound_spatializer_cmd["sources"] = {}
                    sound_spatializer_cmd["room"] = rooms_brir_file

                    #
                    # head
                    #
                    head_sofa_file = ""
                    if scene_yaml["setup"]["listeners_count"] > 1:
                        err = -1
                        logger.error("invalid listeners count (must be 1)")
                    else:
                        head_sofa_file = "none"

                        if scene_yaml["setup"]["listeners_count"] == 1:
                            # copy listener definition
                            sound_spatializer_cmd["listeners"] = ""
                            sound_spatializer_cmd["listeners"] = scene_yaml["setup"]["listeners"]

                            try:
                                _ = scene_yaml["setup"]["listeners"][0]["position"]
                            except:
                                err = -1

                            # SAFE selection for HRTF samplerate, will leverage samplerate conversion if we do not have a match.
                            samplerate_select = scene_yaml["setup"]["format"]["samplerate"]

                            if samplerate_select not in listeners_yaml[0]["hrtf_samplerates"]:
                                samplerate_select = max(listeners_yaml[0]["hrtf_samplerates"])
                                logger.warning(
                                    "render_scene: missing match on HRTF samplerate, fallback on {}".format(
                                        samplerate_select
                                    )
                                )

                            # index match
                            sr_idx = listeners_yaml[0]["hrtf_samplerates"].index(samplerate_select)

                            # check for HRTF name match
                            names = [entry["name"] for entry in listener["hrtf"].values()]

                            if (listener["hrtf"][lidx]["name"]) in names:
                                head_sofa_file = os.path.join(
                                    _RESOURCES_DIR,
                                    scene_yaml["setup"]["listeners"][scene_listener_idx]["type"],
                                    scene_yaml["setup"]["listeners"][scene_listener_idx]["subtype"],
                                    listener["hrtf"][lidx]["file"],
                                )
                            else:
                                logger.error("render_scene: missing match on HRTF name, fallback on default")
                                head_sofa_file = os.path.join(
                                    _RESOURCES_DIR,
                                    scene_yaml["setup"]["listeners"][scene_listener_idx]["type"],
                                    scene_yaml["setup"]["listeners"][scene_listener_idx]["subtype"],
                                    listener["hrtf"][listener["hrtf_main_idx"]]["file"],
                                )
                            sound_spatializer_cmd["head"] = head_sofa_file
                            sound_spatializer_cmd["head_radius"] = listener["geometry"]["head_radius"]

                    # read sources (human voices)
                    for sidx in range(len(sources_wav[0])):
                        err_entry, entry = resolveSpatializerSourceEntry(
                            scene_yaml, "sources", sidx, sources_wav[0][sidx]
                        )
                        if err_entry != 0:
                            err = -1
                        else:
                            entry["is_sound"] = False
                            sound_spatializer_cmd["sources"][sidx] = entry

                            # log for debug
                            logger.info("   sidx: " + str(sidx))
                            logger.info("   source:" + sources_wav[0][sidx])
                            logger.info("      coord: " + entry["coord"])
                            logger.info("      path_csv: " + entry["path_csv"])
                            logger.info("   head:" + head_sofa_file)
                            logger.info("   room:" + rooms_brir_file)

                    # read sounds (non-voice sources, optional, syntax v0.2.0+).
                    # sspat does not distinguish sources from sounds: they are appended to the
                    # same "sources" list (continuing the index) and spatialized identically.
                    # the "is_sound" marker is only used later to optionally exclude them from
                    # the final MKV dry tracks/descriptor, see -is/--include_sounds_output.
                    if sounds_wav and len(sounds_wav[0]) > 0:
                        base_idx = len(sources_wav[0])
                        for j in range(len(sounds_wav[0])):
                            sidx = base_idx + j
                            err_entry, entry = resolveSpatializerSourceEntry(scene_yaml, "sounds", j, sounds_wav[0][j])
                            if err_entry != 0:
                                err = -1
                            else:
                                entry["is_sound"] = True
                                sound_spatializer_cmd["sources"][sidx] = entry

                                # log for debug
                                logger.info("   sidx: " + str(sidx) + " (sound)")
                                logger.info("   source:" + sounds_wav[0][j])
                                logger.info("      coord: " + entry["coord"])
                                logger.info("      path_csv: " + entry["path_csv"])
                                logger.info("   head:" + head_sofa_file)
                                logger.info("   room:" + rooms_brir_file)

                    # append task for execution
                    if err == 0:
                        sound_spatializer_tasks.append(sound_spatializer_cmd.copy())

        #
        # execute tasks
        #
        if err == 0:
            executeSpatializeTasks(cli_params, sound_spatializer_tasks)


def executeSpatializeTasks(cli_params, tasks={}):
    """
    Runs the full rendering pipeline for the task list built by
    audioSpatialize(): (1) writes one sspat config per task and runs them in
    a process pool, (2) if the scene defines "postproc", runs the
    post-processing script per task, (3) muxes the mono source files and
    stereo sspat outputs into one multi-track MKV via ffmpeg, (4) writes the
    MKV's .yaml descriptor, (5) unless -k/--keep_files was given, deletes
    the intermediate tmp/ref/wav working files.
    """
    err = 0

    logger.info("-" * 80)
    logger.info("executeSpatializeTasks")
    logger.info("-" * 80)

    for task in tasks:
        if "syntax" not in task:
            err = -1
            logger.error("invalid audio spatializer task syntax")
        else:
            if "name" not in task["syntax"]:
                err = -1
                logger.error("invalid audio spatializer task name")
            else:
                if task["syntax"]["name"] != "audioSpatialize":
                    err = -1
                    logger.error("invalid audio spatializer task name")

    #
    # create sound_spatializer config files
    #
    sspat_cmds = []

    err = 0
    idx = 0
    for task in tasks:
        tmp_filename = task["scene"]["name"] + "_" + task["name"] + "_" + f"{idx:03d}"
        cfg_filename = os.path.abspath(os.path.join(_OUTPUT_TMP_DIR, tmp_filename) + ".yaml")
        wav_filename = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + ".wav")

        # sspat_cmd = " ".join([_SSPAT_EXE, "-v 0", "-o", wav_filename, "-p", cfg_filename])
        sspat_cmd = [_SSPAT_EXE, "-v", str(0), "-o", wav_filename, "-p", cfg_filename, "> /dev/null 2>&1"]

        if 0 != writeSoundSpatializerCFG(filename=cfg_filename, cfg_yaml=task):
            err = -1
        else:
            sspat_cmds.append(sspat_cmd)
        idx += 1

    if err == 0:
        #
        # compute process pool size based on CPU/MEM requirements
        #
        mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
        mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74

        cpu_count = min([(os.cpu_count() - 2), cli_params["cpu_process"]])
        cpu_count = max([_MIN_CPU_COUNT, cpu_count])

        max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))

        logger.info("SSpat Pool size: {}".format(max_pool_size))
        cpu_pool = Pool(max_pool_size)

        #
        # run SOUND_SPATIALIZER_EXE
        logger.info("-" * 80)
        logger.info("launch SoundSpatializer (multi-process)")
        logger.info("-" * 80)

        _ = cpu_pool.map(executeSoundSpatializerCmd, sspat_cmds)

        cpu_pool.close()
        cpu_pool.join()

        # check results
        for cmd in sspat_cmds:
            if not (os.path.isfile(cmd[4])):
                err = -1
                logger.error("could not render audio file: {}".format(cmd[4]))

    #
    # post-processing
    #
    if err == 0:
        #
        # create pos-procesing config files
        #
        postproc_cmds = []

        scene_yaml = readYamlFile(cli_params["scene_file"])

        postproc_yaml = {}

        if ("postproc") in scene_yaml:
            err = 0
            idx = 0
            for task in tasks:
                tmp_filename = task["scene"]["name"] + "_postproc_" + task["name"] + "_" + f"{idx:03d}"
                cfg_filename = os.path.abspath(os.path.join(_OUTPUT_TMP_DIR, tmp_filename) + ".yaml")

                tmp_filename = task["scene"]["name"] + "_" + task["name"] + "_" + f"{idx:03d}"
                wav_filename = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + ".wav")

                logger.info("config post-processing on: {}".format(wav_filename))
                try:
                    tmp_yaml = scene_yaml["postproc"][0]
                    postproc_yaml_file = os.path.join(
                        _RESOURCES_DIR, tmp_yaml["type"], tmp_yaml["subtype"], "info", tmp_yaml["info"] + ".yaml"
                    )
                    postproc_yaml = readYamlFile(postproc_yaml_file)
                except:
                    err = -1
                    logger.error("could not read post-processing yaml: {}".format(postproc_yaml_file))

                if err == 0:
                    try:
                        if ("script_exe") in postproc_yaml:
                            script_exe_cmd = os.path.join(
                                _RESOURCES_DIR, tmp_yaml["type"], tmp_yaml["subtype"], postproc_yaml["script_exe"]
                            )
                            postproc_cmd = [str(script_exe_cmd), "-i", wav_filename, "-p", cfg_filename]
                        else:
                            err = -1
                            logger.error("missing postprocessing script_exe file")
                    except:
                        logger.error("could not configure post-processing for: {}".format(wav_filename))

                if err == 0:
                    if 0 != writePostProcessingCFG(
                        cfg_file=cfg_filename,
                        wav_file=wav_filename,
                        cli=cli_params,
                        task_yaml=task,
                        postproc_yaml=postproc_yaml_file,
                    ):
                        err = -1
                    else:
                        postproc_cmds.append(postproc_cmd)

                idx += 1

            # execute postproc
            if err == 0:
                mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
                mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74

                cpu_count = min([(os.cpu_count() - 2), cli_params["cpu_process"]])
                cpu_count = max([_MIN_CPU_COUNT, cpu_count])

                max_pool_size = min(cpu_count, int(mem_gib / postproc_yaml["resources"]["min_mem_gb"]))

                logger.info("PostPocessing Pool size: {}".format(max_pool_size))
                cpu_pool = Pool(max_pool_size)

                #
                # run postprocessing script
                logger.info("-" * 80)
                logger.info("launch post-processing (multi-process)")
                logger.info("-" * 80)

                _ = cpu_pool.map(executePostProcessingCmd, postproc_cmds)

                cpu_pool.close()
                cpu_pool.join()

                # check results
                for cmd in postproc_cmds:
                    if not (os.path.isfile(cmd[4])):
                        err = -1
                        logger.error("could not post-prcess audio file: {}".format(cmd[4]))

    if err == 0:
        #
        # mux WAV tracks into one MKV file
        #
        cmd = ""
        tmp_filename = tasks[0]["scene"]["name"]
        ffmpeg_file = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + ".mkv")

        # reference source files (mono): "sounds" are excluded by default (dry track + MKV
        # descriptor) unless explicitly requested with -is/--include_sounds_output. They are
        # always present in the spatialized array/binaural receiver renders regardless of
        # this option, since they still need to acoustically be part of the recorded mix.
        ref_files = getSourceFilesSoundSpatializer(tasks[0], skip_sounds=not cli_params["include_sounds_output"])

        sspat_files = []
        for cmd in sspat_cmds:
            sspat_files.append(cmd[4])

        logger.info("-" * 80)
        logger.info("mux multi-channel WAV file (ffmpeg)")
        logger.info("-" * 80)

        muxWavFilesMKV(ref_files, sspat_files, ffmpeg_file)

        if not (os.path.isfile(ffmpeg_file)):
            err = -1
            logger.error("could not write multi-channcel WAV file :{}".format(ffmpeg_file))

    if err == 0:
        #
        # write the yaml descriptor for the MKV file
        #
        logger.info("-" * 80)
        logger.info("write multi-channel YAML info file")
        logger.info("-" * 80)

        tmp_filename = tasks[0]["scene"]["name"]
        tmp_filename = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + "_mkv.yaml")

        logger.info("file:{}".format(tmp_filename))

        writeAudioMKVDescriptor(
            filename=tmp_filename,
            mono_files=ref_files,
            stereo_files=sspat_files,
            mkv_filename=ffmpeg_file,
            scene_filename=cli_params["scene_file"],
        )

    if (err == 0) and (cli_params["keep_files"] == False):
        #
        # remove intermediate wav files
        #

        # remove tmp folder
        file_path = _OUTPUT_TMP_DIR
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error("Failed to delete {}. Reason: {}".format(file_path, e))

        # remove ref folder
        file_path = _OUTPUT_REF_DIR
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            logger.error("Failed to delete {}. Reason: {}".format(file_path, e))

        # remove wav folder
        files = glob.glob(cli_params["output_folder"] + "/*.wav")
        for f in files:
            try:
                os.remove(f)
            except Exception as e:
                logger.error("Failed to delete {}. Reason: {}".format(file_path, e))


#
###############################################################################
# MAIN
###############################################################################
#

if __name__ == "__main__":
    # install CTRL-C handles
    signal.signal(signal.SIGINT, signal_handler)

    # set user friendly process name for MAIN
    setproctitle("verse_render_scene")

    # random init
    random.seed()

    # parse input params
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-sf",
        "--scene_file",
        type=str,
        default=None,
        help="audio scene to render (default: %(default)s)",
    )
    parser.add_argument(
        "-sn",
        "--scene_name",
        type=str,
        default=None,
        help="scene prefix name for audio files (default: %(default)s)",
    )
    parser.add_argument(
        "-fp",
        "--full_playback",
        action="store_true",
        default=False,
        help="play audio source in full length (default: %(default)s)",
    )
    parser.add_argument(
        "-fo",
        "--force_overwrite",
        action="store_true",
        default=False,
        help="audio source conversion (ffmpeg) force overwrite (default: %(default)s)",
    )
    parser.add_argument(
        "-is",
        "--include_sounds_output",
        action="store_true",
        default=False,
        help="include non-voice 'sounds' as separate dry tracks in the MKV output and its "
        "yaml descriptor (default: %(default)s). Sounds are always spatialized into the "
        "array/binaural receiver renders regardless of this option; this only controls "
        "whether they are also exposed as a labeled ground-truth track.",
    )
    parser.add_argument(
        "-o",
        "--output_folder",
        type=str,
        default=None,
        help="output folder (default: %(default)s)",
    )
    parser.add_argument(
        "-k",
        "--keep_files",
        action="store_true",
        default=False,
        help="keep all output files (default: %(default)s)",
    )
    parser.add_argument(
        "-c",
        "--cpu_process",
        default=8,
        type=int,
        help="maximum number of CPU process to use",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="verbose, repeat for more detail: -v=INFO, -vv=DEBUG, -vvv=DEBUG+source location (default: WARNING)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="suppress all console log output regardless of -v. Takes precedence over "
        "-v/-vv/-vvv (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        default=False,
        help="suppress all console output. Takes precedence over -q and -v/-vv/-vvv (default: %(default)s)",
    )
    parser.add_argument(
        "-log",
        "--logfile",
        type=str,
        default=None,
        help="log verbose output to file (default: %(default)s)",
    )

    args, remaining = parser.parse_known_args()

    #
    # set debug verbosity
    #
    setup_logging(args.verbose, args.logfile, quiet=args.quiet, silent=args.silent)

    #
    # load params from external config file (if given)
    #
    cli_params = vars(args)

    #
    # deallocate args
    #
    args = []

    #
    # setup log
    #
    logger.info("-" * 80)
    logger.info("SETUP:")
    logger.info("-" * 80)

    for p in cli_params:
        logger.info("{} : {}".format(str(p), str(cli_params[p])))

    #
    # sanity checks
    #
    if cli_params["scene_file"] == None:
        logger.error("audio scene file is needed.")
        exit(1)
    else:
        if not (os.path.isfile(cli_params["scene_file"])):
            logger.error("audio scene file {} does not exists.".format(cli_params["scene_file"]))
            exit(1)

    if cli_params["output_folder"] == None:
        logger.error("output_folder is needed.")
        exit(1)
    else:
        if not (os.path.isdir(cli_params["output_folder"])):
            logger.info("output folder does not exists, trying to create it")
            os.makedirs(cli_params["output_folder"])
            if not (os.path.isdir(cli_params["output_folder"])):
                logger.error("cannot create output_folder {}.".format(cli_params["output_folder"]))
                exit(1)

        _OUTPUT_REF_DIR = cli_params["output_folder"] + _OUTPUT_REF_DIR

        if not (os.path.isdir(_OUTPUT_REF_DIR)):
            logger.info("output subfolder does not exists, trying to create it")
            os.makedirs(_OUTPUT_REF_DIR)
            if not (os.path.isdir(_OUTPUT_REF_DIR)):
                logger.error("cannot create output sub folder {}.".format(_OUTPUT_REF_DIR))
                exit(1)

        _OUTPUT_TMP_DIR = cli_params["output_folder"] + _OUTPUT_TMP_DIR

        if not (os.path.isdir(_OUTPUT_TMP_DIR)):
            logger.info("tmp subfolder does not exists, trying to create it")
            os.makedirs(_OUTPUT_TMP_DIR)
            if not (os.path.isdir(_OUTPUT_TMP_DIR)):
                logger.error("cannot create tmp sub folder {}.".format(_OUTPUT_TMP_DIR))
                exit(1)

    #
    # render
    #
    audioSceneRender(cli_params)
