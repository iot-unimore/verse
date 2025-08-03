#ifndef _H_YAML_DEFAULT_CONFIG_H_
#define _H_YAML_DEFAULT_CONFIG_H_


const char * _YAML_DEFAULT_CONFIG = R"(
---

# syntax specification versioning
syntax:
  name: sspat_config
  version:
    major: 0
    minor: 2
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
      # source path (none if static)
      path_csv: none
      # 3dti_params
      3dti:
        enableInterpolation: yes
        enableAnechoicProcess: yes
        enableReverbProcess: true
        enableFarDistanceEffect: no
        enableDistanceAttenuationAnechoic: yes
        enableDistanceAttenuationSmoothingAnechoic: yes
        enableDistanceAttenuationReverb: no
        enableNearFieldEffect: no
        enablePropagationDelay: no

  #
  # audio listeners
  #
  listeners_count: 1
  listeners:
    0:
      # initial position
      coord: 0,0,1
      # listener path (none if static)
      path_csv: none
      # HEAD
      head:
        hrtf_sofa: none
      # 3dti_params
      3dti:
        head_radius: 0.06
        customizedITD: no
        ILDAttenutaion_dB: -6
        directionality: no
        directionality_dB: 6

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