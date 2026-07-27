#!/usr/bin/env python3
"""
Render a full dataset from a "dataset recipe" .yaml (typically under
resources/ds_recipes/*/info/), by expanding it into many individual scene
files and rendering each one via render_scene.py.

A recipe (-i/--input_file) declares one or more "sets", each with "tasks"
that list which scenes to use and, optionally, which voices/heads/rooms/
pre-postproc resources to substitute into them -- with wildcard ("*", "?",
"!") and "all" selectors resolved via readResourceList(). This script does
not spatialize audio itself; it is the orchestration layer over the
leaf-level renderer (render_scene.py), which is spawned as a subprocess
once per generated scene.

Pipeline (see renderDataSet):
  1. Walk every set/task/scene in the recipe and resolve its scenes/heads/
     rooms/voices/preproc/postproc resource lists into one work item per
     (dataset, task, scene) unit.
  2. buildDataSetRecipes(): in a CPU/MEM-sized process pool, expand each
     work item into concrete scene .yaml file(s) under the dataset output
     folder -- either copied "as-is" (only the audio format is overridden)
     or, if voices/heads/rooms customization was requested, once per
     permutation of the given resource lists (buildDataSetRecipe).
  3. soundSpatializeDataSet(): find every generated scene .yaml and render
     each one in a second CPU/MEM-sized process pool by spawning
     render_scene.py as a subprocess (soundSpatializeScene), producing the
     spatialized MKV output for that scene.

Logging/progress: -v/-vv/-vvv, -q/--quiet and -s/--silent control this
script's own console output and its tqdm progress bar (shouldShowProgress);
the same effective verbosity is propagated down to every render_scene.py
subprocess (renderSceneLoggingArgs) so parallel workers don't corrupt the
progress bar or violate quiet/silent mode.

--dry-run: skips both pipeline phases (buildDataSetRecipes/
soundSpatializeDataSet) entirely -- no folder or scene file is ever created,
not even the top-level dataset output folder. Instead, computeWorkItemPlan()
recomputes, for every (set, task) group, how many scene recipes would have
been generated (mirroring buildDataSetRecipe()'s own naming/permutation
logic exactly, without writing anything), and reportDryRun() prints one
summary table per set (task -> scene count) via tabulate. At -v (INFO) or
above, the full list of recipe names that would be rendered under each task
is also logged.
"""

import os
import re
import yaml
import logging
import signal
import argparse
import glob

from multiprocessing import Pool
from setproctitle import setproctitle
from functools import partial
from tqdm import tqdm
from datetime import datetime
from tabulate import tabulate


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
    terminal output (progress bar aside, see shouldShowProgress()) but the
    optional -log FILE still records at the verbose-derived level, so a quiet
    run can still capture full detail for later inspection.
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


def shouldShowProgress(cli_params):
    """-s/--silent always wins (no output at all). -q/--quiet forces the
    progress bar on regardless of -v. Otherwise the progress bar only shows
    in the default (no -v) case, since it doesn't mix well with scrolling
    log lines.
    """
    if cli_params["silent"]:
        return False
    if cli_params["quiet"]:
        return True
    return cli_params["verbose"] == 0


def renderSceneLoggingArgs(cli_params):
    """Build the logging-related CLI flags to pass down to each render_scene.py
    subprocess, so the whole (potentially large) pool of parallel per-scene
    processes behaves consistently with how render_dataset.py itself was invoked.

    This is not a literal mirror of render_dataset's own flags, and it is NOT
    simply "whenever shouldShowProgress() is True" -- that function answers a
    different question (does the parent draw a progress bar?) and, notably,
    returns False when silent=True, since a silent run shows no progress bar
    either. Here we need the opposite: silent/quiet must force children
    silent too. So: whenever render_dataset is silent, quiet, or in its
    default (no -v) mode -- i.e. whenever the console isn't showing explicit
    detail -- every child is forced fully silent (-s), otherwise per-scene
    WARNING/ERROR output from dozens of parallel workers would corrupt the
    progress bar or violate quiet/silent mode. Only when the user explicitly
    asked for detail (-v/-vv/-vvv, with neither -q nor -s) do children mirror
    that same verbosity level.
    """
    if cli_params["silent"] or cli_params["quiet"] or cli_params["verbose"] == 0:
        return ["-s"]

    return ["-" + "v" * cli_params["verbose"]]


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

