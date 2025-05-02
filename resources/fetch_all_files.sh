#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################

cmd_list=`find . -name fetch_files.sh`

for cmd in $cmd_list
do
  mydir=`dirname $cmd`

  echo
  echo "==========================================================="
  echo "FETCHING: $mydir"
  echo "==========================================================="

  cd $mydir
  ./fetch_files.sh
  cd $SCRIPT_DIR
done

echo "done."
