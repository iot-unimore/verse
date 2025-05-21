#!/usr/bin/env python3
"""Render audio scene"""

import os
import sys
import yaml
import coloredlogs
import logging
import signal
import argparse
import sys

import shutil
import glob

import json
import subprocess

from multiprocessing import Pool
from setproctitle import setproctitle
from subprocess import check_output

#
# Set logger format and color
#
logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s]%(levelname)s: %(message)s"


#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads

_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_RESOURCES_DIR = os.path.abspath(os.path.dirname(__file__)) + "/../resources"
_OUTPUT_REF_DIR = "/ref/"
_OUTPUT_TMP_DIR = "/tmp/"

_MIN_CPU_COUNT = 1  # we need at least one CPU for each compute process
_MIN_MEM_GB = 1  # min amount of memory for each compute process
_MAX_MEM_GB = 1  # max amount of memory for each compute process

#
# EXECUTABLES / EXTERNAL CMDs
#
_SSPAT_EXE = _ROOT_DIR + "/../tools/bin/sspat"
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_FFPROBE_EXE = "/usr/bin/ffprobe"


#
# TOOLS
#
def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except Error:
        return text


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

    logger.info("Running ffmpeg command:")
    logger.info(" ".join(cmd))

    os.system(" ".join(cmd))
    # subprocess.run(cmd, check=True)


def getSourceFilesSoundSpatializer(cfg_yaml={}):
    """
    write a config file (.yaml) for sound_spatializer tool

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d
    """
    err = -1

    source_files = []

    if len(cfg_yaml) > 0:
        if "sources" in cfg_yaml:
            for sidx in cfg_yaml["sources"]:
                source_files.append(cfg_yaml["sources"][sidx]["file"])

    return source_files


def writeAudioWavDescriptor(filename=None, mono_files=[], stereo_files=[]):
    """
    write a descriptor file (.yaml) for audio_scene final wav file (multi-track)

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d
    """

    track_id = 0

    yaml_descriptor = {}

    if filename != None:
        yaml_descriptor["sources_count"] = len(mono_files)
        yaml_descriptor["sources"] = {}
        idx = 0
        for file in mono_files:
            yaml_descriptor["sources"][idx] = {}
            yaml_descriptor["sources"][idx]["file"] = os.path.split(file)[1]
            yaml_descriptor["sources"][idx]["channels"] = 1
            yaml_descriptor["sources"][idx]["track_id"] = track_id
            yaml_descriptor["sources"][idx]["lr"] = "none"
            track_id += 1
            idx += 1

        yaml_descriptor["receivers_count"] = len(stereo_files) // * 2
        yaml_descriptor["receivers"] = {}
        idx = 0
        for file in stereo_files:
            for lr in ["left", "right"]:
                yaml_descriptor["receivers"][idx] = {}
                yaml_descriptor["receivers"][idx]["file"] = os.path.split(file)[1]
                yaml_descriptor["receivers"][idx]["channels"] = 1
                yaml_descriptor["receivers"][idx]["track_id"] = track_id
                yaml_descriptor["receivers"][idx]["lr"] = lr
                track_id += 1
                idx += 1

        # print(yaml.dump(yaml_descriptor))

        with open(filename, "w") as file:
            yaml.dump(yaml_descriptor, file)


def writeAudioMKVDescriptor(filename=None, mono_files=[], stereo_files=[], mkv_filename=None):
    """
    write a descriptor file (.yaml) for audio_scene final wav file (multi-track)

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d
    """

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

        with open(filename, "w") as file:
            yaml.dump(yaml_descriptor, file)


def writeSoundSpatializerCFG(filename=None, cfg_yaml={}):
    """
    write a config file (.yaml) for sound_spatializer tool

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d
    """
    err = -1

    cfg = {}

    if len(cfg_yaml) > 0:
        cfg = {}
        cfg["syntax"] = {}
        cfg["syntax"]["name"] = "sspat_config"
        cfg["syntax"]["version"] = {"major": 0, "minor": 1, "revision": 0}

        cfg["setup"] = {}

        cfg["setup"]["head"] = {}
        cfg["setup"]["head"]["hrtf_sofa"] = cfg_yaml["head"]

        cfg["setup"]["room"] = {}
        cfg["setup"]["room"]["brir_sofa"] = cfg_yaml["room"]

        cfg["setup"]["sources_count"] = len(cfg_yaml["sources"])

        cfg["setup"]["sources"] = {}
        for sidx in cfg_yaml["sources"]:
            cfg["setup"]["sources"][sidx] = {}
            cfg["setup"]["sources"][sidx]["file_wav"] = cfg_yaml["sources"][sidx]["file"]
            cfg["setup"]["sources"][sidx]["coord"] = cfg_yaml["sources"][sidx]["coord"]
            cfg["setup"]["sources"][sidx]["path_csv"] = cfg_yaml["sources"][sidx]["path_csv"]

    if len(cfg) > 0:
        # logger.info(yaml.dump(cfg))
        logger.info(cfg)

        with open(filename, "w") as file:
            yaml.dump(cfg, file)

        if os.path.isfile(filename):
            err = 0
        else:
            err = -1
            logger.error("cannot write soundSpatializer config file {}".format(filename))

    return err


