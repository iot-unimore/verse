#!/usr/bin/bash

print_help() {
    echo "Usage: $0 <angle_string> <sofa_folder> <input_file> <output_directory>"
    echo
    echo "  <angle_string>    Format: number,number,number"
    echo "                   - First number: 0 to 360"
    echo "                   - Second number: -90 to 90"
    echo "                   - Third number: any integer"
    echo "  <input_file>      Path to an existing file"
    echo "  <sofa_folder>     Path to folder with sofa files"
    echo "  <output_directory> Path to an existing directory"
    exit 1
}

# Check argument count
if [ "$#" -ne 4 ]; then
    echo "Error: Exactly 4 parameters are required."
    print_help
fi


SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")

angle="$1"
file="$2"
sofa="$3"
dir="$4"

angle_str="${1//,/\-}"

# Validate angle format: int,int,int
if [[ "$angle" =~ ^-?[0-9]+,-?[0-9]+,-?[0-9]+$ ]]; then
    IFS=',' read -r num1 num2 num3 <<< "$angle"

    # Range checks
    if (( num1 < 0 || num1 > 360 )); then
        echo "Error: First number ($num1) must be between 0 and 360."
        print_help
    fi

    if (( num2 < -90 || num2 > 90 )); then
        echo "Error: Second number ($num2) must be between -90 and 90."
        print_help
    fi
else
    echo "Error: Invalid format for <angle_string>: '$angle'"
    print_help
fi

# Check if second parameter is a file
if [ ! -f "$file" ]; then
    echo "Error: '$file' is not a file or does not exist."
    print_help
fi

# Check if second parameter is a file
if [ ! -d "$sofa" ]; then
    echo "Error: '$sofa' is not a folder or does not exist."
    print_help
fi

# Check if third parameter is a directory
if [ ! -d "$dir" ]; then
    echo "Error: '$dir' is not a directory or does not exist."
    print_help
fi

# Check if file has .wav extension (case-insensitive)
if [[ "${file,,}" != *.wav ]]; then
    echo "Error: Input file '$file' does not have a .wav extension."
    print_help
fi

# Extract filename without path and extension
filename=$(basename "$file")
filename_no_ext="${filename%.*}"


#
# RENDERING
#

echo "Rendering audio files."

echo $filename_no_ext

#
# AUDIO RENDERING
#
ending_list=("_binaural" "_array_six_front" "_array_six_middle" "_array_six_rear")

for ending in "${ending_list[@]}"; do

    echo
    echo "Rendering $ending:"
    echo "======================================"
    sofafile=$(find "$sofa" -maxdepth 1 -type f -name '*'$ending'.sofa' | head -n 1)
    if [[ -n "$sofafile" ]]; then
        echo "Found file: $sofafile"
    else
        echo "No file ending with _binaural.sofa found in $sofa"
        print_help
    fi
    $SCRIPT_DIR/render_sofa.py -sss $1 $2 ${sofafile} -o ${dir}/${filename_no_ext}${ending}.wav

    ffmpeg -hide_banner -loglevel panic -i ${dir}/${filename_no_ext}${ending}_r0.wav -i ${dir}/${filename_no_ext}${ending}_r1.wav -filter_complex "[0:a][1:a]join=inputs=2:channel_layout=stereo[aout]" -map "[aout]" ${dir}/${filename_no_ext}${ending}.wav

    rm $dir/$filename_no_ext$ending\_r0.wav
    rm $dir/$filename_no_ext$ending\_r1.wav

done


ffmpeg -loglevel error -stats \
-i $2 \
-i $dir/$filename_no_ext\_binaural.wav \
-i $dir/$filename_no_ext\_array_six_front.wav \
-i $dir/$filename_no_ext\_array_six_middle.wav \
-i $dir/$filename_no_ext\_array_six_rear.wav \
-map 0:a \
-map 1:a \
-map 2:a \
-map 3:a \
-map 4:a \
-metadata:s:a:0 title="input" \
-metadata:s:a:1 title="binaural" \
-metadata:s:a:2 title="array_six_front" \
-metadata:s:a:3 title="array_six_middle" \
-metadata:s:a:4 title="array_six_rear" \
-movflags \
+faststart \
-acodec copy \
${dir}/${filename_no_ext}_${angle_str}.mkv


for ending in "${ending_list[@]}"; do
    rm ${dir}/${filename_no_ext}${ending}.wav
done

echo 
echo
echo "Mux completed, file: {dir}/${filename_no_ext}_${angle_str}.mkv"
echo
echo "Done."