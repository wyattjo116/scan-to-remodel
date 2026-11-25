"""Write an IFC model of the existing house and each variant, for Bonsai, FreeCAD or any BIM tool.

Reads   <project>/existing/house.json, <project>/variants/<id>/variant.json
Writes  house.ifc beside each house file (IFC4, metres)

What is in the file: a site, a building, one storey per floor, walls (each tagged kept or new
in the property set "Remodel"), floor slabs, rooms as spaces with their names and areas, doors
and windows as simple panels, roofs and porches as simple solids. Walls are plain boxes, already
cut round the openings; there are no wall layers, no opening elements and no structure. It is a
planning model for an architect to open, measure and draw over, not a construction model.

Run:  uv run pipeline.py run ifc [-- existing | <variant id> | all]
"""
from __future__ import annotations

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.geometry
import ifcopenshell.api.project
import ifcopenshell.api.pset
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit

import common
import house_geom as G

FT = common.FT


def box_mesh(x0, y0, x1, y1, z0, z1):
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    f = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return v, f


def roof_mesh(ro):
    x0, x1, y0, y1 = ro["rect"]
    ov, base, pitch = ro.get("overhang", 1.0), ro["base"], ro.get("pitch", 6) / 12
    kind, along_x = ro.get("type", "gable"), ro.get("ridge", "x") == "x"
    u0, u1, v0, v1 = (x0 - ov, x1 + ov, y0 - ov, y1 + ov) if along_x else (y0 - ov, y1 + ov, x0 - ov, x1 + ov)
    ze = base - ov * pitch

    def pt(u, v, z):
        return (u, v, z) if along_x else (v, u, z)

    if kind == "flat":
        return box_mesh(x0 - ov, y0 - ov, x1 + ov, y1 + ov, base, base + 0.5)
    if kind == "shed":
        hi = ze + (v1 - v0) * pitch
        za, zb = (hi, ze) if ro.get("low_side", "-y").startswith("+") else (ze, hi)
        v = [pt(u0, v0, ze - 0.01), pt(u1, v0, ze - 0.01), pt(u1, v1, ze - 0.01), pt(u0, v1, ze - 0.01),
             pt(u0, v0, za), pt(u1, v0, za), pt(u1, v1, zb), pt(u0, v1, zb)]
        return v, box_mesh(0, 0, 1, 1, 0, 1)[1]
    mid, zr = (v0 + v1) / 2, ze + (v1 - v0) / 2 * pitch
    inset = min((v1 - v0) / 2, (u1 - u0) / 2 - 0.01) if kind == "hip" else 0.0
    v = [pt(u0, v0, ze), pt(u1, v0, ze), pt(u1, v1, ze), pt(u0, v1, ze), pt(u0 + inset, mid, zr), pt(u1 - inset, mid, zr)]
    f = [(3, 2, 1, 0), (0, 1, 5, 4), (2, 3, 4, 5), (1, 2, 5), (3, 0, 4)]
    return v, f


