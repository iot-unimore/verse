#!/usr/bin/env python3
"""Render dataset recipe"""

import os
import re
import sys
import yaml
import coloredlogs
import logging
import signal
import argparse
import sys
import glob
import shutil

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
_RESOURCES_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../", "resources")
_DATASET_DIR = os.path.join(os.path.abspath(os.path.dirname(__file__)), "../", "datasets")
_OUTPUT_DIR = _RESOURCES_DIR
_OUTPUT_REF_DIR = "/ref/"
_OUTPUT_TMP_DIR = "/tmp/"

_MIN_CPU_COUNT = 1  # we need at least one CPU for each compute process
_MIN_MEM_GB = 1  # min amount of memory for each compute process
_MAX_MEM_GB = 1  # max amount of memory for each compute process

#
# EXECUTABLES / EXTERNAL CMDs
#
_SCENE_RENDER_EXE = _ROOT_DIR + "/render_scene.py"


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


def readAllScenes(folder):
    files_yaml = glob.glob(folder + "/info/*.yaml")
    return files_yaml


def readResourceListFull(recipe_yaml, resource, set_idx, task_idx):
    resource_list = []

    if resource in recipe_yaml["sets"][set_idx]["tasks"][task_idx]:
        if recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource] is not None:
            for res_idx in recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource]:
                tmp_list = readResourceList(recipe_yaml, resource, set_idx, task_idx, res_idx)
                for item in tmp_list:
                    resource_list.append(item)
    return resource_list


def readResourceList(recipe_yaml, resource, set_idx, task_idx, res_idx):
    resource_list = []
    if ("subtype") not in recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]:
        logger.error("listed resource has no subtype")
    else:
        if recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"] is None:
            logger.error("listed resource has no subtype")
        else:
            if "all" == recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["info"][0]:
                tmp = os.path.join(
                    _RESOURCES_DIR,
                    resource,
                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                )
                info_list = glob.glob(os.path.abspath(tmp) + "/info/*.yaml")

                for info in info_list:
                    resource_list.append(
                        [recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"], info]
                    )
            else:
                if ("info" in recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]) and (
                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["info"] is not None
                ):
                    info_list = recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["info"]

                    for info in info_list:
                        # handle wildcard
                        if ("!" == info[0]) or ("*" in info) or ("?" in info):
                            # first build the whole list, then prune
                            tmp = os.path.join(
                                _RESOURCES_DIR,
                                resource,
                                recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                            )
                            item_list = glob.glob(os.path.abspath(tmp) + "/info/*.yaml")

                            rule = info

                            rule = rule.replace("!", "", 1)
                            rule = rule.replace("*", "(\w)*")
                            rule = rule.replace("?", "\w+")
                            # rule = rule.replace("_", "\_")

                            logger.log(logging.INFO, "filter rule: {} {}".format(info[0], rule))

                            filter_rule = re.compile(rule)

                            for item in item_list:
                                if "!" == info[0]:
                                    if not (filter_rule.match(os.path.split(item)[1])):
                                        resource_list.append(
                                            [
                                                recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx][
                                                    "subtype"
                                                ],
                                                item,
                                            ]
                                        )
                                else:
                                    if filter_rule.match(os.path.split(item)[1]):
                                        resource_list.append(
                                            [
                                                recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx][
                                                    "subtype"
                                                ],
                                                item,
                                            ]
                                        )

                        # no wildcard
                        else:
                            filename = ""
                            if info.endswith(".yaml"):
                                filename = os.path.join(
                                    _RESOURCES_DIR,
                                    str(resource),
                                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                                    "info",
                                    info,
                                )
                            else:
                                filename = os.path.join(
                                    _RESOURCES_DIR,
                                    str(resource),
                                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                                    "info",
                                    info + ".yaml",
                                )

                            # add resource only if info file is available
                            if os.path.isfile(filename):
                                # resource_list.append(
                                #     [recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"], info]
                                # )
                                resource_list.append(
                                    [
                                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                                        filename,
                                    ]
                                )
                else:
                    logger.error("listed source is empty.")

    return resource_list


