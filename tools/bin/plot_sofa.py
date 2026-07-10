#!/usr/bin/env python3

import argparse

import numpy as np
import matplotlib.pyplot as plt

from scipy.interpolate import griddata

import sofar
import pyfar as pf



def compute_metric(sofa, metric, receiver):

    ##########################################
    # Extract HRIR
    ##########################################

    ir = sofa.Data_IR[:, receiver, :]


    ##########################################
    # Frequency response
    ##########################################

    signal = pf.Signal(
        ir,
        sampling_rate=sofa.Data_SamplingRate
    )

    H = signal.freq
    magnitude = np.abs(H)


    ##########################################
    # Compute requested metric
    ##########################################

    if metric == "energy":

        value = np.sum(
            ir**2,
            axis=-1
        )

        gain_db = 10*np.log10(
            value + 1e-20
        )


    elif metric == "rms":

        value = np.sqrt(
            np.mean(
                magnitude**2,
                axis=-1
            )
        )

        gain_db = 20*np.log10(
            value + 1e-20
        )


    elif metric == "power":

        value = np.sum(
            magnitude**2,
            axis=-1
        )

        gain_db = 10*np.log10(
            value + 1e-20
        )


    elif metric == "mean_db":

        gain_db = np.mean(
            20*np.log10(
                magnitude + 1e-20
            ),
            axis=-1
        )


    else:

        raise ValueError(
            "Unknown metric"
        )


    return gain_db




def parse_scale(scale):

    """
    Parse scale argument.

    Examples:

        -s -10
            -> vmax=-10
               vmin=-50

        -s -30 -10
            -> vmin=-30
               vmax=-10
    """

    if scale is None:

        return None, None


    if len(scale) == 1:

        vmax = scale[0]
        vmin = vmax - 40


    elif len(scale) == 2:

        vmin = scale[0]
        vmax = scale[1]


    else:

        raise ValueError(
            "Scale accepts one or two values"
        )


    if vmin >= vmax:

        raise ValueError(
            "Scale minimum must be smaller than maximum"
        )


    return vmin, vmax




def interpolate_map(
    gain_db,
    az,
    el,
    AZ,
    EL
):

    ##########################################
    # Linear interpolation only
    #
    # No extrapolation
    ##########################################

    G = griddata(
        (az, el),
        gain_db,
        (AZ, EL),
        method="linear"
    )


    return G




def plot_map(
    G,
    az,
    el,
    title,
    args
):

    ##########################################
    # Color calibration
    ##########################################

    valid = ~np.isnan(G)


    if not np.any(valid):

        raise RuntimeError(
            "No valid interpolation points. "
            "Check SOFA coordinates."
        )


    if args.scale_min is not None:

        vmin = args.scale_min
        vmax = args.scale_max


    else:

        vmin, vmax = np.percentile(
            G[valid],
            [2,98]
        )



    ##########################################
    # Plot
    ##########################################

    cmap = plt.cm.viridis.copy()

    cmap.set_bad(
        color="white"
    )


    im = plt.imshow(
        G,
        extent=[
            180,
            -180,
            -90,
            90
        ],
        origin="lower",
        aspect="auto",
        cmap=cmap,
        vmin=vmin,
        vmax=vmax
    )



    ##########################################
    # Measurement points
    ##########################################

    if args.points:

        plt.scatter(
            az,
            el,
            s=5,
            c="black",
            alpha=0.5,
            label="SOFA measurements"
        )

        plt.legend()



    ##########################################
    # Labels
    ##########################################

    plt.xlabel(
        "Azimuth (deg)"
    )

    plt.ylabel(
        "Elevation (deg)"
    )


    plt.title(
        title
    )


    if(args.lines):
        plt.grid()


    plt.colorbar(
        im,
        label="dB"
    )




def main():

    ##########################################
    # CLI
    ##########################################

    parser = argparse.ArgumentParser(
        description=
        "Visualize broadband HRTF sensitivity from SOFA file"
    )


    parser.add_argument(
        "sofa_file",
        help="SOFA filename"
    )


    parser.add_argument(
        "-r",
        "--receiver",
        type=int,
        default=-1,
        choices=[-1,0,1],
        help=(
            "receiver channel: "
            "-1=both, 0=left, 1=right"
        )
    )


    parser.add_argument(
        "-m",
        "--metric",
        default="energy",
        choices=[
            "energy",
            "rms",
            "power",
            "mean_db"
        ],
        help="sensitivity metric"
    )


    parser.add_argument(
        "-g",
        "--grid",
        type=float,
        default=1,
        help="grid resolution in degrees"
    )


    parser.add_argument(
        "-s",
        "--scale",
        type=float,
        nargs="+",
        default=None,
        metavar="DB",
        help=(
            "Scale limits. "
            "One value sets maximum, "
            "two values set min and max."
        )
    )


    parser.add_argument(
        "-p",
        "--points",
        action="store_true",
        help="show SOFA measurement positions"
    )


    parser.add_argument(
        "-l",
        "--lines",
        default=False,
        action="store_true",
        help="show grid lines"
    )

    args = parser.parse_args()


    args.scale_min, args.scale_max = parse_scale(
        args.scale
    )



    ##########################################
    # Load SOFA
    ##########################################

    sofa = sofar.read_sofa(
        args.sofa_file
    )



    ##########################################
    # Source positions
    ##########################################

    positions = sofa.SourcePosition


    az = positions[:,0].copy()
    el = positions[:,1].copy()



    # SOFA azimuth calibration

    if np.max(az) > 180:

        az = (
            (az + 180) % 360
            - 180
        )



    ##########################################
    # Create plotting grid
    ##########################################

    azi_grid = np.arange(
        180,
        -180.1,
        -args.grid
    )


    ele_grid = np.arange(
        -90,
        90.1,
        args.grid
    )


    AZ, EL = np.meshgrid(
        azi_grid,
        ele_grid
    )



    ##########################################
    # Plot
    ##########################################

    if args.receiver == -1:

        fig, axes = plt.subplots(
            2,
            1,
            figsize=(12,10)
        )


        for receiver, ax, name in [
            (0, axes[0], "Left ear"),
            (1, axes[1], "Right ear")
        ]:

            gain_db = compute_metric(
                sofa,
                args.metric,
                receiver
            )


            G = interpolate_map(
                gain_db,
                az,
                el,
                AZ,
                EL
            )


            plt.sca(ax)


            plot_map(
                G,
                az,
                el,
                (
                    f"HRTF sensitivity map - {name}\n"
                    f"metric={args.metric}"
                ),
                args
            )


    else:

        gain_db = compute_metric(
            sofa,
            args.metric,
            args.receiver
        )


        G = interpolate_map(
            gain_db,
            az,
            el,
            AZ,
            EL
        )


        ear = (
            "Left ear"
            if args.receiver == 0
            else "Right ear"
        )


        plt.figure(
            figsize=(12,5)
        )


        plot_map(
            G,
            az,
            el,
            (
                f"HRTF sensitivity map - {ear}\n"
                f"metric={args.metric}"
            ),
            args
        )


    plt.tight_layout()

    plt.show()




if __name__ == "__main__":

    main()