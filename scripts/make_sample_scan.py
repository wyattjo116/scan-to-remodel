"""Make two made-up phone scans of the sample house, so the scan steps can be tried with no phone.

Reads   <project>/existing/house.json
Writes  <project>/scans/sample-inside.ply, sample-outside.ply   (binary PLY, metres, y up,
        each turned and shifted the way two separate scans would be)

The points are sampled from the house file with about 1 cm of noise. Real scans are worse:
they drift between rooms, miss what furniture hides and never see the roof.

Run:  uv run pipeline.py run sample-scan -- --project examples/sample-house
"""
from __future__ import annotations

import numpy as np

import common
import house_geom as G

STEP = 0.13           # feet between sample points (about 4 cm)
rng = np.random.default_rng(7)


def grid(a0, a1, b0, b1):
    a = np.arange(a0 + STEP / 2, a1, STEP)
    b = np.arange(b0 + STEP / 2, b1, STEP)
    A, B = np.meshgrid(a, b)
    return A.ravel(), B.ravel()


def in_hole(o, z0, along, z):
    a, b = sorted(o["span"])
    top = z0 + (o.get("head") or o.get("height") or 6.8)
    bot = z0 + (o.get("sill", 0.0) if o["kind"] == "window" else 0.0)
    return (along > a) & (along < b) & (z > bot) & (z < top)


def face(run, at, a0, a1, z0, z1, holes, zfloor):
    """Points on a vertical face. run 'x': the face runs along X at y = at."""
    s, z = grid(a0, a1, z0, z1)
    keep = np.ones(len(s), bool)
    for o in holes:
        if o["run"] == run and abs(o["at"] - at) < G.HALF_CUT:
            keep &= ~in_hole(o, zfloor, s, z)
    s, z = s[keep], z[keep]
    return np.c_[s, np.full(len(s), at), z] if run == "x" else np.c_[np.full(len(s), at), s, z]


def inside(house):
    pts = []
    for lv in house["levels"]:
        z0, z1 = lv["floor"], lv["floor"] + lv["ceiling"]
        holes = G.all_openings(lv)
        for r in lv["rooms"]:
            for b in G.to_boxes(G.room_shape(r)):
                x0, y0, x1, y1 = b
                for at in (y0, y1):
                    pts.append(face("x", at, x0, x1, z0, z1, holes, z0))
                for at in (x0, x1):
                    pts.append(face("y", at, y0, y1, z0, z1, holes, z0))
                for z in (z0, z1):
                    a, c = grid(x0, x1, y0, y1)
                    pts.append(np.c_[a, c, np.full(len(a), z)])
        for o in holes:                      # the floor carries on through doorways
            if o["kind"] != "window":
                x0, y0, x1, y1 = G.cut_rect(o, 0.3).bounds
                a, c = grid(x0, x1, y0, y1)
                pts.append(np.c_[a, c, np.full(len(a), z0)])
    return np.vstack(pts)


def outside(house):
    pts = []
    grade = house.get("grade", -1.0)
    lv = house["levels"][0]
    holes = [o for o in G.all_openings(lv)]
    top = lv["floor"] + lv["ceiling"]
    for p in G.polys(G.outline(lv)):
        xy = list(p.exterior.coords)
        for (xa, ya), (xb, yb) in zip(xy, xy[1:]):
            if abs(ya - yb) < 1e-6:
                pts.append(face("x", ya, min(xa, xb), max(xa, xb), grade, top, holes, lv["floor"]))
            else:
                pts.append(face("y", xa, min(ya, yb), max(ya, yb), grade, top, holes, lv["floor"]))
    x0, y0, x1, y1 = G.outline(lv).bounds
    a, c = grid(x0 - 8, x1 + 8, y0 - 8, y1 + 8)
    out = ~((a > x0) & (a < x1) & (c > y0) & (c < y1))
    pts.append(np.c_[a[out], c[out], np.full(out.sum(), grade)])
    return np.vstack(pts)


def write_ply(path, model_ft, yaw_deg, shift, colour):
    p = model_ft * common.FT + rng.normal(0, 0.01, model_ft.shape)
    xyz = np.c_[p[:, 0], p[:, 2], -p[:, 1]]                       # y up, a right-handed top view
    a = np.radians(yaw_deg)
    R = np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])
    xyz = xyz @ R.T + np.array(shift)
    rec = np.zeros(len(xyz), dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("r", "u1"), ("g", "u1"), ("b", "u1")])
    rec["x"], rec["y"], rec["z"] = xyz.T
    rec["r"], rec["g"], rec["b"] = colour
    head = ("ply\nformat binary_little_endian 1.0\ncomment made-up sample scan\n"
            f"element vertex {len(rec)}\nproperty float x\nproperty float y\nproperty float z\n"
            "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(head.encode())
        f.write(rec.tobytes())
    print(f"wrote {path} ({len(rec):,} points)")


def main():
    args = common.parser(__doc__).parse_args()
    pdir, _ = common.project(args)
    house = G.load(pdir / "existing" / "house.json")
    write_ply(pdir / "scans" / "sample-inside.ply", inside(house), 17.0, (2.1, 1.35, -3.4), (200, 190, 175))
    write_ply(pdir / "scans" / "sample-outside.ply", outside(house), -32.0, (-6.0, 1.1, 4.2), (170, 180, 190))


if __name__ == "__main__":
    main()
