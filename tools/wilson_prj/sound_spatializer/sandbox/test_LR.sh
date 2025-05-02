#!/usr/bin/bash

hrtf="./resources/heads/head_003/dry-20250223_001_binaural.sofa"
#hrtf="./resources/heads/head_003/dry-20250223_001_array_six_front.sofa"


for i in $(seq 90 -5 -90)
do
  if [[ $i -ge 0 ]]; then
  	azimuth=$(( $i % 360))
  else
  	azimuth=$(( $i % 360 + 360))
  fi	

  echo $azimuth

  cmd="../sspat -i ./resources/voices/voice_003.wav -v 10 -s $hrtf -c $azimuth,0,1 -o ./audio/pippo_$azimuth.wav"

  $cmd

done
