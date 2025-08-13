#!/usr/bin/env python3
"""
PPAS: Perceptual Phase-Aware Similarity computation between WAV files

Usage:
    python compare_ppas.py ref.wav deg.wav

Requirements:
    pip install numpy scipy librosa matplotlib
"""

import os
import sys
import numpy as np
import librosa
import librosa.display
from scipy.signal import fftconvolve
from scipy.ndimage import uniform_filter1d
import matplotlib.pyplot as plt


#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads
_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

#
# PPAS DEFAULTS
#
_PPAS_DEFAULT_SR_HZ=16000 # Herts
_PPAS_DEFAULT_GLOBAL_SHIFT_MAX_S=0.02 # seconds

_PPAS_DEFAULT_N_MELS=40
_PPAS_DEFAULT_ALPHA=0.8
_PPAS_DEFAULT_ENVELOPE_CORRELATION_WINDOW_FRAMES=21
_PPS_SFFT_TIME_WINDOW=0.1 # seconds
_PPS_SFFT_LEN_MAX=8192
_PPS_SFFT_LEN_MIN=256
_PPS_SFFT_LEN_DEFAULT=2048


# -------------------------
# Perceptual Phase Metric
# -------------------------
def perceptual_phase_similarity(x_ref, 
                                x_deg, 
                                sr,
                                n_fft=_PPS_SFFT_LEN_DEFAULT, 
                                hop_length=(_PPS_SFFT_LEN_DEFAULT/8),
                                n_mels=_PPAS_DEFAULT_N_MELS, 
                                alpha=_PPAS_DEFAULT_ALPHA,
                                env_corr_window_frames=_PPAS_DEFAULT_ENVELOPE_CORRELATION_WINDOW_FRAMES,
                                use_vad_mask=None,
                                eps=1e-8):

    S_ref = librosa.stft(x_ref, n_fft=n_fft, hop_length=hop_length, center=True)
    S_deg = librosa.stft(x_deg, n_fft=n_fft, hop_length=hop_length, center=True)
    mags_ref = np.abs(S_ref); mags_deg = np.abs(S_deg)
    mel_fb = librosa.filters.mel(sr=sr, n_fft=n_fft, n_mels=n_mels, fmin=50, fmax=sr/2.0)
    S_ref_mel = mel_fb @ S_ref
    S_deg_mel = mel_fb @ S_deg
    E_ref = np.abs(S_ref_mel); E_deg = np.abs(S_deg_mel)
    n_frames = S_ref_mel.shape[1]

    # default simple VAD -> speech frames from reference energy
    if use_vad_mask is None:
        frame_energy = E_ref.mean(axis=0)
        thresh = np.maximum(frame_energy.max() * 0.02, np.median(frame_energy) * 0.5)
        vad_mask = frame_energy > thresh
    else:
        vad_mask = np.asarray(use_vad_mask, dtype=bool)
        if vad_mask.shape[0] != n_frames:
            raise ValueError("use_vad_mask must have length equal to number of frames")

    # Phase alignment (real part of coherence)
    prod = S_ref_mel * np.conj(S_deg_mel)
    denom = (E_ref * E_deg) + eps
    coherence = prod / denom
    phase_align = np.real(coherence)
    phase_align_masked = phase_align.copy()
    phase_align_masked[:, ~vad_mask] = 0.0

    # Envelope correlation (smoothed)
    win = max(1, int(env_corr_window_frames))
    E_ref_smooth = uniform_filter1d(E_ref, size=win, axis=1, mode='nearest')
    E_deg_smooth = uniform_filter1d(E_deg, size=win, axis=1, mode='nearest')

    n_mels = E_ref.shape[0]
    env_corr = np.zeros((n_mels, n_frames))
    for b in range(n_mels):
        idx = np.where(vad_mask)[0]
        if idx.size == 0:
            env_corr[b, :] = 0.0
            continue
        r = E_ref_smooth[b, idx]; d = E_deg_smooth[b, idx]
        if np.std(r) < 1e-10 or np.std(d) < 1e-10:
            corr_val = 0.0
        else:
            r_mean = r - r.mean(); d_mean = d - d.mean()
            corr_val = np.sum(r_mean * d_mean) / (np.sqrt(np.sum(r_mean**2) * np.sum(d_mean**2)) + eps)
        env_corr[b, :] = corr_val

    pa_mean = np.sum(phase_align_masked[:, vad_mask], axis=1) / (np.sum(vad_mask) + eps)
    ec_mean = np.mean(env_corr[:, vad_mask], axis=1)
    band_weights = E_ref.mean(axis=1) + eps
    combined_band = alpha * pa_mean + (1.0 - alpha) * ec_mean
    ppas = np.sum(band_weights * combined_band) / (np.sum(band_weights) + eps)
    return ppas

