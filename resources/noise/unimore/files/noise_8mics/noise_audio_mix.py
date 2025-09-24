#!/usr/bin/env python3
"""apply background noise to input file"""

import os
import shutil
import sys
import yaml

# import coloredlogs
import logging
import signal
import argparse
import sys

import shutil
import glob

import json
import subprocess
import random

from multiprocessing import Pool
from setproctitle import setproctitle
from subprocess import check_output

import soundfile as sf
import numpy as np

#
# Set logger format and color
#
logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s]%(levelname)s: %(message)s"


#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads

_SCRIPT_NAME = os.path.basename(__file__)
_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_BASE_DIR = os.path.join(_ROOT_DIR, "../../")
_RESOURCES_DIR = os.path.abspath(os.path.dirname(__file__)) + "../../../../../resources"
_OUTPUT_REF_DIR = "/ref/"
_OUTPUT_TMP_DIR = "/tmp/"

#
# EXECUTABLES / EXTERNAL CMDs
#
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_FFPROBE_EXE = "/usr/bin/ffprobe"


def signal_handler(sig, frame):
    global _CTRL_EXIT_SIGNAL
    print("\npressed Ctrl+C\n")
    _CTRL_EXIT_SIGNAL = 1


def readYamlFile(filename=None):
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


def get_channel_count(wav_file):
    """Uses ffprobe to get number of audio channels in a WAV file."""
    cmd = [
        _FFPROBE_EXE,
        "-hide_banner",
        "-loglevel",
        "panic",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=channels",
        "-of",
        "json",
        str(wav_file),
    ]
    # '-v', 'error',

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
    info = json.loads(result.stdout)
    return info["streams"][0]["channels"]


def getMediaInfo(filename, print_result=True):
    """
    Returns:
        result = dict with audio info where:
        result['format'] contains dict of tags, bit rate etc.
        result['streams'] contains a dict per stream with sample rate, channels etc.
    """
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


###############################################################################
# DSP
###############################################################################


def audioMixMono(src_file=None, noise_file=None, tmp_folder=None, samplerate=0, gain_pre=1.0, gain_post=1.0):
    err = 0

    print("MONO MIX {}".format(src_chnum))
    err = -1
    logger("noise MONO mixing not yet implemented (tbd)")

    return err


