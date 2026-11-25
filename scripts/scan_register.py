"""Put every scan into one frame, in feet, with the front of the house at low X.

Scans made in separate sessions each have their own origin and heading. After scan_prep each is
square to its walls, so only a quarter-turn and a shift in plan are left to find. The first scan
listed in project.json is the reference. Each other scan is tried at all four quarter-turns and
slid over the reference; the best overlap of blurred wall pictures wins. An inside scan and an
outside scan share no surfaces (one sees the inner wall faces, the other the outer), so the blur
is about a wall thickness wide and the result is good to a few inches, not better. Look at
register_check.png before trusting it.

Heights are not matched between scans: inside heights are above the floor, outside heights are
above the ground.

Reads   <project>/scans/derived/<id>_sq.npz, project.json ("front_turns": 0-3 turns the plan so
        the front faces low X; set it after looking at register_check.png)
Writes  <project>/scans/derived/model_frame.npz   every scan's points in feet in the model frame
        <project>/scans/derived/transforms.json, register_check.png

Run:  uv run pipeline.py run scan
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import ndimage, signal

import common
import house_geom as G

CELL = 0.05           # metres


def turn(p, k):
    for _ in range(k % 4):
        p = np.c_[-p[:, 1], p[:, 0]]
    return p


def picture(xy, lo, shape, blur):
    ij = np.floor((xy - lo) / CELL).astype(int)
    ok = (ij >= 0).all(1) & (ij < shape).all(1)
    g = np.zeros(shape, np.float32)
    np.add.at(g, (ij[ok, 0], ij[ok, 1]), 1)
    return ndimage.gaussian_filter(np.minimum(g, 5), blur / CELL)


def fit(ref_xy, xy, blur=0.12):
    """Quarter-turn k and shift that lay xy over ref_xy."""
    best = None
    for k in range(4):
        t = turn(xy, k)
        shift0 = np.median(ref_xy, 0) - np.median(t, 0)
        t0 = t + shift0
        lo = np.minimum(ref_xy.min(0), t0.min(0)) - 2.0
        hi = np.maximum(ref_xy.max(0), t0.max(0)) + 2.0
        shape = tuple(np.ceil((hi - lo) / CELL).astype(int))
        a, b = picture(ref_xy, lo, shape, blur), picture(t0, lo, shape, blur)
        c = signal.fftconvolve(a, b[::-1, ::-1], mode="same")
        i, j = np.unravel_index(np.argmax(c), c.shape)
        score = c[i, j] / np.sqrt((a ** 2).sum() * (b ** 2).sum())
        d = (np.array([i, j]) - np.array(shape) // 2) * CELL
        if best is None or score > best[0]:
            best = (float(score), k, shift0 + d)
    return best


def main():
    args = common.parser(__doc__).parse_args()
    pdir, project = common.project(args)
    out = pdir / "scans" / "derived"
    scans = [s for s in project.get("scans", []) if (out / f"{s['id']}_sq.npz").exists()]
    if not scans:
        sys.exit("Run scan_prep.py first.")
    data = {s["id"]: np.load(out / f"{s['id']}_sq.npz") for s in scans}
    walls = {k: d["xyz"][np.abs(d["nrm"][:, 2]) < 0.2][:, :2].astype(np.float64) for k, d in data.items()}
    ref = scans[0]["id"]
    T = {ref: {"turns": 0, "shift_m": [0.0, 0.0], "score": 1.0}}
    for s in scans[1:]:
        score, k, shift = fit(walls[ref], walls[s["id"]])
        if s.get("kind", "inside") != scans[0].get("kind", "inside"):
            # inside against outside: assume the same wall thickness on opposite sides and centre the two outlines
            t = turn(walls[s["id"]], k) + shift
            c = lambda p: (np.percentile(p, 0.5, axis=0) + np.percentile(p, 99.5, axis=0)) / 2
            nudge = c(walls[ref]) - c(t)
            if np.abs(nudge).max() < 0.5:
                shift = shift + nudge
        T[s["id"]] = {"turns": k, "shift_m": [float(shift[0]), float(shift[1])], "score": round(score, 3)}
        print(f"{s['id']}: {k} quarter-turns, shift {shift[0]:.2f}, {shift[1]:.2f} m, overlap score {score:.2f}")
    front = int(project.get("front_turns", 0))
    placed = {}
    for s in scans:
        d, t = data[s["id"]], T[s["id"]]
        xy = turn(turn(d["xyz"][:, :2].astype(np.float64), t["turns"]) + np.array(t["shift_m"]), front)
        n = turn(turn(d["nrm"][:, :2].astype(np.float64), t["turns"]), front)
        placed[s["id"]] = (xy, n)
    outside = [s["id"] for s in scans if s.get("kind") == "outside"]
    src = np.vstack([placed[i][0][np.abs(data[i]["nrm"][:, 2]) < 0.2] for i in (outside or [ref])])
    lo = np.percentile(src, 0.5, axis=0)
    lo = np.array([np.median(src[np.abs(src[:, i] - lo[i]) < 0.1, i]) for i in (0, 1)])      # the outermost wall face
    if not outside:
        lo -= 0.15                                                                           # an assumed 6 in wall
    xyz, nrm, sid, rgb = [], [], [], []
    for i, s in enumerate(scans):
        d = data[s["id"]]
        xy, n = placed[s["id"]]
        xyz.append(np.c_[(xy - lo) / common.FT, d["xyz"][:, 2] / common.FT])
        nrm.append(np.c_[n, d["nrm"][:, 2]])
        sid.append(np.full(len(xy), i, np.int8))
        rgb.append(d["rgb"])
    np.savez_compressed(out / "model_frame.npz", xyz=np.vstack(xyz).astype(np.float32), nrm=np.vstack(nrm).astype(np.float32),
                        scan=np.concatenate(sid), rgb=np.vstack(rgb), ids=np.array([s["id"] for s in scans]),
                        kinds=np.array([s.get("kind", "inside") for s in scans]),
                        ceiling_ft=float(data[ref]["ceiling"]) / common.FT, voxel_ft=float(data[ref]["voxel"]) / common.FT)
    G.dump(out / "transforms.json", {"reference": ref, "front_turns": front, "origin_m": lo.tolist(), "scans": T,
                                     "note": "squared scan -> quarter-turns -> shift -> front turns -> minus origin -> feet"})
    fig, ax = plt.subplots(figsize=(12, 9), dpi=110)
    for i, (s, col) in enumerate(zip(scans, ["#1f6fd0", "#d62728", "#2ca02c", "#9467bd"])):
        m = (np.concatenate(sid) == i) & (np.abs(np.vstack(nrm)[:, 2]) < 0.2)
        p = np.vstack(xyz)[m]
        ax.scatter(p[::2, 0], p[::2, 1], s=0.08, c=col, label=f"{s['id']} ({s.get('kind', 'inside')})")
    ax.set_aspect("equal")
    ax.grid(True, lw=0.3)
    ax.legend(markerscale=40, loc="upper right")
    ax.set_title("Walls of every scan in the model frame, feet. Front should be on the left (low X).")
    fig.savefig(out / "register_check.png", bbox_inches="tight")
    print(f"wrote {out / 'model_frame.npz'} and register_check.png")


if __name__ == "__main__":
    main()