# -------------------------
# Alignment helpers
# -------------------------
def gcc_phat(sig, refsig, sr, upsample=1):
    """
    Estimate time delay (refsig leads sig by delay samples) using GCC-PHAT.
    Returns delay in samples (can be fractional if upsample>1 via interpolation).
    """
    n = sig.shape[0] + refsig.shape[0]
    # FFT-based cross-correlation with PHAT
    SIG = np.fft.rfft(sig, n=n)
    REF = np.fft.rfft(refsig, n=n)
    R = SIG * np.conj(REF)
    R /= (np.abs(R) + 1e-12)
    cc = np.fft.irfft(R, n=n)
    max_shift = int(n//2)
    cc = np.concatenate((cc[-max_shift:], cc[:max_shift+1]))
    # find peak
    shift = np.argmax(np.abs(cc)) - max_shift
    if upsample > 1:
        # refine by parabolic interpolation around peak
        peak = np.argmax(np.abs(cc))
        if 1 <= peak < len(cc)-1:
            y0, y1, y2 = np.abs(cc[peak-1]), np.abs(cc[peak]), np.abs(cc[peak+1])
            denom = (y0 - 2*y1 + y2)
            if denom != 0:
                shift_refined = peak + 0.5 * (y0 - y2) / denom
            else:
                shift_refined = peak
            shift = shift_refined - max_shift
        # else no refine
    return shift  # samples

def fractional_shift(x, shift_samples):
    """
    Shift signal by fractional samples. Positive shift_samples => delay (move right).
    We'll implement using linear interpolation of the original samples.
    """
    n = len(x)
    orig_idx = np.arange(n)
    new_idx = orig_idx - shift_samples  # where to sample from original to produce shifted signal
    # np.interp handles bounds by filling with left/right values; use 0 outside range
    shifted = np.interp(new_idx, orig_idx, x, left=0.0, right=0.0)
    return shifted

def dtw_warp_signal(ref, deg, sr, n_mfcc=13, hop_length=256):
    """
    Compute DTW on MFCCs and warp the deg signal to align to reference.
    Returns warped_deg (length of ref).
    """
    # compute MFCC sequences (frames)
    mf_ref = librosa.feature.mfcc(ref, sr=sr, n_mfcc=n_mfcc, hop_length=hop_length)
    mf_deg = librosa.feature.mfcc(deg, sr=sr, n_mfcc=n_mfcc, hop_length=hop_length)
    # cost and DTW path (use cosine distance)
    D, wp = librosa.sequence.dtw(X=mf_ref, Y=mf_deg, metric='cosine')
    wp = np.array(wp)[::-1]  # (ref_frame_idx, deg_frame_idx) ordered in time
    ref_frames = wp[:, 0]
    deg_frames = wp[:, 1]
    # create mapping from ref sample indices to deg sample indices via frame centers
    ref_frame_centers = ref_frames * hop_length + hop_length//2
    deg_frame_centers = deg_frames * hop_length + hop_length//2
    # build per-sample warped signal by linear interpolation of deg samples to ref positions
    # first make deg avail at deg_frame_centers -> sample values by taking nearest sample in deg
    # We'll create an interpolant mapping deg sample indices -> deg signal, then resample
    # Simpler: for each ref sample index t, find corresponding deg sample using linear interp of frame centers
    from scipy.interpolate import interp1d
    if len(deg_frame_centers) < 2:
        return deg * 0  # can't warp sensibly
    interp_deg_center = interp1d(deg_frame_centers, deg_frame_centers, kind='linear', fill_value='extrapolate')
    # map every ref sample index to a deg sample index via fitting a linear mapping from ref_frame_centers->deg_frame_centers
    map_func = interp1d(ref_frame_centers, deg_frame_centers, kind='linear', fill_value='extrapolate')
    ref_indices = np.arange(len(ref))
    mapped_deg_indices = map_func(ref_indices)  # fractional deg indices
    # sample deg at these fractional indices
    warped = np.interp(mapped_deg_indices, np.arange(len(deg)), deg, left=0.0, right=0.0)
    return warped

# -------------------------
# Main pipeline
# -------------------------
def align_and_compute_ppas(file_ref, file_deg, sr_target=96000,
                           max_global_shift_s=0.002,  # 2 ms tolerance for global shift
                           do_dtw_fallback=True,
                           verbose=True):
    

    # x_ref, sr1 = librosa.load(file_ref, sr=sr_target, mono=True)
    # x_deg, sr2 = librosa.load(file_deg, sr=sr_target, mono=True)

    # x_ref, sr1 = librosa.load(file_ref, sr=None, mono=True)
    # x_deg, sr2 = librosa.load(file_deg, sr=None, mono=True)

    x_ref, sr1 = librosa.load(file_ref, sr=sr_target, mono=False)
    x_deg, sr2 = librosa.load(file_deg, sr=sr_target, mono=False)

    assert sr1 == sr2 == sr_target
    assert (x_ref.ndim) == (x_deg.ndim)

    # Trim to same length window for global GCC-PHAT search: use min len to avoid huge introduces
    minlen = min(len(x_ref), len(x_deg))
    x_ref_c = x_ref[:minlen]
    x_deg_c = x_deg[:minlen]

    # Compute optimal FFT size for PPAS, we use a window of ~100ms
    fft_size = 1 << (int(np.log(sr1 * _PPS_SFFT_TIME_WINDOW)/np.log(2)))
    fft_size = min(_PPS_SFFT_LEN_MAX, max(_PPS_SFFT_LEN_MIN, fft_size))
    fft_overlap = int(fft_size/4)

    if verbose:
        print(f"PPAS optimal FFT size:{fft_size} overlap:{fft_overlap} for samplerate:{sr1}")

    # GCC-PHAT (generalized cross correlation phase and transform) for coarse delay (in samples)
    gcc_phat_shift_nchan =[]
    shift_samples_nchan = []

    for idx in np.arange(x_ref.ndim):
        shift_samples = 0
        if(x_ref.ndim == 1):
            shift_samples = gcc_phat(x_deg_c, x_ref_c, sr_target, upsample=4)
        else:
            shift_samples = gcc_phat(x_deg_c[idx,:], x_ref_c[idx,:], sr_target, upsample=4)
        if verbose:
            print(f"GCC-PHAT coarse shift (samples) for audio track #{idx}: {shift_samples:.3f} -> {shift_samples/sr_target*1000:.3f} ms")

        shift_samples_nchan.append(shift_samples)
        gcc_phat_shift_nchan.append(shift_samples)

    # using one value for shifting all channels: we use MIN which would be the most agressive on result (agerage as alternative)
    shift_samples = np.min(shift_samples_nchan)

    max_shift_samples = int(max_global_shift_s * sr_target)

    # collect PPAS for all channels
    ppas_nchan = []

    for idx in np.arange(x_ref.ndim):
        err = 0

        # If shift within tolerance, apply fractional shift
        if abs(shift_samples) <= max_shift_samples:

            try:
                if(x_ref.ndim == 1):
                    # fractional shift -> shift deg by shift_samples so deg aligns to ref
                    x_deg_aligned = fractional_shift(x_deg, shift_samples)
                    # trim to same length as ref
                    x_deg_aligned = x_deg_aligned[:len(x_ref)]

                else:
                    # fractional shift -> shift deg by shift_samples so deg aligns to ref
                    x_deg_aligned = fractional_shift(x_deg[idx], shift_samples)
                    # trim to same length as ref
                    x_deg_aligned = x_deg_aligned[:len(x_ref[idx,:])]

                if verbose:
                    print(f"Applied fractional global shift for audio track #{idx} of {shift_samples:.3f} samples")
            except:
                err = -1
        else:
            # out of tolerance, error to force ppas = -1
            print("Global shift exceeds tolerance, mark as ppas=-1")
            err = -1

            # # out of tolerance: if DTW allowed, fallback
            # if do_dtw_fallback:
            #     if verbose:
            #         print("Global shift exceeds tolerance -> attempting DTW warp on MFCCs")
            #     x_deg_aligned = dtw_warp_signal(x_ref, x_deg, sr_target, n_mfcc=20, hop_length=256)
            # else:
            #     raise RuntimeError("Global shift exceeds tolerance and DTW fallback disabled")

        x_ref_final = []
        x_deg_final = []

        if(err==0):
            # Ensure equal length
            L=0                
            if(x_ref.ndim == 1):
                L = min(len(x_ref), len(x_deg_aligned))
                x_ref_final = x_ref[:L]
                x_deg_final = x_deg_aligned[:L]
            else:
                L = min(len(x_ref[idx,:]), len(x_deg_aligned))
                x_ref_final = x_ref[idx,:L]
                x_deg_final = x_deg_aligned[:L]

            # optional: compute a VAD mask for later PPAS reuse a simple VAD on ref:
            S_ref = np.abs(librosa.stft(x_ref_final, n_fft=fft_size, hop_length=fft_overlap))
            frame_energy = S_ref.mean(axis=0)
            vad_mask = frame_energy > max(frame_energy.max() * 0.02, np.median(frame_energy) * 0.5)

            #
            # PPAS compute
            #
            ppas = perceptual_phase_similarity(x_ref_final, x_deg_final, sr_target,
                                               n_fft=fft_size, hop_length=fft_overlap, 
                                               n_mels=_PPAS_DEFAULT_N_MELS, 
                                               alpha=_PPAS_DEFAULT_ALPHA,
                                               env_corr_window_frames=_PPAS_DEFAULT_ENVELOPE_CORRELATION_WINDOW_FRAMES, 
                                               use_vad_mask=vad_mask)
        else:
            # out of tolerance, force ppas = -1
            ppas =-1

        if verbose:
            print(f"PPAS for track#{idx} ([-1..1]): {ppas:.4f}  -> [0..1] {(ppas+1)/2:.4f}")

        # collect result
        ppas_nchan.append(ppas)


    #
    # TIME SHIFT (can be negative)

    # magnitude
    gcc_phat_shift = np.max(np.abs(gcc_phat_shift_nchan))

    # delta_between_channels (will be zero for mono audio)
    gcc_phat_delta_shift = np.abs(np.max(gcc_phat_shift_nchan) - np.min(gcc_phat_shift_nchan))

    #
    # PPAS: select minimum of the results
    ppas = np.min(ppas_nchan)

    return x_ref_final, x_deg_final, ppas, gcc_phat_shift, gcc_phat_delta_shift

# -------------------------
# Command-line
# -------------------------
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python align_and_ppas.py ref.wav deg.wav")
        sys.exit(1)
    
    ref_file = sys.argv[1]; deg_file = sys.argv[2]
    
    # ref_aligned, deg_aligned, ppas = align_and_compute_ppas(ref_file, deg_file, sr_target=96000, max_global_shift_s=0.02, do_dtw_fallback=True)
    ref_aligned, deg_aligned, ppas, gcc_phat_shift, gcc_phat_delta_shift = align_and_compute_ppas(ref_file, deg_file, sr_target=16000, max_global_shift_s=0.02, do_dtw_fallback=True)
    

    print("==================================================")
    print(f"PPAS ([-1..1]): {ppas:.4f}  -> [0..1] {(ppas+1)/2:.4f}")
    print("==================================================")


    # # Plot quick overlay
    # plt.figure(figsize=(10,3))
    # plt.plot(ref_aligned, label='ref', alpha=0.7)
    # plt.plot(deg_aligned, label='deg', alpha=0.7)
    # plt.legend()
    # plt.title(f"Aligned signals (PPAS={(ppas+1)/2:.3f})")
    # plt.tight_layout()
    # plt.show()
