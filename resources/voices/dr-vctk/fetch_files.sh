#!/usr/bin/env bash
set -euo pipefail

#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

RESOURCES_ZIP_FILE="DS_10283_3038.zip"
RESOURCES_ZIP_LINK="https://datashare.ed.ac.uk/download/${RESOURCES_ZIP_FILE}"
RESOURCES_ZIP_SIZE=1795189255

RESOURCES_FILES_FILE="DR-VCTK.zip"
RESOURCES_FILES_LINK="$SCRIPT_DIR/files/${RESOURCES_FILES_FILE}"
RESOURCES_FILES_SIZE=1794891244

RESOURCES_SIZE=2182756

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

  if [ ! -f ./$RESOURCES_ZIP_FILE ] ; then
    $WGET $RESOURCES_ZIP_LINK    
  fi

  if [ ! -f ./$RESOURCES_ZIP_FILE ] ; then
    echo "Error: could not fetch the remote file: $RESOURCES_ZIP_LINK"
    exit 0
  fi

  echo "extracting resources files.."
  unzip -o $RESOURCES_ZIP_FILE > ./error.log

  if [ ! -f ./$RESOURCES_FILES_FILE ] ; then
    echo "Error: could not extract file: $RESOURCES_FILES_LINK"
    exit 0
  fi

  echo "extracting files.."
  unzip -o $RESOURCES_FILES_FILE >> ./error.log

  if [ ! -d  $SCRIPT_DIR/files/DR-VCTK ] ; then
    echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
    exit 0
  fi

  data_size=`du -s ./DR-VCTK | awk '{print $1}'`

  if [[ $data_size -ne $RESOURCES_SIZE ]]; then
    echo "Error: extracted data is not complete, see error.log"
    exit 0
  fi

  echo "generating info files"
  cd $SCRIPT_DIR
  ./parse_wav.sh

fi

#rm -rf ./$RESOURCES_ZIP_FILE
#rm -rf ./error.log

echo "done."
