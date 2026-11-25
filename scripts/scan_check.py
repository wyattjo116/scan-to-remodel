"""Compare the existing-house file with the scans, and say how far apart they are.

Reads   <project>/existing/house.json (or house.draft.json with --draft), scans/derived/model_frame.npz
Writes  <project>/existing/scan-check.png     the plan's walls drawn over the scan's wall points
        <project>/existing/scan-check.json    how far the scan's wall points are from the drawn wall faces

Carry these numbers into anything that quotes a dimension of the house: they are the accuracy of
the plan against the scan, and the scan has its own error on top (phone scans drift between rooms).

Run:  uv run pipeline.py run scan-check
"""
from __future__ import annotations

import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shapely

import common
import house_geom as G
from plans import patch


def main():
    ap = common.parser(__doc__)
    ap.add_argument("--draft", action="store_true", help="check house.draft.json instead of house.json")
    args = ap.parse_args()
    pdir, _ = common.project(args)
    f = pdir / "existing" / ("house.draft.json" if args.draft else "house.json")
    npz = pdir / "scans" / "derived" / "model_frame.npz"
    if not f.exists() or not npz.exists():
        sys.exit(f"Need {f} and {npz}.")
    house = G.load(f)
    lv = house["levels"][0]
    d = np.load(npz)
    xyz, nrm, scan, kinds = d["xyz"].astype(np.float64), d["nrm"], d["scan"], list(d["kinds"])
    ceil = float(d["ceiling_ft"])
    walls = G.walls(lv)
    report = {"file": f.name, "scans": {}}
    fig, ax = plt.subplots(figsize=(14, 10), dpi=110)
    pp = patch(walls, fc="#ffd9a0", ec="#c96a00", lw=0.6)
    if pp:
        ax.add_patch(pp)
    rng = np.random.default_rng(0)
    for i, kind in enumerate(kinds):
        m = (scan == i) & (np.abs(nrm[:, 2]) < 0.2) & (xyz[:, 2] > (1.0 if kind == "inside" else 2.5)) & (xyz[:, 2] < ceil - 0.5)
        p = xyz[m][:, :2]
        if not len(p):
            continue
        sub = p[rng.choice(len(p), min(len(p), 60_000), replace=False)]
        dist = shapely.distance(shapely.points(sub), walls.boundary) * 12
        report["scans"][str(d["ids"][i])] = {
            "kind": kind, "points_checked": int(len(sub)), "median_in": round(float(np.median(dist)), 2),
            "p90_in": round(float(np.percentile(dist, 90)), 2), "share_within_2in": round(float((dist < 2).mean()), 3),
            "share_beyond_6in": round(float((dist > 6).mean()), 3)}
        ax.scatter(sub[:, 0], sub[:, 1], s=0.15, c="k" if kind == "inside" else "#b03030")
        far = sub[dist > 6]
        ax.scatter(far[:, 0], far[:, 1], s=1.5, c="#d000d0")
        r = report["scans"][str(d["ids"][i])]
        print(f"{d['ids'][i]} ({kind}): median {r['median_in']} in, 90% within {r['p90_in']} in, "
              f"{r['share_beyond_6in']:.1%} of points more than 6 in from any drawn wall face")
    ax.set_aspect("equal")
    ax.grid(True, lw=0.2)
    ax.set_title("Orange: walls as drawn. Black / red: scan wall points (inside / outside). Magenta: more than 6 in from a drawn wall. Feet.",
                 fontsize=9)
    fig.savefig(pdir / "existing" / "scan-check.png", bbox_inches="tight")
    report["note"] = "Distance from scan wall points to the nearest drawn wall face. Magenta clusters are walls missing from the plan, furniture, or scan drift."
    G.dump(pdir / "existing" / "scan-check.json", report)


if __name__ == "__main__":
    main()