#
# EXECUTABLES / EXTERNAL CMDs
#
_SCENE_RENDER_EXE = _ROOT_DIR + "/render_scene.py"


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


def generate_dataset_info(output_path, recipe_yaml, origin, info_file="info.yaml"):
    """(Over)write info.yaml inside the dataset output folder for this run,
    recording the recipe this run started from, the recipe file's original
    path (origin) and a timestamp. Kept as its own function (rather than
    inlined in main()) so more per-run info can be added here later. Any
    previous info.yaml content is discarded -- this file always reflects
    only the most recent run."""
    info_path = os.path.join(output_path, info_file)

    info = {
        "syntax": {"name": "dataset_info", "version": {"major": 0, "minor": 1, "revision": 0}},
        "timestamp": datetime.now().strftime("%Y%m%d%H%M%S"),
        "origin": origin,
        "recipe": recipe_yaml,
    }

    try:
        with open(info_path, "w") as file:
            yaml.dump(info, file, sort_keys=False)
    except OSError:
        logger.error("cannot write dataset info file: {}".format(info_path))
        return -1

    return 0


def readAllScenes(folder):
    """Return the list of scene .yaml file paths under folder/info/."""
    files_yaml = glob.glob(folder + "/info/*.yaml")
    return files_yaml


def readResourceListFull(recipe_yaml, resource, set_idx, task_idx):
    """Resolve every entry listed under a task's `resource` key (e.g.
    "heads", "rooms", "preproc", "postproc") into a flat list of
    [subtype, info_file_path] pairs, via readResourceList() per entry."""
    resource_list = []

    if resource in recipe_yaml["sets"][set_idx]["tasks"][task_idx]:
        if recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource] is not None:
            for res_idx in recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource]:
                tmp_list = readResourceList(recipe_yaml, resource, set_idx, task_idx, res_idx)
                for item in tmp_list:
                    resource_list.append(item)

    return resource_list


def readResourceList(recipe_yaml, resource, set_idx, task_idx, res_idx):
    """Resolve one `resource` entry
    (recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]) into
    a list of [subtype, info_file_path] pairs. Supports three "info" forms:
    "all" (every .yaml under that resource/subtype's info/ folder), a
    wildcard rule ("*"/"?" glob-like match, or a leading "!" to negate it),
    or an explicit list of filenames (with or without ".yaml"). Used to
    expand a dataset recipe task into the concrete resource files to render.
    """
    resource_list = []
    if ("subtype") not in recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]:
        logger.error("listed resource has no subtype")
    else:
        if recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"] is None:
            logger.error("listed resource has no subtype")
        else:
            if "all" == recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["info"][0]:
                if resource == "postproc" or resource == "preproc":
                    tmp = os.path.join(
                        _RESOURCES_DIR,
                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["type"],
                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                    )
                else:
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
                            if resource == "postproc" or resource == "preproc":
                                tmp = os.path.join(
                                    _RESOURCES_DIR,
                                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["type"],
                                    recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                                )
                            else:
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

                            logger.debug("filter rule: {} {}".format(info[0], rule))

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
                                if resource == "postproc" or resource == "preproc":
                                    filename = os.path.join(
                                        _RESOURCES_DIR,
                                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["type"],
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
                                        info,
                                    )
                            else:
                                if resource == "postproc" or resource == "preproc":
                                    filename = os.path.join(
                                        _RESOURCES_DIR,
                                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["type"],
                                        recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["subtype"],
                                        "info",
                                        info + ".yaml",
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
                                if resource == "preproc" or resource == "postproc":
                                    resource_list.append(
                                        [
                                            recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx]["type"]
                                            + "/"
                                            + recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx][
                                                "subtype"
                                            ],
                                            filename,
                                        ]
                                    )
                                else:
                                    resource_list.append(
                                        [
                                            recipe_yaml["sets"][set_idx]["tasks"][task_idx][resource][res_idx][
                                                "subtype"
                                            ],
                                            filename,
                                        ]
                                    )
                else:
                    logger.error("listed source is empty.")

    return resource_list


