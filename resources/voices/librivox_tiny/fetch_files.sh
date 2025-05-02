#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_TAR_FILE="librivox_tiny_files.tar"

RESOURCES_TAR_LINK="http://www.brainworks.it/$RESOURCES_TAR_FILE"

WGET=`which wget`

cd $SCRIPT_DIR

if [ ! -d  $SCRIPT_DIR/files ] ; then
  $WGET $RESOURCES_TAR_LINK

  if [ ! -f ./$RESOURCES_TAR_FILE ] ; then
    echo "Error: could not fetch the remote file: $RESOURCES_TAR_LINK"
    exit 0
  fi    

  echo "extracting files.."
  tar -xvf $RESOURCES_TAR_FILE > ./error.log

  if [ ! -d  $SCRIPT_DIR/files ] ; then
    echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
    exit 0
  fi    

fi

rm -rf ./$RESOURCES_TAR_FILE
rm -rf ./error.log

echo "done."