def buildDataSetRecipe(data=None):
    err = 0

    recipe_custom_id = 0

    if data is not None:
        ds_idx = data["dataset_idx"]
        t_idx = data["task_idx"]
        s_idx = data["scene_idx"]

        recipe_output_folder = os.path.join(_OUTPUT_DIR, str(ds_idx))

        # check if we can copy the recipe "As is" or "custom"
        if (0 == len(data["voices_list"])) and (0 == len(data["heads_list"])) and (0 == len(data["rooms_list"])):
            #
            # AS-IS scene recipe
            #

            # we do not need to customize the recipe.
            # make the folder for it and save the recipe
            for scene in data["scenes_list"]:
                if (len(scene) == 2) and scene[1].endswith((".yaml")):
                    recipe_name = os.path.split(scene[1])[1][0:-5]
                    recipe_name = "_".join([recipe_name, str(t_idx), str(s_idx), str(recipe_custom_id)])

                    recipe_output_folder = os.path.join(_OUTPUT_DIR, str(ds_idx), str(recipe_name))

                    if not os.path.isdir(recipe_output_folder):
                        os.makedirs(recipe_output_folder)
                        logger.log(logging.DEBUG, "mkdir: {}", format(recipe_output_folder))

                    if not os.path.isdir(recipe_output_folder):
                        err = -1
                        logger.error("could not create recipe folder: {}".format(recipe_output_folder))

                    if err == 0:
                        # copy scene file
                        recipe_output_filename = os.path.join(recipe_output_folder, recipe_name + ".yaml")
                        # print(scene[1] + " -> " + os.path.join(recipe_output_filename))

                        shutil.copy(scene[1], recipe_output_filename)

                    recipe_custom_id += 1

        else:
            #
            # CUSTOMIZED scene recipe
            #
            for scene in data["scenes_list"]:
                if (len(scene) == 2) and scene[1].endswith((".yaml")):
                    # load scene
                    recipe_name = os.path.split(scene[1])[1][0:-5]
                    scene_yaml = readYamlFile(scene[1])

                    # check voices count in scene recipe
                    scene_sources_count = scene_yaml["setup"]["sources_count"]

                    #
                    # compute number of permutations due to customization (VOICES_MAX*HEAD_MAX*ROOM_MAX)
                    #

                    # compute max iteration on given voices
                    voices_iteration_count = 0
                    for voice in data["voices_list"]:
                        if len(voice) > voices_iteration_count:
                            voices_iteration_count = len(voice)

                    # compute max iteration on given heads
                    heads_iteration_count = len(data["heads_list"])

                    # compute max iteration on given rooms
                    rooms_iteration_count = len(data["rooms_list"])

                    scene_iteration_count = (
                        max(1, voices_iteration_count) * max(1, heads_iteration_count) * max(1, rooms_iteration_count)
                    )

                    #
                    # customizazion of the new scene
                    #
                    for it_idx in range(scene_iteration_count):
                        # retrieve original scene
                        custom_scene_yaml = readYamlFile(scene[1])

                        # customize voices
                        if voices_iteration_count > 0:
                            for vidx in custom_scene_yaml["setup"]["sources"]:
                                if vidx < len(data["voices_list"]):
                                    tmp_idx = it_idx % len(data["voices_list"][vidx])
                                    # set the subtype
                                    custom_scene_yaml["setup"]["sources"][vidx]["subtype"] = data["voices_list"][vidx][
                                        tmp_idx
                                    ][0]
                                    # set the info file (remove path and file extensions)
                                    custom_scene_yaml["setup"]["sources"][vidx]["info"] = os.path.split(
                                        data["voices_list"][vidx][tmp_idx][1]
                                    )[1][0:-5]

                        # customize heads
                        if heads_iteration_count > 0:
                            tmp_idx = it_idx % heads_iteration_count
                            custom_scene_yaml["setup"]["listeners_count"] = 1
                            # set the subtype
                            custom_scene_yaml["setup"]["listeners"][0] = {}
                            custom_scene_yaml["setup"]["listeners"][0]["type"] = "heads"
                            custom_scene_yaml["setup"]["listeners"][0]["subtype"] = data["heads_list"][tmp_idx][0]
                            # set the info file (remove path and file extensions)
                            custom_scene_yaml["setup"]["listeners"][0]["info"] = os.path.split(
                                data["heads_list"][tmp_idx][1]
                            )[1][0:-5]

                        # customize rooms
                        if rooms_iteration_count > 0:
                            tmp_idx = it_idx % rooms_iteration_count
                            custom_scene_yaml["setup"]["rooms_count"] = 1
                            # set the subtype
                            custom_scene_yaml["setup"]["rooms"][0] = {}
                            custom_scene_yaml["setup"]["rooms"][0]["type"] = "rooms"
                            custom_scene_yaml["setup"]["rooms"][0]["subtype"] = data["rooms_list"][tmp_idx][0]
                            # set the info file (remove path and file extensions)
                            custom_scene_yaml["setup"]["rooms"][0]["info"] = os.path.split(
                                data["rooms_list"][tmp_idx][1]
                            )[1][0:-5]

                        #
                        # save custom scene.yaml
                        #

                        # filenaming
                        recipe_name = os.path.split(scene[1])[1][0:-5]
                        recipe_name = "_".join([recipe_name, str(t_idx), str(s_idx), str(recipe_custom_id)])

                        recipe_output_folder = os.path.join(_OUTPUT_DIR, str(ds_idx), str(recipe_name))
                        if not os.path.isdir(recipe_output_folder):
                            os.makedirs(recipe_output_folder)
                            logger.log(logging.DEBUG, "mkdir: {}", format(recipe_output_folder))

                        if not os.path.isdir(recipe_output_folder):
                            err = -1
                            logger.error("could not create recipe folder: {}".format(recipe_output_folder))

                        # write custom scene yaml
                        if err == 0:
                            recipe_output_filename = os.path.join(recipe_output_folder, recipe_name + ".yaml")
                            with open(recipe_output_filename, "w") as file:
                                yaml.dump(custom_scene_yaml, file)

                        # increment custom index
                        recipe_custom_id += 1


