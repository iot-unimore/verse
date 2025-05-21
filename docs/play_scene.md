# Tool: play_scene

This tool is located under "verse/tools/bin" folder and its purpose is to facilitate audio playback of an audio scene by selecting the proper audio track (if needed).

VERSE dataset provides output results as folders with multi-track audio file (.mkv) and the related descriptor file (.yaml)

For example we can refer to a file of the "simple_example" dataset (rendered by VERSE). Under the folder "datasets/simple_example/train/000000_static_singlevoice_0_0_0" we see the following files:

```
.
├── 000000_static_singlevoice_0_0_0.yaml
├── static_singlevoice.mkv
└── static_singlevoice_mkv.yaml
```

"static_singlevoice.mkv" is the acutual rendered audio scene file (Matroska container), the "static_singlevoice_mkv.yaml" is the corrispondent descriptor and the "000000_static_singlevoice_0_0_0.yaml" is the scene definition itself (used to render the audio file).

## syntax
The syntax of this command has the following options:

```
./play_scene.py -h
usage: play_scene.py [-h] [-i INPUT_FILE] [-l] [-t TRACK] [-v] [-log LOGFILE]

options:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input_file INPUT_FILE
                        input path file (yaml or mkv) to display (default: None)
  -l, --list_tracks     list tracks title (default: False)
  -t TRACK, --track TRACK
                        audio track to play
  -v, --verbose         verbose (default: False)
  -log LOGFILE, --logfile LOGFILE
                        log verbose output to file (default: None)
```

## usage

The first thing to understand the content of a VERSE .mkv file is to list the tracks inside the file itself.

This can be done with option "-l" as below:

```
[VERSE]/tools/bin/play_scene.py -i ./static_singlevoice_mkv.yaml -l
0 : 000056_gentlemenpreferblondes.wav
1 : 000055_gentlemenpreferblondes.wav
2 : static_singlevoice_binaural_000.wav
3 : static_singlevoice_array_six_front_001.wav
4 : static_singlevoice_array_six_middle_002.wav
5 : static_singlevoice_array_six_rear_003.wav
```

This audio render contains two sources that are carried by track #0 and #1. The remaining four tracks are related to the rendered audio on a specific pair of microphones of the listner head. In this case we have two binaural microphones and six microphones placed on an array.

To play a single track use the option "-t"

```
[VERSE]/tools/bin/play_scene.py -i ./static_singlevoice_mkv.yaml --t 1
```
## descriptor
The same information can be retrieved from the .yaml descriptor of the mkv file:

```
syntax:
  name: verse_audio_mkv

name: verse rendered audio scene
description: none

file: /media/gfilippi/bigdata_01/verse/datasets/simple_example/train/000000_static_singlevoice_0_0_0/static_singlevoice.mkv

sources_count: 2
sources:
  0:
    channels: 1
    file: 000056_gentlemenpreferblondes.wav
    track_id: 0
  1:
    channels: 1
    file: 000055_gentlemenpreferblondes.wav
    track_id: 1

receivers_count: 4
receivers:
  0:
    channels: 2
    file: static_singlevoice_binaural_000.wav
    track_id: 2
  1:
    channels: 2
    file: static_singlevoice_array_six_front_001.wav
    track_id: 3
  2:
    channels: 2
    file: static_singlevoice_array_six_middle_002.wav
    track_id: 4
  3:
    channels: 2
    file: static_singlevoice_array_six_rear_003.wav

## scene visualization
To visualize the scene (source positions and their motion) please see the command [display_scene](docs/display_scene.md)

for this example the command would be:
```
[VERSE]/tools/bin/display_scene.py -i ./000000_static_singlevoice_0_0_0.yaml
```
where [VERSE] is the file path to your local VERSE folder.
    track_id: 5
```

The descriptor shows two sources and 4 pairs of receivers.
