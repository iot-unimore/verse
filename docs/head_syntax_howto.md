# Syntax: head resource
A head in VERSE is referring to the head of the listener. It can be any physical device with multple microphones attached to it. There must be only one listener for VERSE dataset rendering.

In VERSE headss are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/heads".

Users of VERSE can select the pre-defined heads or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/heads".

VERSE resources follow the same repetitive architecture: an info.yaml file in the subtype folder to provide generic informations, and a specific .yaml file inside the info folder. Data for each path are contained inside the "files" folder. See the structure here:

```
cd [VERSE]/resources/heads/unimore

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

title: unimore_heads

type: dataset

content: hrtf

description: multi-channel .sofa file for HRTFs on different subjects as per 3D-TuneIn project requirements

size_bytes:

source: none

source_original: none

fetch_script: fetch_files.sh

copyright: MIT

license: https://en.wikipedia.org/wiki/MIT_License

details: 
```


The "syntax" field is mandatory and allows to automatically identify and parse the type of info.yaml file, independently from its location inside the dataset.

Following this field we have general information about the type of data, the title, content, description. We also have information on copyright and source of the data. Most important the "size_bytes" field does specify the amount of disk space needed to fetch all the "files" to complete the resource.

# info files
The "fetch_script" field indicates which script needs to be executed to fetch external files (not present in this github repo) required for the resource to be completed.

Heads are described with their Head-Related-Tranfer-Function (HRTFs).

Each resource is identified by a separate .yaml file inside the info folder. For example "head_003.yaml" inside [VERSE]resources/heads/unimore/info has the following content:

```
# head related impulse response (HRTF)
syntax:
  name: hrtf_file
  version:
    major: 0
    minor: 1
    revision: 0

name: wilson_prj_head_barebone

description: wilson_prj head with no hair/hat on top (barebone) with glasses having six microphones (three pairs of L/R mics). Mics are also inside ears (binaural) for reference.

format: sofa

format_3dti: yes

#
# HRTFs definition:
# we can have more than one HRTF for the same head because the 3DTuneIn tool will
# take only binaural hrtf for rendering. For this head we have multiple micropones
# arranged in L/R pairs (for binaural and for glasses array).
# we list them in order with the associated hrtf file.
#
hrtf_count: 4
hrtf_main_idx: 0
hrtf:
  0:
    name: binaural
    file: files/head_003/dry-20250223_001_binaural.sofa
  1:
    name: array_six_front
    file: files/head_003/dry-20250223_001_array_six_front.sofa
  2:
    name: array_six_middle
    file: files/head_003/dry-20250223_001_array_six_middle.sofa
  3:
    name: array_six_rear
    file: files/head_003/dry-20250223_001_array_six_rear.sofa
```

The above syntax shows a format of SOFA type. The "format_3dti" shows that the original file has been adapted to the 3D-TuneIn requirements for zero delay impulse response (where delay is added as a separate field inside the SOFA file). Each HRTFs is listed from the last section.

- hrtf_count: how many hrtf files are linked by the info file
- hrtf_main_idx: which of the available hrtf files has to be considered the main one
- hrtf: list of all the linked hrtf, each one whith its specific name

It is important to assign a meaningful name to each HRTF file, it will be used when rendering the final audio by VERSE.

# visualization
To visualize each .sofa file use the tool [display_sofa](display_sofa.md)

