#!/usr/bin/env bash

ROOT="${1:-$(pwd)}"

# ----------------------------
# Find LOCATA roots robustly
# ----------------------------
roots=()

if compgen -G "$ROOT/task*" > /dev/null; then
    # direct LOCATA layout
    roots=("$ROOT")

elif compgen -G "$ROOT"/*/task* > /dev/null; then
    # split layout (dev/val/eval/etc.)
    for d in "$ROOT"/*; do
        [ -d "$d" ] || continue
        if compgen -G "$d/task*" > /dev/null; then
            roots+=("$d")
        fi
    done

else
    echo "ERROR: No LOCATA structure found under $ROOT"
    exit 1
fi

# ----------------------------
# Histogram
# ----------------------------
declare -A hist
declare -A split_recordings

echo "Scanning from: $ROOT"

for locata_root in "${roots[@]}"; do

    if [[ "$locata_root" == *"/"* && "$locata_root" != "$ROOT" ]]; then
        split=$(basename "$locata_root")
    else
        split="all"
    fi

    while IFS= read -r recdir; do

        n_sources=$(find "$recdir" -maxdepth 1 -type f -name 'position_source*.txt' | wc -l)

        key="$split:$n_sources"

        hist["$key"]=$(( ${hist["$key"]:-0} + 1 ))
        split_recordings["$split"]=$(( ${split_recordings["$split"]:-0} + 1 ))

    done < <(find "$locata_root" -mindepth 3 -maxdepth 3 -type d)

done

# ----------------------------
# SUMMARY
# ----------------------------
echo
echo "=== SOURCE COUNT DISTRIBUTION ==="

for split in "${!split_recordings[@]}"; do

    total=${split_recordings["$split"]}

    echo
    echo "$split"
    echo "-----------------------------------"

    # collect bins
    bins=$(for k in "${!hist[@]}"; do
        [[ "$k" == "$split:"* ]] && echo "${k#*:}"
    done | sort -n | uniq)

    for b in $bins; do
        count=${hist["$split:$b"]:-0}

        pct=$(awk -v c="$count" -v t="$total" \
            'BEGIN { if (t==0) printf "0"; else printf "%.1f", 100*c/t }')

        printf "  %2s sources : %4d recordings (%s%%)\n" \
            "$b" "$count" "$pct"
    done

done