def executeSoundSpatializerCmd(cmd=""):
    err = 0
    logger.info("soundSpatializer, executing:" + str(cmd))

    result = check_output(cmd)

    if not (os.path.isfile(cmd[4])):
        err = -1
        logger.error("could not run sound spatializer: {}".format(cmd))


#
# AUDIO PROCESSING
#
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


def verifySpericalCoord(source_coord):
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


def audioSceneRender(cli_params=None):
    """
    Render audio scene (.yaml) file.

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d

    Description
    -----------
    Get an audio scene yaml file from imput parameters and render the audio output.
    run sanity checks on syntax and launch the spatializer tool
    to render audio in the required format (WAV).
    """

    err = 0

    scene_yaml = []
    sources_yaml = []
    sources_wav = []
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
    # loop over sources
    #
    if err == 0:
        # sources
        for idx in scene_yaml["setup"]["sources"]:
            tmp_yaml = []
            try:
                tmp_filename = os.path.join(
                    _RESOURCES_DIR,
                    scene_yaml["setup"]["sources"][idx]["type"],
                    scene_yaml["setup"]["sources"][idx]["subtype"],
                    "info",
                    scene_yaml["setup"]["sources"][idx]["info"],
                )
                with open(tmp_filename + ".yaml", "r") as file:
                    tmp_yaml = yaml.safe_load(file)
                sources_yaml.append(tmp_yaml)
            except:
                err = -1
                logger.error("cannot open/parse source yaml file: {}".format(tmp_filename))

    if err == 0:
        tmp_sources_coord = []
        tmp_sources_wav = []
        for idx in range(scene_yaml["setup"]["sources_count"]):
            media_filename = os.path.join(
                _RESOURCES_DIR,
                scene_yaml["setup"]["sources"][idx]["type"],
                scene_yaml["setup"]["sources"][idx]["subtype"],
                sources_yaml[idx]["file"],
            )

            media_info = getMediaInfo(media_filename, print_result=False)

            # sanity checks : only one audio stream
            if media_info["format"]["nb_streams"] != 1:
                err = -1
                logger.error("more than one stream in file {}".format(tmp_filename))

            # sanity checks : position
            if "position" in scene_yaml["setup"]["sources"][idx]:
                if scene_yaml["setup"]["sources"][idx]["position"]["type"] == "static":
                    if scene_yaml["setup"]["sources"][idx]["position"]["coord"]["type"] != "spherical":
                        err = -1
                        logger.error("invalid position type for source {} in file {}".format(idx, tmp_filename))

                    mycoord = list(scene_yaml["setup"]["sources"][idx]["position"]["coord"]["value"])

                    if 0 != verifySpericalCoord(str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])):
                        err = -1
                        logger.error(
                            "invalid position coordinates {} for source {} in file {}".format(
                                scene_yaml["setup"]["sources"][idx]["position"]["coord"]["value"], idx, tmp_filename
                            )
                        )
                elif scene_yaml["setup"]["sources"][idx]["position"]["type"] == "dynamic":
                    tmp_filename = os.path.join(
                        _RESOURCES_DIR,
                        scene_yaml["setup"]["sources"][idx]["position"]["value"]["type"],
                        scene_yaml["setup"]["sources"][idx]["position"]["value"]["subtype"],
                        "info",
                        scene_yaml["setup"]["sources"][idx]["position"]["value"]["info"],
                    )
                    if not os.path.isfile(tmp_filename):
                        err = -1
                        logger.error("missing path file {}".format(tmp_filename))
                else:
                    err = -1
                    logger.error("invalid position type for source {} in file {}".format(idx, tmp_filename))
            else:
                err = -1
                logger.error("invalid position for source {} in file {}".format(idx, tmp_filename))

            if err == 0:
                out_filename = os.path.join(_OUTPUT_REF_DIR, scene_yaml["setup"]["sources"][idx]["info"]) + ".wav"

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
                    # "-ss",
                    # sources_yaml[idx]["playback"]["begin"],
                    # "-to",
                    # sources_yaml[idx]["playback"]["end"],
                    "-c:a",
                    str(scene_yaml["setup"]["format"]["subtype"]),
                    "-ar",
                    str(scene_yaml["setup"]["format"]["samplerate"]),
                    "-ac",
                    "1",
                    # out_filename,
                ]

                if "playback" in sources_yaml[idx]:
                    os_cmd += [
                        "-ss",
                        str(sources_yaml[idx]["playback"]["begin"]),
                        "-to",
                        str(sources_yaml[idx]["playback"]["end"]),
                    ]

                if "playback" in scene_yaml["setup"]["sources"][idx]:
                    if "padding" in scene_yaml["setup"]["sources"][idx]["playback"]:
                        if ("pre" in scene_yaml["setup"]["sources"][idx]["playback"]["padding"]) and (
                            "post" in scene_yaml["setup"]["sources"][idx]["playback"]["padding"]
                        ):
                            os_cmd += [
                                "-af",
                                "adelay="
                                + str(scene_yaml["setup"]["sources"][idx]["playback"]["padding"]["pre"])
                                + ",apad=pad_dur="
                                + str(scene_yaml["setup"]["sources"][idx]["playback"]["padding"]["post"]),
                            ]
                        elif "pre" in scene_yaml["setup"]["sources"][idx]["playback"]["padding"]:
                            os_cmd += [
                                "-af",
                                "adelay="
                                + str(scene_yaml["setup"]["sources"][idx]["playback"]["padding"]["pre"])
                                + "s:all_true",
                            ]
                        elif "post" in scene_yaml["setup"]["sources"][idx]["playback"]["padding"]:
                            os_cmd += [
                                "-af",
                                "apad=pad_dur="
                                + str(scene_yaml["setup"]["sources"][idx]["playback"]["padding"]["post"]),
                            ]

                os_cmd += [out_filename]

                if not os.path.isfile(out_filename):
                    logger.info("convert audio file {}".format(out_filename))
                    result = check_output(os_cmd)
                    # os.system(" ".join(os_cmd))
                else:
                    logger.info("audio file already converted {}".format(out_filename))

                tmp_sources_wav.append(os.path.join(_ROOT_DIR, out_filename))

                if not os.path.isfile(os.path.join(_ROOT_DIR, out_filename)):
                    err = -1
                    logger.error("could not render .wav file {}".format(os.path.join(_ROOT_DIR, out_filename)))

        # collect .wav files (converted) for each source
        sources_wav.append(tmp_sources_wav)

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

    #
    # render scene or exit on error
    #
    if err != 0:
        logger.error("could not render audio scene: {}".format(cli_params["scene_file"]))
    else:
        audioSpatialize(cli_params, scene_yaml, sources_yaml, sources_wav, listeners_yaml, rooms_yaml)


