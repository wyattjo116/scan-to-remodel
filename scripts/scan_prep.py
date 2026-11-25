"""Thin each raw scan, square it to its walls and find its floor.

Reads   the PLY files named in <project>/project.json under "scans"
        (Modelar exports are metric and gravity-aligned with y up; set "up": "z" for other apps)
Writes  <project>/scans/derived/<id>_sq.npz    plan x, y and height h in metres, normals, colour
        <project>/scans/derived/<id>_views.png top view of walls, and a side view

Only a turn about the vertical is solved: phone scans already know which way is down.
Heights are measured from the scan's own floor (inside scans) or ground (outside scans).

Run:  uv run pipeline.py run scan
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.spatial import cKDTree

import common

VOXEL = 0.03
TYPES = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8", "uchar": "u1", "uint8": "u1", "char": "i1",
         "int8": "i1", "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2", "int": "<i4", "int32": "<i4",
         "uint": "<u4", "uint32": "<u4"}


def read_ply(path):
    """xyz (N, 3) and rgb (N, 3) from a binary little-endian or ASCII PLY. Only the vertex element is read."""
    with open(path, "rb") as f:
        head = f.read(8192)
    end = head.index(b"end_header") + len(b"end_header")
    end += 2 if head[end:end + 2] == b"\r\n" else 1
    lines = head[:end].decode("ascii", "replace").splitlines()
    fmt = next(l.split()[1] for l in lines if l.startswith("format"))
    n, props, in_vertex = 0, [], False
    for l in lines:
        t = l.split()
        if t[:1] == ["element"]:
            in_vertex = t[1] == "vertex"
            n = int(t[2]) if in_vertex else n
        elif t[:1] == ["property"] and in_vertex:
            if t[1] == "list":
                sys.exit(f"{path}: list properties on vertices are not supported")
            props.append((t[2], TYPES[t[1]]))
    if fmt == "ascii":
        d = np.loadtxt(path, skiprows=len(lines), max_rows=n)
        d = {name: d[:, i] for i, (name, _) in enumerate(props)}
    elif fmt == "binary_little_endian":
        d = np.memmap(path, dtype=np.dtype(props), mode="r", offset=end, shape=(n,))
    else:
        sys.exit(f"{path}: PLY format {fmt} is not supported; export binary little-endian or ASCII")
    xyz = np.c_[d["x"], d["y"], d["z"]].astype(np.float64)
    names = [p[0] for p in props]
    rgb = np.c_[d["red"], d["green"], d["blue"]].astype(np.uint8) if "red" in names else np.full((n, 3), 180, np.uint8)
    return xyz, rgb


def thin(xyz, rgb, voxel):
    """One point per voxel."""
    q = np.floor((xyz - xyz.min(0)) / voxel).astype(np.int64)
    key = (q[:, 0] << 42) | (q[:, 1] << 21) | q[:, 2]
    _, idx = np.unique(key, return_index=True)
    return xyz[idx], rgb[idx]


def normals(xyz, k=12):
    """Surface direction at each point from its k nearest neighbours."""
    tree = cKDTree(xyz)
    out = np.empty_like(xyz)
    for s in range(0, len(xyz), 200_000):
        _, nb = tree.query(xyz[s:s + 200_000], k=k, workers=-1)
        p = xyz[nb]
        p = p - p.mean(1, keepdims=True)
        w, v = np.linalg.eigh(np.einsum("nki,nkj->nij", p, p))
        out[s:s + 200_000] = v[:, :, 0]
    return out


def wall_yaw(nx, ny):
    """Angle (mod 90 degrees) the wall normals make with +x: histogram peak, then a mean near it."""
    th = np.degrees(np.arctan2(ny, nx)) % 90
    h, e = np.histogram(th, bins=180, range=(0, 90))
    h = np.convolve(np.r_[h, h, h], np.ones(5), "same")[180:360]
    peak = e[np.argmax(h)] + 0.25
    d = (th - peak + 45) % 90 - 45
    return peak + d[np.abs(d) < 4].mean()


def level_heights(h, kind):
    """Floor (or ground) and ceiling from the heights of horizontal surfaces."""
    c, e = np.histogram(h, bins=np.arange(h.min() - 0.02, h.max() + 0.04, 0.02))
    c = np.convolve(c, np.ones(3), "same")
    strong = np.where(c > 0.25 * c.max())[0]
    lo, hi = e[strong[0]] + 0.01, e[strong[-1]] + 0.01
    return h[np.abs(h - lo) < 0.05].mean(), h[np.abs(h - hi) < 0.05].mean()


def sharpen(xy, yaw):
    """Fine-tune the turn: the right one stacks wall points into the narrowest lines."""
    best = (0.0, yaw)
    for trial in np.arange(yaw - 0.6, yaw + 0.601, 0.05):
        a = np.radians(-trial)
        x = xy[:, 0] * np.cos(a) - xy[:, 1] * np.sin(a)
        y = xy[:, 0] * np.sin(a) + xy[:, 1] * np.cos(a)
        score = sum((np.histogram(v, bins=np.arange(v.min(), v.max() + 0.02, 0.02))[0].astype(float) ** 2).sum() for v in (x, y))
        best = max(best, (score, trial))
    return best[1]


def main():
    args = common.parser(__doc__).parse_args()
    pdir, project = common.project(args)
    out = pdir / "scans" / "derived"
    out.mkdir(parents=True, exist_ok=True)
    scans = [s for s in project.get("scans", []) if (pdir / s["file"]).exists()]
    if not scans:
        sys.exit("No scan files found. List them under \"scans\" in project.json and put the PLY files in scans/.")
    for s in scans:
        xyz, rgb = read_ply(pdir / s["file"])
        raw = len(xyz)
        xyz, rgb = thin(xyz, rgb, VOXEL)
        if s.get("up", "y") == "y":                    # to plan x, plan y, height; a true top view
            xyz = np.c_[xyz[:, 0], -xyz[:, 2], xyz[:, 1]]
        nrm = normals(xyz)
        wall = np.abs(nrm[:, 2]) < 0.2
        flat = np.abs(nrm[:, 2]) > 0.9
        yaw = sharpen(xyz[wall][::2, :2], wall_yaw(nrm[wall, 0], nrm[wall, 1]))
        a = np.radians(-yaw)
        R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1]])
        xyz, nrm = xyz @ R.T, nrm @ R.T
        floor, ceiling = level_heights(xyz[flat, 2], s.get("kind", "inside"))
        xyz[:, 2] -= floor
        np.savez_compressed(out / f"{s['id']}_sq.npz", xyz=xyz.astype(np.float32), nrm=nrm.astype(np.float32), rgb=rgb,
                            yaw_deg=yaw, voxel=VOXEL, ceiling=ceiling - floor)
        fig, ax = plt.subplots(1, 2, figsize=(14, 6), dpi=110)
        w = xyz[wall]
        ax[0].scatter(w[::3, 0], w[::3, 1], s=0.05, c="k")
        ax[0].set_aspect("equal")
        ax[0].set_title(f"{s['id']}: walls from above, squared (turned {yaw:.1f} deg), metres")
        ax[1].scatter(xyz[::5, 0], xyz[::5, 2], s=0.05, c="k")
        ax[1].set_aspect("equal")
        ax[1].set_title("side view; height 0 is the floor" if s.get("kind", "inside") == "inside" else "side view; height 0 is the ground")
        fig.savefig(out / f"{s['id']}_views.png", bbox_inches="tight")
        plt.close(fig)
        print(f"{s['id']}: {raw:,} points -> {len(xyz):,}; turned {yaw:.2f} deg; "
              f"{'ceiling' if s.get('kind', 'inside') == 'inside' else 'highest flat surface'} {ceiling - floor:.2f} m above the "
              f"{'floor' if s.get('kind', 'inside') == 'inside' else 'ground'}")


if __name__ == "__main__":
    main()
