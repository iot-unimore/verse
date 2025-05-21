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

## usage
As an example we refer to path "path_001.yaml" under the "unimore" resource.
After enabling your conda environment for VERSE use the following command to display the path:

```
cd [VERSE]tools/bin/
./display_path.py -i ../../resources/paths/unimore/info/path_001.yaml
```

This will generate a plot like the following:

<img src="/docs/pics/path_001.png" align="left" width="517px"/>
<img src="/docs/pics/OpenAural.png" align="left" width="300px"/>
<br clear="left"/>

This path is defined as moving from the right to the left side of the listener, following a semi-circular path at a distance of 1m from the center of the listener position.

The red-green-blu lines are placed as a reference to the listener head position. In this example the movement from right to left is on the front side of the listener.

Using the "-v" (verbose) option a table is presented with all the numerical details of each step with coordinates

```
./display_path.py -i ../../resources/paths/unimore/info/path_001.yaml -v
INFO:root:name        :left_to_right_front_circle
INFO:root:description :panning on the horizontal plane from left to right, 1m distance circle, front side
+----+----------------+------------------+---------------+-----------------+--------------+--------+---------------+-----------------+-------------+-----------+-----+
|    |   time_percent |   volume_percent |   azimuth_deg |   elevation_deg |   distance_m | type   |   azimuth_rad |   elevation_rad |           x |         y |   z |
|----+----------------+------------------+---------------+-----------------+--------------+--------+---------------+-----------------+-------------+-----------+-----|
|  0 |              2 |              100 |           -90 |               0 |            1 | s      |     -1.5708   |               0 | 6.12323e-17 | -1        |   0 |
|  1 |              5 |              100 |           -81 |               0 |            1 | s      |     -1.41372  |               0 | 0.156434    | -0.987688 |   0 |
|  2 |             10 |              100 |           -72 |               0 |            1 | s      |     -1.25664  |               0 | 0.309017    | -0.951057 |   0 |
|  3 |             15 |              100 |           -63 |               0 |            1 | s      |     -1.09956  |               0 | 0.45399     | -0.891007 |   0 |
|  4 |             20 |              100 |           -54 |               0 |            1 | s      |     -0.942478 |               0 | 0.587785    | -0.809017 |   0 |
|  5 |             25 |              100 |           -45 |               0 |            1 | s      |     -0.785398 |               0 | 0.707107    | -0.707107 |   0 |
|  6 |             30 |              100 |           -36 |               0 |            1 | s      |     -0.628319 |               0 | 0.809017    | -0.587785 |   0 |
|  7 |             35 |              100 |           -27 |               0 |            1 | s      |     -0.471239 |               0 | 0.891007    | -0.45399  |   0 |
|  8 |             40 |              100 |           -18 |               0 |            1 | s      |     -0.314159 |               0 | 0.951057    | -0.309017 |   0 |
|  9 |             45 |              100 |            -9 |               0 |            1 | s      |     -0.15708  |               0 | 0.987688    | -0.156434 |   0 |
| 10 |             50 |              100 |             0 |               0 |            1 | s      |      0        |               0 | 1           |  0        |   0 |
| 11 |             55 |              100 |             9 |               0 |            1 | s      |      0.15708  |               0 | 0.987688    |  0.156434 |   0 |
| 12 |             60 |              100 |            18 |               0 |            1 | s      |      0.314159 |               0 | 0.951057    |  0.309017 |   0 |
| 13 |             65 |              100 |            27 |               0 |            1 | s      |      0.471239 |               0 | 0.891007    |  0.45399  |   0 |
| 14 |             70 |              100 |            36 |               0 |            1 | s      |      0.628319 |               0 | 0.809017    |  0.587785 |   0 |
| 15 |             75 |              100 |            45 |               0 |            1 | s      |      0.785398 |               0 | 0.707107    |  0.707107 |   0 |
| 16 |             80 |              100 |            54 |               0 |            1 | s      |      0.942478 |               0 | 0.587785    |  0.809017 |   0 |
| 17 |             85 |              100 |            63 |               0 |            1 | s      |      1.09956  |               0 | 0.45399     |  0.891007 |   0 |
| 18 |             90 |              100 |            72 |               0 |            1 | s      |      1.25664  |               0 | 0.309017    |  0.951057 |   0 |
| 19 |             95 |              100 |            81 |               0 |            1 | s      |      1.41372  |               0 | 0.156434    |  0.987688 |   0 |
| 20 |            100 |              100 |            90 |               0 |            1 | s      |      1.5708   |               0 | 6.12323e-17 |  1        |   0 |
+----+----------------+------------------+---------------+-----------------+--------------+--------+---------------+-----------------+-------------+-----------+-----+
```
