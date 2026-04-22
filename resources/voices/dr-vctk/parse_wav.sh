#!/usr/bin/env bash

set -euo pipefail

# ===== CONFIG =====
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"

INPUT_DIR="./files"     # root folder containing subfolders with wavs
OUTPUT_DIR="./info"  # where YAML files will be written
REL_AUDIO_PATH="files"         # path used inside YAML for "file:" field

########################### DO NOT MODIFY BELOW THIS LINE ##########################################
export LC_NUMERIC=C

cd $SCRIPT_DIR

verbose=0

if [[ "${1:-}" == "-v" ]]; then
    verbose=1
    shift
fi


if [ ! -d  $SCRIPT_DIR/$OUTPUT_DIR ] ; then
   mkdir -p "$OUTPUT_DIR"
fi

if [ ! -d  $SCRIPT_DIR/$OUTPUT_DIR ] ; then
   echo "Error: could not create info folder"
   exit 0
fi


# Function to format seconds into HH:MM:SS.xx
format_duration() {
    local duration="$1"
    awk -v d="$duration" 'BEGIN {
        h = int(d / 3600)
        m = int((d % 3600) / 60)
        s = d % 60
        printf "%02d:%02d:%05.2f", h, m, s
    }'
}

tmpfile=$(mktemp)
find "$INPUT_DIR" -type f -iname "*.wav" > "$tmpfile"

# get the total wav file count

total=$(wc -l < "$tmpfile")
count=0
spinner='-\|/'
i=0

exec 3< "$tmpfile"

while IFS= read -r wavfile <&3; do
    count=$((count + 1))   
    
    percent=$((count * 100 / total))
    spin_char=${spinner:i++%${#spinner}:1}

    if (( ! (( $verbose )) )); then
      printf "\r[%c] %3d%% (%d/%d)" "$spin_char" "$percent" "$count" "$total"
    fi

    # ---- your existing code ----
    filename=$(basename "$wavfile")
    wavdir="${wavfile%/*}/"

    str=$wavfile
    prefix=""
    description=""
    if [[ "$str" == *"device-recorded"* ]]; then
        if [[ "$str" == *"trainset"* ]]; then
            prefix="dr_train_"
            description="device-recorded, train"
        elif [[ "$str" == *"testset"* ]]; then
            prefix="dr_test_"
            description="device-recorded, test"
        fi
    elif [[ "$str" == *"clean"* ]]; then
        if [[ "$str" == *"trainset"* ]]; then
            prefix="clean_train_"
            description="clean audio file, train"
        elif [[ "$str" == *"testset"* ]]; then
            prefix="clean_test_"
            description="clean audio file, test"
        fi
    fi

    name="$prefix${filename%.*}"
    yaml_out="$OUTPUT_DIR/${name}.yaml"

    mapfile -t probe < <(
        ffprobe -v error \
            -select_streams a:0 \
            -show_entries stream=sample_rate,channels \
            -show_entries format=duration \
            -of default=noprint_wrappers=1:nokey=1 \
            "$wavfile"
    )

    samplerate=${probe[0]}
    channels=${probe[1]}
    duration=${probe[2]}

    duration_fmt=$(format_duration "$duration")

    # Generate YAML
    cat > "$yaml_out" <<EOF
---
# Device Recorded VCTK (Small subset version)
syntax:
  name: voice_file
  version:
    major: 0
    minor: 1
    revision: 0
description: ${description}
copyright: National Institute of Informatics (NII) and The Centre for Speech Technology Research (CSTR)
source: https://datashare.ed.ac.uk/handle/10283/3038
name: ${filename}
file: ${wavfile#./}
speaker: 
  count: 1
format:
  type: wav
  samplerate:  ${samplerate} Hz 
  channels: ${channels} 
  duration: ${duration_fmt}
# [optional] preferred playback section (for audio rendering)
playback:
  begin: 00:00:00.00
  end: ${duration_fmt}
#EOF
...
EOF
     
     if (( verbose )); then
        echo "Generated: $yaml_out"
     fi
done

exec 3<&-

# Move to next line after loop
echo

rm -f "$tmpfile"
#rm -rf ./$RESOURCES_TAR_FILE
rm -rf ./error.log




