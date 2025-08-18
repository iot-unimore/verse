#!/usr/bin/env python3
"""mux a multi-track wav file into the equivalent Matroska container"""

import os
import re
import sys
import argparse
import datetime
import yaml

import numpy as np
import queue
import logging
import tempfile
import json
import subprocess
import shutil

import seaborn as sns 
import pandas as pd
import matplotlib.pylab as plt

import multiprocessing as mp
from multiprocessing import current_process, Pool
from setproctitle import setproctitle
from subprocess import check_output



logger = logging.getLogger(__name__)



#
# DEFINES / CONSTANT / GLOBALS
#
_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
_VERSE_DIR=os.path.join(_ROOT_DIR, "../../")

#
# EXECUTABLES / EXTERNAL CMDs
#
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_FFPROBE_EXE = "/usr/bin/ffprobe"
_APLAY_EXE = "/usr/bin/aplay"

#
# HW RESOURCES
#
_MIN_CPU_COUNT = 1  # we need at least one CPU for each compute process
_MAX_CPU_COUNT = 16  # this script is not optimized, keep a top limit
_MIN_MEM_GB = 1  # min amount of memory for each compute process
_MAX_MEM_GB = 2.5  # max amount of memory for each compute process


# Auralys Audio Recordings
_AURALYS_AUDIO_FOLDER= "/media/gfilippi/bigdata_01/auralys_measures/wilsonAudio_20250818_001/"
_AURALYS_AUDIO_SUBFOLDER="wilsonAudio_"

_VERSE_TYPE="voice"
_VERSE_SUBTYPE="unimore"
_VERSE_INFO="000007"

# _AURALYS_AZIMUTH=np.arange(-90,100,10)
# _AURALYS_ELEVATION=[-45,-30,-15,0,15,30,45]
# _AURALYS_DISTANCE=[1]

_AURALYS_AZIMUTH=np.arange(-60,70,10)
_AURALYS_ELEVATION=[-45,-30,-15,0,15,30,45]
_AURALYS_DISTANCE=[1]


########################################################################################################################
#  DO NOT MODIFY CODE BELOW THIS LINE
########################################################################################################################

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def restore_terminal():
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, termios.tcgetattr(sys.stdin.fileno()))
    except:
        pass
    os.system("stty sane")  # fallback


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



def compute_ppas(data=[]):

    if(len(data)!=6):
        logger.error("invalid data for ppas computation, got {}",format(data))
        return result

    cmd_ppas = os.path.join(_VERSE_DIR,"src","compute_ppas.py")
    if not (os.path.isfile(cmd_ppas)):
        logger.error("mising PPAS script: {}".format(cmd))
        return(result)

    logger.info("compute PPAS for {} vs {}".format(str(data[-2]),str(data[-1])))

    cmd = [
        cmd_ppas,
        "-r", str(data[-2]),
        "-d", str(data[-1]),
        "-n", "#".join(("WPPAS",str(data[0]))),
        "-j",
        # "-v"
    ]

    # execute command
    idx=data[0]
    try:
        result=check_output(cmd)
        result = json.loads(result)
        return (idx,[data[1], data[2], data[3],result["wppas"],result["ppas"]])
    except:
        logger.error("idx:{} cannot compute ppas. set to zero".format(idx))
        return (idx, [data[1], data[2], data[3], 0.0, 0.0])


