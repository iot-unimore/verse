#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INPUT_DIR="$(realpath "$1")"

# format_time() {
#     local t=$1
#     printf "%02d:%02d:%02d.00" $((t/3600)) $(((t%3600)/60)) $((t%60))
# }

random_start() {
    # shuf -i 5-10 -n 10
    shuf -i 3-10 -n 1
    # echo $(( RANDOM % 1 + 5 ))
}

format_time() {
    local input="$1"

    # integer seconds
    local int_part="${input%.*}"

    # fractional part (pad to avoid empty)
    local frac_part="${input#*.}"
    frac_part="${frac_part:0:2}"

    # ensure 2 digits
    frac_part=$(printf "%02d" "${frac_part:-0}")

    local hours=$(( int_part / 3600 ))
    local minutes=$(( (int_part % 3600) / 60 ))
    local seconds=$(( int_part % 60 ))

    printf "%02d:%02d:%02d.%02d" "$hours" "$minutes" "$seconds" "$frac_part"
}

while IFS= read -r -d '' INPUT_FILE; do

    # DEBUG (important while fixing)
    printf 'DEBUG INPUT: <%s>\n' "$INPUT_FILE"

    BASENAME="$(basename "$INPUT_FILE" .wav)"

    OUTPUT_WAV="${SCRIPT_DIR}/files/${BASENAME}_cut.wav"
    OUTPUT_YAML="${SCRIPT_DIR}/info/${BASENAME}_cut.yaml"

    echo "Processing:"
    echo "  Input : $INPUT_FILE"
    echo "  Output: $OUTPUT_WAV"

    START_SEC=$(random_start)

    # IMPORTANT: prevent ffmpeg from touching loop stdin
    ffmpeg -y -v error \
        -ss "$START_SEC"\
        -t 60 \
        -i "$INPUT_FILE" \
        "$OUTPUT_WAV" </dev/null

    SAMPLE_RATE=$(ffprobe -v error \
        -select_streams a:0 \
        -show_entries stream=sample_rate \
        -of default=noprint_wrappers=1:nokey=1 \
        "$OUTPUT_WAV")

    CHANNELS=$(ffprobe -v error \
        -select_streams a:0 \
        -show_entries stream=channels \
        -of default=noprint_wrappers=1:nokey=1 \
        "$OUTPUT_WAV")

    DURATION_SEC=$(ffprobe -v error \
        -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 \
        "$OUTPUT_WAV")

    DURATION_SEC=${DURATION_SEC%.*}

    cat > "$OUTPUT_YAML" <<EOF
---
# human voice audio file
# this is the descriptor file for a human voice recording
# this should be a "dry" recording without echo or reverberation
# if the recording is done in stereo mode it will be converted
# to mono. Audio format will be also converted to WAV (mono) before
# being used by the render_3dti script

syntax:
  name: voice_file
  version:
    major: 0
    minor: 1
    revision: 0

description: daps_database
copyright: daps
source: daps

file: files/$(basename "$OUTPUT_WAV")

speaker:
  count: 1

format:
  type: wav
  samplerate: ${SAMPLE_RATE} Hz
  channels: ${CHANNELS}
  duration: ${DURATION_SEC}

playback:
  begin: 00:00:00.00
  end: 00:01:00.00
#EOF
...
EOF

done < <(
    find "$INPUT_DIR" -type f -iname "*.wav" -print0
)