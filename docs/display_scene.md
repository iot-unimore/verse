# Tool: display_scene

This tool is located under "verse/tools/bin" folder and its purpose is to show an interactive plot of a pre-defined path file.

## syntax
The syntax of this command has the following options:

```
./display_scene.py -h

usage: display_scene.py [-h] [-i INPUT_FILE] [-v] [-log LOGFILE]

options:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input_file INPUT_FILE
                        input scene file (yaml) to display (default: None)
  -v, --verbose         verbose (default: False)
  -log LOGFILE, --logfile LOGFILE
                        log verbose output to file (default: None)
```
As input file you can specify yaml scene definition file.
Ascene is defined by VERSE with the following syntax: [scene_syntax](docs/scene_syntax_howto.md)

## usage
As an example we refer to file "dynamic_twovoice_000001.yaml" under the "unimore" resource/path folder.
After enabling your conda environment for VERSE use the following command to display the path:

```
cd [VERSE]tools/bin/
./display_scene.py -i ../../resources/scenes/unimore/info/dynamic_twovoice_000001.yaml
```

The tool will show an interactive 3D plot of the dynamic scene where two audio sources are moving along a specific path in space. Each audio source has an audio filename attached: this is specific of the selected scene file (.yaml).

<img src="/docs/pics/dyn_path_001_45.png" align="left" width="400px" />
<img src="/docs/pics/dyn_path_001_side.png" align="left" width="400px" />
<img src="/docs/pics/dyn_path_001_top.png" align="left" width="400px" />
<br clear="left"/>

Where the origin is centered on the listener head and the orientation of the 3D coordinates follows the schema in the picture below

<img src="/docs/pics/OpenAural.png" align="left" width="200px"/>
<br clear="left"/>

From the above scene we have two voice sources: the first moves on a linear path on the right side of the listner, starting on the rear side and moving towards the front side. The second source is moving on a semi-circular path, starting from the right side of the listener towards the left side, keeping a distance of about 1m from the listener.

From the unimore resource folder we can see more complex scenes, up to three voice sources, with more complex path involving also up/down orientations.

<img src="/docs/pics/dyn_path_002_45.png" align="left" width="400px" />
<img src="/docs/pics/dyn_path_002_side.png" align="left" width="400px" />
<img src="/docs/pics/dyn_path_002_top.png" align="left" width="400px" />
<br clear="left"/>

In this scene we have three audio sources. The first source is moving along a semi-circular path similar to the previous one. The second source is moving on the rear-left side of the listener, going from near to far distance and going up in direction. The last source is moving on a linear path in front of the listener, starting from far distance towards the listener himself. While doing so the sources is moving also on the front-lower side.

The combination of audio scene definition and the flexibility of motion paths for each source allows to create virtual scenario while keeping a numerical reference for the position of each source during the playback of an audio file.
