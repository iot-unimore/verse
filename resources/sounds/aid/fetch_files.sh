#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_TAR_FILE="AID.zip"

RESOURCES_TAR_LINK="https://zenodo.org/records/6974033/files/${RESOURCES_TAR_FILE}"

TOOL_LINK="https://github.com/audiolabs/anechoic-noise.git"

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

  git clone "$TOOL_LINK" 

  $WGET $RESOURCES_TAR_LINK

  if [ ! -f ./$RESOURCES_TAR_FILE ] ; then
    echo "Error: could not fetch the remote file: $RESOURCES_TAR_LINK"
    exit 1
  fi

  echo "extracting files.."
  unzip $RESOURCES_TAR_FILE > ./error.log

  if [ ! -d  $SCRIPT_DIR/files ] ; then
    echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
    exit 1
  fi

  rm -rf ./$RESOURCES_TAR_FILE

fi

echo "done."
