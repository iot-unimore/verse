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
Ascene is defined by VERSE with the following syntax: [scene_syntax](docs/scene_syntax.md)

## usage
