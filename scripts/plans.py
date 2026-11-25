"""Floor plans, areas, checks and the cost estimate for the existing house and each variant.

Reads   <project>/existing/house.json, <project>/variants/<id>/variant.json,
        <project>/project.json, <project>/rates.json
Writes  plan-<level>.png and plan-<level>.dxf   beside each house file (feet and inches)
        summary.json                            areas, checks, and for a variant the cost
        README.md                               the same in words, for a variant
        <project>/variants/README.md            the variants side by side

Run:  uv run pipeline.py run plans [-- existing | <variant id> | all]
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import ezdxf
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, PathPatch
from matplotlib.path import Path as MPath

import common
import house_geom as G

KEPT, NEW, DEMO = "#4d4d4d", "#1f6fd0", "#d62728"
TINT = {"living": "#fff4d6", "dining": "#fff4d6", "kitchen": "#fdebd0", "bedroom": "#e3efe0", "office": "#e6e9f5", "bath": "#dff1f5",
        "hall": "#f3f3f3", "stair": "#ececec", "closet": "#f1e9df", "utility": "#f1e9df", "porch": "#efefe6",
        "void": "#ffffff"}


def patch(g, **kw):
    verts, codes = [], []
    for p in G.polys(g):
        for ring in [p.exterior, *p.interiors]:
            xy = list(ring.coords)
            verts += xy
            codes += [MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY]
    return PathPatch(MPath(verts, codes), **kw) if verts else None


def draw_level(ax, house, lv, cmp_, project, title):
    out_ = G.outline(lv)
    for p in house.get("porches", []):
        if lv is house["levels"][0]:
            x0, x1, y0, y1 = p["rect"]
            ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, fc=TINT["porch"], ec="#888", lw=0.8, ls="--"))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, "Porch", ha="center", va="center", fontsize=7, color="#555", rotation=90 if (y1 - y0) > (x1 - x0) else 0)
    for r in lv.get("rooms", []):
        s = G.room_shape(r)
        pp = patch(s, fc=TINT.get(r.get("type", ""), "#fafafa"), ec="none")
        if pp:
            ax.add_patch(pp)
    walls = G.walls(lv)
    holes = [G.cut_rect(o).intersection(walls) for o in G.all_openings(lv)]
    if cmp_:
        for key, col, kw in (("kept", KEPT, {}), ("new", NEW, {}),
                             ("demolished", DEMO, {"alpha": 0.35, "hatch": "////"})):
            g = cmp_[key]
            for h in holes:
                if key != "demolished":
                    g = g.difference(h)
            pp = patch(g, fc=col if key != "demolished" else "none", ec=col, lw=0.4, **kw)
            if pp:
                ax.add_patch(pp)
    else:
        g = walls
        for h in holes:
            g = g.difference(h)
        pp = patch(g, fc=KEPT, ec=KEPT, lw=0.4)
        if pp:
            ax.add_patch(pp)
    for o in G.all_openings(lv):
        a, b = sorted(o["span"])
        at, t = o["at"], 0.25
        horiz = o["run"] == "x"
        if o["kind"] == "window":
            for d in (-0.08, 0.08):
                xs, ys = ([a, b], [at + d, at + d]) if horiz else ([at + d, at + d], [a, b])
                ax.plot(xs, ys, color="#1a7fa8", lw=1.0)
        elif o["kind"] == "door":
            w = b - a
            if horiz:
                ax.plot([a, a], [at, at + w], color="#7a4a1e", lw=0.9)
                ax.add_patch(Arc((a, at), 2 * w, 2 * w, theta1=0, theta2=90, color="#7a4a1e", lw=0.5))
            else:
                ax.plot([at, at + w], [a, a], color="#7a4a1e", lw=0.9)
                ax.add_patch(Arc((at, a), 2 * w, 2 * w, theta1=0, theta2=90, color="#7a4a1e", lw=0.5))
        else:
            xs, ys = ([a, b], [at, at]) if horiz else ([at, at], [a, b])
            ax.plot(xs, ys, color="#999", lw=0.6, ls=":")
    for r in lv.get("rooms", []):
        s = G.room_shape(r)
        big = max(G.polys(s), key=lambda p: p.area)
        x0, y0, x1, y1 = big.bounds
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, f"{r.get('label', r['id'])}\n{G.ftin(x1 - x0)} x {G.ftin(y1 - y0)}\n{s.area:.0f} sq ft",
                ha="center", va="center", fontsize=6.5, linespacing=1.3)
    st = house.get("stair")
    if st and lv["id"] in (st.get("from"), st.get("to")):
        x0, x1, y0, y1 = st["rect"]
        along_x = (x1 - x0) >= (y1 - y0)
        n = 14
        for i in range(1, n):
            f = i / n
            if along_x:
                ax.plot([x0 + f * (x1 - x0)] * 2, [y0, y1], color="#999", lw=0.4)
            else:
                ax.plot([x0, x1], [y0 + f * (y1 - y0)] * 2, color="#999", lw=0.4)
    X0, Y0, X1, Y1 = out_.bounds
    ax.annotate("", (X0, Y0 - 3), (X1, Y0 - 3), arrowprops=dict(arrowstyle="<->", lw=0.6))
    ax.text((X0 + X1) / 2, Y0 - 3.6, G.ftin(X1 - X0), ha="center", va="top", fontsize=7)
    ax.annotate("", (X1 + 3, Y0), (X1 + 3, Y1), arrowprops=dict(arrowstyle="<->", lw=0.6))
    ax.text(X1 + 3.6, (Y0 + Y1) / 2, G.ftin(Y1 - Y0), ha="left", va="center", fontsize=7, rotation=90)
    ang = G.north_label(project)
    if ang is not None:
        import math
        cx, cy = X0 - 8, Y1 + 2
        ax.annotate("", (cx + 3 * math.sin(ang), cy + 3 * math.cos(ang)), (cx, cy), arrowprops=dict(arrowstyle="->", lw=1))
        ax.text(cx + 3.8 * math.sin(ang), cy + 3.8 * math.cos(ang), "N", ha="center", va="center", fontsize=8)
    ax.plot([X0, X0 + 10], [Y0 - 7, Y0 - 7], color="k", lw=2)
    ax.text(X0 + 5, Y0 - 7.6, "10 ft", ha="center", va="top", fontsize=7)
    ax.set_title(title, fontsize=10, loc="left")
    ax.set_aspect("equal")
    ax.axis("off")


def write_png(path, house, lv, cmp_, project, title):
    lot_ = G.outline(lv)
    porch = G.rects([p["rect"] for p in house.get("porches", [])])
    x0, y0, x1, y1 = lot_.union(porch).bounds
    w, h = (x1 - x0) + 22, (y1 - y0) + 18
    fig, ax = plt.subplots(figsize=(w / 6, h / 6), dpi=160)
    draw_level(ax, house, lv, cmp_, project, title)
    ax.set_xlim(x0 - 12, x1 + 10)
    ax.set_ylim(y0 - 10, y1 + 8)
    if cmp_:
        ax.text(x0 - 11, y0 - 9.5, "grey: kept    blue: new    red hatch: taken down", fontsize=6.5, color="#333")
    ax.text(x1 + 9.5, y0 - 9.5, "Planning study. Not for construction.", fontsize=6, color="#777", ha="right")
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def write_dxf(path, house, lv, cmp_):
    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.FT
    msp = doc.modelspace()
    for name, colour in (("A-WALL", 7), ("A-WALL-NEW", 5), ("A-WALL-DEMO", 1), ("A-DOOR", 30), ("A-GLAZ", 4),
                         ("A-AREA", 8), ("A-ANNO-TEXT", 7), ("A-FLOR-PORCH", 9)):
        doc.layers.add(name, color=colour)
    walls = G.walls(lv)
    holes = [G.cut_rect(o).intersection(walls) for o in G.all_openings(lv)]

    def put(g, layer, cut=True):
        if cut:
            for h in holes:
                g = g.difference(h)
        for p in G.polys(g):
            for ring in [p.exterior, *p.interiors]:
                msp.add_lwpolyline(list(ring.coords)[:-1], close=True, dxfattribs={"layer": layer})

    if cmp_:
        put(cmp_["kept"], "A-WALL")
        put(cmp_["new"], "A-WALL-NEW")
        put(cmp_["demolished"], "A-WALL-DEMO", cut=False)
    else:
        put(walls, "A-WALL")
    for o in G.all_openings(lv):
        a, b = sorted(o["span"])
        p, q = ((a, o["at"]), (b, o["at"])) if o["run"] == "x" else ((o["at"], a), (o["at"], b))
        msp.add_line(p, q, dxfattribs={"layer": "A-GLAZ" if o["kind"] == "window" else "A-DOOR"})
    for r in lv.get("rooms", []):
        s = G.room_shape(r)
        for p in G.polys(s):
            msp.add_lwpolyline(list(p.exterior.coords)[:-1], close=True, dxfattribs={"layer": "A-AREA"})
        c = max(G.polys(s), key=lambda p: p.area).centroid
        msp.add_text(r.get("label", r["id"]), height=0.5, dxfattribs={"layer": "A-ANNO-TEXT"}).set_placement(
            (c.x, c.y), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
    if lv is house["levels"][0]:
        for p in house.get("porches", []):
            x0, x1, y0, y1 = p["rect"]
            msp.add_lwpolyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], close=True, dxfattribs={"layer": "A-FLOR-PORCH"})
    doc.saveas(path)


def variant_readme(vid, v, summary):
    c = summary["cost"]
    L = [f"# {v.get('title', vid)}", "", v.get("concept", ""), "",
         f"**Expected cost: ${c['total']:,}.** An estimate from `rates.json`, not a bid. "
         f"{c['guessed_share_of_construction']:.0%} of the construction figure rests on guessed rates or guessed items.",
         "", "This is a planning study. Nothing here has been checked against the zoning code or by an engineer.", "",
         "## Areas", "", "| Floor | Gross sq ft |", "|---|---|"]
    for lid, a in summary["areas"]["levels"].items():
        L.append(f"| {lid} | {a['gross_sqft']:,.0f} |")
    L += [f"| **Total floor area** | **{summary['areas']['floor_area_sqft']:,.0f}** |",
          f"| Covered ground (house and porches) | {summary['areas']['covered_sqft']:,.0f} |", "",
          "## Checks", "", "| Where | Check | Result | Detail |", "|---|---|---|---|"]
    for k in summary["checks"]:
        L.append(f"| {k['level']} | {k['check']} | {'ok' if k['ok'] else '**FAIL**'} | {k['detail']} |")
    L += ["", "## Cost lines", "", "| Line | Quantity | Rate | Amount | Source |", "|---|---|---|---|---|"]
    for ln in c["lines"]:
        L.append(f"| {ln['label']} | {ln['quantity']:,.0f} {ln['unit']} | ${ln['rate']:,.0f} | ${ln['amount']:,.0f} | "
                 f"{ln['source']}{' (guess)' if ln['guess'] else ''} |")
    on = ", ".join(f"{k.replace('_', ' ')} {v_:.0%}" for k, v_ in c["on_top"].items())
    L += [f"| Construction | | | ${c['construction']:,.0f} | |", f"| On top: {on} | | | ${c['total'] - c['construction']:,.0f} | |",
          f"| **Expected cost** | | | **${c['total']:,.0f}** | |", "", "## Plans", ""]
    L += [f"![{lv['label']}](plan-{lv['id']}.png)" for lv in v["levels"]]
    return "\n".join(L) + "\n"


def main():
    ap = common.parser(__doc__)
    ap.add_argument("which", nargs="*", help="existing, a variant id, or all (default)")
    args = ap.parse_args()
    pdir, project = common.project(args)
    existing = common.existing_of(pdir)
    rates = G.load(pdir / "rates.json") if (pdir / "rates.json").exists() else None
    rows = []
    for vid, f, out in common.targets(pdir, args.which):
        house = G.load(f)
        is_var = vid != "existing"
        cmp_ = G.compare(existing, house) if is_var and existing else None
        for lv in house["levels"]:
            title = f"{house.get('title', house.get('name', vid))}: {lv.get('label', lv['id'])}"
            write_png(out / f"plan-{lv['id']}.png", house, lv, cmp_[lv["id"]] if cmp_ else None, project, title)
            write_dxf(out / f"plan-{lv['id']}.dxf", house, lv, cmp_[lv["id"]] if cmp_ else None)
        summary = {"id": vid, "areas": G.areas(house), "checks": G.checks(house, project, existing if is_var else None),
                   "height_ft": round(G.top_of_house(house) - house.get("grade", 0), 1)}
        if is_var and existing and rates:
            summary["cost"] = G.cost(house, existing, rates)
            (out / "README.md").write_text(variant_readme(vid, house, summary), encoding="utf-8")
            rows.append((vid, house, summary))
        G.dump(out / "summary.json", summary)
        fails = [k for k in summary["checks"] if not k["ok"]]
        print(f"{vid}: {summary['areas']['floor_area_sqft']:,.0f} sq ft, {len(fails)} failed checks"
              + (f", expected cost ${summary['cost']['total']:,}" if "cost" in summary else ""))
        for k in fails:
            print(f"   FAIL {k['level']}: {k['check']} ({k['detail']})")
    if rows:
        L = ["# Variants", "", "Planning studies. Costs are estimates from `rates.json`, not bids.", "",
             "| Variant | Floor area | Covered ground | Expected cost | Failed checks |", "|---|---|---|---|---|"]
        for vid, v, s in rows:
            L.append(f"| [{v.get('title', vid)}]({vid}/README.md) | {s['areas']['floor_area_sqft']:,.0f} sq ft | "
                     f"{s['areas']['covered_sqft']:,.0f} sq ft | ${s['cost']['total']:,} | {sum(not k['ok'] for k in s['checks'])} |")
        if {r[0] for r in rows} == {d.name for d in (pdir / "variants").iterdir() if (d / "variant.json").exists()}:
            (pdir / "variants" / "README.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
