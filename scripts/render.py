"""Render pictures of the existing house and each variant with Cycles, and a line drawing of each.

Reads   house.blend beside each house file, scripts/styles.json (or <project>/styles.json)
Writes  renders/<style>/<view>.jpg          street, rear, aerial, and a cutaway of each floor
        renders/lines/<view>.png            the same views as black lines on white

The line drawing is what keeps an AI picture on the model: image_pass.py sends the render and
its line drawing together. A style recolours materials by role and writes nothing back to the
model. "massing" shows kept walls grey and new walls blue.

Run:  uv run pipeline.py run render [-- <variant id> --style white-cottage --views street rear --quick]
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

import common
import house_geom as G

FT = common.FT


def load_styles(pdir):
    styles = G.load(common.ROOT / "scripts" / "styles.json")
    if (pdir / "styles.json").exists():
        styles.update(G.load(pdir / "styles.json"))
    return styles


def apply_style(style):
    for m in bpy.data.materials:
        role = m.name.replace("Finish.", "")
        if role in style and m.use_nodes:
            b = m.node_tree.nodes.get("Principled BSDF")
            col = style[role]
            b.inputs["Base Color"].default_value = (*col[:3], 1)
            if len(col) > 3:
                b.inputs["Roughness"].default_value = col[3]
        if role == "glass" and m.use_nodes:
            b = m.node_tree.nodes.get("Principled BSDF")
            b.inputs["Base Color"].default_value = (0.05, 0.07, 0.09, 1)
            b.inputs["Roughness"].default_value = 0.05
            b.inputs["Alpha"].default_value = 1.0


def world(strength=1.0):
    w = bpy.data.worlds.new("Sky")
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc, sep, ramp = (nt.nodes.new(n) for n in ("ShaderNodeTexCoord", "ShaderNodeSeparateXYZ", "ShaderNodeValToRGB"))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs[2], ramp.inputs[0])
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.0, (0.80, 0.86, 0.92, 1)
    e[1].position, e[1].color = 0.55, (0.24, 0.45, 0.78, 1)
    nt.links.new(ramp.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.context.scene.world = w
    return bg


def look(cam, eye, target):
    cam.location = Vector(eye) * FT
    d = Vector(target) * FT - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def hide(names_start, flag):
    def walk(lc):
        for ch in lc.children:
            if any(ch.name.startswith(n) for n in names_start):
                ch.exclude = flag
            walk(ch)
    walk(bpy.context.view_layer.layer_collection)


def views_for(house):
    base = G.outline(house["levels"][0]).union(G.rects([p["rect"] for p in house.get("porches", [])]))
    x0, y0, x1, y1 = base.bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    top = G.top_of_house(house)
    size = max(x1 - x0, y1 - y0)
    grade = house.get("grade", -1.0)
    v = {
        "street": dict(eye=(x0 - size * 0.62, y0 - size * 0.38, grade + 5.5), at=(cx - size * 0.1, cy, top * 0.42), lens=30),
        "rear": dict(eye=(x1 + size * 0.62, y1 + size * 0.38, grade + 5.5), at=(cx + size * 0.1, cy, top * 0.42), lens=30),
        "aerial": dict(eye=(x0 - size * 0.6, y0 - size * 0.75, top + size * 0.7), at=(cx, cy, top * 0.3), lens=35),
    }
    for i, lv in enumerate(house["levels"]):
        ox0, oy0, ox1, oy1 = G.outline(lv).bounds
        s = max(ox1 - ox0, (oy1 - oy0) * 1.6)
        v[f"cutaway-{lv['id']}"] = dict(eye=((ox0 + ox1) / 2, (oy0 + oy1) / 2 - s * 0.35, lv["floor"] + s * 1.25),
                                        at=((ox0 + ox1) / 2, (oy0 + oy1) / 2, lv["floor"]), lens=35,
                                        hide=["Roof"] + [f"Ceiling - {l.get('label', l['id'])}" for l in house["levels"][i:]]
                                        + [f"Floor - {l.get('label', l['id'])}" for l in house["levels"][i + 1:]])
    return v


def setup(quick):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16 if quick else 48
    sc.cycles.use_denoising = True
    for attr in dir(sc.render):                    # no file paths, dates or host names inside the pictures
        if attr.startswith("use_stamp_"):
            setattr(sc.render, attr, False)
    sc.render.resolution_x, sc.render.resolution_y = (800, 500) if quick else (1600, 1000)
    for vt in ("AgX", "Filmic", "Standard"):
        try:
            sc.view_settings.view_transform = vt
            break
        except TypeError:
            continue
    sc.view_settings.exposure = -1.0
    bg = world(0.8)
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy, sun.data.angle = 4.0, math.radians(2.0)
    sun.rotation_euler = (math.radians(52), 0, math.radians(-35))
    sc.collection.objects.link(sun)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.clip_end = 600
    sc.collection.objects.link(cam)
    sc.camera = cam
    return sc, cam, sun, bg


def lines_on(sc, bg, sun):
    """Black outlines on white: every surface a flat white emitter, edges drawn by Freestyle."""
    white = bpy.data.materials.new("LineWhite")
    white.use_nodes = True
    nt = white.node_tree
    nt.nodes.clear()
    em, out = nt.nodes.new("ShaderNodeEmission"), nt.nodes.new("ShaderNodeOutputMaterial")
    em.inputs["Color"].default_value = (1, 1, 1, 1)
    nt.links.new(em.outputs[0], out.inputs[0])
    bpy.context.view_layer.material_override = white
    for l in list(bg.id_data.links):
        if l.to_socket == bg.inputs["Color"]:
            bg.id_data.links.remove(l)
    bg.inputs["Color"].default_value = (1, 1, 1, 1)
    bg.inputs["Strength"].default_value = 1.0
    sun.data.energy = 0
    sc.cycles.samples = 4
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0
    sc.render.use_freestyle = True
    sc.render.line_thickness = 1.6
    vl = bpy.context.view_layer
    ls = vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new("lines")
    if ls.linestyle is None:
        ls.linestyle = bpy.data.linestyles.new("lines")
    ls.linestyle.color = (0, 0, 0)
    ls.select_silhouette = ls.select_border = ls.select_crease = True
    ls.select_material_boundary = True
    vl.freestyle_settings.crease_angle = math.radians(150)
    sc.render.image_settings.file_format = "PNG"


def main():
    ap = common.parser(__doc__)
    ap.add_argument("which", nargs="*")
    ap.add_argument("--style", default="massing")
    ap.add_argument("--views", nargs="*", help="street rear aerial cutaway-<level> (default: all)")
    ap.add_argument("--quick", action="store_true", help="half size, 16 samples")
    ap.add_argument("--no-lines", action="store_true", help="skip the line drawings")
    args = ap.parse_args()
    pdir, project = common.project(args)
    styles = load_styles(pdir)
    if args.style not in styles:
        raise SystemExit(f"No style '{args.style}'. Styles: {', '.join(styles)}")
    for vid, f, out in common.targets(pdir, args.which):
        blend = out / "house.blend"
        if not blend.exists():
            raise SystemExit(f"{blend} is missing. Run the model stage first.")
        house = G.load(f)
        views = views_for(house)
        want = args.views or list(views)
        for mode in (["colour"] if args.no_lines else ["colour", "lines"]):
            bpy.ops.wm.open_mainfile(filepath=str(blend))
            sc, cam, sun, bg = setup(args.quick)
            apply_style(styles[args.style])
            if mode == "lines":
                lines_on(sc, bg, sun)
            else:
                sc.render.image_settings.file_format = "JPEG"
                sc.render.image_settings.quality = 90
            for name in want:
                if name not in views:
                    raise SystemExit(f"No view '{name}'. Views: {', '.join(views)}")
                v = views[name]
                hide(v.get("hide", []), True)
                cam.data.lens = v["lens"]
                look(cam, v["eye"], v["at"])
                sub = "lines" if mode == "lines" else args.style
                sc.render.filepath = str(out / "renders" / sub / (name + (".png" if mode == "lines" else ".jpg")))
                bpy.ops.render.render(write_still=True)
                if mode == "lines":                      # plain 8-bit grey: a tenth of the size
                    from PIL import Image
                    Image.open(sc.render.filepath).convert("L").save(sc.render.filepath, optimize=True)
                hide(v.get("hide", []), False)
                print(f"{vid}: {sc.render.filepath}", flush=True)


if __name__ == "__main__":
    main()