def audioSpatialize(
    cli_params=None, scene_yaml=None, sources_yaml=None, sources_wav=None, listeners_yaml=None, rooms_yaml=None
):
    """
    Runs the spatializer tool on a specific scene configuration

    Parameters
    ----------
    t.b.d

    Returns
    -------
    t.b.d

    Description
    -----------
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

            #
            # room
            #
            rooms_brir_file = ""
            if scene_yaml["setup"]["rooms_count"] > 1:
                err = -1
                logger.error("invalid rooms count (must be 1)")
            else:
                if scene_yaml["setup"]["rooms_count"] == 1:
                    rooms_brir_file = os.path.join(
                        _RESOURCES_DIR,
                        scene_yaml["setup"]["rooms"][scene_listener_idx]["type"],
                        scene_yaml["setup"]["rooms"][scene_listener_idx]["subtype"],
                        rooms_yaml[0]["brir"][0]["file"],
                    )
                else:
                    rooms_brir_file = "none"

            if err == 0:
                for lidx in listener["hrtf"]:
                    logger.info("==============================")
                    logger.info("LISTENER IDX: " + str(lidx))
                    logger.info("==============================")

                    sound_spatializer_cmd["name"] = listener["hrtf"][lidx]["name"]
                    sound_spatializer_cmd["sources"] = {}
                    sound_spatializer_cmd["room"] = rooms_brir_file

                    #
                    # head
                    #
                    head_sofa_file = os.path.join(
                        _RESOURCES_DIR,
                        scene_yaml["setup"]["listeners"][scene_listener_idx]["type"],
                        scene_yaml["setup"]["listeners"][scene_listener_idx]["subtype"],
                        listener["hrtf"][lidx]["file"],
                    )
                    sound_spatializer_cmd["head"] = head_sofa_file

                    # read sources
                    for sidx in range(len(sources_wav[0])):
                        # position static or dynamic, if dynamic load motion file definition
                        path_file = ""
                        if scene_yaml["setup"]["sources"][sidx]["position"]["type"] == "static":
                            mycoord = list(scene_yaml["setup"]["sources"][sidx]["position"]["coord"]["value"])
                            if 0 != verifySpericalCoord(
                                str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])
                            ):
                                err = -1
                                logger.error(
                                    "invalid position coordinates {} for source {} in file {}".format(
                                        scene_yaml["setup"]["sources"][sidx]["position"]["coord"]["value"],
                                        idx,
                                        tmp_filename,
                                    )
                                )
                        else:
                            tmp_filename = os.path.join(
                                _RESOURCES_DIR,
                                scene_yaml["setup"]["sources"][sidx]["position"]["value"]["type"],
                                scene_yaml["setup"]["sources"][sidx]["position"]["value"]["subtype"],
                                "info",
                                scene_yaml["setup"]["sources"][sidx]["position"]["value"]["info"],
                            )

                            path_yaml = readYamlFile(tmp_filename)

                            # sanity checks: must be a csv
                            if "format" in path_yaml:
                                if path_yaml["format"] != "csv":
                                    err = -1
                                    logger.error("unsupported path file format: {}", format(tmp_filename))
                            else:
                                err = -1
                                logger.error("missing path file format: {}", format(tmp_filename))

                            # sanity checks: must have a path file
                            if "path" in path_yaml:
                                if (len(path_yaml["path"]) > 1) or (len(path_yaml["path"]) == 0):
                                    err = -1
                                    logger.error("more than one path in file: {}", format(tmp_filename))

                                if "file" in path_yaml["path"][0]:
                                    tmp_filename = os.path.join(
                                        _RESOURCES_DIR,
                                        scene_yaml["setup"]["sources"][sidx]["position"]["value"]["type"],
                                        scene_yaml["setup"]["sources"][sidx]["position"]["value"]["subtype"],
                                        path_yaml["path"][0]["file"],
                                    )
                                    if os.path.isfile(tmp_filename):
                                        path_file = tmp_filename
                                    else:
                                        err = -1
                                        logger.error("missing path file in folder: {}", format(tmp_filename))
                                else:
                                    err = -1
                                    logger.error("missing path filename: {}", format(tmp_filename))
                            else:
                                err = -1
                                logger.error("invalid path file syntax: {}", format(tmp_filename))

                        # add spatializer to task list
                        if err == 0:
                            sound_spatializer_cmd["sources"][sidx] = {}
                            sound_spatializer_cmd["sources"][sidx]["file"] = sources_wav[0][sidx]
                            if scene_yaml["setup"]["sources"][sidx]["position"]["type"] == "static":
                                mycoord = list(scene_yaml["setup"]["sources"][sidx]["position"]["coord"]["value"])
                                sound_spatializer_cmd["sources"][sidx]["coord"] = (
                                    str(mycoord[0]) + "," + str(mycoord[1]) + "," + str(mycoord[2])
                                )
                                sound_spatializer_cmd["sources"][sidx]["path_csv"] = "none"
                            else:
                                sound_spatializer_cmd["sources"][sidx]["coord"] = "0,0,0"
                                sound_spatializer_cmd["sources"][sidx]["path_csv"] = path_file

                            # log for debug
                            logger.info("   sidx: " + str(sidx))
                            logger.info("   source:" + sources_wav[0][sidx])
                            # if(scene_yaml["setup"]["sources"][sidx]["position"]["type"]=="static"):
                            logger.info("      coord:")
                            if scene_yaml["setup"]["sources"][sidx]["position"]["type"] == "static":
                                logger.info("      static:")
                                logger.info(
                                    "      " + str(scene_yaml["setup"]["sources"][sidx]["position"]["coord"]["value"])
                                )
                            else:
                                logger.info("      dynamic:")
                                logger.info("      " + path_file)
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
        # print(yaml.dump(task))

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

        result = cpu_pool.map(executeSoundSpatializerCmd, sspat_cmds)

        cpu_pool.close()
        cpu_pool.join()

        # check results
        for cmd in sspat_cmds:
            if not (os.path.isfile(cmd[4])):
                err = -1
                logger.error("could not render audio file: {}".format(cmd[4]))

    if err == 0:
        #
        # mux WAV tracks into one MKV file
        #
        cmd = ""
        tmp_filename = tasks[0]["scene"]["name"]
        # ffmpeg_file = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + ".wav")
        ffmpeg_file = os.path.abspath(os.path.join(_OUTPUT_REF_DIR + "/../", tmp_filename) + ".mkv")

        # reference source files (mono)
        ref_files = getSourceFilesSoundSpatializer(tasks[0])

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
            filename=tmp_filename, mono_files=ref_files, stereo_files=sspat_files, mkv_filename=ffmpeg_file
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
