# Syntax: voice resource
A voice in VERSE is referring to a single audio file recorded with no reverberation (or minimal reverberation) and with only one mono channel (stereo files will be converted to mono). Voices are used to simulate human subject talking in a room as specified in an audio_scene definition.

In VERSE voices are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/voices".

Users of VERSE can select the pre-defined voices or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/voices".

VERSE resources follow the same repetitive architecture: an info.yaml file in the subtype folder to provide generic informations, and a specific .yaml file inside the info folder. Data for each path are contained inside the "files" folder. See the structure here:

```
cd [VERSE]/resources/voices/unimore

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

title: librivox_tiny

type: dataset

content: audio

description: a curated small selection of audio recordings for human voice (single person)

size_bytes:

source: none

source_original: https://librivox.org/

fetch_script: fetch_files.sh

copyright: public_domain

license: https://en.wikipedia.org/wiki/Public_domain

details: https://wiki.librivox.org/index.php?title=Copyright_and_Public_Domain
```

The "syntax" field is mandatory and allows to automatically identify and parse the type of info.yaml file, independently from its location inside the dataset.

Following this field we have general information about the type of data, the title, content, description. We also have information on copyright and source of the data. Most important the "size_bytes" field does specify the amount of disk space needed to fetch all the "files" to complete the resource.

# info files
The "fetch_script" field indicates which script needs to be executed to fetch external files (not present in this github repo) required for the resource to be completed.

Voices are identified by audio files (wav, mp3, opus etc.) which are associated to a specific descriptor placed in the info folder. For example info file "000001_voice.yaml" inside "[VERSE]resources/voices/unimore/info" has the following syntax:

```
# human voice audio file
# this is the descriptor file for a human voice recording
# this should be a "dry" recording without echo or reverberation
# if the recording is done in stereo mode it will be converted
# to mono. Audio format will be also converted to WAV (mono) before
# being used by the render_3dti script
syntax:
  name: voice_file
  version:
    major: 0
    minor: 1
    revision: 0
description: testing
copyright: not available
source: not available
name: none
file: files/voice_001.wav
speaker: 
  count: 1
format:
  type: wav
  samplerate:  44100 Hz 
  channels: 1 
  duration: 00:01:41.87
# [optional] preferred playback section (for audio rendering)
playback:
  begin: 00:00:40.00
  end: 00:01:40.00
```
