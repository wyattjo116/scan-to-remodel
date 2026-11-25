"""Build the Blender model of the existing house and of each variant from its house file.

Reads   <project>/existing/house.json, <project>/variants/<id>/variant.json, project.json
Writes  house.blend and house.glb beside each house file

Blender does not need to be installed: the bpy package is Blender as a Python library.
Everything is boxes and simple roof slabs, stored in metres and shown in feet. Collections:
one per floor (walls, floor, openings, ceiling), Roof, Porches, Stair and Site. Materials are
named Finish.<role>; the render script recolours them by role, so keep the names.

To change the model, change the house file and rebuild. A rebuild overwrites house.blend;
save hand edits made in Blender under another name.

Run:  uv run pipeline.py run model [-- existing | <variant id> | all]
"""
from __future__ import annotations

import bpy  # must come before bmesh
import bmesh

import common
import house_geom as G

FT = common.FT
COLOURS = {
    "wall_kept": (0.78, 0.76, 0.70, 1), "wall_new": (0.55, 0.70, 0.90, 1), "roof": (0.30, 0.31, 0.33, 1),
    "floor": (0.62, 0.48, 0.33, 1), "ceiling": (0.92, 0.92, 0.90, 1), "glass": (0.55, 0.75, 0.90, 0.35),
    "door": (0.42, 0.27, 0.16, 1), "porch": (0.66, 0.64, 0.60, 1), "trim": (0.93, 0.93, 0.91, 1),
    "foundation": (0.50, 0.50, 0.48, 1), "ground": (0.36, 0.47, 0.28, 1), "lot": (0.42, 0.53, 0.32, 1),
    "stair": (0.70, 0.52, 0.32, 1),
}


def material(role):
    name = f"Finish.{role}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    r, g, bl, a = COLOURS[role]
    b.inputs["Base Color"].default_value = (r, g, bl, 1)
    b.inputs["Roughness"].default_value = 0.1 if role == "glass" else 0.8
    b.inputs["Alpha"].default_value = a
    m.diffuse_color = (r, g, bl, a)
    return m


