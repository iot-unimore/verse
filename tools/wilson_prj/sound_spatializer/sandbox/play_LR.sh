#!/usr/bin/bash

for i in $(seq 90 -5 -90)
do
  if [[ $i -ge 0 ]]; then
  	azimuth=$(( $i % 360))
  else
  	azimuth=$(( $i % 360 + 360))
  fi

  echo $azimuth

  cmd="ffplay ./audio/pippo_$azimuth.wav"

  $cmd

done
