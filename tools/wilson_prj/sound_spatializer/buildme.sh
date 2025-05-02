#!/usr/bin/bash
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

#
# set your temp folder for externals here
#
EXTERNALS_DIR=$SCRIPT_DIR/externals


#
########################### DO NOT MODIFY BELOW THIS LINE ##########################################
#
clear

echo
echo "========================================="
echo "=== SOUND_SPATIALIZER: setup          ==="
echo "========================================="
echo "Build Script directory:"
echo "$SCRIPT_DIR"
echo
echo "External Libraries folder:"
echo "$EXTERNALS_DIR"

cd $SCRIPT_DIR


echo
echo "=== checking for packages to install ==="
#
# check for required packages
#
if dpkg -s libpulse-dev &>/dev/null; then
  echo 'libpulse-dev is installed'
else
  echo 'libpulse-dev is NOT installed, installing...'
  sudo apt-get install libpulse-dev
  if ! dpkg -s libpulse-dev &>/dev/null; then
      echo "Cannot install libpulse-dev, exit"
      exit 0
  fi
fi

if dpkg -s libnetcdf-c++4-dev &>/dev/null; then
  echo 'libnetcdf-c++ is installed'
else
  echo 'libnetcdf-c++ is NOT installed, installing...'
  sudo apt-get install libnetcdf-c++4-dev libnetcdf-c++4 
  if ! dpkg -s libnetcdf-c++4-dev &>/dev/null; then
      echo "Cannot install libnetcdf-c++, exit"
      exit 0
  fi
fi

#
# check for external folder
#
echo
echo "=== checking for external components ==="


if [ ! -d $EXTERNALS_DIR ] ; then
	mkdir -p $SCRIPT_DIR/externals
    if [ ! -d $SCRIPT_DIR/externals ] ; then
      echo "Cannot create folder for external libraries, exit"
      exit 0
    fi
fi

#
# 3dTune-In: fetch 
#
if [ ! -d $EXTERNALS_DIR/3dTuneIn ] ; then
	mkdir $EXTERNALS_DIR/3dTuneIn
    if [ ! -d $EXTERNALS_DIR/3dTuneIn ] ; then
      echo "Cannot create folder for 3dTuneIn, exit"
      exit 0
    fi
fi

cd $EXTERNALS_DIR/3dTuneIn

if [ ! -d 3dti_AudioToolkit ] ; then
   git clone --recurse-submodules https://github.com/3DTune-In/3dti_AudioToolkit
   if [ ! -d 3dti_AudioToolkit ] ; then
        echo "Cannot fetch 3dti_AudioToolkit, exit"
        exit 0
   else
        echo "3dti_AudioToolkit: OK"   	
   fi
else
    echo "3dti_AudioToolkit: OK"   	
fi

if [ ! -d 3dti_AudioToolkit_Examples ] ; then
   git clone https://github.com/3DTune-In/3dti_AudioToolkit_Examples
   if [ ! -d 3dti_AudioToolkit_Examples ] ; then
        echo "Cannot fetch 3dti_AudioToolkit_examples, exit"
        exit 0
   else
        echo "3dti_AudioToolkit_examples: OK"   	
   fi
else
    echo "3dti_AudioToolkit_examples: OK"   	
fi

#
# Yaml-cpp: fetch and build
#
cd $EXTERNALS_DIR
if [ ! -d yaml-cpp ] ; then
   git clone https://github.com/jbeder/yaml-cpp.git
   if [ ! -d yaml-cpp ] ; then
        echo "Cannot fetch yaml-cpp, exit"
        exit 0
   fi

   if [ ! -f $EXTERNALS_DIR/yaml-cpp/build/libyaml-cpp.a ] ; then
      cd $EXTERNALS_DIR/yaml-cpp
      mkdir build
      cd build
      cmake ../
      make
   else
        echo "yaml-cpp: OK"
   fi
else
    echo "yaml-cpp: OK"
fi

#
# update Makefile
#
cd $SCRIPT_DIR
MY_LINE=`grep -n "DO NOT MODIFY" ./Makefile | cut -f 1 -d ":"`
tail -n +$MY_LINE ./Makefile > $EXTERNALS_DIR/Makefile
echo "EXTERNALS_PATH = $EXTERNALS_DIR" > ./Makefile
cat $EXTERNALS_DIR/Makefile >> ./Makefile

echo
echo "========================================="
echo "=== SOUND_SPATIALIZER: build release  ==="
echo "========================================="


make clean
echo "Build in progress ..."
make > ./build.log 2>&1

if [ -f $SCRIPT_DIR/bin/release/sspat ] ; then
   rm $SCRIPT_DIR/build.log
   echo "buid complete, printing help."
   echo
   ./sspat -h
   echo
else
   echo "build failed, see build.log for details"
fi

echo "=== done ==="