def buildDataSetRecipes(cli_params=None, data=None):
    err = 0

    for item in data:
        logger.info("-" * 80)
        logger.info(yaml.dump(item))

    #
    # compute process pool size based on CPU/MEM requirements
    #
    mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
    mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74

    cpu_count = min([(os.cpu_count() - 2), cli_params["cpu_process"]])
    cpu_count = max([_MIN_CPU_COUNT, cpu_count])

    max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))

    logger.info("buildDataSetRecipes Pool size: {}".format(max_pool_size))
    cpu_pool = Pool(max_pool_size)

    result = cpu_pool.map(buildDataSetRecipe, data)

    cpu_pool.close()
    cpu_pool.join()


def soundSpatializeScene(data=None):
    if data is not None:
        output_dir = os.path.split(data)[0]
        logger.info("Dataset, Rendering Scene: " + str(output_dir))

        logfile = os.path.join(output_dir, "soundspatializer.log")

        # SYNTAX: ./render_scene.py -sf path/scene.yaml  -o path/out_folder/ -c 8 -v

        # scene_render: with logfile for debug, keep intermediate files
        # cmd = [_SCENE_RENDER_EXE, "-k", "-c", "8", "-sf", str(data), "-o", str(output_dir), "-v", "-log", str(logfile) ]

        # scene_render: no verbose, no logfile, keep intermediate files
        # cmd = [_SCENE_RENDER_EXE, "-k", "-c", "8", "-sf", str(data), "-o", str(output_dir)]

        # scene_render: no verbose, no logfile, no intermediate files
        cmd = [_SCENE_RENDER_EXE, "-c", "8", "-sf", str(data), "-o", str(output_dir)]

        # execute
        os.system(" ".join(cmd))


def soundSpatializeDataSet(cli_params=None):
    #
    # search for all available scene yaml files
    #

    tmp_yaml = glob.glob(_OUTPUT_DIR + "/**/*.yaml", recursive=True)

    scenes_yaml = []

    # cleanup from non valid .yaml files
    for scene in tmp_yaml:
        remove_flag = False
        # skip temporary files
        if "tmp" in scene:
            remove_flag = True
        else:
            # skip other types of yaml files
            tmp_yaml = readYamlFile(scene)
            if "syntax" not in tmp_yaml:
                remove_flag = True
            else:
                if tmp_yaml["syntax"]["name"] != "audio_rendering_scene":
                    remove_flag = True

        if remove_flag == False:
            scenes_yaml.append(scene)

    #
    # compute process pool size based on CPU/MEM requirements
    #
    mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
    mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74

    cpu_count = min([(os.cpu_count() - 2), cli_params["cpu_process"]])
    cpu_count = max([_MIN_CPU_COUNT, cpu_count])

    max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))

    logger.info("soundSpatializeDataSet Pool size: {}".format(max_pool_size))
    cpu_pool = Pool(max_pool_size)

    result = cpu_pool.map(soundSpatializeScene, scenes_yaml)

    cpu_pool.close()
    cpu_pool.join()


