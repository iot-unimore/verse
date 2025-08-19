#!/usr/bin/env python3
"""
W-PPAS: Perceptual Phase-Aware Similarity computation between MKV (multi-track) files
"""

import os
import numpy as np
import librosa
import matplotlib.pyplot as plt
import soundfile as sf
import logging
import subprocess
import argparse
import tempfile
import json
import termios

import scipy.signal as sig
from multiprocessing import current_process, Pool
from subprocess import check_output
from numpy.fft import fft, ifft
import tempfile
import json

from compute_ppas import align_and_compute_ppas

#
# Set logger format and color
#
logger = logging.getLogger(__name__)
FORMAT = "[%(asctime)s %(filename)s->%(funcName)s():%(lineno)s]%(levelname)s: %(message)s"

#
# EXECUTABLES / EXTERNAL CMDs
#
_FFMPEG_EXE = "/usr/bin/ffmpeg"
_FFPROBE_EXE = "/usr/bin/ffprobe"

#
# DEFINES / CONSTANT / GLOBALS
#
_CTRL_EXIT_SIGNAL = 0  # driven by CTRL-C, 0 to exit threads
_ROOT_DIR = os.path.abspath(os.path.dirname(__file__))

#
# HW RESOURCES
#
_MIN_CPU_COUNT = 1  # we need at least one CPU for each compute process
_MAX_CPU_COUNT = 8  # this script is not optimized, keep a top limit
_MIN_MEM_GB = 1  # min amount of memory for each compute process
_MAX_MEM_GB = 1  # max amount of memory for each compute process

#
# AUDIO
#
_DEFAULT_SR=96000 # Hertz
_PPAS_GLOBAL_SHIFT_MAX_TH = 0.0005 # in seconds
_WPPAS_SHIFT_MIN = 0.0002 # in seconds
_WPPAS_SHIFT_MAX = _PPAS_GLOBAL_SHIFT_MAX_TH # in seconds

####################################################################################################
# DO NOT MODIFY CODE BELOW THIS LINE
####################################################################################################

def int_or_str(text):
    """Helper function for argument parsing."""
    try:
        return int(text)
    except ValueError:
        return text


def restore_terminal():
    try:
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, termios.tcgetattr(sys.stdin.fileno()))
    except:
        pass
    os.system("stty sane")  # fallback        

# ----------------------------------------------------------
#  Audio I/O Utilities
# ----------------------------------------------------------
def load_multichannel_wav(path, sr=None):
    """
    Load a WAV file and return it as a NumPy array with shape [channels, samples].
    librosa returns shape [samples,] for mono, so ensure output is always 2D.
    """
    y, sr = librosa.load(path, sr=sr, mono=False)
    if y.ndim == 1:  # mono file
        y = y[np.newaxis, :]
    return y, sr


def save_multichannel_wav(path, audio, sr):
    """
    Save a multichannel NumPy array [channels, samples] to a WAV file.
    soundfile expects [samples, channels], so we transpose first.
    """
    sf.write(path, audio.T, sr)

def get_media_info(filename, print_result=True):
    """
    Returns:
        result = dict with audio info where:
        result['format'] contains dict of tags, bit rate etc.
        result['streams'] contains a dict per stream with sample rate, channels etc.
    """
    result = check_output(
        [_FFPROBE_EXE, "-hide_banner", "-loglevel", "panic", "-show_format", "-show_streams", "-of", "json", filename]
    )

    result = json.loads(result)

    if print_result:
        print("\nFormat")

        for key, value in result["format"].items():
            print("   ", key, ":", value)

        print("\nStreams")
        for stream in result["streams"]:
            for key, value in stream.items():
                print("   ", key, ":", value)

        print("\n")

    return result

