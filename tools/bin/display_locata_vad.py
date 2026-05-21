#!/usr/bin/env python3

import argparse
import os
import sys

import numpy as np
import soundfile as sf
import plotly.graph_objects as go


# ============================================================
# CONFIG
# ============================================================

MAX_WAVEFORM_POINTS = 5000


# ============================================================
# FILE VALIDATION
# ============================================================

def validate_file_exists(path, description="file"):
    """
    Verify that a file exists and is readable.
    """

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{description.capitalize()} does not exist:\n{path}"
        )

    if not os.path.isfile(path):
        raise ValueError(
            f"{description.capitalize()} is not a file:\n{path}"
        )

    if not os.access(path, os.R_OK):
        raise PermissionError(
            f"{description.capitalize()} is not readable:\n{path}"
        )


# ============================================================
# AUDIO LOADING
# ============================================================

def load_wav(wav_path):
    """
    Load WAV audio file.

    Returns:
        audio
        sample_rate
        num_samples
    """

    try:
        audio, sr = sf.read(wav_path)

    except RuntimeError as e:
        raise RuntimeError(
            f"Failed to read WAV file:\n{wav_path}\n\n{e}"
        )

    if audio.ndim > 1:
        print(
            f"[INFO] Multichannel audio detected "
            f"({audio.shape[1]} channels). "
            f"Converting to mono by averaging channels."
        )

        audio = np.mean(audio, axis=1)

    return audio, sr, len(audio)


# ============================================================
# VAD LOADING
# ============================================================

def load_locata_vad(vad_path):
    """
    Load LOCATA-style VAD file.

    Format:
        VAD
        0
        1
        0
        ...
    """

    try:
        with open(vad_path, "r") as f:
            lines = [line.strip() for line in f.readlines()]

    except Exception as e:
        raise RuntimeError(
            f"Failed to read VAD file:\n{vad_path}\n\n{e}"
        )

    # Remove empty lines
    lines = [x for x in lines if x != ""]

    if len(lines) == 0:
        raise ValueError(
            f"Empty VAD file:\n{vad_path}"
        )

    # Optional LOCATA header
    if lines[0].upper() == "VAD":
        lines = lines[1:]

    if len(lines) == 0:
        raise ValueError(
            f"VAD file contains no data:\n{vad_path}"
        )

    vad_values = []

    for idx, line in enumerate(lines):

        if line not in ("0", "1"):
            raise ValueError(
                f"Invalid VAD value in file:\n"
                f"{vad_path}\n\n"
                f"Line {idx + 1}: '{line}'\n"
                f"Expected only 0 or 1."
            )

        vad_values.append(int(line))

    return np.array(vad_values, dtype=np.int8)


# ============================================================
# VALIDATION
# ============================================================

def validate_lengths(audio_len, vad_len, vad_path):

    if audio_len != vad_len:

        raise ValueError(
            f"Length mismatch between WAV and VAD.\n\n"
            f"VAD file : {vad_path}\n"
            f"Audio samples : {audio_len}\n"
            f"VAD samples   : {vad_len}\n\n"
            f"LOCATA VAD must contain EXACTLY one value "
            f"per audio sample."
        )


# ============================================================
# WAVEFORM ENVELOPE
# ============================================================

