#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################


RESOURCES_TAR_SERVER=https://dl.fbaipublicfiles.com/mls

declare -a filelist=(\
#mls_english_opus.tar.gz \
#mls_german_opus.tar.gz \
#mls_dutch_opus.tar.gz \
#mls_french_opus.tar.gz \
#mls_spanish_opus.tar.gz \
mls_italian_opus.tar.gz \
#mls_portuguese_opus.tar.gz \
mls_polish_opus.tar.gz )


WGET=`which wget`

TAR=`which tar`

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

  for i in "${filelist[@]}"
  do
    echo
    echo "FETCHING FILE: $i"
    echo

    RESOURCES_TAR_LINK=`echo $RESOURCES_TAR_SERVER/$i`
    RESOURCES_TAR_FILE=$i

    #echo $RESOURCES_TAR_LINK

    $WGET $RESOURCES_TAR_LINK -a ./wget_fetch.log

    if [ ! -f ./$RESOURCES_TAR_FILE ] ; then
       echo "Error: could not fetch the remote file: $RESOURCES_TAR_FILE"
    fi

    if [ -f ./$RESOURCES_TAR_FILE ] ; then
  	 echo "EXTRACTING FILE: $i"
         $TAR -xvf $i 2>> tar_extract.log
         rm -rf ./$RESOURCES_TAR_FILE
    fi

  done
fi

#rm -rf ./wget_fetch.log
#rm -rf ./tar_extract.log

echo "done."