def buildDataSetRecipe(data=None):
    """
    Worker function (run in a process pool by buildDataSetRecipes()): for one
    (dataset, task, scene) unit of work, writes the concrete per-recipe scene
    .yaml file(s) under the dataset output folder. If no voices/heads/rooms
    customization was requested, copies each scene "as-is" (only overriding
    the dataset's audio output format). Otherwise generates one customized
    scene per permutation of voices/heads/rooms/postproc, cycling through
    the provided resource lists.
    """
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
                        logger.debug("mkdir: {}".format(recipe_output_folder))

                    if not os.path.isdir(recipe_output_folder):
                        err = -1
                        logger.error("could not create recipe folder: {}".format(recipe_output_folder))

                    if err == 0:
                        # copy scene file but override dataset parameters if needed

                        recipe_output_filename = os.path.join(recipe_output_folder, recipe_name + ".yaml")

                        custom_scene_yaml = readYamlFile(scene[1])

                        #
                        # dataset audio output format has priority on scene audio output format
                        #

                        # type (WAV)
                        if custom_scene_yaml["setup"]["format"]["type"] != data["formats_dict"]["type"]:
                            custom_scene_yaml["setup"]["format"]["type"] = data["formats_dict"]["type"]
                        # subtype (pcm_s16le, pcm_s24le)
                        if custom_scene_yaml["setup"]["format"]["subtype"] != data["formats_dict"]["subtype"]:
                            custom_scene_yaml["setup"]["format"]["subtype"] = data["formats_dict"]["subtype"]
                        # samplerate (Hz)
                        if custom_scene_yaml["setup"]["format"]["samplerate"] != data["formats_dict"]["samplerate"]:
                            custom_scene_yaml["setup"]["format"]["samplerate"] = data["formats_dict"]["samplerate"]

                        # write custom scene yaml
                        with open(recipe_output_filename, "w") as file:
                            yaml.dump(custom_scene_yaml, file)

                    recipe_custom_id += 1

        else:
            #
            # CUSTOMIZED scene recipe
            #
            for scene in data["scenes_list"]:
                if (len(scene) == 2) and scene[1].endswith((".yaml")):
                    # load scene
                    recipe_name = os.path.split(scene[1])[1][0:-5]

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

                    # compute max iteration on given rooms
                    preprocessing_iteration_count = len(data["preproc_list"])

                    # compute max iteration on given rooms
                    postprocessing_iteration_count = len(data["postproc_list"])

                    scene_iteration_count = (
                        max(1, voices_iteration_count) * max(1, heads_iteration_count) * max(1, rooms_iteration_count)
                    )

                    #
                    # customizazion of the new scene
                    #
                    for it_idx in range(scene_iteration_count):
                        # retrieve original scene
                        custom_scene_yaml = readYamlFile(scene[1])

                        #
                        # dataset audio output format has priority on scene audio output format
                        #

                        # type (WAV)
                        if custom_scene_yaml["setup"]["format"]["type"] != data["formats_dict"]["type"]:
                            custom_scene_yaml["setup"]["format"]["type"] = data["formats_dict"]["type"]
                        # subtype (pcm_s16le, pcm_s24le)
                        if custom_scene_yaml["setup"]["format"]["subtype"] != data["formats_dict"]["subtype"]:
                            custom_scene_yaml["setup"]["format"]["subtype"] = data["formats_dict"]["subtype"]
                        # samplerate (Hz)
                        if custom_scene_yaml["setup"]["format"]["samplerate"] != data["formats_dict"]["samplerate"]:
                            custom_scene_yaml["setup"]["format"]["samplerate"] = data["formats_dict"]["samplerate"]

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
                            # if heads_iteration_count > 1:
                            #     logger.error("there must be only one listener/head for each scene")
                            tmp_idx = it_idx % heads_iteration_count

                            head_position_bkp = {}
                            head_position_bkp = custom_scene_yaml["setup"]["listeners"][0]["position"]

                            custom_scene_yaml["setup"]["listeners_count"] = 1
                            # set the subtype
                            custom_scene_yaml["setup"]["listeners"][0] = {}
                            custom_scene_yaml["setup"]["listeners"][0]["position"] = head_position_bkp
                            custom_scene_yaml["setup"]["listeners"][0]["type"] = "heads"
                            custom_scene_yaml["setup"]["listeners"][0]["subtype"] = data["heads_list"][tmp_idx][0]
                            # set the info file (remove path and file extensions)
                            custom_scene_yaml["setup"]["listeners"][0]["info"] = os.path.split(
                                data["heads_list"][tmp_idx][1]
                            )[1][0:-5]

                            # check that each head has a position
                            try:
                                if "static" == custom_scene_yaml["setup"]["listeners"][0]["position"]["type"]:
                                    _ = custom_scene_yaml["setup"]["listeners"][0]["position"]["coord"]["value"]
                                elif "dynamic" == custom_scene_yaml["setup"]["listeners"][0]["position"]["type"]:
                                    _ = custom_scene_yaml["setup"]["listeners"][0]["position"]["value"]["info"]
                                else:
                                    logger.error("listener invalid position type")
                                    err = -1
                            except:
                                logger.error("listener invalid position syntax")
                                err = -1

                        # customize rooms
                        if rooms_iteration_count > 0:
                            if rooms_iteration_count > 1:
                                logger.error("there must be only one room (max) for each scene")
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

                        # customize preprocessing
                        if preprocessing_iteration_count > 0:
                            logger.error("pre-processing not yet implemented")

                        # customize postprocessing
                        if postprocessing_iteration_count > 0:
                            # if postprocessing_iteration_count > 1:
                            #     logger.error("posproc: there must be only one listener/head for each scene ")
                            custom_scene_yaml["postproc"] = {}
                            custom_scene_yaml["postproc"][0] = {}
                            custom_scene_yaml["postproc"][0]["type"] = data["postproc_list"][0][0].split("/")[0]
                            custom_scene_yaml["postproc"][0]["subtype"] = data["postproc_list"][0][0].split("/")[1]
                            custom_scene_yaml["postproc"][0]["info"] = str(
                                data["postproc_list"][0][1].split("/")[-1]
                            ).split(".")[0]

                        #
                        # save custom scene.yaml
                        #

                        # filenaming
                        recipe_name = os.path.split(scene[1])[1][0:-5]
                        recipe_name = "_".join([recipe_name, str(t_idx), str(s_idx), str(recipe_custom_id)])

                        recipe_output_folder = os.path.join(_OUTPUT_DIR, str(ds_idx), str(recipe_name))
                        if not os.path.isdir(recipe_output_folder):
                            os.makedirs(recipe_output_folder)
                            logger.debug("mkdir: {}".format(recipe_output_folder))

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