def compute_waveform_envelope(signal, max_points=MAX_WAVEFORM_POINTS):
    """
    Compute min/max envelope for efficient plotting.
    """

    n = len(signal)

    if n <= max_points:

        x = np.arange(n)

        return x, signal, signal

    block_size = int(np.ceil(n / max_points))

    trimmed_length = (n // block_size) * block_size

    trimmed = signal[:trimmed_length]

    reshaped = trimmed.reshape(-1, block_size)

    y_min = reshaped.min(axis=1)
    y_max = reshaped.max(axis=1)

    x = np.arange(len(y_min)) * block_size

    return x, y_min, y_max


# ============================================================
# VAD SEGMENTS
# ============================================================

def vad_to_segments(vad):
    """
    Convert binary VAD into active speech segments.
    """

    diff = np.diff(vad.astype(np.int8))

    starts = np.where(diff == 1)[0] + 1
    ends = np.where(diff == -1)[0] + 1

    if vad[0] == 1:
        starts = np.insert(starts, 0, 0)

    if vad[-1] == 1:
        ends = np.append(ends, len(vad))

    return list(zip(starts, ends))


# ============================================================
# VISUALIZATION
# ============================================================

def visualize(wav_path, vad_paths):

    # --------------------------------------------------------
    # Load audio
    # --------------------------------------------------------

    print(f"[INFO] Loading WAV file:\n  {wav_path}")

    audio, sr, n_samples = load_wav(wav_path)

    duration_sec = n_samples / sr

    print(f"[INFO] Audio loaded successfully")
    print(f"       Sample rate : {sr} Hz")
    print(f"       Samples     : {n_samples}")
    print(f"       Duration    : {duration_sec:.2f} s")

    # --------------------------------------------------------
    # Build waveform envelope
    # --------------------------------------------------------

    x_env, y_min, y_max = compute_waveform_envelope(audio)

    time_env = x_env / sr

    # --------------------------------------------------------
    # Create figure
    # --------------------------------------------------------

    fig = go.Figure()

    # --------------------------------------------------------
    # Plot waveform
    # --------------------------------------------------------

    fig.add_trace(
        go.Scattergl(
            x=np.concatenate([time_env, time_env[::-1]]),
            y=np.concatenate([y_max, y_min[::-1]]),
            fill='toself',
            mode='lines',
            line=dict(width=0.5),
            name='Audio',
            hoverinfo='skip'
        )
    )

    # --------------------------------------------------------
    # Plot VAD square waves
    # --------------------------------------------------------

    audio_peak = np.max(np.abs(audio))

    for idx, vad_path in enumerate(vad_paths):

        print(f"[INFO] Loading VAD:\n  {vad_path}")

        vad = load_locata_vad(vad_path)

        validate_lengths(n_samples, len(vad), vad_path)

        print(f"[INFO] VAD validated successfully")

        name = os.path.basename(vad_path)

        # ----------------------------------------------------
        # Downsample VAD for plotting
        # ----------------------------------------------------

        plot_step = max(1, n_samples // 200000)

        vad_plot = vad[::plot_step]

        time_vad = np.arange(len(vad_plot)) * plot_step / sr

        # ----------------------------------------------------
        # Vertical positioning
        # ----------------------------------------------------

        offset = -(idx + 1) * (audio_peak * 1.5)

        vad_wave = vad_plot.astype(float) * audio_peak + offset

        # ----------------------------------------------------
        # Plot square wave
        # ----------------------------------------------------

        fig.add_trace(
            go.Scattergl(
                x=time_vad,
                y=vad_wave,
                mode='lines',
                name=name,
                line=dict(
                    shape='hv',
                    width=2
                ),
                hovertemplate=(
                    "Time: %{x:.6f} s<br>"
                    "VAD: %{y}<extra></extra>"
                )
            )
        )



    # --------------------------------------------------------
    # Plot VADs
    # --------------------------------------------------------

    # for idx, vad_path in enumerate(vad_paths):

    #     print(f"[INFO] Loading VAD:\n  {vad_path}")

    #     vad = load_locata_vad(vad_path)

    #     validate_lengths(n_samples, len(vad), vad_path)

    #     print(f"[INFO] VAD validated successfully")

    #     segments = vad_to_segments(vad)

    #     name = os.path.basename(vad_path)

    #     for seg_idx, (start, end) in enumerate(segments):

    #         start_time = start / sr
    #         end_time = end / sr

    #         fig.add_vrect(
    #             x0=start_time,
    #             x1=end_time,
    #             opacity=0.25,
    #             line_width=0,
    #             annotation_text=name if seg_idx == 0 else None,
    #             annotation_position="top left",
    #             layer="below",
    #         )

    # --------------------------------------------------------
    # Layout
    # --------------------------------------------------------

    title = "LOCATA Audio + VAD Visualization: \n"+str(os.path.basename(wav_path))
    for v in vad_paths:
        title = title + " " + str(os.path.basename(v))

    fig.update_layout(
        title=title,
        xaxis_title="Time [s]",
        yaxis_title="Amplitude",
        template="plotly_white",
        hovermode="x unified",
        height=700,
    )

    fig.update_xaxes(
        rangeslider_visible=True
    )

    fig.show()


# ============================================================
# ARGUMENT PARSER
# ============================================================

def parse_args():

    parser = argparse.ArgumentParser(
        description=(
            "Interactive visualization tool for "
            "LOCATA waveform + VAD files."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-w",
        "--wav",
        required=True,
        help="Input WAV audio file"
    )

    parser.add_argument(
        "-v",
        "--vad",
        required=True,
        nargs="+",
        help=(
            "One or more LOCATA VAD text files"
        )
    )

    return parser.parse_args()


# ============================================================
# MAIN
# ============================================================

def main():

    args = parse_args()

    try:

        # ----------------------------------------------------
        # Validate WAV
        # ----------------------------------------------------

        validate_file_exists(args.wav, "wav file")

        if not args.wav.lower().endswith(".wav"):

            raise ValueError(
                f"Input file is not a WAV file:\n{args.wav}"
            )

        # ----------------------------------------------------
        # Validate VAD files
        # ----------------------------------------------------

        for vad_path in args.vad:

            validate_file_exists(vad_path, "vad file")

            if not vad_path.lower().endswith(".txt"):

                print(
                    f"[WARNING] VAD file does not "
                    f"have .txt extension:\n"
                    f"  {vad_path}"
                )

        # ----------------------------------------------------
        # Run visualization
        # ----------------------------------------------------

        visualize(args.wav, args.vad)

    except Exception as e:

        print("\n[ERROR]")
        print(e)

        sys.exit(1)


if __name__ == "__main__":
    main()