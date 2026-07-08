#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_LINK="https://github.com/facebookresearch/ears_dataset/releases/download/dataset/"

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

  for X in $(seq -w 001 107); do

      file="p${X}.zip"
      url="${RESOURCES_LINK}${file}"

      echo "Downloading ${file}..."

      #curl -L --fail -o "${file}" "${url}"
      $WGET --show-progress -q $url

      if [ ! -f ./${file} ] ; then
        echo "Error: could not fetch the remote file: $file" >&2
        continue
      fi

      echo "Extracting ${file}..."
      unzip -q "${file}"
      rm "${file}"
      
  done

fi

echo "done."