def computeWorkItemPlan(data):
    """Compute, for one work item (as built by renderDataSet()'s main loop),
    the list of recipe names that buildDataSetRecipe() would generate and
    write to disk -- without touching the filesystem. Mirrors that
    function's naming/permutation logic exactly: each scene in
    data["scenes_list"] contributes one recipe per permutation of the given
    voices/heads/rooms resource lists (1 permutation when none of them are
    customized, i.e. the "AS-IS" case), and recipe names follow the same
    "{scene}_{task_idx}_{scene_idx}_{recipe_custom_id}" scheme.
    """
    voices_iteration_count = max((len(v) for v in data["voices_list"]), default=0)
    heads_iteration_count = len(data["heads_list"])
    rooms_iteration_count = len(data["rooms_list"])

    scene_iteration_count = (
        max(1, voices_iteration_count) * max(1, heads_iteration_count) * max(1, rooms_iteration_count)
    )

    names = []
    recipe_custom_id = 0
    for scene in data["scenes_list"]:
        if (len(scene) == 2) and scene[1].endswith(".yaml"):
            base_name = os.path.split(scene[1])[1][0:-5]
            for _ in range(scene_iteration_count):
                recipe_name = "_".join(
                    [base_name, str(data["task_idx"]), str(data["scene_idx"]), str(recipe_custom_id)]
                )
                names.append(recipe_name)
                recipe_custom_id += 1

    return names