def export(house, existing, project, path):
    f = ifcopenshell.api.project.create_file(version="IFC4")
    proj = ifcopenshell.api.root.create_entity(f, ifc_class="IfcProject", name=project.get("name", "House"))
    ifcopenshell.api.unit.assign_unit(f)
    model = ifcopenshell.api.context.add_context(f, context_type="Model")
    body = ifcopenshell.api.context.add_context(f, context_type="Model", context_identifier="Body",
                                                target_view="MODEL_VIEW", parent=model)
    site = ifcopenshell.api.root.create_entity(f, ifc_class="IfcSite", name="Site")
    bld = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuilding", name=house.get("title", house.get("name", "House")))
    ifcopenshell.api.aggregate.assign_object(f, products=[site], relating_object=proj)
    ifcopenshell.api.aggregate.assign_object(f, products=[bld], relating_object=site)
    cmp_ = G.compare(existing, house) if existing else None

    def add(cls, name, mesh, where, props=None, predefined=None):
        v, faces = mesh
        e = ifcopenshell.api.root.create_entity(f, ifc_class=cls, name=name, predefined_type=predefined)
        rep = ifcopenshell.api.geometry.add_mesh_representation(
            f, context=body, vertices=[[tuple(c * FT for c in p) for p in v]], faces=[[list(x) for x in faces]])
        ifcopenshell.api.geometry.assign_representation(f, product=e, representation=rep)
        ifcopenshell.api.geometry.edit_object_placement(f, product=e)
        if cls == "IfcSpace":
            ifcopenshell.api.aggregate.assign_object(f, products=[e], relating_object=where)
        else:
            ifcopenshell.api.spatial.assign_container(f, products=[e], relating_structure=where)
        if props:
            ps = ifcopenshell.api.pset.add_pset(f, product=e, name="Remodel")
            ifcopenshell.api.pset.edit_pset(f, pset=ps, properties=props)
        return e

    n = 0
    storeys = {}
    for lv in house["levels"]:
        st = ifcopenshell.api.root.create_entity(f, ifc_class="IfcBuildingStorey", name=lv.get("label", lv["id"]))
        st.Elevation = lv["floor"] * FT
        ifcopenshell.api.aggregate.assign_object(f, products=[st], relating_object=bld)
        storeys[lv["id"]] = st
        z0, z1 = lv["floor"], lv["floor"] + lv["ceiling"]
        walls = G.walls(lv)
        holes = G.all_openings(lv)
        solid = walls
        for o in holes:
            solid = solid.difference(G.cut_rect(o).intersection(walls))
        parts = [("new", solid.intersection(cmp_[lv["id"]]["new"])), ("kept", solid.difference(cmp_[lv["id"]]["new"]))] \
            if cmp_ else [("existing", solid)]
        for status, g in parts:
            for b in G.to_boxes(G.clean(g, 0.005)):
                n += 1
                add("IfcWall", f"Wall {lv['id']} {n}", box_mesh(b[0], b[1], b[2], b[3], z0, z1), st, {"Status": status})
        for o in holes:
            h = G.cut_rect(o).intersection(walls)
            if h.is_empty:
                continue
            head = z0 + (o.get("head") or o.get("height") or 6.8)
            sill = z0 + o.get("sill", 0.0)
            for b in G.to_boxes(h):
                add("IfcWall", f"Wall over {o.get('id', o['kind'])}", box_mesh(b[0], b[1], b[2], b[3], head, z1), st)
                if o["kind"] == "window":
                    add("IfcWall", f"Wall under {o.get('id', 'window')}", box_mesh(b[0], b[1], b[2], b[3], z0, sill), st)
            a, b_ = sorted(o["span"])
            t = 0.08
            pane = (a, o["at"] - t, b_, o["at"] + t) if o["run"] == "x" else (o["at"] - t, a, o["at"] + t, b_)
            if o["kind"] == "window":
                add("IfcWindow", o.get("id", "Window"), box_mesh(pane[0], pane[1], pane[2], pane[3], sill, head), st)
            elif o["kind"] == "door":
                add("IfcDoor", o.get("id", "Door"), box_mesh(pane[0], pane[1], pane[2], pane[3], z0, head), st)
        for b in G.to_boxes(G.outline(lv)):
            add("IfcSlab", f"Floor {lv['id']}", box_mesh(b[0], b[1], b[2], b[3], z0 - 1.0, z0), st, predefined="FLOOR")
        for r in lv.get("rooms", []):
            s = G.room_shape(r)
            for i, b in enumerate(G.to_boxes(s)):
                sp = add("IfcSpace", r["id"] if i == 0 else f"{r['id']}-{i + 1}", box_mesh(b[0], b[1], b[2], b[3], z0, z1), st,
                         {"RoomType": r.get("type", ""), "AreaSqFt": round(s.area, 1)})
                sp.LongName = r.get("label", r["id"])
    top = storeys[house["levels"][-1]["id"]]
    ground = storeys[house["levels"][0]["id"]]
    for ro in house.get("roofs", []):
        add("IfcRoof", ro.get("id", "Roof"), roof_mesh(ro), top)
    grade = house.get("grade", -1.0)
    for p in house.get("porches", []):
        x0, x1, y0, y1 = p["rect"]
        add("IfcSlab", f"Porch {p.get('id', '')}", box_mesh(x0, y0, x1, y1, grade, p.get("floor", -0.5)), ground, predefined="FLOOR")
    f.write(str(path))
    return len(f.by_type("IfcWall")), len(f.by_type("IfcSpace"))


def main():
    ap = common.parser(__doc__)
    ap.add_argument("which", nargs="*")
    args = ap.parse_args()
    pdir, project = common.project(args)
    existing = common.existing_of(pdir)
    for vid, src, out in common.targets(pdir, args.which):
        walls, spaces = export(G.load(src), existing if vid != "existing" else None, project, out / "house.ifc")
        print(f"{vid}: wrote {out / 'house.ifc'} ({walls} wall pieces, {spaces} spaces)")


if __name__ == "__main__":
    main()
