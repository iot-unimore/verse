# Tool: parse_sofa

This tool is located under "verse/tools/bin" folder and its purpose is to show the content of a .sofa file (Spatially Oriented Format for Audio)

This file format is defined by the Audio Engineering Society (AES) within the standard [AES69-2022](https://www.aes.org/publications/standards/search.cfm?docID=99) see also [sofaconventions](https://www.sofaconventions.org/mediawiki/index.php/SOFA_(Spatially_Oriented_Format_for_Acoustics)

VERSE usese this format for both the HRTF (head related transfer function) and RIR (room impulse response).

## syntax
The syntax of this command has the following options:

```
./parse_sofa.py -h
usage: parse_sofa.py [-h] [-input INPUT]

options:
  -h, --help            show this help message and exit
  -input INPUT, --input INPUT
                        input SOFA file (.sofa)
```

## usage
This tool is useful to quickly dump the content of a .sofa file and verify the convention for it.

As an example we refer to file "dry-20250223_001_binaural.sofa" under the "unimore" resource/head folder.
After enabling your conda environment for VERSE use the following command to parse the file:

```
[VERSE]/tools/bin/parse_sofa.py -i -i ./dry-20250223_001_binaural.sofa
```

The output is a list of information showing the convention, number of source/emitters (and location), number of listeners/receivers (and location). The .sofa file also indicates the type of room (or free field)

note: for VERSE there must be only one listener in the room.

## visualization

To display the location of emitters/receivers over multiple measures contained in a .sofa file use the tool "display_sofa" described here: [display_sofa](display_sofa.md)