def computeExpectedScenePaths(workers_data):
    """Compute the exact absolute paths of every scene .yaml that
    buildDataSetRecipes() is about to write for this run, by combining each
    work item's (dataset_idx, recipe_name) from computeWorkItemPlan() with
    the same output-folder layout buildDataSetRecipe() writes to
    (_OUTPUT_DIR/<dataset_idx>/<recipe_name>/<recipe_name>.yaml). Used by
    soundSpatializeDataSet() to tell this run's own scenes apart from
    unrelated leftover scene files it might otherwise pick up under
    _OUTPUT_DIR."""
    expected = set()
    for data in workers_data:
        ds_idx = data["dataset_idx"]
        for recipe_name in computeWorkItemPlan(data):
            expected.add(os.path.abspath(os.path.join(_OUTPUT_DIR, str(ds_idx), recipe_name, recipe_name + ".yaml")))
    return expected


def taskLabel(task_idx, task_name):
    """Return the display label for a task in dry-run reporting: the task's
    "name" field (recipe syntax 0.2.1+) when available, falling back to its
    plain task_idx for older recipes that don't have one."""
    return task_name if task_name else task_idx


def reportDryRun(cli_params, recipe_yaml, workers_data):
    """--dry-run reporting: group `workers_data` by (set, task), compute how
    many scene recipes each group would generate via computeWorkItemPlan()
    (no file/folder is written), and print one summary table per set using
    tabulate. Tasks are labeled by their "name" field when the recipe
    provides one (syntax 0.2.1+, see taskLabel()), otherwise by their plain
    task_idx. Each row shows both "Recipe Scenes" (the raw scene count
    listed under the task's "scenes" key in the recipe file) and "Render
    Scenes" (the actual number of scene recipes that will be rendered, i.e.
    "Recipe Scenes" multiplied by however many voices/heads/rooms
    permutations the task's customization produces) and "Ratio" (Render
    Scenes / Recipe Scenes, to 1 decimal place) so it's easy to see how many
    variations a task's voice/head/room combinations generate. After the
    grand total, also prints one line breaking down what percentage of all
    rendered scenes falls in each set (1 decimal place), e.g.
    "train (60.0%), validate (20.0%), test (20.0%)". At INFO verbosity (-v)
    or above, also logs the full list of recipe names that would be
    rendered under each task.
    """
    sets_order = []
    tasks_by_set = {}
    names_by_set_task = {}
    task_names = {}
    recipe_scene_counts = {}

    for data in workers_data:
        ds_idx = data["dataset_idx"]
        t_idx = data["task_idx"]

        if ds_idx not in tasks_by_set:
            tasks_by_set[ds_idx] = []
            sets_order.append(ds_idx)
        if t_idx not in tasks_by_set[ds_idx]:
            tasks_by_set[ds_idx].append(t_idx)

        key = (ds_idx, t_idx)
        task_names[key] = data.get("task_name")
        recipe_scene_counts[key] = recipe_scene_counts.get(key, 0) + len(data["scenes_list"])
        names_by_set_task.setdefault(key, []).extend(computeWorkItemPlan(data))

    print("")
    print("DRY RUN -- recipe: {}".format(recipe_yaml.get("name")))
    print("no scene file or output folder will be created")
    print("")

    grand_total = 0
    set_totals = {}

    for ds_idx in sets_order:
        rows = []
        set_total = 0
        for t_idx in tasks_by_set[ds_idx]:
            key = (ds_idx, t_idx)
            count = len(names_by_set_task[key])
            recipe_count = recipe_scene_counts[key]
            ratio = count / recipe_count if recipe_count else 0.0
            rows.append([taskLabel(t_idx, task_names[key]), recipe_count, count, ratio])
            set_total += count

        print("Set: {}".format(ds_idx))
        print(
            tabulate(
                rows, headers=["Task", "Recipe Scenes", "Render Scenes", "Ratio"], tablefmt="psql", floatfmt=".1f"
            )
        )
        print("Set {} total: {} scene(s)".format(ds_idx, set_total))
        print("")

        if cli_params["verbose"] >= 1:
            for t_idx in tasks_by_set[ds_idx]:
                names = names_by_set_task[(ds_idx, t_idx)]
                label = taskLabel(t_idx, task_names[(ds_idx, t_idx)])
                logger.info("Set {} / Task {}: {} scene(s) to render:".format(ds_idx, label, len(names)))
                for name in names:
                    logger.info("  - {}/{}".format(ds_idx, name))

        set_totals[ds_idx] = set_total
        grand_total += set_total

    print("TOTAL: {} scene(s) across {} set(s)".format(grand_total, len(sets_order)))

    if grand_total:
        breakdown = ", ".join(
            "{} ({:.1f}%)".format(ds_idx, 100.0 * set_totals[ds_idx] / grand_total) for ds_idx in sets_order
        )
        print(breakdown)
    print("")


