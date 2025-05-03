#!/usr/bin/env python3
"""play a scene (.mkv) file"""

import logging
import signal
import argparse
import yaml
import os

import json
import subprocess

#
# Set logger format and color
#
logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s]%(levelname)s: %(message)s"

#
# EXECUTABLES / EXTERNAL CMDs
#
_FFPLAY_EXE = "/usr/bin/ffplay"
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


def get_mkv_info(mkv_file):
    """Uses ffprobe to get number of audio channels in a WAV file."""
    cmd = [
        _FFPROBE_EXE,
        "-hide_banner",
        "-loglevel",
        "panic",
        "-show_entries",
        "stream_tags=title",
        "-of",
        "json",
        str(mkv_file),
    ]
    # '-v', 'error',

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
    info = json.loads(result.stdout)

    return info["streams"]


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


#
###############################################################################
# MAIN
###############################################################################
#

if __name__ == "__main__":
    # install CTRL-C handles
    signal.signal(signal.SIGINT, signal_handler)

    # parse input params
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input_file",
        type=str,
        default=None,
        help="input path file (yaml or mkv) to display (default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--list_tracks",
        action="store_true",
        default=False,
        help="list tracks title (default: %(default)s)",
    )
    parser.add_argument(
        "-t",
        "--track",
        default=-1,
        type=int,
        help="audio track to play",
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
    else:
        logging.basicConfig(level=logging.WARNING)

    #
    #
    if args.input_file == None:
        logging.error("missing input file, use option '-i [FILE]'")
        exit(0)

    #
    # check if the input file is yaml or csv
    #
    if not (args.input_file.endswith((".yaml", ".mkv"))):
        logging.error("unsupported file type (only .yaml or .mkv)")
        exit(0)

    if not (os.path.isfile(args.input_file)):
        logging.error("cannot read file {}".format(args.input_file))
        exit(0)

    mkv_path_file = args.input_file

    if args.input_file.endswith((".yaml")):
        info_yaml = readYamlFile(args.input_file)

        if not ("syntax" in info_yaml):
            logging.error("invalid scene file syntax")
            exit(0)
        if not ("name" in info_yaml["syntax"]):
            logging.error("invalid scene file syntax")
            exit(0)
        if info_yaml["syntax"]["name"] != "verse_audio_mkv":
            logging.error("invalid scene file syntax, not a rendered (.mkv) audio scene")
            exit(0)
        if not ("file" in info_yaml):
            logging.error("invalid scene file syntax, missing mkv filename")
            exit(0)
        #
        # only mkv files for now
        if not (info_yaml["file"].endswith(".mkv")):
            logging.error("only .mkv scene files are supported")
            exit(0)

        tmp = os.path.split(os.path.abspath(args.input_file))

        mkv_path_file = os.path.join(tmp[0], "./", info_yaml["file"])

    if args.verbose and args.input_file.endswith((".yaml")):
        logging.info("name        :{}".format(info_yaml["name"]))
        logging.info("description :{}".format(info_yaml["description"]))

    # check for MKV file presence
    if not (os.path.isfile(mkv_path_file)):
        logging.error("cannot read file {}".format(mkv_path_file))
        exit(0)

    #
    # PLAYBACK
    #

    mkv_titles = get_mkv_info(mkv_path_file)

    idx = 0
    if args.list_tracks:
        for title in mkv_titles:
            print("{} : {}".format(idx, title["tags"]["title"]))
            idx += 1

    else:
        if args.track < 0:
            cmd = [
                _FFPLAY_EXE,
            ]

            if not (args.verbose):
                cmd += ["-hide_banner", "-loglevel", "panic", "-nodisp"]

            cmd += [mkv_path_file]

            logger.info("no track selection: playing all tracks at the same time")

            os.system(" ".join(cmd))

        else:
            if args.track > len(mkv_titles):
                logger.error("selected track is not valid, max is {}".format(len(mkv_titles)))

            cmd = [
                _FFPLAY_EXE,
            ]

            if not (args.verbose):
                cmd += ["-hide_banner", "-loglevel", "panic", "-nodisp"]

            cmd += ["-ast a:{}".format(args.track)]

            cmd += [mkv_path_file]

            logger.info("playing track:{} title:{}".format(args.track, mkv_titles[args.track]["tags"]["title"]))

            os.system(" ".join(cmd))
