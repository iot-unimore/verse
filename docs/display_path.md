# Tool: display_path

This tool is located under "verse/tools/bin" folder and its purpose is to show an interactive plot of a pre-defined path file.

## syntax
The sintax of this command has the following options:

```
./display_path.py -h
usage: display_path.py [-h] [-i INPUT_FILE] [-v] [-log LOGFILE]

options:
  -h, --help            show this help message and exit
  -i INPUT_FILE, --input_file INPUT_FILE
                        input path file (yaml or csv) to display (default: None)
  -v, --verbose         verbose (default: False)
  -log LOGFILE, --logfile LOGFILE
                        log verbose output to file (default: None)
```

As input file you can specify either a yaml or a csv file, it must be a valid file as per VERSE definition [path_syntax](docs/path_syntax.md)
