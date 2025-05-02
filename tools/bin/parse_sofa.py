#!/usr/bin/env python3
"""read sofa file and print info"""

import argparse

import pyfar as pf
import soundfile as sf
import sofar as sof
import logging

logger = logging.getLogger(__name__)

#
# TOOLS
#
def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


#
# MAIN
#
if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
            "-input",
            "--input",
            type=str,
            help="input SOFA file (.sofa)",
        )

    args, remaining = parser.parse_known_args()

    print(args.input)

    try:
        sofa = sof.read_sofa(args.input)
        sofa.inspect()
        sofa.verify()
    except:
        logger.error( "[ERROR] cannot read file: {}".format(args.input) )