def audioMixStereo(src_file=None, noise_file=None, tmp_folder=None, samplerate=0, gain_pre=1.0, gain_post=1.0):
    err = 0

    src_info = getMediaInfo(src_file, print_result=False)
    noise_info = getMediaInfo(noise_file, print_result=False)

    src_duration = float(src_info["streams"][0]["duration"])
    noise_duration = float(noise_info["streams"][0]["duration"])

    if noise_duration < src_duration:
        logger.error("{} cannot mix: noise duration is less than input file".format(_SCRIPT_NAME))
        return -1

    # shuffe noise if possible
    noise_cut = 0
    if noise_duration > src_duration:
        noise_cut = round(random.uniform(0, (noise_duration - (src_duration * 1.05))), 2)

    #
    # generate noise chunk
    #
    noise_tmp_filename = os.path.join(tmp_folder, os.path.basename(noise_file))

    cmd = [
        _FFMPEG_EXE,
        "-y",
        "-loglevel",
        "error",
        "-stats",
        "-i",
        str(noise_file),
        "-ss",
        str(noise_cut),
        "-t",
        str(src_duration),
        str(noise_tmp_filename),
        " > /dev/null 2>&1",
    ]

    logger.info("Running ffmpeg command:")
    logger.info(" ".join(cmd))

    try:
        os.system(" ".join(cmd))
    except:
        logger.error("{} cannot mix: error on noise file cut".format(_SCRIPT_NAME))
        return -1

    #
    # audio mix
    #
    # ffmpeg -i input0.mp3 -i input1.mp3 -filter_complex amix=inputs=2:duration=longest output.mp3

    out_tmp_filename = os.path.join(tmp_folder, os.path.basename(src_file))

    audio1, sr1 = sf.read(src_file)
    audio2, sr2 = sf.read(noise_tmp_filename)

    # Check that both are stereo
    if audio1.ndim != 2 or audio1.shape[1] != 2:
        raise ValueError(f"{file1_path} is not stereo")
    if audio2.ndim != 2 or audio2.shape[1] != 2:
        raise ValueError(f"{file2_path} is not stereo")

    # Check sample rate consistency
    if sr1 != sr2:
        raise ValueError(f"Sample rates differ: {sr1} vs {sr2}. Resample before mixing.")

    # Pad shorter file with zeros (on the time axis)
    max_len = max(audio1.shape[0], audio2.shape[0])
    if audio1.shape[0] < max_len:
        pad_width = max_len - audio1.shape[0]
        audio1 = np.pad(audio1, ((0, pad_width), (0, 0)))
    if audio2.shape[0] < max_len:
        pad_width = max_len - audio2.shape[0]
        audio2 = np.pad(audio2, ((0, pad_width), (0, 0)))

    # Mix audio with pre/post gain control
    mixed = (gain_pre*audio1 + audio2) * gain_post

    # Normalize to avoid clipping (optional)
    max_abs = np.max(np.abs(mixed))
    if max_abs > 1.0:
        mixed = mixed / max_abs

    # Save the result
    sf.write(out_tmp_filename, mixed, sr1)

    # Sanity checks on results
    if not (os.path.isfile(out_tmp_filename)):
        logger.error("{} cannot mix: error on audio+noise downmix".format(_SCRIPT_NAME))
        return -1

    noise_info = getMediaInfo(out_tmp_filename, print_result=False)

    try:
        noise_duration = float(noise_info["streams"][0]["duration"])
        if noise_duration != src_duration:
            logger.error(
                "{} invalid duration, src_duration={} out_duration={}".format(
                    _SCRIPT_NAME, src_duration, noise_duration
                )
            )
            return -1
    except:
        return -1

    # everything looks good, swap files
    try:
        shutil.move(out_tmp_filename, src_file)
    except:
        return -1

    return err




def audioMix(src_file=None, noise_file=None, tmp_folder=None, samplerate=0, gain_pre=1.0, gain_post=1.0):
    err = 0

    if not (os.path.isdir(tmp_folder)):
        return -1

    try:
        src_info = getMediaInfo(src_file, print_result=False)
        noise_info = getMediaInfo(noise_file, print_result=False)
    except:
        return -1

    if samplerate < 8000:
        logger.error("{} invalid samplerate (too low)".format(_SCRIPT_NAME))
        return -1

    src_chnum = int(src_info["streams"][0]["channels"])
    noise_chnum = int(src_info["streams"][0]["channels"])

    if (noise_chnum < 1) or (src_chnum < 1) or (noise_chnum < src_chnum) or (noise_chnum > 2) or (src_chnum > 2):
        logger.error(
            "{} cannot perform noise audio mix due to channel num mismatch input:{} noise:{}".format(
                _SCRIPT_NAME, src_chnum, noise_chnum
            )
        )

    # resampling
    if src_info["streams"][0]["sample_rate"] != noise_info["streams"][0]["sample_rate"]:
        noise_basename = os.path.basename(noise_file)
        output_file = os.path.join(tmp_folder, noise_basename)

        cmd = [
            _FFMPEG_EXE,
            "-y",
            "-loglevel",
            "error",
            "-stats",
            "-i",
            str(noise_file),
            "-ar",
            str(samplerate),
            str(output_file),
            " > /dev/null 2>&1",
        ]

        logger.info("Running ffmpeg command:")
        logger.info(" ".join(cmd))

        # execute resampling
        os.system(" ".join(cmd))

        if os.path.isfile(output_file):
            noise_file = output_file
        else:
            logger.error(
                "{} cannot perform noise audio mix due to channel num mismatch input:{} noise:{}".format(
                    _SCRIPT_NAME, src_chnum, noise_chnum
                )
            )

    if src_chnum == 1:
        err = audioMixMono(src_file, noise_file, tmp_folder, samplerate, gain_pre, gain_post)
    elif src_chnum == 2:
        err = audioMixStereo(src_file, noise_file, tmp_folder, samplerate, gain_pre, gain_post)

    return err