def buildDataSetRecipes(cli_params=None, data=None):
    """Run buildDataSetRecipe() over every work item in `data` (one dict per
    dataset/task/scene unit) using a CPU/MEM-sized process pool, writing out
    every dataset recipe's concrete scene .yaml file(s) to disk. Shows a
    progress bar when shouldShowProgress(cli_params) is True."""
    for item in data:
        logger.debug("-" * 80)
        logger.debug(yaml.dump(item))

    #
    # compute process pool size based on CPU/MEM requirements
    #
    mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
    mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74

    cpu_count = min([(os.cpu_count() - 2), cli_params["cpu_process"]])
    cpu_count = max([_MIN_CPU_COUNT, cpu_count])

    max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))

    logger.debug("buildDataSetRecipes Pool size: {}".format(max_pool_size))
    cpu_pool = Pool(max_pool_size)

    iterator = cpu_pool.imap_unordered(buildDataSetRecipe, data)

    if shouldShowProgress(cli_params):
        iterator = tqdm(iterator, total=len(data), desc="buildDataSetRecipes")

    for _ in iterator:
        if _CTRL_EXIT_SIGNAL:
            break

    if _CTRL_EXIT_SIGNAL:
        cpu_pool.terminate()
    else:
        cpu_pool.close()
    cpu_pool.join()


def soundSpatializeScene(data=None, cli_params=None):
    """Worker function (run in a process pool by soundSpatializeDataSet()):
    renders one scene .yaml (`data`) by spawning render_scene.py as a
    subprocess, with logging flags matched to the parent's own verbosity via
    renderSceneLoggingArgs() so per-scene output stays consistent across the
    whole (potentially large) parallel pool."""
    if data is not None:
        output_dir = os.path.split(data)[0]
        logger.info("Dataset, Rendering Scene: " + str(output_dir))

        # SYNTAX: ./render_scene.py -sf path/scene.yaml  -o path/out_folder/ -c 8 -v

        # scene_render: with logfile for debug, keep intermediate files
        # cmd = [_SCENE_RENDER_EXE, "-k", "-c", "8", "-sf", str(data), "-o", str(output_dir), "-v", "-log", str(logfile) ]

        # scene_render: no verbose, no logfile, keep intermediate files
        # cmd = [_SCENE_RENDER_EXE, "-k", "-c", "8", "-sf", str(data), "-o", str(output_dir)]

        # scene_render: no logfile, no intermediate files, logging level/silence
        # matched to the parent render_dataset.py invocation (see renderSceneLoggingArgs)
        cmd = [_SCENE_RENDER_EXE, "-c", "8", "-sf", str(data), "-o", str(output_dir)]
        cmd += renderSceneLoggingArgs(cli_params)

        # execute
        os.system(" ".join(cmd))


