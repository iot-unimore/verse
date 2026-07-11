#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_TAR_FILE="UrbanSound8K.tar.gz"

RESOURCES_TAR_LINK="https://zenodo.org/record/1203745/files/${RESOURCES_TAR_FILE}"

WGET=`which wget`

cd $SCRIPT_DIR

if [ ! -d  $SCRIPT_DIR/files ] ; then
  mkdir $SCRIPT_DIR/files
fi

if [ ! -d  $SCRIPT_DIR/files ] ; then
   echo "Error: could not create files folder"
   exit 0
fi

if [ -d  $SCRIPT_DIR/files ] ; then

  cd $SCRIPT_DIR/files

  $WGET $RESOURCES_TAR_LINK

  if [ ! -f ./$RESOURCES_TAR_FILE ] ; then
    echo "Error: could not fetch the remote file: $RESOURCES_TAR_LINK"
    exit 1
  fi

  echo "extracting files.."
  tar -xvf $RESOURCES_TAR_FILE > ./error.log

  if [ ! -d  $SCRIPT_DIR/files ] ; then
    echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
    exit 1
  fi

  rm -rf ./$RESOURCES_TAR_FILE

  # generate long wav files
  cd $SCRIPT_DIR

  ./make_dataset.py -j 8 -g ./files_wav/ >> ./error.log 

  # check for last file
  if [ ! -f  $SCRIPT_DIR/files_wav/sound_000499.wav ] ; then
    echo "Error: could not generate wav files see error.log"
    exit 1
  fi

  # generate info files
  cd $SCRIPT_DIR
  ./make_info.py -j 8 >> ./error.log 

fi

echo "done."
