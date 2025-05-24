# Syntax: dataset recipe
The dataset recipe (ds_recipe) is the most important syntax definition of VERSE. This is the entity that brings all the comonents (heads, voices, rooms, paths) togheter and allow to generate a full syntetic dataset of audio scenes. The ds_recipe is the entry point to render a dataset "as is" (i.e. as it was designed by the developers) or to customize parts of it.

In VERSE da_recipes are a RESOURCE and so they are placed inside the folder "[VERSE]/resources/ds_recipes".

Users of VERSE can select the pre-defined ds_recipers or add more examples: this will need the creation of a subtype (i.e. a subfolder) under the "[VERSE]/resources/ds_recipes".

VERSE resources follow the same repetitive architecture: an info.yaml file in the subtype folder to provide generic informations, and a specific .yaml file inside the info folder. Data for each path are contained inside the "files" folder. See the structure here:

```
cd [VERSE]/resources/ds_recipes/unimore_tiny
tree -L 2
.
├── info
│   └── unimore_tiny_recipe.yaml
└── info.yaml
```
# info.yaml
The top level info.yaml has the following syntax:

```
# VERSE resource info                  
syntax:
  name: resource_info
  version:
    major: 0
    minor: 1
    revision: 0

title: unimore_tiny

type: dataset

content: dataset_recipe

description: a recipe to build a dataset from other resources (voices, heads, rooms)

size_bytes: 54G

source:

source_original:

fetch_script:

copyright: MIT

license: https://en.wikipedia.org/wiki/MIT_License

details: none

```

The "syntax" field is mandatory and allows to automatically identify and parse the type of info.yaml file, independently from its location inside the dataset.

Following this field we have general information about the type of data, the title, content, description. We also have information on copyright and source of the data. Most important the "size_bytes" field does specify the amount of disk space needed to fetch all the "files" to complete the resource.

# ds_recipe info file
The YAML file inside in the "info" subfolder is the *real* dataset definition file. There could be more than one YAML file but normally there is only one recipe for each dataset definition.

The syntax for a ds recipe is fairly flexible, but in the simpler form it is defined like this:

* a "syntax" version which identify the nature of the YAML file and the versioning of the syntax definition for the file itself. This is needed for proper parsing and to handle additions/modifications of the ds_recipe syntax in future.
* a name of the recipe
* an "output" definition: here we define the file location used to generate the folder under [VERSE]/dataset and the audio file format to be used for audio rendering (samplerate, bit format)
* sets: this is where we define the split of data in sub-sections. There could be as many sets as needed, normally train/test/validate.

