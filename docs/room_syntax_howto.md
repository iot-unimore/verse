# Syntax: room resource
A room in VERSE is referring to the room impulse response (RIR) where the audio scene will be rendered. Essentially the room will define the reverberation applied to the final audio rendering.

In VERSE roomss are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/rooms".

Users of VERSE can select the pre-defined rooms or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/rooms".

VERSE resources follow the same repetitive architecture: an info.yaml file in the subtype folder to provide generic informations, and a specific .yaml file inside the info folder. Data for each path are contained inside the "files" folder. See the structure here:

```
cd [VERSE]/resources/rooms/unimore

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
<pre># VERSE resource info 
syntax:
  name: resource_info
  version:
    major: 0
    minor: 1
    revision: 0

title: unimore_rooms

type: dataset

content: brir

description: a small selection of rooms impulse responses in SOFA format

size_bytes:

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

Rooms are described by their Room Impulse Response (RIR). Specifically since VERSE uses the 3D-TuneIn convolver we need binaural type (two receivers) for the IR, so the specification is listing the content as BRIR (binaural room impulse response)

Each resource is identified by a separate .yaml file inside the info folder. For example "room_brir_001.yaml" inside [VERSE]resources/rooms/unimore/info has the following content:

```
# binaural room impulse response (BRIR)

syntax:
  name: brir_file
  version:
    major: 0
    minor: 1
    revision: 0

name: room_001

description: large, very reverberant room

format: sofa

format_3dti: yes

brir_count: 1
brir_main_idx: 0
brir:
  0:
    file: files/room_brir_001.sofa
```

The info file shows the format (sofa) and the number of BRIR linked to the info file. In this case there is only one which is linked as "file: files/room_brir_001.sofa".

Info files are used by the audio scene to specify the type of room (reverb) to be computed while rendering the final audio.