# ----------------------------------------------------------
#  MKV Track Extraction
# ----------------------------------------------------------
def extract_track(mkv_path, track_num, out_wav):
    """
    Extract a specific audio track from a MKV file into a WAV file using ffmpeg.
    - mkv_path: path to the .mkv file
    - track_num: integer track index (0-based)
    - out_wav: path where the extracted WAV will be saved
    """
    cmd = [
        "ffmpeg", "-y",              # overwrite without asking
        "-i", mkv_path,              # input file
        "-map", f"0:{track_num}",    # select track number
        "-acodec", "pcm_s24le",      # uncompressed PCM 24-bit
        out_wav
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ----------------------------------------------------------
#  WPPAS: weighted ppas 
# ----------------------------------------------------------
def compute_wppas(ppas, shift, delta_shift, min_shift=_WPPAS_SHIFT_MIN, max_shift=_WPPAS_SHIFT_MAX, max_delta_shift=_WPPAS_SHIFT_MIN*2, sr=_DEFAULT_SR, weight_linear=True):

    # everything is computed in "samples"
    shift=np.abs(shift)
    delta_shift=np.abs(delta_shift)

    max_shift = max_shift * sr
    min_shift = min_shift * sr
    max_delta_shift = max_delta_shift * sr

    w=1.0
    dw=1.0

    # weigth for shift magnitude (linear or cosine)
    if(weight_linear):
        # linear weigth
        w = (-1/(max_shift-min_shift)) * (shift - min_shift) +1
        w = min(1,(max(0,w)))
    else:
        # raised cosine weight
        shift = min(max_shift, max(min_shift, shift))
        w =  ( 1+ np.cos( ((np.pi)/((max_shift-min_shift))) * (shift - min_shift) ) ) /2 

    # weigth for delta shift (linear)
    dw = (-1/max_delta_shift) * (delta_shift) +1
    dw = min(1,(max(0,dw)))

    # print(f"compute wpas: ppas={ppas} w={w} dw={dw}")

    return (w*dw)

# ----------------------------------------------------------
#  Gain Normalization
# ----------------------------------------------------------
def normalize_global_gain(real, sim):
    """
    Apply the SAME gain to both signals based on the loudest sample across both.
    This ensures no clipping and keeps the relative balance between them.
    """
    peak_real = np.max(np.abs(real))
    peak_sim = np.max(np.abs(sim))
    global_peak = max(peak_real, peak_sim)

    if global_peak == 0:
        gain = 1.0
    else:
        gain = 1.0 / global_peak

    logger.info(f"Applied global gain: {20 * np.log10(gain):.2f} dB (peak before = {global_peak:.5f})")
    return real * gain, sim * gain


def normalize_gain(real, sim):
    """
    Apply independent peak normalization to each signal so each reaches full scale.
    Keeps both signals from clipping but does not enforce same gain.
    """
    peak_real = np.max(np.abs(real))
    peak_sim = np.max(np.abs(sim))

    if peak_real < 1.0:
        gain = 1.0 / peak_real
        logger.info(f"ref: Applied gain: {20 * np.log10(gain):.2f} dB")
        real = real * gain

    if peak_sim < 1.0:
        gain = 1.0 / peak_sim
        logger.info(f"deg: Applied gain: {20 * np.log10(gain):.2f} dB")
        sim = sim * gain

    return real, sim


# ----------------------------------------------------------
#  Alignment (FFT-based, Multi-channel Averaging)
# ----------------------------------------------------------
def align_and_trim_fft(real, sim):
    """
    Align two multichannel signals using FFT-based cross-correlation.
    - real, sim: [channels, samples]
    - Computes correlation per channel, sums results, finds best lag
    - Trims both arrays to the same length after alignment
    """
    n_channels = real.shape[0]

    n = 1 << (real.shape[1] + sim.shape[1] - 1).bit_length()

    corr_sum = np.zeros(n)
    for ch in range(n_channels):
        ref_ch = real[ch]
        sim_ch = sim[ch]
        corr_ch = ifft(fft(ref_ch, n) * np.conj(fft(sim_ch, n))).real

        data_corr = sig.correlate(ref_ch, sim_ch)

        corr_ch = np.roll(corr_ch, len(sim_ch) - 1)  # move zero-lag to center

        corr_sum += corr_ch

    lag = np.argmax(corr_sum) - (len(sim_ch) - 1)

    logger.info(f"Lag found: {lag} samples, correlation_sum={corr_sum[np.argmax(corr_sum)]}, len_sim={len(sim_ch)}")

    # Apply lag correction
    if lag > 0:
        real = real[:, lag:]
    elif lag < 0:
        sim = sim[:, -lag:]

    # Trim to the same length
    min_len = min(real.shape[1], sim.shape[1])

    # plt.figure()
    # plt.plot(sim[0,:])
    # plt.plot(real[0,:])
    # plt.show()
    # plt.figure()
    # plt.plot(sim[1,:])
    # plt.plot(real[1,:])
    # plt.show()

    return real[:, :min_len], sim[:, :min_len], lag


# ----------------------------------------------------------
#  Multi-process: single audio track computation
# ----------------------------------------------------------
def process_audio_ppas(data=[]):

    if(len(data)<6):
        return result

    name=data[0]
    idx=data[1]
    tmpdir=data[2]
    lag=int(float(data[3]))
    sim_mkv=data[4]
    real_mkv=data[5]

    # --- default result zero ---
    result = (idx,[0.0,0.0])

    # --- Extract comparison tracks ---
    logger.info(f"{name}:{idx}: Extracting track: {idx}")

    real_cmp_wav = os.path.join(tmpdir, "_"+str(idx)+"real_cmp.wav")
    sim_cmp_wav = os.path.join(tmpdir, "_"+str(idx)+"sim_cmp.wav")
    extract_track(real_mkv, idx, real_cmp_wav)
    extract_track(sim_mkv, idx, sim_cmp_wav)     

    # --- Load reference and comparison tracks ---
    real_cmp, sr_real = load_multichannel_wav(real_cmp_wav)
    sim_cmp, sr_sim = load_multichannel_wav(sim_cmp_wav)

    if sr_real != sr_sim:
        logger.error(f"{name}:{idx} Skipping {sim_mkv}: sampling rate mismatch.")
        return result
    if real_cmp.shape[0] != sim_cmp.shape[0]:
        logger.error(f"{name}:{idx} Skipping {sim_mkv}: channel count mismatch.")
        return result  

    # --- Apply lag to comparison tracks ---
    if lag > 0:
        real_cmp = real_cmp[:, lag:]
    elif lag < 0:
        sim_cmp = sim_cmp[:, -lag:]

    min_len = min(real_cmp.shape[1], sim_cmp.shape[1])
    real_cmp = real_cmp[:, :min_len]
    sim_cmp = sim_cmp[:, :min_len]


    # --- Normalize again after alignment ---
    logger.info(f"{name}:{idx}: Normalizing track: {idx}")
    real_cmp, sim_cmp = normalize_gain(real_cmp, sim_cmp)

    # Save temporary aligned versions
    # temp_real_path = os.path.join(folder_path, 'real_aligned.wav')
    # temp_sim_path = os.path.join(folder_path, 'sim_aligned.wav')
    # save_multichannel_wav(temp_real_path, real_cmp, sr_real)
    # save_multichannel_wav(temp_sim_path, sim_cmp, sr_real)

    temp_real_path = os.path.join(tmpdir, "_"+str(idx)+'real_aligned.wav')
    temp_sim_path = os.path.join(tmpdir, "_"+str(idx)+'sim_aligned.wav')
    save_multichannel_wav(temp_real_path, real_cmp, sr_real)
    save_multichannel_wav(temp_sim_path, sim_cmp, sr_real)


    # --- sub-align and compute PPAS ---
    logger.info(f"{name}:{idx}: Coarse alignement track: {idx}")
    ref_aligned, deg_aligned, ppas, gcc_phat_shift, gcc_phat_delta_shift = align_and_compute_ppas(temp_real_path, temp_sim_path, sr_target=sr_real, max_global_shift_s=_PPAS_GLOBAL_SHIFT_MAX_TH, do_dtw_fallback=False, verbose=args.verbose)

    # print("==================================================")
    # print(f"PPAS [-1..1]:{ppas:.4f} -> [0..1]:{(ppas+1)/2:.4f}, gcc-phat_shift:{gcc_phat_shift:.2f} [samples] -> {gcc_phat_shift*1000/sr_real:.3f} [ms]")
    # print("==================================================")

    # --- Adjust PPAS measure by weighting on shift amount and collect results ---
    logger.info(f"{name}:{idx}: Compute WPPAS track: {idx}")
    wppas = compute_wppas(ppas, gcc_phat_shift, gcc_phat_delta_shift, _WPPAS_SHIFT_MIN, _WPPAS_SHIFT_MAX, _WPPAS_SHIFT_MIN*2, sr_real,weight_linear=True)

    # # collect results
    result=(idx, [wppas, ppas])

    # m_wppas.append(wppas)
    # m_ppas.append(ppas)

    return result


# ----------------------------------------------------------
#  Folder Processing Logic
# ----------------------------------------------------------
def process_recording_folder(folder_path, args, result):
    """
    Process one folder containing real.mkv and sim.mkv:
    - Extract reference tracks for alignment (mono)
    - Extract stereo comparison tracks
    - Compute alignment lag using reference tracks
    - Apply lag to comparison tracks
    - Normalize gain
    """
    m_wppas = []
    m_ppas=[]

    real_mkv = os.path.join(folder_path, args.reference)
    sim_mkv = os.path.join(folder_path, args.degraded)

    real_mkv_media_info = get_media_info(real_mkv, print_result=False)
    sim_mkv_media_info = get_media_info(sim_mkv, print_result=False)

    # real_mkv = args.real
    # sim_mkv = args.simulated

    if not os.path.exists(real_mkv) or not os.path.exists(sim_mkv):
        logger.error(f"Skipping {folder_path}: missing MKV files.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:

        # --- Extract reference tracks from cointainer (MKV) ---
        real_ref_wav = os.path.join(tmpdir, "real_ref.wav")
        sim_ref_wav = os.path.join(tmpdir, "sim_ref.wav")
        extract_track(real_mkv, args.st, real_ref_wav)
        extract_track(sim_mkv, args.st, sim_ref_wav)

        # --- Load reference tracks as array ---
        real_ref, sr_real = load_multichannel_wav(real_ref_wav)
        sim_ref, sr_sim = load_multichannel_wav(sim_ref_wav)

        # --- Normalize gain globally for alignment ---
        logger.info(f"{args.name}: Normalizing reference track: {args.st}")

        # real_ref, sim_ref = normalize_global_gain(real_ref, sim_ref)
        real_ref, sim_ref = normalize_gain(real_ref, sim_ref)

        # --- Align reference tracks ---
        lag=0
        
        real_ref_aligned, sim_ref_aligned, lag= align_and_trim_fft(real_ref, sim_ref)
        
        logger.info(f"{args.name}: Applying lag {lag} to comparison tracks")

        if(1):
            ppas_list=[]
            for idx in np.arange(ref_media_info["format"]["nb_streams"]):
                if(idx!=args.st):
                    task_params=[args.name, idx, tmpdir, str(lag), sim_mkv, real_mkv]
                    ppas_list.append(task_params)

            if(len(ppas_list)>0):
                # compute process pool size based on CPU/MEM requirements
                mem_bytes = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")  # e.g. 4015976448
                mem_gib = mem_bytes / (1024.0**3)  # e.g. 3.74
                # cpu_count = min([(os.cpu_count() - 2), cpu_cores])
                cpu_count = os.cpu_count()
                cpu_count = max([_MIN_CPU_COUNT, cpu_count])
                cpu_count = min([_MAX_CPU_COUNT, cpu_count])

                max_pool_size = min(cpu_count, int(mem_gib / _MIN_MEM_GB))
                cpu_pool_result={}
                cpu_pool = Pool(max_pool_size)
                if len(ppas_list) > 0:
                    cpu_pool_result=dict(cpu_pool.map(process_audio_ppas,ppas_list))
                cpu_pool.close()
                cpu_pool.join()

                for d in cpu_pool_result:
                    m_wppas.append(cpu_pool_result[d][0])
                    m_ppas.append(cpu_pool_result[d][1])

        else:
            for idx in np.arange(ref_media_info["format"]["nb_streams"]):
                if(idx!=args.st):

                    # --- Extract comparison tracks ---
                    logger.info(f"{args.name}: Extracting track: {idx}")

                    real_cmp_wav = os.path.join(tmpdir, "_"+str(idx)+"real_cmp.wav")
                    sim_cmp_wav = os.path.join(tmpdir, "_"+str(idx)+"sim_cmp.wav")
                    extract_track(real_mkv, idx, real_cmp_wav)
                    extract_track(sim_mkv, idx, sim_cmp_wav)     

                    # --- Load reference and comparison tracks ---
                    real_cmp, sr_real = load_multichannel_wav(real_cmp_wav)
                    sim_cmp, sr_sim = load_multichannel_wav(sim_cmp_wav)

                    if sr_real != sr_sim:
                        logger.error(f"Skipping {sim_mkv}: sampling rate mismatch.")
                        return
                    if real_cmp.shape[0] != sim_cmp.shape[0]:
                        logger.error(f"Skipping {sim_mkv}: channel count mismatch.")
                        return   

                    # --- Apply lag to comparison tracks ---
                    if lag > 0:
                        real_cmp = real_cmp[:, lag:]
                    elif lag < 0:
                        sim_cmp = sim_cmp[:, -lag:]

                    min_len = min(real_cmp.shape[1], sim_cmp.shape[1])
                    real_cmp = real_cmp[:, :min_len]
                    sim_cmp = sim_cmp[:, :min_len]


                    # --- Normalize again after alignment ---
                    logger.info(f"{args.name}: Normalizing track: {idx}")
                    real_cmp, sim_cmp = normalize_gain(real_cmp, sim_cmp)

                    # Save temporary aligned versions
                    # temp_real_path = os.path.join(folder_path, 'real_aligned.wav')
                    # temp_sim_path = os.path.join(folder_path, 'sim_aligned.wav')
                    # save_multichannel_wav(temp_real_path, real_cmp, sr_real)
                    # save_multichannel_wav(temp_sim_path, sim_cmp, sr_real)

                    temp_real_path = os.path.join(tmpdir, "_"+str(idx)+'real_aligned.wav')
                    temp_sim_path = os.path.join(tmpdir, "_"+str(idx)+'sim_aligned.wav')
                    save_multichannel_wav(temp_real_path, real_cmp, sr_real)
                    save_multichannel_wav(temp_sim_path, sim_cmp, sr_real)


                    # --- sub-align and compute PPAS ---
                    logger.info(f"{args.name}: Coarse alignement track: {idx}")
                    ref_aligned, deg_aligned, ppas, gcc_phat_shift, gcc_phat_delta_shift = align_and_compute_ppas(temp_real_path, temp_sim_path, sr_target=sr_real, max_global_shift_s=_PPAS_GLOBAL_SHIFT_MAX_TH, do_dtw_fallback=False, verbose=args.verbose)

                    # print("==================================================")
                    # print(f"PPAS [-1..1]:{ppas:.4f} -> [0..1]:{(ppas+1)/2:.4f}, gcc-phat_shift:{gcc_phat_shift:.2f} [samples] -> {gcc_phat_shift*1000/sr_real:.3f} [ms]")
                    # print("==================================================")

                    # --- Adjust PPAS measure by weighting on shift amount and collect results ---
                    logger.info(f"{args.name}: Compute WPPAS track: {idx}")
                    wppas = compute_wppas(ppas, gcc_phat_shift, gcc_phat_delta_shift, _WPPAS_SHIFT_MIN, _WPPAS_SHIFT_MAX, _WPPAS_SHIFT_MIN*2, sr_real,weight_linear=True)

                    # collect results
                    m_wppas.append(wppas)
                    m_ppas.append(ppas)

        # -------------------------
        # Final PPAS result
        # -------------------------
        wppas_mean = np.mean(m_wppas)
        ppas_mean = np.mean(m_ppas)

        logger.info(f"{args.name}: WPPAS [0..1]:{wppas_mean*((ppas_mean+1)/2):.4f}, PPAS [0..1]:{(ppas_mean+1)/2:.4f}")

        # return PPAS in scale [0 ..1] only (easier to use), both in scaled and non-scaled version
        result.append([wppas_mean*((ppas_mean+1)/2) , ((ppas_mean+1)/2)])

        if(args.json):
            print(json.dumps({"wppas":wppas_mean*((ppas_mean+1)/2), "ppas": ((ppas_mean+1)/2)}))

        return 


def process_all_recordings(base_folder, args, result):
    """Loop over all subfolders and process each recording pair."""

    for subfolder in sorted(os.listdir(base_folder)):
        folder_path = os.path.join(base_folder, subfolder)
        if os.path.isdir(folder_path):
            rv=process_recording_folder(folder_path, args)
            result.append(rv)

    return

#
###############################################################################
# MAIN
###############################################################################
#
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Compute Perceptual Phase Alignement index between MKV files",add_help=True)
    # parser.add_argument("folder", help="Root folder with subfolders containing real.mkv and sim.mkv")

    parser.add_argument(
        "-f",
        "--folder",
        type=str,
        default=None,
        help="Root folder with subfolders containing real.mkv and sim.mkv (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        "--degraded",
        type=str,
        default="sim.mkv",
        help="degraded/simulated MKV audio file (default: %(default)s)",
    )
    parser.add_argument(
        "-r",
        "--reference",
        type=str,
        default="real.mkv",
        help="reference (real recorded) MKV audio file (default: %(default)s)",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        default="WPPAS",
        help="name for multiprocess logging (default: %(default)s)",
    )    
    parser.add_argument(
        "-l",
        "--logfile",
        type=str,
        default=None,
        help="output logfile (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="verbose (default: %(default)s)",
    )
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        default=False,
        help="use json for output results (default: %(default)s)",
    )    
    parser.add_argument("-st", 
        type=int, 
        default=0, 
        help="Sync track index (must be a mono track)"
    )

    args = parser.parse_args()


    #
    # set debug verbosity
    #
    if args.verbose:
        if args.logfile != None:
            logging.basicConfig(filename=args.logfile, encoding="utf-8", level=logging.INFO)
        else:
            logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


    #
    # setup log
    #
    # logger.info("-" * 80)
    # logger.info("SETUP:")
    # logger.info("-" * 80)

    # for p in args:
    #     logger.info("{} : {}".format(str(p), str(args)))

    #
    # select behavior: if we do not specify folder we expect full path for file names

    process_subfolders=False

    # if there is no folder specified we search for given files
    if(args.folder==None):
        args.folder=''

        # sanity check: file presence
        if not (os.path.isfile(os.path.join(args.folder,args.degraded))):
            logger.error("missing degraded file: {}".format(os.path.join(args.folder,args.degraded)))
            exit(1)

        if not (os.path.isfile(os.path.join(args.folder,args.reference))):
            logger.error("missing reference file: {}".format(os.path.join(args.folder,args.reference)))
            exit(1)
    else:
        process_subfolders=True


    # process subfodlers in parallel process
    if(process_subfolders==True):
        print("t.b.d")
        #process_all_recordings(args.folder, args)


    else:
        # single file processing

        # verify MKV structure as identical
        ref_filename = os.path.join(args.folder,args.reference)
        ref_media_info = get_media_info(ref_filename, print_result=False)

        deg_filename = os.path.join(args.folder,args.degraded)
        deg_media_info = get_media_info(deg_filename, print_result=False)

        try:
            # MATROSKA
            if ("matroska" in ref_media_info["format"]["format_name"]) or ("matroska" in deg_media_info["format"]["format_name"]) :
                # they mast be the same
                if(ref_media_info["format"]["format_name"] != deg_media_info["format"]["format_name"]) :
                    logger.error("input files of different types, must be the same")
                    exit(1)

                # must have the same number of tracks
                if(ref_media_info["format"]["nb_streams"] != deg_media_info["format"]["nb_streams"]) :
                    logger.error("input files with different numebr of streams, must be the same")
                    exit(1)

                # must have the same structure (i.e. channels per stream)
                for idx in np.arange(ref_media_info["format"]["nb_streams"]):
                    if (ref_media_info["streams"][idx]["channels"]!= deg_media_info["streams"][idx]["channels"]):
                        logger.error("input files differ in channels num [{} vs {}] for substream #{}".format(deg_media_info["streams"][idx]["channels"],ref_media_info["streams"][idx]["channels"]),idx)
                        exit(1)

            # WAV
            if ("wav" in ref_media_info["format"]["format_name"]) or ("wav" in deg_media_info["format"]["format_name"]) :
                logger.error("PPAS computation not yet implemented for native .WAV files")
                exit(1)
        except:
            logger.error("incorrect media info on given files")
            exit(1)


        # process single files
        try:         
            result = []
            process_recording_folder(args.folder, args, result)
        except KeyboardInterrupt:
            print("\nInterrupted by user")

        # clean exit
        restore_terminal()
