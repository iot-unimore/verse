# Tool: parse_sofa

This tool is located under "verse/tools/bin" folder and its purpose is to show the content of a .sofa file (Spatially Oriented Format for Audio)

This file format is defined by the Audio Engineering Society (AES) within the standard [AES69-2022](https://www.aes.org/publications/standards/search.cfm?docID=99) see also [sofaconventions](https://www.sofaconventions.org/mediawiki/index.php/SOFA_(Spatially_Oriented_Format_for_Acoustics))

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

The output will be similar to the following:

```
SOFA file contained custom entries
----------------------------------
GLOBAL_WilsonPrjAPI, GLOBAL_WilsonPrjAPIName, GLOBAL_WilsonPrjAPIVersion
SimpleFreeFieldHRIR 1.0 (SOFA version 2.1)
-------------------------------------------
GLOBAL_Conventions : SOFA
GLOBAL_Version : 2.1
GLOBAL_SOFAConventions : SimpleFreeFieldHRIR
GLOBAL_SOFAConventionsVersion : 1.0
GLOBAL_APIName : sofar SOFA API for Python (pyfar.org)
GLOBAL_APIVersion : sofar v1.1.4 implementing SOFA standard AES69-2022 (SOFA conventions 2.1)
GLOBAL_ApplicationName : Wilson Project SOFA
GLOBAL_ApplicationVersion : 0.0
GLOBAL_AuthorContact : info@brainworks.it
GLOBAL_Comment : https://creativecommons.org/licenses/by/4.0/
GLOBAL_DataType : FIR
GLOBAL_History : none
GLOBAL_License : CC-BY-4.0
GLOBAL_Organization : brainworks.it
GLOBAL_References : none
GLOBAL_RoomType : free field
GLOBAL_Origin : none
GLOBAL_DateCreated : 2024-01-01
GLOBAL_DateModified : 2025-03-07
GLOBAL_Title : Wilson Project
GLOBAL_DatabaseName : none
GLOBAL_ListenerShortName : wilson_head
ListenerPosition : (I=1, C=3)
  [0. 0. 0.]
ListenerPosition_Type : cartesian
ListenerPosition_Units : metre
ReceiverPosition : (R=2, C=3, I=1)
  [[ 0.     0.065  0.   ]
   [ 0.    -0.065  0.   ]]
ReceiverPosition_Type : cartesian
ReceiverPosition_Units : metre
SourcePosition : (M=648, C=3)
SourcePosition_Type : spherical
SourcePosition_Units : degree,degree,metre
EmitterPosition : (E=1, C=3, I=1)
  [0. 0. 0.]
EmitterPosition_Type : cartesian
EmitterPosition_Units : metre
ListenerUp : (I=1, C=3)
  [0. 0. 1.]
ListenerView : (I=1, C=3)
  [1. 0. 0.]
ListenerView_Type : cartesian
ListenerView_Units : metre
SourceUp : (M=648, C=3)
SourceView : (M=648, C=3)
SourceView_Type : cartesian
SourceView_Units : meter
Data_IR : (M=648, R=2, N=1440)
Data_SamplingRate : 96000.0
Data_SamplingRate_Units : hertz
Data_Delay : (M=648, R=2)
GLOBAL_WilsonPrjAPI : wilson_prj
GLOBAL_WilsonPrjAPIName : audio_measure
GLOBAL_WilsonPrjAPIVersion : 0.2.0
```

## visualization

To display the location of emitters/receivers over multiple measures contained in a .sofa file use the tool "display_sofa" described here: [display_sofa](display_sofa.md)
