#!/usr/bin/env python3
"""display a source path (csv file)"""

import pandas as pd
from tabulate import tabulate
import numpy as np
import matplotlib.pyplot as plt
import logging
import signal
import argparse
import yaml
import os

#
# Set logger format and color
#
logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s]%(levelname)s: %(message)s"


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
        help="input path file (yaml or csv) to display (default: %(default)s)",
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
    if not (args.input_file.endswith((".yaml", ".csv"))):
        logging.error("unsupported file type (only .yaml or .csv)")
        exit(0)

    if not (os.path.isfile(args.input_file)):
        logging.error("cannot read file {}".format(args.input_file))
        exit(0)

    csv_path_file = args.input_file

    if args.input_file.endswith((".yaml")):
        info_yaml = readYamlFile(args.input_file)

        if not ("syntax" in info_yaml):
            logging.error("invalid path file syntax")
            exit(0)
        if not ("name" in info_yaml["syntax"]):
            logging.error("invalid path file syntax")
            exit(0)
        if info_yaml["syntax"]["name"] != "path_map":
            logging.error("invalid path file syntax")
            exit(0)
        if not (("format" in info_yaml) and ("path" in info_yaml)):
            logging.error("invalid path file syntax")
            exit(0)
        #
        # only csv files for now
        if info_yaml["format"] != "csv":
            logging.error("only .csv path files are supported")
            exit(0)

        tmp = os.path.split(os.path.abspath(args.input_file))

        csv_path_file = os.path.join(tmp[0], "../", info_yaml["path"][0]["file"])

    if args.verbose and args.input_file.endswith((".yaml")):
        logging.info("name        :{}".format(info_yaml["name"]))
        logging.info("description :{}".format(info_yaml["description"]))

    # check for CSV file presence
    if not (os.path.isfile(csv_path_file)):
        logging.error("cannot read file {}".format(csv_path_file))
        exit(0)

    # Load the file, skipping metadata
    file_path = csv_path_file
    df = pd.read_csv(file_path, comment="#")
    df.columns = ["time_percent", "volume_percent", "azimuth_deg", "elevation_deg", "distance_m", "type"]

    # Convert angles to radians
    df["azimuth_rad"] = np.radians(df["azimuth_deg"])
    df["elevation_rad"] = np.radians(df["elevation_deg"])

    # IMPORTANT: the define 3DTI_AXIS_CONVENTION_BINAURAL_TEST_APP will define also:
    # #define UP_AXIS AXIS_Z                  ///< In the test app Z is the UP direction
    # #define RIGHT_AXIS AXIS_MINUS_Y         ///< In the test app -Y is the RIGHT direction
    # #define FORWARD_AXIS AXIS_X             ///< In the test app X is the FORWARD direction
    #
    # IMPORTANT: the define 3DTI_ANGLE_CONVENTION_LISTEN will define also:
    # #define AZIMUTH_ZERO FORWARD_AXIS       ///< In LISTEN database, azimuth=0 is in the front
    # #define AZIMUTH_MOTION ANTICLOCKWISE    ///< In LISTEN database, azimuth motion is anti-clockwise
    # #define ELEVATION_ZERO FORWARD_AXIS     ///< In LISTEN database, elevation=0 is in the front
    # #define ELEVATION_MOTION ANTICLOCKWISE  ///< In LISTEN database, elevation motion is anti-clockwise

    # Spherical to Cartesian conversion
    df["x"] = df["distance_m"] * np.cos(df["elevation_rad"]) * np.cos(df["azimuth_rad"])
    df["y"] = df["distance_m"] * np.cos(df["elevation_rad"]) * np.sin(df["azimuth_rad"])
    df["z"] = df["distance_m"] * np.sin(df["elevation_rad"])

    if args.verbose:
        print(tabulate(df, headers="keys", tablefmt="psql"))

    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    ax.scatter(df["x"], df["y"], df["z"], marker="x")

    last = len(df["x"]) - 1

    ax.scatter(df["x"][0], df["y"][0], df["z"][0], marker="o", color="green")
    ax.text(
        df["x"][0],
        df["y"][0],
        df["z"][0],
        "begin",
        color="green",
    )

    ax.scatter(df["x"][last], df["y"][last], df["z"][last], marker="o", color="red")
    ax.text(
        df["x"][last],
        df["y"][last],
        df["z"][last],
        "end",
        color="red",
    )

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_xlim(min(-1, min(df["x"])), max(1, max(df["x"])))
    ax.set_ylim(min(-1, min(df["y"])), max(1, max(df["y"])))
    ax.set_zlim(min(-1, min(df["z"])), max(1, max(df["z"])))

    # Draw positive part of X-axis (from 0 to max)
    ax.plot([0, ax.get_xlim()[1]], [0, 0], [0, 0], color="blue", linewidth=1)
    ax.plot([0, 0], [0, ax.get_ylim()[1]], [0, 0], color="red", linewidth=1)
    ax.plot([0, 0], [0, 0], [0, ax.get_zlim()[1]], color="green", linewidth=1)

    ax.set_aspect("equal", adjustable="box")

    plt.show()
