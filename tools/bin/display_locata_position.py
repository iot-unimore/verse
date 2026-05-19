#!/usr/bin/env python3

import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def apply_minimum_bounds(ax, x, y, z, min_limit=2.0):

    def bound(data):
        dmin = data.min()
        dmax = data.max()

        # expand to at least [-min_limit, +min_limit]
        if dmin > -min_limit:
            dmin = -min_limit
        if dmax < min_limit:
            dmax = min_limit

        return dmin, dmax

    xmin, xmax = bound(x)
    ymin, ymax = bound(y)
    zmin, zmax = bound(z)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_zlim(zmin, zmax)

    ax.set_box_aspect([xmax - xmin, ymax - ymin, zmax - zmin])

def symmetric_min_bounds(ax, x, y, z, min_limit=2.0):

    def sym_range(data):
        m = max(abs(data.min()), abs(data.max()), min_limit)
        return -m, m

    xmin, xmax = sym_range(x)
    ymin, ymax = sym_range(y)
    zmin, zmax = sym_range(z)

    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_zlim(zmin, zmax)

    ax.set_box_aspect([1, 1, 1])    

def plot_reference_frames(ax, df, scale=1.0):
    """
    Plot local reference frames using rotation matrix columns.

    Colors:
        X axis -> green
        Y axis -> blue
        Z axis -> red
    """

    required_cols = [
        "rotation_11", "rotation_12", "rotation_13",
        "rotation_21", "rotation_22", "rotation_23",
        "rotation_31", "rotation_32", "rotation_33",
    ]

    # Check availability
    for col in required_cols:
        if col not in df.columns:
            return

    n = len(df)

    if n == 0:
        return

    # Plot only 1/10 of displayed points
    num_frames = max(1, n // 10)

    step = max(1, n // num_frames)

    indices = range(0, n, step)

    for idx in indices:
        row = df.iloc[idx]

        px = row["x"]
        py = row["y"]
        pz = row["z"]

        # Rotation matrix
        R = np.array([
            [row["rotation_11"], row["rotation_12"], row["rotation_13"]],
            [row["rotation_21"], row["rotation_22"], row["rotation_23"]],
            [row["rotation_31"], row["rotation_32"], row["rotation_33"]],
        ])

        # Columns are local axes in world coordinates
        x_axis = R[:, 0]
        y_axis = R[:, 1]
        z_axis = R[:, 2]

        # X axis (green)
        ax.plot(
            [px, px + scale * x_axis[0]],
            [py, py + scale * x_axis[1]],
            [pz, pz + scale * x_axis[2]],
            color="red",
            linewidth=1.5
        )

        # Y axis (blue)
        ax.plot(
            [px, px + scale * y_axis[0]],
            [py, py + scale * y_axis[1]],
            [pz, pz + scale * y_axis[2]],
            color="green",
            linewidth=1.5
        )

        # Z axis (red)
        ax.plot(
            [px, px + scale * z_axis[0]],
            [py, py + scale * z_axis[1]],
            [pz, pz + scale * z_axis[2]],
            color="blue",
            linewidth=1.5
        )



def decimate_dataframe(df, max_points):
    """
    Reduce the number of displayed points uniformly.

    max_points = 0  -> keep all points
    """
    n = len(df)

    if max_points <= 0 or max_points >= n:
        return df

    # Uniform sampling
    step = n / max_points

    indices = [int(i * step) for i in range(max_points)]

    return df.iloc[indices]


def main():
    parser = argparse.ArgumentParser(
        description="3D plot viewer for x,y,z CSV/TSV files"
    )

    parser.add_argument(
        "filename",
        help="Input CSV/TSV file"
    )

    parser.add_argument(
        "-n",
        "--num-points",
        type=int,
        default=0,
        help="Maximum number of points to display "
             "(0 = all points, default: 0)"
    )

    args = parser.parse_args()

    # Read file with automatic separator detection
    df = pd.read_csv(args.filename, sep=None, engine="python")

    # Validate required columns
    required = ["x", "y", "z"]

    for col in required:
        if col not in df.columns:
            print(f"ERROR: Missing required column '{col}'")
            sys.exit(1)

    original_count = len(df)

    # Decimation
    df = decimate_dataframe(df, args.num_points)

    displayed_count = len(df)

    print(f"Loaded points   : {original_count}")
    print(f"Displayed points: {displayed_count}")

    x = df["x"]
    y = df["y"]
    z = df["z"]

    # Create figure
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")

    # Plot line
    ax.plot(x, y, z, linewidth=0.8)

    # Plot points
    ax.scatter(x, y, z, s=2)

    # Start point (green)
    ax.scatter(
        x.iloc[0],
        y.iloc[0],
        z.iloc[0],
        color="green",
        s=100,
        label="Start"
    )

    # End point (red)
    ax.scatter(
        x.iloc[-1],
        y.iloc[-1],
        z.iloc[-1],
        color="red",
        s=100,
        label="End"
    )

    # Optional text labels
    ax.text(
        x.iloc[0],
        y.iloc[0],
        z.iloc[0],
        " Start",
        color="green"
    )

    ax.text(
        x.iloc[-1],
        y.iloc[-1],
        z.iloc[-1],
        " End",
        color="red"
    )

    # Labels
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    ax.set_title("3D Plot")


    # -------------------------------------------------
    # Plot reference frames if rotation matrix exists
    # -------------------------------------------------

    xyz_range = max(
        x.max() - x.min(),
        y.max() - y.min(),
        z.max() - z.min()
    )

    frame_scale = 0.03 * xyz_range

    plot_reference_frames(
        ax,
        df,
        scale=frame_scale
    )

    apply_minimum_bounds(ax, x, y, z, min_limit=1.0)

    symmetric_min_bounds(ax, x, y, z, min_limit=1.0)
    
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()

