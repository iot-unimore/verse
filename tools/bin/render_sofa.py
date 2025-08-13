#!/usr/bin/env python3

import argparse
import numpy as np
import soundfile as sf
import pyfar as pf
import h5py
import os
import pyfar.plot as pfplot
import matplotlib
import matplotlib.pyplot as plt

#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads
_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

def parse_args():
    parser = argparse.ArgumentParser(description="Render audio using SOFA HRIRs with multiple receivers.")
    parser.add_argument("wav_file", help="Input mono .wav file")
    parser.add_argument("sofa_file", help="Input .sofa file (HRIR with multiple receivers)")
    parser.add_argument("-sss", required=True, help="Source position in spherical coordinates: az,el,dist")
    parser.add_argument("-o", "--output", help="Output base name (default: render_<r>.wav)")
    return parser.parse_args()

def load_sofa_data(sofa_file):
    with h5py.File(sofa_file, 'r') as f:
        source_pos = f['SourcePosition'][:]            # shape [M, 3]
        ir = f['Data.IR'][:]                           # shape [M, R, N]
        delay = f['Data.Delay'][:]                     # shape [M, R]
        fs = f['Data.SamplingRate'][0]                 # float

        # Default unit is seconds if attribute missing
        delay_units_attr = f['Data.Delay'].attrs.get('Units', b'samples')
        # decode bytes to string if needed
        if isinstance(delay_units_attr, bytes):
            delay_units = delay_units_attr.decode('utf-8')
        else:
            delay_units = str(delay_units_attr)

        try:
            peaks = f['IRPeakDelay'][:]                    # shape [M, R]
        except:
            peaks = -1 * np.ones(delay.shape)

    return source_pos, ir, delay, fs, delay_units, peaks

def find_closest_source_idx(source_pos, target_pos):
    diffs = source_pos - target_pos
    dists = np.linalg.norm(diffs, axis=1)
    idx = np.argmin(dists)
    if dists[idx] > 1e-3:
        match = source_pos[idx]
        print(f"[INFO] Closest source: az={match[0]}°, el={match[1]}°, dist={match[2]}m (Δ = {dists[idx]:.3f})")
    return idx

def main():
    args = parse_args()

    # Parse -sss input
    try:
        az, el, dist = map(float, args.sss.split(","))
        target_pos = np.array([az, el, dist])
    except Exception:
        raise ValueError("Invalid -sss format. Use: -sss az,el,dist (e.g. 0,0,1)")

    # 
    # Load WAV file
    #
    audio, fs_wav = sf.read(args.wav_file)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # Convert to mono

    # plt.figure()
    # ax=plt.plot(audio, label="Input Signal (Mono)")
    # ax[0]=plt.xlabel("Samples")
    # ax[0]=plt.ylabel("Amplitude")
    # ax[0]=plt.legend()
    # ax[0]=plt.grid(True)
    # # plt.tight_layout()
    # plt.show()

    # Load SOFA data
    source_pos, irs, delays, fs_sofa, delay_units, peaks = load_sofa_data(args.sofa_file)
    print(f"[INFO] Delay units in SOFA file: '{delay_units}'")

    fs_sofa = int (fs_sofa)
    fs_wav = int(fs_wav)

    # Convert to pyfar Signal
    signal = pf.Signal(audio, fs_wav)
    signal_max = np.max(signal.time) 

    # Resample if needed
    if fs_wav != fs_sofa:
        print(f"[WARNING] Resampling input from {fs_wav} Hz to {fs_sofa} Hz to match SOFA.")
        signal = pf.dsp.resample(signal, fs_sofa)
        signal_max_r = np.max(signal.time) 
        signal *= (signal_max/signal_max_r)

    # plt.plot(signal.time.flatten())
    # plt.show()

    # Match closest source
    idx = find_closest_source_idx(source_pos, target_pos)
    num_receivers = irs.shape[1]

    print("======================================")
    print("Rendering Audio for Listener/Receivers")
    print("======================================")

    for r in range(num_receivers):

        h = irs[idx, r, :]            # IR for this receiver
        delay_val = delays[idx, r]
        peak_val = peaks[idx, r]

        if delay_units.lower() == "seconds":
            delay_samples = delay_val * fs_sofa
        elif delay_units.lower() == "samples":
            delay_samples = delay_val
        else:
            raise ValueError(f"[ERROR] Unsupported delay unit: '{delay_units}' (expected 'seconds' or 'samples')")

        ir = pf.Signal(h, fs_sofa)
        out = pf.dsp.convolve(signal, ir)

        if(delay_samples>0):
            out = pf.dsp.fractional_time_shift(out, delay_samples)

        out_filename = args.output or "render.wav"
        if num_receivers > 1:
            base, ext = os.path.splitext(out_filename)
            out_filename = f"{base}_r{r}{ext}"


        sf.write(out_filename, out.time.flatten(), fs_sofa)

        if(delay_samples>0):
            if delay_units.lower() == "seconds":
                print(f"Saved: {out_filename} (delay {delay_val:.6f} {delay_units})")
            elif delay_units.lower() == "samples":
                print(f"Saved: {out_filename} (delay {delay_val:.0f} {delay_units})")
        else:
            # print(f"Saved: {out_filename} (delay {delay_val:.0f} {delay_units})")
            print(f"Saved: {out_filename} (IR-peak at {peak_val:.0f} {delay_units})")

if __name__ == "__main__":
    main()
