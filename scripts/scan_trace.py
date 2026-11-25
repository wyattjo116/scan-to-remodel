"""Draft the existing floor plan from the registered scans.

What it does, on the inside scan(s):
  1. finds wall faces as peaks of wall points along X and along Y
  2. cuts the plan into a grid on those lines and keeps the cells that have a ceiling over them
  3. joins neighbouring cells unless the scan shows a wall between them: each joined group is a room
  4. looks along each wall between two rooms, and each outside wall, for gaps: a gap from the floor
     up is a door or an opening, a gap only at window height is a window
The outline is the outside scan's wall faces if there is one, else the rooms grown by a wall
thickness.

It is a draft. Rooms are rectangles on one grid, so walls off the grid, curves and bay windows
are missed; furniture and mirrors make false walls and false gaps; sill and head heights and the
roof are typed in as guesses and marked "estimated". Correct the draft by eye against
refs/plan-slice.png, save it as existing/house.json, then run scan_check.py.

Reads   <project>/scans/derived/model_frame.npz
Writes  <project>/existing/house.draft.json
        <project>/scans/derived/refs/plan-slice.png        wall points with a foot grid and the wall lines found
        <project>/scans/derived/refs/elevation-<side>.png  the outside scan seen from each side, if there is one

Run:  uv run pipeline.py run trace
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks
from shapely.geometry import box
from shapely.ops import unary_union

import common
import house_geom as G

BIN = 0.05


def face_lines(v, need):
    """Positions where wall points pile up along one axis."""
    e = np.arange(v.min() - 0.5, v.max() + 0.5, BIN)
    h = np.convolve(np.histogram(v, bins=e)[0], np.ones(3), "same")
    pk, _ = find_peaks(h, height=need, distance=int(0.25 / BIN))
    return [round(float(np.average(e[max(p - 2, 0):p + 3] + BIN / 2, weights=h[max(p - 2, 0):p + 3] + 1e-9)), 2) for p in pk]


def occupied(pts_along, lo, hi, step=0.25):
    """Which bins of [lo, hi] hold points."""
    n = max(int(round((hi - lo) / step)), 1)
    return np.histogram(pts_along, bins=np.linspace(lo, hi, n + 1))[0] > 0


def runs(empty, lo, step=0.25, least=2.0):
    """Stretches of empty bins at least `least` feet long, as (from, to)."""
    out, start = [], None
    for i, e in enumerate(list(empty) + [False]):
        if e and start is None:
            start = i
        if not e and start is not None:
            if (i - start) * step >= least:
                out.append((round(lo + start * step, 1), round(lo + i * step, 1)))
            start = None
    return out


def main():
    args = common.parser(__doc__).parse_args()
    pdir, project = common.project(args)
    out = pdir / "scans" / "derived"
    if not (out / "model_frame.npz").exists():
        sys.exit("Run the scan stage first.")
    d = np.load(out / "model_frame.npz")
    xyz, nrm, scan = d["xyz"].astype(np.float64), d["nrm"], d["scan"]
    kinds = list(d["kinds"])
    ceil = float(d["ceiling_ft"])
    inside = np.isin(scan, [i for i, k in enumerate(kinds) if k == "inside"])
    outside = ~inside
    if not inside.any():
        sys.exit("The draft needs at least one scan with \"kind\": \"inside\".")
    P, N = xyz[inside], nrm[inside]
    band = (P[:, 2] > 1.0) & (P[:, 2] < ceil - 0.5)
    wx = P[band & (np.abs(N[:, 0]) > 0.8)]            # faces whose normal is along X: lines of constant x
    wy = P[band & (np.abs(N[:, 1]) > 0.8)]
    per_ft2 = (1 / float(d["voxel_ft"])) ** 2
    need = per_ft2 * 2.5 * (ceil - 1.5) * 0.35           # a face at least about 2.5 ft long
    xs, ys = face_lines(wx[:, 0], need), face_lines(wy[:, 1], need)
    top = P[(P[:, 2] > ceil - 0.25) & (np.abs(N[:, 2]) > 0.8)]

    def wall_between(axis, at, lo, hi):
        """Share of the edge [lo, hi] on the line axis = at that has wall points, mid height or above doors."""
        w = wx if axis == 0 else wy
        near = w[np.abs(w[:, axis] - at) < 0.15]
        along = near[:, 1 - axis]
        mid = occupied(along[(near[:, 2] > 3.0) & (near[:, 2] < 5.5)], lo, hi).mean()
        high = occupied(along[near[:, 2] > min(7.6, ceil - 1.0)], lo, hi).mean()
        return max(mid, high)

    # grid cells with a ceiling over them
    nx, ny = len(xs) - 1, len(ys) - 1
    space = np.zeros((nx, ny), bool)
    for i in range(nx):
        for j in range(ny):
            m = (top[:, 0] > xs[i]) & (top[:, 0] < xs[i + 1]) & (top[:, 1] > ys[j]) & (top[:, 1] < ys[j + 1])
            area = (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
            space[i, j] = m.sum() > 0.5 * per_ft2 * area
    parent = {(i, j): (i, j) for i in range(nx) for j in range(ny) if space[i, j]}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for (i, j) in list(parent):
        if (i + 1, j) in parent and wall_between(0, xs[i + 1], ys[j], ys[j + 1]) < 0.5:
            parent[find((i, j))] = find((i + 1, j))
        if (i, j + 1) in parent and wall_between(1, ys[j + 1], xs[i], xs[i + 1]) < 0.5:
            parent[find((i, j))] = find((i, j + 1))
    groups = {}
    for c in parent:
        groups.setdefault(find(c), []).append(c)
    rooms = []
    for cells in groups.values():
        shape = unary_union([box(xs[i], ys[j], xs[i + 1], ys[j + 1]) for i, j in cells])
        shape = shape.simplify(0)
        if shape.area < 6:
            continue
        rs = [[round(b[0], 2), round(b[2], 2), round(b[1], 2), round(b[3], 2)] for b in G.to_boxes(shape)]
        merged = shape.bounds
        if abs(shape.area - box(*merged).area) < 0.1:
            rs = [[round(merged[0], 2), round(merged[2], 2), round(merged[1], 2), round(merged[3], 2)]]
        rooms.append((shape, rs))
    rooms.sort(key=lambda r: (round(r[0].bounds[0]), r[0].bounds[1]))

    # outline
    if outside.any():
        O, ON = xyz[outside], nrm[outside]
        ow = O[(np.abs(ON[:, 2]) < 0.2) & (O[:, 2] > 2.0)]
        ox = face_lines(ow[np.abs(ON[(np.abs(ON[:, 2]) < 0.2) & (O[:, 2] > 2.0)][:, 0]) > 0.8][:, 0], need * 0.5)
        oy = face_lines(ow[np.abs(ON[(np.abs(ON[:, 2]) < 0.2) & (O[:, 2] > 2.0)][:, 1]) > 0.8][:, 1], need * 0.5)
        outline = [[ox[0], ox[-1], oy[0], oy[-1]]]
        outline_note = "bounding rectangle of the outside scan's wall faces; split it into more rectangles if the house steps in or out"
    else:
        b = unary_union([r[0] for r in rooms]).bounds
        outline = [[round(b[0] - 0.5, 2), round(b[2] + 0.5, 2), round(b[1] - 0.5, 2), round(b[3] + 0.5, 2)]]
        outline_note = "no outside scan: the rooms grown by an assumed 6 in wall"
    ext = box(outline[0][0], outline[0][2], outline[0][1], outline[0][3])

    # openings
    doors, windows, openings = [], [], []

    def look(axis, at, face_a, face_b, lo, hi, exterior):
        """Gaps along one wall. axis 0: wall on a line of constant x. face_a/b are the two wall faces."""
        allp = P[(P[:, axis] > min(face_a, face_b) - 0.15) & (P[:, axis] < max(face_a, face_b) + 0.15) & (np.abs(N[:, axis]) > 0.8)]
        along, z = allp[:, 1 - axis], allp[:, 2]
        low = occupied(along[(z > 0.4) & (z < 2.0)], lo, hi)
        mid = occupied(along[(z > 4.5) & (z < 6.0)], lo, hi)
        run = "y" if axis == 0 else "x"
        for a, b in runs(~mid, lo, least=1.5):
            i0, i1 = int(round((a - lo) / 0.25)), int(round((b - lo) / 0.25))
            through = (~low[i0:i1]).mean() > 0.7
            o = {"run": run, "at": round(at, 2), "span": [a, b], "estimated": True}
            if through:
                if b - a > 4.0 and not exterior:
                    openings.append({**o, "id": f"opening-{len(openings) + 1}", "height": 7.0})
                else:
                    doors.append({**o, "id": f"door-{len(doors) + 1}", "height": 6.8, **({"exterior": True} if exterior else {})})
            elif not through and exterior:
                windows.append({**o, "id": f"window-{len(windows) + 1}", "sill": 2.5, "head": 6.8})

    for a_i, (sa, _) in enumerate(rooms):
        ax0, ay0, ax1, ay1 = sa.bounds
        for ba in G.to_boxes(sa):
            for sb, _ in rooms[a_i + 1:]:
                for bb in G.to_boxes(sb):
                    for axis in (0, 1):
                        lo_a, hi_a, lo_b, hi_b = (ba[0], ba[2], bb[0], bb[2]) if axis == 0 else (ba[1], ba[3], bb[1], bb[3])
                        o_lo = max((ba[1], bb[1]) if axis == 0 else (ba[0], bb[0]))
                        o_hi = min((ba[3], bb[3]) if axis == 0 else (ba[2], bb[2]))
                        if o_hi - o_lo < 2.0:
                            continue
                        for fa, fb in ((hi_a, lo_b), (hi_b, lo_a)):
                            if 0.05 < fb - fa < 1.5:
                                look(axis, (fa + fb) / 2, fa, fb, o_lo, o_hi, False)
            ex0, ey0, ex1, ey1 = ext.bounds
            for axis, face, edge, lo, hi in ((0, ba[0], ex0, ba[1], ba[3]), (0, ba[2], ex1, ba[1], ba[3]),
                                             (1, ba[1], ey0, ba[0], ba[2]), (1, ba[3], ey1, ba[0], ba[2])):
                if abs(face - edge) < 1.5:
                    look(axis, (face + edge) / 2, face, face, lo, hi, True)

    house = {
        "name": f"{project.get('name', 'House')} as it stands (draft from the scans)",
        "units": "ft",
        "source": "Drafted by scan_trace.py. Check every room, door and window against refs/plan-slice.png before use.",
        "wall": {"exterior": 0.5, "interior": 0.4},
        "levels": [{
            "id": "main", "label": "Main floor", "floor": 0.0, "ceiling": round(ceil, 2),
            "outline": outline, "outline_note": outline_note,
            "rooms": [{"id": f"room-{i + 1}", "label": f"Room {i + 1}", "type": "",
                       **({"rect": rs[0]} if len(rs) == 1 else {"rects": rs})} for i, (_, rs) in enumerate(rooms)],
            "doors": doors, "openings": openings, "windows": windows}],
        "porches": [],
        "roofs": [{"id": "main", "rect": outline[0], "type": "gable", "ridge": "x" if outline[0][1] - outline[0][0] >= outline[0][3] - outline[0][2] else "y",
                   "pitch": 6, "overhang": 1.0, "base": round(ceil, 2), "estimated": True,
                   "note": "A guess. Phone scans from the ground do not see the roof."}],
        "grade": -1.5, "grade_note": "A guess; measure the floor height above the ground outside.",
    }
    G.dump(pdir / "existing" / "house.draft.json", house)

    refs = out / "refs"
    refs.mkdir(exist_ok=True)
    allw = P[band & (np.abs(N[:, 2]) < 0.3)]
    x0, x1, y0, y1 = allw[:, 0].min() - 3, allw[:, 0].max() + 3, allw[:, 1].min() - 3, allw[:, 1].max() + 3
    fig, ax = plt.subplots(figsize=((x1 - x0) / 3, (y1 - y0) / 3), dpi=120)
    ax.scatter(allw[:, 0], allw[:, 1], s=0.03, c="k")
    if outside.any():
        ax.scatter(ow[::2, 0], ow[::2, 1], s=0.03, c="#b03030")
    for v in xs:
        ax.axvline(v, color="#1f6fd0", lw=0.3)
        ax.text(v, y1 - 0.2, f"{v:g}", rotation=90, fontsize=5, color="#1f6fd0", va="top", ha="right")
    for v in ys:
        ax.axhline(v, color="#1f6fd0", lw=0.3)
        ax.text(x0 + 0.2, v, f"{v:g}", fontsize=5, color="#1f6fd0", va="bottom")
    for i, (s, _) in enumerate(rooms):
        c = max(G.polys(s), key=lambda p: p.area).centroid
        ax.text(c.x, c.y, f"room-{i + 1}\n{s.area:.0f} sq ft", ha="center", va="center", fontsize=7, color="#2a7a2a")
    ax.set_xticks(np.arange(np.floor(x0), x1, 5))
    ax.set_yticks(np.arange(np.floor(y0), y1, 5))
    ax.grid(True, lw=0.2)
    ax.set_aspect("equal")
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_title("Wall points between 1 ft and the ceiling (black: inside scan, red: outside). Blue: wall faces found. Feet.", fontsize=8)
    fig.savefig(refs / "plan-slice.png", bbox_inches="tight")
    plt.close(fig)
    if outside.any():
        for side, axis, sign in (("front", 0, -1), ("rear", 0, 1), ("right", 1, -1), ("left", 1, 1)):
            m = np.abs(ON[:, axis]) > 0.8
            q = O[m]
            mid = (q[:, axis].min() + q[:, axis].max()) / 2
            q = q[(q[:, axis] - mid) * sign > 0]
            fig, ax = plt.subplots(figsize=(12, 5), dpi=110)
            ax.scatter(q[:, 1 - axis], q[:, 2], s=0.05, c="k")
            ax.set_aspect("equal")
            ax.grid(True, lw=0.2)
            ax.set_title(f"Outside scan, {side} wall (low X is the front). Feet; height above the ground.", fontsize=9)
            fig.savefig(refs / f"elevation-{side}.png", bbox_inches="tight")
            plt.close(fig)
    print(f"draft: {len(rooms)} rooms, {len(doors)} doors, {len(openings)} openings, {len(windows)} windows, "
          f"ceiling {G.ftin(ceil)}, outline {G.ftin(outline[0][1] - outline[0][0])} by {G.ftin(outline[0][3] - outline[0][2])}")
    print(f"wrote {pdir / 'existing' / 'house.draft.json'} and {refs / 'plan-slice.png'}")


if __name__ == "__main__":
    main()
