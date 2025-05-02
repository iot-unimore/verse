#!/usr/bin/bash

list=`find . -name *.mp3`

#echo $list#

idx=0
for i in ${list[@]}; 
do 
    echo $idx

    foo=$(printf "%06d" $idx)

    echo $i; 

    name=$i
    folder=`echo $name |cut -d / -f -5`
    name=`echo $name |cut -d / -f 6`
    name=`echo $name |cut -d _ -f 1`

    info_yaml=${foo}_$name.yaml

    echo $info_yaml


    ### WRITE FILES
    cat ./head.txt > ./info/$info_yaml

    tmp="description:"
    echo $tmp >> ./info/$info_yaml
    tmp="copyright: public domain"
    echo $tmp >> ./info/$info_yaml

    tmp=`cat $folder/source.txt`
    #tmp=`echo $tmp | cut -d "/" -f 3-`
    echo "source: $tmp" >> ./info/$info_yaml

    tmp=`echo $tmp | cut -d / -f 4`
    echo "name: "$tmp >> ./info/$info_yaml


    tmp=`echo $i | cut -d / -f 2-`
    echo "file: "$tmp >> ./info/$info_yaml

    tmp=`echo $i | cut -d / -f 3`
    tmp=`echo $tmp | cut -d _ -f 2`

    echo "speaker: " >> ./info/$info_yaml
    echo "  count: 1" >> ./info/$info_yaml
    echo "  gender: $tmp">> ./info/$info_yaml

    tmp=`echo $i | cut -d / -f 5 | cut -d _ -f 3`
    echo "  language: $tmp">> ./info/$info_yaml


    ffprobe $i > /tmp/probe.txt 2>&1

    echo "metadata:" >> ./info/$info_yaml
    #tail -n 9 /tmp/probe.txt  | head -n 5 >>./info/$info_yaml

    tmp=`grep title /tmp/probe.txt`
    tmp=`echo $tmp | cut -d ":" -f 2`
    echo "  title: $tmp" >> ./info/$info_yaml
    tmp=`grep album /tmp/probe.txt`
    tmp=`echo $tmp | cut -d ":" -f 2`
    echo "  album: $tmp" >> ./info/$info_yaml
    tmp=`grep track /tmp/probe.txt`
    tmp=`echo $tmp | cut -d ":" -f 2`    
    echo "  track: $tmp" >> ./info/$info_yaml
    tmp=`grep genre /tmp/probe.txt`
    tmp=`echo $tmp | cut -d ":" -f 2`    
    echo "  genre: $tmp" >> ./info/$info_yaml


    echo "format:" >> ./info/$info_yaml
    echo "  type: mp3" >> ./info/$info_yaml
    tmp=`grep Stream /tmp/probe.txt`
    tmp=`echo $tmp | cut -d "," -f 2`
    echo "  samplerate: $tmp " >> ./info/$info_yaml
    echo "  channels: 1 " >> ./info/$info_yaml

    #tmp=`tail -n 4 /tmp/probe.txt | head -n 1`
    #tmp=`echo $tmp | cut -d "," -f 1 | cut -d " " -f 2`

    tmp=`grep Duration /tmp/probe.txt`
    tmp=`echo $tmp | cut -d "," -f 1 | cut -d " " -f 2`

    duration=`echo $tmp`

    echo "  duration: $duration" >> ./info/$info_yaml

    echo $duration

    echo "# [optional] preferred playback section (for audio rendering)" >> ./info/$info_yaml

    echo "playback:" >> ./info/$info_yaml
    echo "  begin: 00:01:00.00" >> ./info/$info_yaml
    echo "  end: 00:02:00.00" >> ./info/$info_yaml
    #echo "  end: "$duration >> ./info/$info_yaml

    echo "#EOF" >> ./info/$info_yaml
    echo "..." >> ./info/$info_yaml


    idx=$((idx + 1))
done
