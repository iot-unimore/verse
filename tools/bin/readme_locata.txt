
#
# steps to convert a VERSE dataset into a LOCATA format
#

# STEP-1: conversion of VERSE Dataset, use convert_verse2locata and specify your options

# example: output folder in /tmp, single process, no verbosity
./convert_verse2locata.py -i ../../datasets/simple_example/ -o /tmp/ -m 1

# example: output folder in /tmp, 10 paralell processes, verbosity 
./convert_verse2locata.py -i ../../datasets/simple_example/ -o /tmp/ -v -m 10

# example: output folder in /tmp, m=[CPU_NUM] parallell processes (default), verbosity, set the array position in space with "-p x y z" (cartesian WORLD coordinates) 
./convert_verse2locata.py -i ../../datasets/simple_example/ -o /tmp/ -v -p 2 3 1

#
# STEP-2: optional, plot source or array trajectory to verify audio scene
#

# example: plot one single path for a source or array, plot 100 points on the graph
./display_locata_position.py /tmp/locata/simple_example/dev/task4/recording7/unimore_head_003/position_source_talker2.txt -n 100

# example: plot a full audio scene from the locata folder, with all sources and array of mics.
./display_locata_scene.py /tmp/locata/simple_example/dev/task4/recording7/unimore_head_003/  -n 100 --frames --frames-step 10 --frames-scale 0.06


