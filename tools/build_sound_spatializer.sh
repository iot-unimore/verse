#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################
#
clear

cd $SCRIPT_DIR

TOOL_DIR=$SCRIPT_DIR/wilson_prj/sound_spatializer

#
# check for tool folder
#
echo
echo "=== checking for external components ==="


if [ ! -d  $TOOL_DIR ] ; then
   echo "missing $TOOL_DIR (did you clone with -recursive?), exit"
   exit 0
fi

cd $TOOL_DIR
./buildme.sh

if [ -f $TOOL_DIR/sspat ] ; then
   ln -s $TOOL_DIR/sspat $SCRIPT_DIR/./bin/
fi

