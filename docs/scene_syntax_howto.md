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
  sources_count: 1
  sources:
    0:
      # source type and info file
      type: voices
      subtype: librivox_tiny
      info: 000005_meraviglieduemila
      {POSITIONING}

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
The "syntax" versioning allows to identify the source definition intependenlty of the file location. The "details" section is important since it will be use to generate the name of the final folder for audio files.

## setup
The "setup" section is the core definition for an audio scene.

## format
The "format" section defines samplerate and bit format of the rendered audio files.

## sources
Audio sources can be more than one and are listed with an incremental number, starting from zero. The source definition requires type, subtype and info file name to identify an audio voice. 
The positioning of a source can be of two types: static or dynamic.

A static source position requires only the spatial coordinates, normally in spherical mode (azimuth, elevation, distance) as per AES69-2022 specification. For example the following source is placed in front of the listener at 1 metre distance on a lower position (at 45 degree). View vector and Up vector define the orientation of the source itself (as per AES69-2022 definition)

```
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
```

For dynamic sources the position will chance during playback and so a "path" must be associated to the source. For example:

```
      # positioning using spherical coord
      position:
        type: dynamic
        value:
          type: paths
          subtype: unimore
          info: path_001.yaml
```

Paths are a RESOURCE and are defined in VERSE as specified here: (path_syntax)[path_syntax_howto]

## listeners
There must be only one listener in one scene.

A "listener" is defined by its "head" (hrtf) definition and its position. The position is specified with spherical coordinates while the head is RESOURCE in VERSE, see specification here: [head_syntax](head_syntax_howto.md)

The syntax for a listener is the following:

```
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
```



## rooms
There must be only one room, which is defined by the corrispondent RIR (room impulse response). Room syntax for VERSE is defined here: [room_syntax](room_syntax_howto.md)

The definition of a room is optional: if the room is not specified in a scene there will be no audio reverberation while rendering the scene itself. Here is an example for the room indication

```
  rooms:
   0:
      type: rooms
      subtype: unimore
      info: room_brir_001
```

All the above sections are specified in one single audio scene file, see below for two examples with multiple audio sources.

# Examples

The first example is a scene with two audio sources that are STATIC, they do not move in space during playback of the voice files.

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

The second example is similar but this time the audio sources are both DYNAMIC, so there is a path associated to each source.

Source of different types can be mixed to create an appropriate audio configuration for the final rendering.

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


# Audio scene rendering

Rendering an audio scene requires to use the "render_scene.py" script available under [VERSE]/src folder.

The full syntax of this command is the following:

```
usage: render_scene.py [-h] [-sf SCENE_FILE] [-sn SCENE_NAME] [-fp] [-fo] [-o OUTPUT_FOLDER] [-k] [-c CPU_PROCESS] [-v]
                       [-log LOGFILE]

options:
  -h, --help            show this help message and exit
  -sf SCENE_FILE, --scene_file SCENE_FILE
                        audio scene to render (default: None)
  -sn SCENE_NAME, --scene_name SCENE_NAME
                        scene prefix name for audio files (default: None)
  -fp, --full_playback  play audio source in full length (default: False)
  -fo, --force_overwrite
                        audio source conversion (ffmpeg) force overwrite (default: False)
  -o OUTPUT_FOLDER, --output_folder OUTPUT_FOLDER
                        output folder (default: None)
  -k, --keep_files      keep all output files (default: False)
  -c CPU_PROCESS, --cpu_process CPU_PROCESS
                        maximum number of CPU process to use
  -v, --verbose         verbose (default: False)
  -log LOGFILE, --logfile LOGFILE
                        log verbose output to file (default: None)

```
* The "scene_file" is the main option to indicate the .yaml file to be used, this is mandatory.
* Use the "scene_name" option to indicate a specific prefix to be used when generating the final folder with rendered audio. The folder name is specified by the corrispondent option "output".
* The "full_playback" option is useful when you want to render the source audio files in full length without using the "preferred playback segment" of the source itself.
* The "keep_files" will keep all the temporary files in the final folder, useful for debug only.

Once a scene is rendered you will have a folder with three files, for example:

```
001301_dynamic_multivoice_0_1_1
    ├── 001301_dynamic_multivoice_0_1_1.yaml
    ├── dynamic_multivoice.mkv
    └── dynamic_multivoice_mkv.yaml
```
The final audio file is the Matroska (.mkv) file. This will contain the original sources used for rendering and the rendered output. Matroska is a so called "transport" or "container" format that allows multiple .WAV (LPCM) files to be grouped (muxed) in different tracks. The same file has a corrispondent descriptor in YAML format, useful to get informations on the matroska file with a more readable format. The remaining YAML file is the actual audio scene definition as it was used for rendering.

See [play_scene](play_scene.md) and [display_scene.md](display_scene.md) tools to learn how to play and display audio rendering results.