def soundSpatializeDataSet(cli_params=None, expected_scenes=None):
    """Find every rendered dataset scene .yaml under _OUTPUT_DIR (filtering
    out tmp files and any .yaml that isn't an "audio_rendering_scene"), then
    render each one via soundSpatializeScene() in a CPU/MEM-sized process
    pool, with an optional progress bar (shouldShowProgress()).

    _OUTPUT_DIR is searched recursively, so if it's a shared parent folder
    that already holds other datasets (e.g. -o pointed at the common
    "datasets/" folder instead of a recipe-specific subfolder), or leftover
    scene files from a previous interrupted run, this search would otherwise
    pick those up too and render them alongside this run's own output.
    `expected_scenes`, when given (see computeExpectedScenePaths(), called
    from renderDataSet() before this function), is the exact set of scene
    paths this run's buildDataSetRecipes() just generated: anything found
    here that isn't in that set is logged as a warning and skipped rather
    than silently rendered.
    """
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

    if expected_scenes is not None:
        unrelated = [scene for scene in scenes_yaml if os.path.abspath(scene) not in expected_scenes]
        if unrelated:
            logger.warning(
                "found {} scene file(s) under the output folder that were NOT generated by this "
                "run (leftover from another dataset or a previous run sharing the same output "
                "folder) -- skipping them:".format(len(unrelated))
            )
            for scene in unrelated:
                logger.warning("  - {}".format(scene))
        scenes_yaml = [scene for scene in scenes_yaml if os.path.abspath(scene) in expected_scenes]

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

    iterator = cpu_pool.imap_unordered(partial(soundSpatializeScene, cli_params=cli_params), scenes_yaml)

    if shouldShowProgress(cli_params):
        iterator = tqdm(iterator, total=len(scenes_yaml), desc="soundSpatializeDataSet")

    for _ in iterator:
        if _CTRL_EXIT_SIGNAL:
            break

    if _CTRL_EXIT_SIGNAL:
        cpu_pool.terminate()
    else:
        cpu_pool.close()
    cpu_pool.join()