A set is composed of multiple "tasks". There must be at least one task (#0). Tasks are needed to mix & match components that are coming from different resources. For a specific set we might need to pull voices from more (different) resources, same for heads and rooms, and for each different resource origin we need a separate task.

# simple definition
But for the simplest use case the set/task only refer to a list of scenes without specifying modifications to the resources used by the scene itself. This means the dataset is using the scenes "as-is", as defined by the original resource.


```
# Dataset Recipe:
# each recipe is a set of rules to select voices/heads/rooms to be used to 
# render a selection of audio scenes.
syntax:
  name: ds_recipe
  version:
    major: 0
    minor: 1
    revision: 0

#
# recipe
#
name: simple_example

output:
  path: datasets/simple_example
  store_info: True
  audio:
    format:
      type: wav
      subtype: pcm_s16le
      samplerate: 48000

#
# set is a collection of scenes that will be grouped in a subfolder (same name)
#
sets:
  # train/test/validate : only listed sets will be rendered
  
  train:
    # each task is a separate selection
    # of voices/heads/rooms needed to render a scene.
    # if you want to render each scene with default values
    # leave the voices/heads/rooms empty and the one
    # specified in the recipe will be used.
  
    # for voice/heads/rooms specification do not add the ".yaml"
    # use only filename without extention

    tasks:
      # TRAIN/TASK #0      
      0:
        # note: this task shows that you can mix&match scenes from different datasets using the right subtype
        #       in this task we use the resources listed in the recipes itself, no customization
        voices:
        heads:
        rooms:
        scenes:
          0:
            subtype: unimore
            info: ["000000_static_singlevoice","000001_static_singlevoice"]

```
In the example above the dataset is made of a "train" set which is composed of only two audio scenes, rendered without any modifications from the original audio_scene definition itself.

The final output is placed under [VERSE]/dataset/simple_example folder and the tree will resamble the following:

```
[VERSE]/dataset/simple_example
                    └── train
                        ├── 000000_static_singlevoice_0_0_0
                        │   ├── 000000_static_singlevoice_0_0_0.yaml
                        │   ├── static_singlevoice.mkv
                        │   └── static_singlevoice_mkv.yaml
                        └── 000001_static_singlevoice_0_0_1
                            ├── 000001_static_singlevoice_0_0_1.yaml
                            ├── static_singlevoice.mkv
                            └── static_singlevoice_mkv.yaml
```

See [scene_sintax](scene_syntax_howoto.md) for the details of each scene file definition and usage.

# adding tasks to a dataset
Sometime we need a set to be rendered across multiple sources, either scenes, voices, heads or rooms. This is where adding one more task is needed to allow flexibility for the dataset recipe.

For example in the recipe below we have one set "train" with two tasks, both picking audio scenes from two different resource location. Still no modification to the other components.

```
# Dataset Recipe:
# each recipe is a set of rules to select voices/heads/rooms to be used to 
# render a selection of audio scenes.
syntax:
  name: ds_recipe
  version:
    major: 0
    minor: 1
    revision: 0

#
# recipe
#
name: simple_example

output:
  path: datasets/simple_example
  store_info: True
  audio:
    format:
      type: wav
      subtype: pcm_s16le
      samplerate: 48000

#
# set is a collection of scenes that will be grouped in a subfolder (same name)
#
sets:  
  train:
    tasks:
      # TASK #0      
      0:
        voices:
        heads:
        rooms:
        scenes:
          0:
            subtype: unimore
            info: ["000000_static_singlevoice","000001_static_singlevoice"]
      # TASK #1
      1:
        voices:
        heads:
        rooms:
        scenes:
          0:
            subtype: brainworks.it
            info: ["000000_sceneA","0000001_sceneB"]
```

# mixing resources
The purpose of a recipe is to allow a flexible mix&match of multiple voice, heads, rooms resources on top a pre-defined audio scene. This is the capability to expand the datased with just the combination of available resources. **This is a powerful option but it will also increase the size (bytes) of the final dataset, quite fast**.

While adding a "permutation" to the recipe you have the option to specify "all" files from a resource or "just a list". 
For example in the recipe below:

* task #0 is rendering ALL the scenes from the resource "scenes/unimore" keeping them "as-is", without changing anyone of the scene components. This is the simplest way to render a dataset as it was specified by the authors of the scenes resource.
* taks #1 does a "mix&match": for its definition it is pulling few specific scenes from two different resources, without changing anyone of the components of the sources itself.
the first task is specifying only few files while the second task is selecting "all" the files of a resource.
* task #2 selects one specific scene but does the rendering by altering the voices to be used for the scene itself
* task #3 selects one specific scene but is changign the heads and rooms to be used when rendering audio.

Note that when specifying a list of resources the dataset will do the permutation on all combination for those lists. Here again the final dataset will grow up in size, fast.

It is important to note the difference between voices lists and room/heads list:
- A scene might require multiple voices to be rendered. For this reason there are multiple lists of voices for task #1
- A scene always uses only one listeners (one head) and optionally one room (room can be skipped to avoid reverberation in final result). For this reason when using a list of heads or a list of rooms we are activating a permutation of data once more.

```
[...]
sets:
  train:
    tasks:
       # TRAIN/TASK #0
       0:
         # note: this task shows that you can list "all" the scenes in a dataset
         voices:
         heads:
         rooms:
         scenes:
           0:
             subtype: unimore
             info: ["all"]

      # TASK #1
      1:
        voices:
        heads:
        rooms:
        scenes:
          0:
            subtype: unimore
            info: ["000000_static_singlevoice","000001_static_singlevoice"]
          1:
            subtype: brainworks
            info: ["001300_scene_AA","001301_scene_BB"]

      # TRAIN/TASK #2
      2:
        voices:
          0:
            subtype: unimore
            info: ["000001_voice","000003_voice"]
          1:
            subtype: unimore
            info: ["000004_voice"]
        heads:
        rooms:
        scenes:
          0:
            subtype: unimore
            info: ["001300_dynamic_multivoice"]

      # TRAIN/TASK #3
      3:
        voices:
        heads:
          0:
            subtype: unimore
            info: ["head_001","head_003"]
        rooms:
          0:
            subtype: unimore
            info: ["room_brir_001"]
        scenes:
          0:
            subtype: unimore
            info: ["000300_dynamic_singlevoice"]
```

The example above is referred to one set (called "train") but it could be referred to any set definition.

# advanced resource definition

Sometime it is more difficult to select or split resources across different sources and we need a more flexible way to define which files to be used.

For this reason it is possible to use wildcards when specifying resources names. We can use the asterisk for multiple selection and exclamation mark (at the beginning) to indicate exclusion.

The following task definition is selecting scene resource "librivox_tiny", specifically all the files having a name starting with "static_one" or "mix":

```
    [...]
    tasks:
       # TRAIN/TASK #3
       3:
         # note: this task shows that you can list "all" the scenes in a dataset
         voices:
         heads:
         rooms:
         scenes:
          0:
            subtype: librivox_tiny
            info: ["static_one*|mix*"]
```

The following task definition instead, is selecting scene resource "librivox_tiny", specifically all the files havign a name starting with "mix" and also excluding all the files starting with "static_one":

```
    [...]
    tasks:
       # TRAIN/TASK #3
       3:
         # note: this task shows that you can list "all" the scenes in a dataset
         voices:
         heads:
         rooms:
         scenes:
          0:
            subtype: librivox_tiny
            info: ["!static_one*|mix*"]
```

The same can be done for all resource definition in a ds_recipe.

The combination of sets, tasks and wildcards allow the definition of fairly articulated dataset recipes, all starting from audio scenes previously defined.

***The main advantage of this technique is to provide a method to render the same "source motion path" while mixing sources (human voices) listener (human head) and room (reverb), saving the time to physically record all these sessions**
