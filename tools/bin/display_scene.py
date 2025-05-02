#!/usr/bin/env python3
"""display a scene path (yaml file)"""

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

_RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../", "resources")


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
        help="input scene file (yaml) to display (default: %(default)s)",
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
    # check if the input file is yaml
    #
    if not (args.input_file.endswith((".yaml"))):
        logging.error("unsupported file type (only .yaml)")
        exit(0)

    if not (os.path.isfile(args.input_file)):
        logging.error("cannot read file {}".format(args.input_file))
        exit(0)

    yaml_path_file = args.input_file

    if args.input_file.endswith((".yaml")):
        info_yaml = readYamlFile(args.input_file)

        if not ("syntax" in info_yaml):
            logging.error("invalid path file syntax")
            exit(0)
        if not ("name" in info_yaml["syntax"]):
            logging.error("invalid path file syntax")
            exit(0)
        if info_yaml["syntax"]["name"] != "audio_rendering_scene":
            logging.error("invalid path file syntax")
            exit(0)
        if not ("scene" in info_yaml):
            logging.error("invalid scene file syntax")
            exit(0)
        if not ("setup" in info_yaml):
            logging.error("invalid scene file syntax")
            exit(0)
        # #
        # # only yaml files for now
        # if info_yaml["format"] != "csv":
        #     logging.error("only .csv path files are supported")
        #     exit(0)

        # tmp = os.path.split(os.path.abspath(args.input_file))

        # csv_path_file = os.path.join(tmp[0], "../", info_yaml["path"][0]["file"])

    if args.verbose and args.input_file.endswith((".yaml")):
        logging.info("name        :{}".format(info_yaml["scene"]["name"]))
        logging.info("description :{}".format(info_yaml["scene"]["description"]))
        logging.info("sources num :{}".format(info_yaml["setup"]["sources_count"]))

    fig = plt.figure()
    ax = fig.add_subplot(projection="3d")

    xx = []
    yy = []
    zz = []

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

    for src in info_yaml["setup"]["sources"]:
        if "static" == info_yaml["setup"]["sources"][src]["position"]["type"]:
            if args.verbose:
                print(
                    ":".join(
                        [
                            info_yaml["setup"]["sources"][src]["type"],
                            info_yaml["setup"]["sources"][src]["subtype"],
                            info_yaml["setup"]["sources"][src]["info"],
                        ]
                    )
                )
                print(info_yaml["setup"]["sources"][src]["position"]["type"])
                print(info_yaml["setup"]["sources"][src]["position"]["coord"]["value"])
                print(info_yaml["setup"]["sources"][src]["position"]["coord"]["type"])

            if "spherical" == info_yaml["setup"]["sources"][src]["position"]["coord"]["type"]:
                tmp = info_yaml["setup"]["sources"][src]["position"]["coord"]["value"]

                # Spherical to Cartesian conversion
                x = tmp[2] * np.cos(np.radians(tmp[1])) * np.cos(np.radians(tmp[0]))
                y = tmp[2] * np.cos(np.radians(tmp[1])) * np.sin(np.radians(tmp[0]))
                z = tmp[2] * np.sin(np.radians(tmp[1]))

            if "cartesian" == info_yaml["setup"]["sources"][src]["position"]["coord"]["type"]:
                coord = info_yaml["setup"]["sources"][src]["position"]["coord"]["value"]

            pt = ax.scatter(x, y, z, marker="o")
            ax.text(
                x,
                y,
                z,
                ":".join([info_yaml["setup"]["sources"][src]["subtype"], info_yaml["setup"]["sources"][src]["info"]]),
                color=pt.get_facecolor()[0].tolist(),
            )

            xx.append(x)
            yy.append(y)
            zz.append(z)

        elif "dynamic" == info_yaml["setup"]["sources"][src]["position"]["type"]:
            if args.verbose:
                print(
                    ":".join(
                        [
                            info_yaml["setup"]["sources"][src]["type"],
                            info_yaml["setup"]["sources"][src]["subtype"],
                            info_yaml["setup"]["sources"][src]["info"],
                        ]
                    )
                )

                print(info_yaml["setup"]["sources"][src]["position"]["type"])
                print(info_yaml["setup"]["sources"][src]["position"]["value"]["type"])
                print(info_yaml["setup"]["sources"][src]["position"]["value"]["subtype"])
                print(info_yaml["setup"]["sources"][src]["position"]["value"]["info"])

            yaml_path_file = os.path.join(
                _RESOURCES_DIR,
                info_yaml["setup"]["sources"][src]["position"]["value"]["type"],
                info_yaml["setup"]["sources"][src]["position"]["value"]["subtype"],
                "info",
                info_yaml["setup"]["sources"][src]["position"]["value"]["info"],
            )

            print(yaml_path_file)

            path_info_yaml = readYamlFile(yaml_path_file)
            if not ("syntax" in path_info_yaml):
                logging.error("invalid path file syntax")
                exit(0)
            if not ("name" in path_info_yaml["syntax"]):
                logging.error("invalid path file syntax")
                exit(0)
            if path_info_yaml["syntax"]["name"] != "path_map":
                logging.error("invalid path file syntax")
                exit(0)
            if not (("format" in path_info_yaml) and ("path" in path_info_yaml)):
                logging.error("invalid path file syntax")
                exit(0)
            #
            # only csv files for now
            if path_info_yaml["format"] != "csv":
                logging.error("only .csv path files are supported")
                exit(0)

            csv_path_file = os.path.join(
                _RESOURCES_DIR,
                info_yaml["setup"]["sources"][src]["position"]["value"]["type"],
                info_yaml["setup"]["sources"][src]["position"]["value"]["subtype"],
                path_info_yaml["path"][0]["file"],
            )

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

            # Spherical to Cartesian conversion
            df["x"] = df["distance_m"] * np.cos(df["elevation_rad"]) * np.cos(df["azimuth_rad"])
            df["y"] = df["distance_m"] * np.cos(df["elevation_rad"]) * np.sin(df["azimuth_rad"])
            df["z"] = df["distance_m"] * np.sin(df["elevation_rad"])

            if args.verbose:
                print(tabulate(df, headers="keys", tablefmt="psql"))

            pt = ax.scatter(df["x"], df["y"], df["z"], marker="x")

            last = len(df["x"]) - 1

            ax.scatter(df["x"][0], df["y"][0], df["z"][0], marker="o", color="green")
            ax.text(
                df["x"][0],
                df["y"][0],
                df["z"][0],
                ":".join([info_yaml["setup"]["sources"][src]["subtype"], info_yaml["setup"]["sources"][src]["info"]]),
                color=pt.get_facecolor()[0].tolist(),
            )

            ax.scatter(df["x"][last], df["y"][last], df["z"][last], marker="o", color="red")

            xx.append(min(df["x"]))
            xx.append(max(df["x"]))
            yy.append(min(df["y"]))
            yy.append(max(df["y"]))
            zz.append(min(df["z"]))
            zz.append(max(df["z"]))

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_xlim(min(-1, min(xx)), max(1, max(xx)))
    ax.set_ylim(min(-1, min(yy)), max(1, max(yy)))
    ax.set_zlim(min(-1, min(zz)), max(1, max(zz)))

    # Draw positive part of X-axis (from 0 to max)
    ax.plot([0, ax.get_xlim()[1]], [0, 0], [0, 0], color="blue", linewidth=1)
    ax.plot([0, 0], [0, ax.get_ylim()[1]], [0, 0], color="red", linewidth=1)
    ax.plot([0, 0], [0, 0], [0, ax.get_zlim()[1]], color="green", linewidth=1)

    ax.set_aspect("equal", adjustable="box")

    plt.show()