def coll(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c


class Mesh:
    """Collects boxes and free-form solids, then becomes one object."""

    def __init__(self):
        self.bm = bmesh.new()

    def box(self, x0, y0, x1, y1, z0, z1):
        if x1 - x0 < 1e-4 or y1 - y0 < 1e-4 or z1 - z0 < 1e-4:
            return
        self.solid([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
                   [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])

    def shape(self, g, z0, z1):
        for b in G.to_boxes(g):
            self.box(b[0], b[1], b[2], b[3], z0, z1)

    def solid(self, bottom, top):
        """A prism between two rings with the same number of points (counter-clockwise from above)."""
        vb = [self.bm.verts.new((x * FT, y * FT, z * FT)) for x, y, z in bottom]
        vt = [self.bm.verts.new((x * FT, y * FT, z * FT)) for x, y, z in top]
        n = len(vb)
        self.bm.faces.new(vb[::-1])
        self.bm.faces.new(vt)
        for i in range(n):
            j = (i + 1) % n
            self.bm.faces.new([vb[i], vb[j], vt[j], vt[i]])

    def faces(self, rings):
        for ring in rings:
            self.bm.faces.new([self.bm.verts.new((x * FT, y * FT, z * FT)) for x, y, z in ring])

    def done(self, name, role, collection):
        if not self.bm.faces:
            self.bm.free()
            return None
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        me.materials.append(material(role))
        collection.objects.link(ob)
        return ob


def build_level(house, lv, cmp_, top_level):
    lid = lv["id"]
    c = coll(f"Floor - {lv.get('label', lid)}")
    z0, z1 = lv["floor"], lv["floor"] + lv["ceiling"]
    walls = G.walls(lv)
    holes = G.all_openings(lv)
    cuts = [G.cut_rect(o).intersection(walls) for o in holes]
    solid_walls = walls
    for h in cuts:
        solid_walls = solid_walls.difference(h)
    parts = [("wall_new", solid_walls.intersection(cmp_["new"])), ("wall_kept", solid_walls.difference(cmp_["new"]))] \
        if cmp_ else [("wall_kept", solid_walls)]
    for role, g in parts:
        m = Mesh()
        m.shape(G.clean(g, 0.005), z0, z1)
        m.done(f"{lid}.walls.{role.split('_')[1]}", role, c)
    # above and below each opening
    for o, h in zip(holes, cuts):
        if h.is_empty:
            continue
        role = "wall_new" if cmp_ and h.intersection(cmp_["new"]).area > 0.5 * h.area else "wall_kept"
        head = z0 + (o.get("head") or o.get("height") or 6.8)
        sill = z0 + o.get("sill", 0.0)
        m = Mesh()
        m.shape(h, head, z1)
        if o["kind"] == "window":
            m.shape(h, z0, sill)
        m.done(f"{lid}.{o['kind']}.{o.get('id', 'x')}.wall", role, c)
        a, b = sorted(o["span"])
        thin = 0.06
        pane = (a, o["at"] - thin, b, o["at"] + thin) if o["run"] == "x" else (o["at"] - thin, a, o["at"] + thin, b)
        if o["kind"] == "window" or o.get("glazed"):
            m = Mesh()
            m.box(pane[0], pane[1], pane[2], pane[3], sill, head)
            m.done(f"{lid}.{o['kind']}.{o.get('id', 'x')}.glass", "glass", c)
        elif o["kind"] == "door":
            m = Mesh()
            m.box(pane[0], pane[1], pane[2], pane[3], z0, head)
            m.done(f"{lid}.door.{o.get('id', 'x')}.leaf", "door", c)
    m = Mesh()
    m.shape(G.outline(lv), z0 - 1.0, z0)
    m.done(f"{lid}.floor", "floor", c)
    cc = coll(f"Ceiling - {lv.get('label', lid)}", c)
    m = Mesh()
    m.shape(G.outline(lv), z1, z1 + 0.02)
    m.done(f"{lid}.ceiling", "ceiling", cc)


def roof(ro, c, wc, infill):
    x0, x1, y0, y1 = ro["rect"]
    ov, base, t = ro.get("overhang", 1.0), ro["base"], 0.5
    pitch = ro.get("pitch", 6) / 12
    kind = ro.get("type", "gable")
    m, w = Mesh(), Mesh()
    along_x = ro.get("ridge", "x") == "x"

    def pt(u, v, z):            # u along the ridge, v across it
        return (u, v, z) if along_x else (v, u, z)

    u0, u1, v0, v1 = (x0, x1, y0, y1) if along_x else (y0, y1, x0, x1)
    if kind == "flat":
        m.box(x0 - ov, y0 - ov, x1 + ov, y1 + ov, base, base + t)
    elif kind == "shed":
        low = ro.get("low_side", "-y" if along_x else "-x")
        flip = low.startswith("+")
        va, vb = (v1, v0) if flip else (v0, v1)                       # va is the low edge
        s = 1 if vb > va else -1
        rise = abs(vb - va) * pitch
        a, b = va - s * ov, vb + s * ov
        za, zb = base - ov * pitch, base + rise + ov * pitch
        ring = [pt(u0 - ov, a, za), pt(u1 + ov, a, za), pt(u1 + ov, b, zb), pt(u0 - ov, b, zb)]
        if (s > 0) != along_x:
            ring = ring[::-1]
        m.solid(ring, [(x, y, z + t) for x, y, z in ring])
        if infill:
            for u in (u0, u1 - 0.5):
                w.faces([[pt(u, va, base), pt(u, vb, base), pt(u, vb, base + rise)],
                         [pt(u + 0.5, va, base), pt(u + 0.5, vb, base), pt(u + 0.5, vb, base + rise)]])
    else:
        mid, rise = (v0 + v1) / 2, (v1 - v0) / 2 * pitch
        inset = (v1 - v0) / 2 if kind == "hip" else 0.0
        inset = min(inset, (u1 - u0) / 2 - 0.01)
        ze, zr = base - ov * pitch, base + rise
        for sgn, v_e in ((-1, v0 - ov), (1, v1 + ov)):
            ring = [pt(u0 - ov, v_e, ze), pt(u1 + ov, v_e, ze), pt(u1 + ov - inset - (ov if inset else 0), mid, zr),
                    pt(u0 - ov + inset + (ov if inset else 0), mid, zr)]
            if (sgn < 0) != along_x:
                ring = ring[::-1]
            m.solid(ring, [(x, y, z + t) for x, y, z in ring])
        if kind == "hip":
            for u_e, u_r in ((u0 - ov, u0 + inset), (u1 + ov, u1 - inset)):
                m.faces([[pt(u_e, v0 - ov, ze + t), pt(u_e, v1 + ov, ze + t), pt(u_r, mid, zr + t)]])
        elif infill:
            base += 0.03
            for u in (u0, u1 - 0.5):
                w.solid([pt(u, v0, base), pt(u + 0.5, v0, base), pt(u + 0.5, mid, zr), pt(u, mid, zr)][::(1 if along_x else -1)],
                        [pt(u, v1, base), pt(u + 0.5, v1, base), pt(u + 0.5, mid, zr + 0.001), pt(u, mid, zr + 0.001)][::(1 if along_x else -1)])
    m.done(f"roof.{ro.get('id', 'x')}", "roof", c)
    w.done(f"roof.{ro.get('id', 'x')}.gable", "wall_kept", wc)


def build(house, existing, project, out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "IMPERIAL"
    sc.unit_settings.length_unit = "FEET"
    cmp_ = G.compare(existing, house) if existing else None
    for lv in house["levels"]:
        build_level(house, lv, cmp_[lv["id"]] if cmp_ else None, lv is house["levels"][-1])
    rc = coll("Roof")
    porch_ids = {p.get("id") for p in house.get("porches", [])}
    for ro in house.get("roofs", []):
        roof(ro, rc, rc, infill=ro.get("id") not in porch_ids)
    grade = house.get("grade", -1.0)
    pc = coll("Porches")
    roofs = {r.get("id"): r for r in house.get("roofs", [])}
    for p in house.get("porches", []):
        x0, x1, y0, y1 = p["rect"]
        f = p.get("floor", -0.5)
        m = Mesh()
        m.box(x0, y0, x1, y1, grade, f)
        m.done(f"porch.{p.get('id', 'x')}.floor", "porch", pc)
        if p.get("posts"):
            top = roofs.get(p.get("id"), {}).get("base", f + 8.0)
            m = Mesh()
            s = 0.5
            for (px, py) in ((x0, y0), (x0, y1 - s), (x1 - s, y0), (x1 - s, y1 - s)):
                m.box(px, py, px + s, py + s, f, top)
            m.done(f"porch.{p.get('id', 'x')}.posts", "trim", pc)
    st = house.get("stair")
    if st:
        sc_ = coll("Stair")
        lo, hi = G.level(house, st["from"]), G.level(house, st["to"])
        x0, x1, y0, y1 = st["rect"]
        n = 16
        m = Mesh()
        d = st.get("up_toward", "+x")
        for i in range(n):
            f0, f1 = i / n, (i + 1) / n
            if d.startswith("-"):
                f0, f1 = 1 - f1, 1 - f0
            z = lo["floor"] + (hi["floor"] - lo["floor"]) * ((i + 1) / n)
            if d.endswith("x"):
                m.box(x0 + f0 * (x1 - x0), y0, x0 + f1 * (x1 - x0), y1, z - 0.6, z)
            else:
                m.box(x0, y0 + f0 * (y1 - y0), x1, y0 + f1 * (y1 - y0), z - 0.6, z)
        m.done("stair", "stair", sc_)
    fc = coll("Site")
    base = G.outline(house["levels"][0])
    m = Mesh()
    m.shape(base, grade, house["levels"][0]["floor"] - 1.0)
    m.done("foundation", "foundation", fc)
    bx0, by0, bx1, by1 = base.bounds
    m = Mesh()
    m.box(bx0 - 150, by0 - 150, bx1 + 150, by1 + 150, grade - 0.5, grade - 0.05)
    m.done("ground", "ground", fc)
    lot = (project.get("lot") or {}).get("rect")
    if lot:
        m = Mesh()
        m.box(lot[0], lot[2], lot[1], lot[3], grade - 0.05, grade)
        m.done("lot", "lot", fc)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "house.blend"))
    bpy.ops.export_scene.gltf(filepath=str(out / "house.glb"), export_apply=True)


def main():
    ap = common.parser(__doc__)
    ap.add_argument("which", nargs="*")
    args = ap.parse_args()
    pdir, project = common.project(args)
    existing = common.existing_of(pdir)
    for vid, f, out in common.targets(pdir, args.which):
        build(G.load(f), existing if vid != "existing" else None, project, out)
        print(f"{vid}: wrote {out / 'house.blend'} and house.glb")


if __name__ == "__main__":
    main()
