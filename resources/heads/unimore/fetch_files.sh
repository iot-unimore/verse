#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

RESOURCES_TAR_FILE_LIST=( "verse_unimore_head-003_files_20250924.tar" "verse_unimore_head-005_files_20250925.tar" "verse_unimore_head-006_files_20250925.tar" "verse_unimore_head-007_files_20250925.tar" "verse_unimore_head-008_files_20250925.tar" "verse_unimore_head-009_files_20260906.tar" "verse_unimore_head-010_files_20260906.tar" "verse_unimore_head-011_files_20260906.tar" "verse_unimore_head-012_files_20260906.tar")

RESOURCES_README_LIST=( "head_003/readme.txt" "head_005/readme.txt" "head_006/readme.txt" "head_007/readme.txt" "head_008/readme.txt" "head_009/readme.txt" "head_010/readme.txt" "head_011/readme.txt" "head_012/readme.txt")

WGET=`which wget`

cd $SCRIPT_DIR

idx=0
for i in ${RESOURCES_TAR_FILE_LIST[@]}; do

    RESOURCES_README=${RESOURCES_README_LIST[$idx]}

    RESOURCES_TAR_FILE=$i
    RESOURCES_TAR_LINK="http://www.brainworks.it/$RESOURCES_TAR_FILE"

    if [ ! -f  $SCRIPT_DIR/files/$RESOURCES_README ] ; then
      $WGET $RESOURCES_TAR_LINK

      if [ ! -f ./$RESOURCES_TAR_FILE ] ; then
        echo "Error: could not fetch the remote file: $RESOURCES_TAR_LINK"
        exit 0
      fi    

      echo "extracting files.."
      tar -xvf $RESOURCES_TAR_FILE > ./error.log

      if [ ! -f  $SCRIPT_DIR/files/$RESOURCES_README ] ; then
        echo "Error: could not extract files from: $RESOURCES_TAR_LINK, see error.log"
        exit 0
      fi    

    fi

    rm -rf ./$RESOURCES_TAR_FILE
    rm -rf ./error.log

    idx=$((idx+1))
done


echo "done."
