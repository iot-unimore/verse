# Syntax: path for audio source
A path is specified as a sequence of 3D position in spaces that the audio source will follow during playback.

In VERSE paths are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/paths".

Users of VERSE can select the pre-defined paths or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/paths".

VERSE resources follow the same repetitive architecture: an info.yaml file in the subtype folder to provide generic informations, and a specific .yaml file inside the info folder. Data for each path are contained inside the "files" folder. See the structure here:

```
cd [VERSE]/resources/paths/unimore
tree -L 1

.
├── fetch_files.sh
├── files
├── info
└── info.yaml
```

# info.yaml
The top level info.yaml has the following syntax:

```
# VERSE resource info                  
syntax:
  name: resource_info
  version:
    major: 0
    minor: 1
    revision: 0

title: unimore_path_csv

type: dataset

content: paths in spherical coordinates (3dti convention) for object moving in space

description: each path is a trajectory in 3D space with absolute coordinates centered in listener position

size_bytes: 576K

source:

source_original:

fetch_script: fetch_files.sh

copyright: MIT

license: https://en.wikipedia.org/wiki/MIT_License

details: 

```

The "syntax" field is mandatory and allows to automatically identify and parse the type of info.yaml file, independently from its location inside the dataset.

Following this field we have general information about the type of data, the title, content, description. We also have information on copyright and source of the data. Most important the "size_bytes" field does specify the amount of disk space needed to fetch all the "files" to complete the resource.

# info files
The "fetch_script" field indicates which script needs to be executed to fetch external files (not present in this github repo) required for the resource to be completed.

Each resource is identified by a separate .yaml file inside the info folder. For example "path_001.yaml" inside [VERSE]resources/paths/unimore/info has the following content:

```
# moving path map.
# this is the descriptor file for a moving object path.
# the associated .CSV file will contain the detailed
# positioning of the object within the 0-100% timeline
# of the associated audio file. The association with
# a mono audio file is done at runtime by the 
# render 3dti script.
syntax:
  name: path_map
  version:
    major: 0
    minor: 1
    revision: 0

name: left_to_right_front_circle

description: panning on the horizontal plane from left to right, 1m distance circle, front side

# file format (only CSV supported)
format: csv

column_mapping:
  time: 0
  volume: 1
  azimuth: 2
  elevation: 3
  distance: 4
  type: 5
#
# coordinates (only spherical supported) and column mapping
coord:
  type: spherical
  angle: degree

path_count: 1
path_main_idx: 0
path:
  0:
    file: files/path_001.csv
```

this info file is abstracting the final data which is contained in "files/path_001.csv".

the format is specified as CSV (Comma separated values) and the conlumns are mapped as per "column_mapping" field. Coordinates for this path files are spherical with angles in degrees as specified bu te "coord" field.

# raw file
the low-level data is specified by a CSV file which has the following structure:

- the 1st column is a time in % of the total playback time of the associated audio file. This will be specified by the scene definition later, so we cannot use absolute playback time.
- the second column is the amplitude (Volume) for audio playback
- following are the coordinates for source position at that specific playback time (currenlty only spherical coords are supported)
- the last column indicates the type (spherical/cartesian) for source coordinates.
  
```
#audio_path
#syntax_ver:1.0
#time[%], volume[%], azimuth[degree], elevation[degree], distance[metre], spherical(s)/cartesian(c)
00.00,100,-90,0,1,s
02.00,100,-90,0,1,s
05.00,100,-81,0,1,s
10.00,100,-72,0,1,s
15.00,100,-63,0,1,s
[...]
80.00,100,54,0,1,s
85.00,100,63,0,1,s
90.00,100,72,0,1,s
95.00,100,81,0,1,s
100.00,100,90,0,1,s
#eof
```

each position is referred to the space origin which is centered at the same position of the listener's head.

# visualization
Path can be visualized with the "display_path" tool, see (display_path)[display_path.md]
