#!/usr/bin/env python3

import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tqdm import tqdm


# ============================================================
# Utilities
# ============================================================

def apply_minimum_bounds(ax, xs, ys, zs, min_limit=2.0):

    def bound(data):

        dmin = np.min(data)
        dmax = np.max(data)

        if dmin > -min_limit:
            dmin = -min_limit

        if dmax < min_limit:
            dmax = min_limit

        return dmin, dmax

    xmin, xmax = bound(xs)
    ymin, ymax = bound(ys)
    zmin, zmax = bound(zs)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_zlim(zmin, zmax)

    ax.set_box_aspect([
        xmax - xmin,
        ymax - ymin,
        zmax - zmin
    ])


def decimate_dataframe(df, max_points):

    n = len(df)

    if max_points <= 0 or max_points >= n:
        return df

    step = n / max_points

    indices = [int(i * step) for i in range(max_points)]

    return df.iloc[indices]

def plot_reference_frames(ax, df, scale=0.1, step=20):

    cols = [
        "rotation_11","rotation_12","rotation_13",
        "rotation_21","rotation_22","rotation_23",
        "rotation_31","rotation_32","rotation_33",
    ]

    if not all(c in df.columns for c in cols):
        return

    for i in range(0, len(df), step):

        r = df.iloc[i]

        p = np.array([r["x"], r["y"], r["z"]])

        R = np.array([
            [r["rotation_11"], r["rotation_12"], r["rotation_13"]],
            [r["rotation_21"], r["rotation_22"], r["rotation_23"]],
            [r["rotation_31"], r["rotation_32"], r["rotation_33"]],
        ])

        x_axis = R[:, 0]
        y_axis = R[:, 1]
        z_axis = R[:, 2]

        # X (red)
        ax.plot(*zip(p, p + scale * x_axis), color="red")

        # Y (green)
        ax.plot(*zip(p, p + scale * y_axis), color="green")

        # Z (blue)
        ax.plot(*zip(p, p + scale * z_axis), color="blue")



# ============================================================
# Worker
# ============================================================

def load_position_file(task):

    file, max_points = task

    try:

        # LOCATA files are whitespace separated
        df = pd.read_csv(
            file,
            sep=r"\s+"
        )

    except Exception as e:

        return {
            "error": f"{file}: {e}"
        }

    required = ["x", "y", "z"]

    if not all(c in df.columns for c in required):

        return {
            "error": f"{file}: missing x,y,z columns"
        }

    df = decimate_dataframe(df, max_points)

    return {
        "file": file,
        "label": file.stem.replace("position_", ""),
        "x": df["x"].to_numpy(),
        "y": df["y"].to_numpy(),
        "z": df["z"].to_numpy(),
        "df": df,
    }


# ============================================================
# Main
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="Plot all LOCATA trajectories from a given folder",

        epilog="""
examples:

  %(prog)s data/session01

  %(prog)s data/session01 -n 100 --no-points

  %(prog)s data/session01 -n 100 --frames --frames-step 10 --frames-scale 0.06
    """,

    formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "folder",
        help="LOCATA recording folder"
    )

    parser.add_argument(
        "-n",
        "--num-points",
        type=int,
        default=0,
        help="Maximum displayed points per trajectory "
             "(0 = all)"
    )

    parser.add_argument(
        "--frames",
        action="store_true",
        help="Display local reference frames"
    )

    parser.add_argument(
        "--no-points",
        action="store_true",
        help="Disable scatter points"
    )

    parser.add_argument(
        "-j",
        "--jobs",
        type=int,
        default=None,
        help="Number of parallel workers "
             "(default: CPU count)"
    )

    parser.add_argument(
        "--frames-scale",
        type=float,
        default=0.05,
        help="Reference frame scale factor "
             "(relative to trajectory size)"
    )

    parser.add_argument(
        "--frames-step",
        type=int,
        default=20,
        help="Plot one reference frame every N samples"
    )    

    args = parser.parse_args()

    folder = Path(args.folder)

    if not folder.exists():

        print(f"ERROR: Folder not found: {folder}")
        return

    # --------------------------------------------------------
    # Find all position files
    # --------------------------------------------------------

    files = sorted(folder.rglob("position*.txt"))

    if not files:

        print("No position files found.")
        return

    print(f"Found {len(files)} position files")

    # --------------------------------------------------------
    # Parallel loading
    # --------------------------------------------------------

    tasks = [
        (file, args.num_points)
        for file in files
    ]

    results = []

    with ProcessPoolExecutor(
        max_workers=args.jobs
    ) as executor:

        for result in tqdm(
            executor.map(load_position_file, tasks),
            total=len(tasks),
            desc="Loading trajectories"
        ):

            if "error" in result:

                print("Skipping:", result["error"])
                continue

            results.append(result)

    if not results:

        print("No valid trajectories loaded.")
        return

    print(f"Loaded {len(results)} trajectories")

    # --------------------------------------------------------
    # Figure
    # --------------------------------------------------------

    fig = plt.figure(figsize=(12, 10))

    ax = fig.add_subplot(
        111,
        projection="3d"
    )

    # --------------------------------------------------------
    # Colors
    # --------------------------------------------------------

    colors = plt.get_cmap("tab10")(
        np.linspace(0, 1, len(results))
    )

    all_x = []
    all_y = []
    all_z = []

    # --------------------------------------------------------
    # Plot trajectories
    # --------------------------------------------------------

    for idx, result in enumerate(
        tqdm(results, desc="Plotting")
    ):

        x = result["x"]
        y = result["y"]
        z = result["z"]

        df = result["df"]

        label = result["label"]

        color = colors[idx]

        all_x.extend(x)
        all_y.extend(y)
        all_z.extend(z)

        # ----------------------------------------------------
        # Line
        # ----------------------------------------------------

        ax.plot(
            x,
            y,
            z,
            linewidth=1.5,
            color=color,
            label=label
        )

        # ----------------------------------------------------
        # Scatter
        # ----------------------------------------------------

        if not args.no_points:

            ax.scatter(
                x,
                y,
                z,
                s=4,
                color=color
            )

        # ----------------------------------------------------
        # Start marker
        # ----------------------------------------------------

        ax.scatter(
            x[0],
            y[0],
            z[0],
            color="green",
            s=50
        )

        # ----------------------------------------------------
        # End marker
        # ----------------------------------------------------

        ax.scatter(
            x[-1],
            y[-1],
            z[-1],
            color="red",
            s=50
        )

        # ----------------------------------------------------
        # Labels
        # ----------------------------------------------------

        ax.text(
            x[0],
            y[0],
            z[0],
            f"{label}",
            fontsize=8
        )

        # ----------------------------------------------------
        # Reference frames
        # ----------------------------------------------------

        if args.frames and "source" in label.lower():

            xyz_range = max(
                x.max() - x.min(),
                y.max() - y.min(),
                z.max() - z.min()
            )

            frame_scale = args.frames_scale * xyz_range

            plot_reference_frames(
                ax,
                df,
                scale=frame_scale,
                step=args.frames_step
            )

    # --------------------------------------------------------
    # Bounds
    # --------------------------------------------------------

    apply_minimum_bounds(
        ax,
        np.array(all_x),
        np.array(all_y),
        np.array(all_z),
        min_limit=1.0
    )

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_title("LOCATA Audio Scene")

    ax.legend(
        loc="upper right",
        fontsize=8
    )

    plt.tight_layout()

    plt.show()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    main()
