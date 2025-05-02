To build this tool you need to pull 3dTuneIn project first:

0) create a "3dTuneIn" folder in a specific path

   mkdir ../../3dTuneIn/

   cd ../../3dTuneIn

1) pull 3dti in separate folders inside prev folder
   https://github.com/3DTune-In/3dti_AudioToolkit
   https://github.com/3DTune-In/3dti_AudioToolkit_Examples

   git clone --recurse-submodules https://github.com/3DTune-In/3dti_AudioToolkit

   git clone --recurse-submodules https://github.com/3DTune-In/3dti_AudioToolkit_Examples
   (note: portaudio will fail)

   ./3dTuneIn
   ├── 3dti_AudioToolkit
   ├── 3dti_AudioToolkit_Examples
   └── readme.txt

2) you also need to clone yaml-cpp at the same level of 3dTuneIn

git clone https://github.com/jbeder/yaml-cpp.git

3) For Ubuntu you also need to install these packages:
   sudo apt install libpulse-dev
   sudo apt-get install libnetcdf-c++4-dev libnetcdf-c++4

4) now build this tool with "make"