def compute_ppas_map(args, path, cpu_cores=1):

    auralys_audio_list=[]
    ppas_list=[]

    idx=0
    for distance in _AURALYS_DISTANCE:
        for elevation in _AURALYS_ELEVATION:
            for azimuth in _AURALYS_AZIMUTH:

                # azimut from 0->360
                azimuth_360 = azimuth %360

                # bugfix!
                azi=str(f'{azimuth_360:+04d}') #"-000" if (int(azimuth)==0) else str(f'{azimuth:+04d}')
                ele="-000" if (int(elevation)==0) else str(f'{elevation:+04d}')
                dis="-000" if (int(distance)==0) else str(f'{distance:+04d}')

                filename= os.path.join(_AURALYS_AUDIO_FOLDER,_AURALYS_AUDIO_SUBFOLDER+azi+ele+dis+"_xAngle",str(_VERSE_SUBTYPE),str(_VERSE_INFO)+"_"+str(_VERSE_TYPE),"audio_0.mkv")

                if os.path.isfile (filename):
                    tmp=[idx, int(azimuth),int(elevation),int(distance),args.input,filename]
                    auralys_audio_list.append(tmp)
                    idx+=1
                else:
                    logger.error("missing file {}",filename)


    # for l in auralys_audio_list:
    #     print(l)

    # sanity check, should I meake an option to speedup?
    if(len(auralys_audio_list)>0):
        i_info = getMediaInfo(auralys_audio_list[0][-1], print_result=False)
        for f in auralys_audio_list:
            f_info = getMediaInfo(f[-1], print_result=False)
            if(i_info["format"]["nb_streams"] == f_info["format"]["nb_streams"]):
                ppas_list.append(f)
            else:
                logger.error("invalid track number for {}, expecting {} got {}. skip.",f[-1],i_info["format"][0]["nb_streams"],f_info["format"][0]["nb_streams"])

    #
    # compute map
    if(len(ppas_list)>0):

        # compute process pool size based on CPU/MEM requirements
        mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
        mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74
        cpu_count = min([(os.cpu_count() - 2), cpu_cores])
        cpu_count = max([_MIN_CPU_COUNT, cpu_count])
        cpu_count = min([_MAX_CPU_COUNT, cpu_count])

        cpu_result = np.zeros([len(_AURALYS_AZIMUTH)*len(_AURALYS_ELEVATION)*len(_AURALYS_DISTANCE),5])

        if(cpu_count==1):
            for p in ppas_list:
                cpu_pool_result = compute_ppas(p)
                print(cpu_result)
                print(type(cpu_pool_result))
                for d in cpu_pool_result:
                    cpu_result[int(d)]=cpu_pool_result[d]
        else:
            max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))
            logger.info("CPU Pool size: {}".format(max_pool_size))

            cpu_pool = Pool(max_pool_size)
            cpu_pool_result={}
            if len(ppas_list) > 0:
                cpu_pool_result=dict(cpu_pool.map(compute_ppas,ppas_list))
            cpu_pool.close()
            cpu_pool.join()

            for d in cpu_pool_result:
                cpu_result[int(d)]=cpu_pool_result[d]

    return cpu_result

# #############################################################################################################
# MAIN
# #############################################################################################################

def run_main(args):
    if not (os.path.isfile(args.input)):
        logger.error("missing input file: {}".format(args.input))
        exit(1)


    try:
        result = compute_ppas_map(args,"./",cpu_cores=args.cpu_process)

        # # print map
        ppas_map_reduced=np.delete(result,2,1)
        ppas_map_reduced=np.delete(ppas_map_reduced,3,1)

        df = pd.DataFrame(ppas_map_reduced)
        table = df.pivot(index=1, columns=0, values=2)
        ax = sns.heatmap(table)
        ax.invert_yaxis()
        print(table)
        plt.show()


    except KeyboardInterrupt:
        print("\nInterrupted by user")

    # clean exit
    restore_terminal()


#
# MAIN - CLI
#
if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, parents=[parser]
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        required=True,
        default="./audio.wav",
        help="input file or folder (default: %(default)s)",
    )
    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        required=False,
        default="./",
        help="auralys audio folder (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="verbose (default: %(default)s)",
    )
    parser.add_argument(
        "-c",
        "--cpu_process",
        type=int,
        default=4,
        required=False,
        help="maximum number of CPU process to use",
    )    

    args, remaining = parser.parse_known_args()

    #
    # set debug verbosity
    #
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)

    #
    run_main(args)