#
###############################################################################
# MAIN
###############################################################################
#

if __name__ == "__main__":
    # install CTRL-C handles
    signal.signal(signal.SIGINT, signal_handler)

    # set user friendly process name for MAIN
    setproctitle("noise-8mics_audio_mix")

    # parse input params
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input_file",
        type=str,
        default=None,
        help="input_file (default: %(default)s)",
    )
    parser.add_argument(
        "-o",
        "--output_folder",
        type=str,
        default=None,
        help="output folder (default: %(default)s)",
    )
    parser.add_argument(
        "-p",
        "--param_file",
        type=str,
        default=None,
        help="parameter config file (default: %(default)s)",
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
        action="store_true",
        default=False,
        help="verbose (default: %(default)s)",
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
    if args.verbose:
        if args.logfile != None:
            logging.basicConfig(filename=args.logfile, encoding="utf-8", level=logging.INFO, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO)
            # coloredlogs.install(level='INFO', logger=logger)
    else:
        logging.basicConfig(level=logging.WARNING)
        # coloredlogs.install(level='WARNING', logger=logger)

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
    if cli_params["input_file"] == None:
        logger.error("{}: missing input file.".format(_SCRIPT_NAME))
        exit(1)
    else:
        if not (os.path.isfile(cli_params["input_file"])):
            logger.error("{}: input_file {} does not exists.".format(_SCRIPT_NAME, cli_params["input_file"]))
            exit(1)

    if cli_params["param_file"] == None:
        logger.error("{}: missing parameter file.".format(_SCRIPT_NAME))
        exit(1)
    else:
        if not (os.path.isfile(cli_params["param_file"])):
            logger.error("{}: input_file {} does not exists.".format(_SCRIPT_NAME, cli_params["param_file"]))
            exit(1)

    if cli_params["output_folder"] == None:
        # logger.error("{}: output_folder is needed.".format(_SCRIPT_NAME))
        # exit(1)
        # output folder is the same of input
        cli_params["output_folder"] = os.path.dirname(cli_params["input_file"])
        logger.info("{}: output folder is {}".format(_SCRIPT_NAME, cli_params["output_folder"]))

    else:
        if not (os.path.isdir(cli_params["output_folder"])):
            logger.info("{}: output folder does not exists, trying to create it".format(_SCRIPT_NAME))
            os.makedirs(cli_params["output_folder"])
            if not (os.path.isdir(cli_params["output_folder"])):
                logger.error("{}: cannot create output_folder {}.".format(_SCRIPT_NAME, cli_params["output_folder"]))
                exit(1)

    _OUTPUT_REF_DIR = cli_params["output_folder"] + _OUTPUT_REF_DIR

    if not (os.path.isdir(_OUTPUT_REF_DIR)):
        logger.info("{}: output subfolder does not exists, trying to create it".format(_SCRIPT_NAME))
        os.makedirs(_OUTPUT_REF_DIR)
        if not (os.path.isdir(_OUTPUT_REF_DIR)):
            logger.error("{}: cannot create output sub folder {}.".format(_SCRIPT_NAME, _OUTPUT_REF_DIR))
            exit(1)

    _OUTPUT_TMP_DIR = cli_params["output_folder"] + _OUTPUT_TMP_DIR

    if not (os.path.isdir(_OUTPUT_TMP_DIR)):
        logger.info("{}: tmp subfolder does not exists, trying to create it".format(_SCRIPT_NAME))
        os.makedirs(_OUTPUT_TMP_DIR)
        if not (os.path.isdir(_OUTPUT_TMP_DIR)):
            logger.error("{}: cannot create tmp sub folder {}.".format(_SCRIPT_NAME, _OUTPUT_TMP_DIR))
            exit(1)

    #
    # load info files
    #
    err = 0

    #
    # load params
    #
    params_yaml = {}
    try:
        params_yaml = readYamlFile(cli_params["param_file"])
    except:
        err = -1
        logger.error("could not read post-processing yaml: {}".format(cli_params["param_file"]))
        exit(1)

    #
    # load scene yaml
    #
    scene_yaml = {}
    try:
        scene_yaml = readYamlFile(params_yaml["scene"]["file"])
    except:
        err = -1
        logger.error("could not read post-processing yaml: {}".format(params_yaml["scene"]["file"]))
        exit(1)

    #
    # load noise setup
    #
    setup_yaml = {}
    try:
        setup_yaml = readYamlFile(params_yaml["setup"]["file"])
    except:
        err = -1
        logger.error("could not read post-processing yaml: {}".format(params_yaml["setup"]["file"]))
        exit(1)

    #
    # check: do we have he correct type of noise
    #
    tgt_name = "None"
    try:
        tgt_name = params_yaml["task"]["name"]

        # if we do not have a match, warning and pick one
        if not (tgt_name in setup_yaml["names"]):
            logger.error(
                "{} not a noise match for {}, selecting {}".format(_SCRIPT_NAME, tgt_name, setup_yaml["names"][0])
            )
            tgt_name = setup_yaml["names"][0]
        else:
            logger.info("{} noise name match found: {}".format(_SCRIPT_NAME, tgt_name))

    except:
        err = -1
        logger.error("{} invalid task name".format(_SCRIPT_NAME))
        exit(1)

    #
    # check: do we have he correct samplerate
    #
    tgt_samplerate = 0
    src_samplerate = 0
    src_channel_count = 0
    try:
        tgt_samplerate = int(scene_yaml["setup"]["format"]["samplerate"])
    except:
        err = -1
        logger.error("{} invalid scene file syntax".format(_SCRIPT_NAME))
        exit(1)

    try:
        src_media_info = getMediaInfo(cli_params["input_file"], print_result=False)
        if src_media_info["format"]["nb_streams"] != 1:
            err = -1
            logger.error("{} more than one stream in file {}".format(_SCRIPT_NAME, cli_params["input_file"]))
            exit(1)
        src_samplerate = int(src_media_info["streams"][0]["sample_rate"])
        src_channel_count = int(src_media_info["streams"][0]["channels"])
    except:
        err = -1
        logger.error("{} invalid input file".format(_SCRIPT_NAME))
        exit(1)

    if tgt_samplerate != src_samplerate:
        logger.error(
            "{} rendering scene_samplerate {} != input_file samplerate {}, resampling...".format(
                _SCRIPT_NAME, tgt_samplerate, src_samplerate
            )
        )
        logger.info("{} rendering by matching input_file samplerate {}".format(_SCRIPT_NAME, src_samplerate))
        tgt_samplerate = src_samplerate

    #
    # search for samplerate match
    #
    idx_match = 0
    try:
        for idx in setup_yaml["files"]:
            if tgt_samplerate == setup_yaml["files"][idx]["audio"]["format"]["samplerate"]:
                logger.info("{} found matching samplerate {} for idx {}".format(_SCRIPT_NAME, tgt_samplerate, idx))
                idx_match = idx
    except:
        err = -1
        logger.error("{} cannot find matching noise for {}".format(_SCRIPT_NAME, cli_params["input_file"]))
        exit(1)

    #
    # Audio Noise Mixing
    #
    if err == 0:
        try:
            rv = audioMix(
                str(cli_params["input_file"]),
                os.path.join(_BASE_DIR, setup_yaml["files"][idx_match][tgt_name]["file"]),
                _OUTPUT_TMP_DIR,
                tgt_samplerate,
                setup_yaml["files"][idx]["audio"]["gain"]["pre"], # gain_pre
                setup_yaml["files"][idx]["audio"]["gain"]["post"], # gain_post
            )
            if rv != 0:
                logger.error("{} cannot perform noise audio mix {}".format(_SCRIPT_NAME, cli_params["input_file"]))
                exit(1)
            else:
                logger.info(
                    "Noise PostProcessing done: IN: {}, NOISE: {}".format(
                        str(cli_params["input_file"]),
                        os.path.join(_BASE_DIR, setup_yaml["files"][idx_match][tgt_name]["file"]),
                    ),
                )

        except:
            logger.error("{} error while performing noise audio mix {}".format(_SCRIPT_NAME, cli_params["input_file"]))
            exit(1)
