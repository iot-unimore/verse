#!/usr/bin/bash

#/media/gfilippi/bigdata_01/verse/resources/voices/OpenSLR_LibriSpeech/files/mls_italian_opus/test/

MLS_LANG="polish"

MLS_SET="test"

MLS_FOLDER="/media/gfilippi/bigdata_01/verse/resources/voices/OpenSLR_LibriSpeech/files/mls_"$MLS_LANG"_opus/"$MLS_SET

echo $MLS_FOLDER

##################################################################################################

list=`find $MLS_FOLDER -name "*.opus" `


#idx=0
#for i in ${list[@]}; 
#do
#   echo $idx." ".$i;
#   idx=$((idx+1))
#done


idx=0
for i in ${list[@]}; 
do
    echo $idx

    foo=$(printf "%06d" $idx)

    echo $i

    name=$i
    folder=`echo $name |cut -d / -f -14`


    name=`echo $name |cut -d / -f 15`
    name=`echo $name |cut -d . -f 1`

    info_yaml=${foo}_${MLS_LANG}_$name.yaml

    echo $info_yaml

    ### WRITE FILES
    cat ./head.txt > ./info/$info_yaml

    tmp="description:"
    echo $tmp >> ./info/$info_yaml
    tmp="copyright: CC BY 4.0"
    echo $tmp >> ./info/$info_yaml

#    tmp=`cat $folder/source.txt`
#    #tmp=`echo $tmp | cut -d "/" -f 3-`
#    echo "source: $tmp" >> ./info/$info_yaml
    echo "source: https://openslr.org/94/index.html" >> ./info/$info_yaml

    #tmp=`echo $tmp | cut -d / -f 4`
    echo "name: "${MLS_LANG}_${name} >> ./info/$info_yaml


    tmp=`echo $i | cut -d / -f 9-`
    echo "file: "$tmp >> ./info/$info_yaml

    tmp=`echo $i | cut -d / -f 3`
    tmp=`echo $tmp | cut -d _ -f 2`

    echo "speaker: " >> ./info/$info_yaml
    echo "  count: 1" >> ./info/$info_yaml
    echo "  gender: ">> ./info/$info_yaml

    tmp=`echo $i | cut -d / -f 5 | cut -d _ -f 3`
    echo "  language: $MLS_LANG">> ./info/$info_yaml


    ffprobe $i > /tmp/probe.txt 2>&1

    echo "metadata:" >> ./info/$info_yaml
    #tail -n 9 /tmp/probe.txt  | head -n 5 >>./info/$info_yaml

    tmp=`cat /tmp/probe.txt |  tr -dc '[:print:] -dc [\n]' | grep title `
    tmp=`echo $tmp | cut -d ":" -f 2`
    echo "  title: $tmp" >> ./info/$info_yaml
    tmp=`cat /tmp/probe.txt |  tr -dc '[:print:] -dc [\n]' | grep album `
    tmp=`echo $tmp | cut -d ":" -f 2`
    echo "  album: $tmp" >> ./info/$info_yaml
    tmp=`cat /tmp/probe.txt |  tr -dc '[:print:] -dc [\n]' | grep artist `
    tmp=`echo $tmp | cut -d ":" -f 2`    
    echo "  artist: $tmp" >> ./info/$info_yaml


    echo "format:" >> ./info/$info_yaml
    echo "  type: opus" >> ./info/$info_yaml
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
    echo "  begin: 00:00:00.00" >> ./info/$info_yaml
    #echo "  end: 00:02:00.00" >> ./info/$info_yaml
    echo "  end: "$duration >> ./info/$info_yaml

    echo "#EOF" >> ./info/$info_yaml
    echo "..." >> ./info/$info_yaml


    idx=$((idx + 1))

#    rm /tmp/probe.txt

done
