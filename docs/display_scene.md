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
<img src="/docs/pics/dyn_path_001_side.png" align="left" width="300px" />
<img src="/docs/pics/dyn_path_001_top.png" align="left" width="300px" />
<img src="/docs/pics/OpenAural.png" align="left" width="200px"/>
<br clear="left"/>
