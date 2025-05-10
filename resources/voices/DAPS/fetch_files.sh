#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_TAR_FILE="daps.tar.gz"

RESOURCES_TAR_LINK="https://zenodo.org/records/4660670/files/daps.tar.gz?download=1"

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
    exit 0
  fi

  echo "extracting files.."
  tar -xvf $RESOURCES_TAR_FILE > ./error.log

  if [ ! -d  $SCRIPT_DIR/files ] ; then
    echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
    exit 0
  fi

fi

#rm -rf ./$RESOURCES_TAR_FILE
#rm -rf ./error.log

echo "done."