def renderDataSet(cli_params=None, recipe_yaml=None):
    err = 0

    workers_data = []

    if ("sets" not in recipe_yaml) or (recipe_yaml["sets"] is None):
        logger.error("invalid dataset syntax")
        return

    for dsidx in recipe_yaml["sets"]:
        if recipe_yaml["sets"][dsidx] is not None:
            if ("tasks" in recipe_yaml["sets"][dsidx]) and (recipe_yaml["sets"][dsidx]["tasks"] is not None):
                # set folder output
                tasks_output_folder = _OUTPUT_DIR + "/" + dsidx

                # print(tasks_output_folder)

                # scenes folder output
                # print(_OUTPUT_DIR + "/" + dsidx + "/scenes")

                # loop over Tasks
                for tidx in recipe_yaml["sets"][dsidx]["tasks"]:
                    # print("-----")
                    # print("TASK: " + str(tidx))
                    # print("-----")

                    # loop over Scenes
                    for sidx in recipe_yaml["sets"][dsidx]["tasks"][tidx]["scenes"]:
                        scenes_list = readResourceList(recipe_yaml, "scenes", dsidx, tidx, sidx)
                        # print("scenes: " + str(scenes_list))

                        # loop for Heads
                        heads_list = []
                        heads_list = readResourceListFull(recipe_yaml, "heads", dsidx, tidx)
                        # print("heads: " + str(heads_list))

                        # loop for Rooms
                        rooms_list = []
                        rooms_list = readResourceListFull(recipe_yaml, "rooms", dsidx, tidx)
                        # print("rooms: " + str(rooms_list))

                        # loop for Voices: this is different because in one scene there could
                        # be multiple voices and we replace them "in order"
                        voices_list = []
                        if recipe_yaml["sets"][dsidx]["tasks"][tidx]["voices"] is not None:
                            for vidx in recipe_yaml["sets"][dsidx]["tasks"][tidx]["voices"]:
                                tmp_list = readResourceList(recipe_yaml, "voices", dsidx, tidx, vidx)
                                voices_list.append(tmp_list)

                        # print("voices: " + str(voices_list))

                        # workers params: dataset_idx, task_idx, scene_idx, scenes, heads, rooms, voices
                        data = {}
                        data["dataset_idx"] = dsidx
                        data["task_idx"] = tidx
                        data["scene_idx"] = sidx
                        data["scenes_list"] = scenes_list
                        data["heads_list"] = heads_list
                        data["rooms_list"] = rooms_list
                        data["voices_list"] = voices_list

                        workers_data.append(data)

    # we got all the work listed, now spawn multi-process to create all the scene files
    # inside the dataset folder [DATASET]/scenes

    if (err == 0) and (len(workers_data)):
        buildDataSetRecipes(cli_params, workers_data)

        soundSpatializeDataSet(cli_params)


#
###############################################################################
# MAIN
###############################################################################
#

if __name__ == "__main__":
    # install CTRL-C handles
    signal.signal(signal.SIGINT, signal_handler)

    # set user friendly process name for MAIN
    setproctitle("verse_dataset_render")

    # parse input params
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i",
        "--input_file",
        type=str,
        default=None,
        help="dataset recipe to render (default: %(default)s)",
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
        logger.error("audio scene file is needed.")
        exit(1)
    else:
        if not (os.path.isfile(cli_params["input_file"])):
            logger.error("dataset recipe file {} does not exists.".format(cli_params["input_file"]))
            exit(1)

    #
    # read recipe
    #
    recipe_yaml = readYamlFile(cli_params["input_file"])

    # sanity check
    if len(recipe_yaml) == 0:
        logger.error("missing yaml filename")
        exit(1)
    if not ("syntax" in recipe_yaml):
        logger.error("invalid recipe syntax")
        exit(1)
    if not ("name" in recipe_yaml["syntax"]):
        logger.error("invalid recipe syntax")
        exit(1)
    if recipe_yaml["syntax"]["name"] != "ds_recipe":
        logger.error("invalid recipe syntax")
        exit(1)

    #
    # name is mandatory
    if not ("name" in recipe_yaml):
        logger.error("missing name in recipe syntax")
        exit(1)

    #
    # overwrite output folder name
    if not (cli_params["output_folder"] == None):
        _OUTPUT_DIR = os.path.abspath(cli_params["output_folder"])
    else:
        if "output" in recipe_yaml:
            if "path" in recipe_yaml["output"]:
                _OUTPUT_DIR = os.path.join(_DATASET_DIR, "../", recipe_yaml["output"]["path"])
            else:
                _OUTPUT_DIR = os.path.join(_DATASET_DIR, recipe_yaml["name"])
        else:
            _OUTPUT_DIR = os.path.join(_DATASET_DIR, recipe_yaml["name"])

    logger.info("dataset output folder: {}".format(_OUTPUT_DIR))

    #
    # check for output folder presence
    if not os.path.isdir(_OUTPUT_DIR):
        logger.info("missing output folder, will create one. {}".format(_OUTPUT_DIR))

        os.makedirs(_OUTPUT_DIR)
        if not os.path.isdir(_OUTPUT_DIR):
            log.error("cannot create output folder. exit")

    renderDataSet(cli_params, recipe_yaml)

    # cleanup, restore termina & exit
    os.system("tset")
