# Syntax: scene resource
An audio scene in VERSE is referring to the description of audio source positions and motion inside a specific room, with a specific listener. The purpose of a scene is to combine one or more voices, with motion (dynamic source), or without motion (static source), inside a room using a specific head (listener)

In VERSE scenes are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/scenes".

Users of VERSE can select the pre-defined heads or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/scenes".

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

Audio scenes are important because they define the "skeleton" of an audio playback. They allow sources type to be swapped but the physical location in space (and movement) will be the same across multiple configuration. Voices, Heads and Rooms can be swapped by a dataset recipe but once an audio scene is defined it will be rendered always in the same way.

# info.yaml
The top level info.yaml has the following syntax:

STATIC SOURCES

```
# audio rendering scene configuration file
syntax:
  name: audio_rendering_scene
  version:
    major: 0
    minor: 1
    revision: 0

#
# details
#
scene:
  name: static_twovoice_000000
  description: scene with two static voices in the room, see position coordinates

#
# audio setup
#
setup:
  #
  # scene audio format for final rendering
  #
  format:
    type: wav
    subtype: pcm_s16le
    samplerate: 48000

  #
  # audio sources (voices)
  #
  sources_count: 2
  sources:
    0:
      # source type and info file
      type: voices
      subtype: librivox_tiny
      info: 000005_meraviglieduemila

      # positioning using spherical coord
      position:
        type: static
        coord:
          value: [0, -45, 1]
          type: spherical
          units: ['degree','degree','metre']
        view_vect:
          value: [1, 0, 0]
          type: cartesian
          units: ['metre']
        up_vect:
          value: [0, 0, 1]
    1:
      # source type and info file
      type: voices
      subtype: librivox_tiny
      info: 000051_davidcopperfield

      # positioning using spherical coord
      position:
        type: static
        coord:
          value: [45, 15, 3]
          type: spherical
          units: ['degree','degree','metre']
        view_vect:
          value: [1, 0, 0]
          type: cartesian
          units: ['metre']
        up_vect:
          value: [0, 0, 1]

  #
  # listener heads (MUST be count=1)
  #
  listeners_count: 1
  listeners:
    0:
       type: heads
       subtype: unimore 
       info: head_003

       # positioning: listener is static
       position:
         type: static
         coord:
           value: [0, 0, 0]
           type: spherical
           units: ['degree','degree','metre']
         view_vect:
           value: [1, 0, 0]
           type: cartesian
           units: ['metre']
         up_vect:
           value: [0, 0, 1]
  #
  # rooms (MUST be count=1 or count=0 for no reverberation)
  #
  rooms_count: 0
  rooms:
   0:
      type: rooms
      subtype:
      info:
```

DYNAMIC SOURCES

```
# audio rendering scene configuration file
syntax:
  name: audio_rendering_scene
  version:
    major: 0
    minor: 1
    revision: 0

#
# details
#
scene:
  name: dynamic_twovoice_000001
  description: scene with two voices moving in the room

#
# audio setup
#
setup:
  #
  # scene audio format for final rendering
  #
  format:
    type: wav
    subtype: pcm_s16le
    samplerate: 48000

  #
  # audio sources (voices)
  #
  sources_count: 2
  sources:
    0:
      # source type and info file
      type: voices
      subtype: librivox_tiny
      info: 000005_meraviglieduemila

      # positioning using spherical coord
      position:
        type: dynamic
        value:
          type: paths
          subtype: unimore
          info: path_001.yaml
    1:
      # source type and info file
      type: voices
      subtype: librivox_tiny
      info: 000051_davidcopperfield

      # positioning using spherical coord
      position:
        type: dynamic
        value:
          type: paths
          subtype: unimore
          info: path_006.yaml

  #
  # listener heads (MUST be count=1)
  #
  listeners_count: 1
  listeners:
    0:
       type: heads
       subtype: unimore 
       info: head_003

       # positioning: listener is static
       position:
         type: static
         coord:
           value: [0, 0, 0]
           type: spherical
           units: ['degree','degree','metre']
         view_vect:
           value: [1, 0, 0]
           type: cartesian
           units: ['metre']
         up_vect:
           value: [0, 0, 1]
  #
  # rooms (MUST be count=1 or count=0 for no reverberation)
  #
  rooms_count: 0
  rooms:
   0:
      type: rooms
      subtype:
      info:
```
```
