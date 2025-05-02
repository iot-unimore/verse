# First Setup
After cloning the repo you have to make sure your environment is setup correclty.

There are three things to take care of:
- your python setup
- binary tools
- resource files

## Python setup
To quickly setup python dependencies it is suggested to use [Conda] (https://docs.conda.io/projects/conda/en/stable/user-guide/getting-started.html).
This is to keep an isolated environment dedicated to the dataset toolchain.

After installing Conda open a shell and create your "verse" environment:
```
conda create -n "verse" python=3.10.0
```
Activate your new environment with
```
conda activate verse
```
Enter the VERSE repository and use the "requirements.txt" file to update your environment:
```
pip install -r requirements.txt
```

Remeber to activate your "verse" python environment each time you want to use the toolchain or render new audio data.

## Fetching external files
Each resource exposes a set of info/[name].yaml definition files with details about the resource content.
But resources often require to download large files that are not included in github (like .wav|.sofa) files.

For this reason a specific "fetch_files.sh" script is present in each resource folder.
The user can decide to manually fetch only the resources he needs or to simply "fetch all data" (WARNING: this will be time consuming and will require a lot of data space. Check the info.yaml details for disk space requirements)

To fetch all data simply enter the "verse/resources" folder and launch the script as:
```
cd verse/resources
./fetch_all_files.sh
```

You will get an output similar to the following:

```
===========================================================
FETCHING: ./voices/librivox_tiny
===========================================================
--2025-05-02 17:37:54--  http://www.brainworks.it/librivox_tiny_files.tar
Resolving www.brainworks.it (www.brainworks.it)... 89.46.110.65
Connecting to www.brainworks.it (www.brainworks.it)|89.46.110.65|:80... connected.
HTTP request sent, awaiting response... 200 OK
Length: 1370961920 (1,3G) [application/x-tar]
Saving to: ‘librivox_tiny_files.tar’

librivox_tiny_files.tar            100%[=============================================================>]   1,28G  6,58MB/s    in 3m 17s  

2025-05-02 17:41:11 (6,64 MB/s) - ‘librivox_tiny_files.tar’ saved [1370961920/1370961920]

extracting files..
done.

===========================================================
FETCHING: ./voices/unimore
===========================================================
done.

===========================================================
FETCHING: ./rooms/unimore
===========================================================
done.

===========================================================
FETCHING: ./scenes/unimore
===========================================================
done.

===========================================================
FETCHING: ./heads/unimore
===========================================================
done.

===========================================================
FETCHING: ./paths/unimore
===========================================================
done.

```

## Compile tools
VERSE leverages [3D-TuneIn](https://3d-tune-in.eu/) to render binaural audio using custom recorded HRTF (head related transfer function) and BRIR (binaural room impulse response)
The sound_spatializer tool (built on top of 3D-TuneIn library) is release as C/C++ source code under "verse/tools/sound_spatializer" folder.

To compile the tool enter the folder: verse/tools and launch the script as below:

```
cd verse/tools/
./build_sound_spatializer.sh
```

The build script will check for library requirements, download external libraries (3D-TuneIn) and compile sound_spatializer tool (sspat). The binary file is placed in "verse/tools/bin" as a symlink.