def renderDataSet(cli_params=None, recipe_yaml=None):
    """
    Top-level dataset build (called from __main__): for every set/task/scene
    in the recipe, resolves the scenes/heads/rooms/voices/preproc/postproc
    resource lists and collects one work item per unit into workers_data.
    Then runs the two-phase pipeline: buildDataSetRecipes() (write out the
    concrete per-recipe scene files) followed by soundSpatializeDataSet()
    (render each one via sspat).
    """
    workers_data = []

    if ("sets" not in recipe_yaml) or (recipe_yaml["sets"] is None):
        logger.error("invalid dataset syntax")
        return

    for dsidx in recipe_yaml["sets"]:
        if recipe_yaml["sets"][dsidx] is not None:
            if ("tasks" in recipe_yaml["sets"][dsidx]) and (recipe_yaml["sets"][dsidx]["tasks"] is not None):
                # loop over Tasks
                for tidx in recipe_yaml["sets"][dsidx]["tasks"]:
                    # loop over Scenes
                    for sidx in recipe_yaml["sets"][dsidx]["tasks"][tidx]["scenes"]:
                        scenes_list = readResourceList(recipe_yaml, "scenes", dsidx, tidx, sidx)

                        # loop for Heads
                        heads_list = []
                        heads_list = readResourceListFull(recipe_yaml, "heads", dsidx, tidx)

                        # loop for Rooms
                        rooms_list = []
                        rooms_list = readResourceListFull(recipe_yaml, "rooms", dsidx, tidx)

                        # loop for Voices: this is different because in one scene there could
                        # be multiple voices and we replace them "in order"
                        voices_list = []
                        if recipe_yaml["sets"][dsidx]["tasks"][tidx]["voices"] is not None:
                            for vidx in recipe_yaml["sets"][dsidx]["tasks"][tidx]["voices"]:
                                tmp_list = readResourceList(recipe_yaml, "voices", dsidx, tidx, vidx)
                                voices_list.append(tmp_list)

                        # loop for task pre-processing
                        preproc_list = []
                        preproc_list = readResourceListFull(recipe_yaml, "preproc", dsidx, tidx)

                        # loop for task post-processing
                        postproc_list = []
                        postproc_list = readResourceListFull(recipe_yaml, "postproc", dsidx, tidx)

                        # dataset format info
                        format_dict = {}
                        format_dict = recipe_yaml["output"]["audio"]["format"]

                        # workers params: dataset_idx, task_idx, scene_idx, scenes, heads, rooms, voices
                        data = {}
                        data["dataset_idx"] = dsidx
                        data["task_idx"] = tidx
                        # "name" is only present from ds_recipe syntax 0.2.1 onward; older recipes
                        # leave this None, and reportDryRun() falls back to task_idx for them.
                        data["task_name"] = recipe_yaml["sets"][dsidx]["tasks"][tidx].get("name")
                        data["scene_idx"] = sidx
                        data["scenes_list"] = scenes_list
                        data["heads_list"] = heads_list
                        data["rooms_list"] = rooms_list
                        data["voices_list"] = voices_list
                        data["formats_dict"] = format_dict
                        data["preproc_list"] = preproc_list
                        data["postproc_list"] = postproc_list

                        workers_data.append(data)

    if cli_params["dry_run"]:
        reportDryRun(cli_params, recipe_yaml, workers_data)
        return

    # we got all the work listed, now spawn multi-process to create all the scene files
    # inside the dataset folder [DATASET]/scenes

    if len(workers_data):
        buildDataSetRecipes(cli_params, workers_data)

        if _CTRL_EXIT_SIGNAL:
            logger.warning("Ctrl+C detected, aborting before rendering phase")
            return

        expected_scenes = computeExpectedScenePaths(workers_data)
        soundSpatializeDataSet(cli_params, expected_scenes)


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
        action="count",
        default=0,
        help="verbose, repeat for more detail: -v=INFO, -vv=DEBUG, -vvv=DEBUG+source location (default: WARNING)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="suppress all console log output regardless of -v; show only the progress bar. "
        "Takes precedence over -v/-vv/-vvv (default: %(default)s)",
    )
    parser.add_argument(
        "-s",
        "--silent",
        action="store_true",
        default=False,
        help="suppress all console output, including the progress bar. "
        "Takes precedence over -q and -v/-vv/-vvv (default: %(default)s)",
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
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="compute and print, per set/task, how many scenes would be rendered, without creating "
        "any file or folder (not even the output folder). Combine with -v to also list every scene "
        "that would be rendered (default: %(default)s)",
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
    if cli_params["input_file"] == None:
        logger.error("dataset recipe file is needed.")
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
        if cli_params["dry_run"]:
            logger.info("dry-run: output folder does not exist yet, would create: {}".format(_OUTPUT_DIR))
        else:
            logger.info("missing output folder, will create one. {}".format(_OUTPUT_DIR))

            os.makedirs(_OUTPUT_DIR)
            if not os.path.isdir(_OUTPUT_DIR):
                logger.error("cannot create output folder. exit")

    if not cli_params["dry_run"]:
        generate_dataset_info(_OUTPUT_DIR, recipe_yaml, os.path.abspath(cli_params["input_file"]))

    renderDataSet(cli_params, recipe_yaml)

    # cleanup, restore termina & exit
    os.system("tset")
