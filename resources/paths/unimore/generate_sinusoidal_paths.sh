#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------
# Random walk path review loop
# ---------------------------------------------------------

if [ -z "$1" ]; then
    echo "Usage: $0 <start_number>"
    exit 1
fi


num=$1


while true
do

    echo "----------------------------------------"
    echo "Generating path_${num}.csv"
    echo "----------------------------------------"


    # Generate path

    $SCRIPT_DIR/sinusoidal_walk_generator.py \
        -c 10 \
        -o "./path_${num}.csv"


    if [ $? -ne 0 ]; then
        echo "Error generating path"
        exit 1
    fi


    # Display path

    $SCRIPT_DIR/../../../tools/bin/display_path.py \
        -i "./path_${num}.csv"


    if [ $? -ne 0 ]; then
        echo "Error displaying path"
        exit 1
    fi


    # Confirmation

    while true
    do
        read -p "Accept path? [y/n/q]: " answer

        case "$answer" in

            y|Y)
                echo "Accepted"
                num=$((num + 1))
                break
                ;;

            n|N)
                echo "Rejected - regenerating same number"
                break
                ;;

            q|Q)
                echo "Quit"
                exit 0
                ;;

            *)
                echo "Please answer y, n, or q"
                ;;

        esac
    done

done
