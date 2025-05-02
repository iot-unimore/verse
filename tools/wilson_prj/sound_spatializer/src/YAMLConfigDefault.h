#ifndef _H_YAML_DEFAULT_CONFIG_H_
#define _H_YAML_DEFAULT_CONFIG_H_


const char * _YAML_DEFAULT_CONFIG = R"(
---

# syntax specification versioning
syntax:
  name: sspat_config
  version:
    major: 0
    minor: 1
    revision: 0

#
# audio setup and wav track description
#
setup:

  #
  # audio sources
  #
  sources_count: 1
  sources:
    0:
      # audio wav file
      file_wav: ./voice1.wav
      # source initial position
      coord: 0,0,1
      # sourc path (none if static)
      path_csv: none

  #
  # head
  #
  head:
    hrtf_sofa: none

  #
  # room
  #
  room:
    brir_sofa: none

#EOF
...

)";



#endif