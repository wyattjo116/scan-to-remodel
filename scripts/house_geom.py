"""Shared plan geometry, checks and cost for a house file (no Blender needed).

A house file (existing/house.json or variants/<id>/variant.json) describes each floor as
axis-aligned rectangles, in feet:

    outline   rectangles [x0, x1, y0, y1] whose union is the outside face of the exterior walls
    rooms     each a rectangle ("rect") or several ("rects"); the clear inside of the room
    doors, windows, openings
              "run": "x" means the wall runs along X; "at" is the wall's centre line (a Y value);
              "span" is [from, to] along the wall

Whatever is inside the outline and is not a room is wall. That one rule gives walls, and by
comparing a variant with the existing house it gives kept, demolished and new walls.

Frame: X to the right and Y up the page, Z up, main finished floor at Z = 0. By convention the
front of the house is at low X. project.json says where north is.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

MITRE = 2
HALF_CUT = 0.75          # an opening is cut this far each side of the wall's centre line


# ---------------------------------------------------------------- files
def load(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump(path, obj) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1) + "\n", encoding="utf-8")


def ftin(v: float) -> str:
    """12.5 -> 12'-6\""""
    inches = round(abs(v) * 12)
    return f"{'-' if v < 0 else ''}{inches // 12}'-{inches % 12}\""


# ---------------------------------------------------------------- shapes
def rect(r):
    x0, x1, y0, y1 = r
    return box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def rects(lst):
    return unary_union([rect(r) for r in lst]) if lst else Polygon()


def clean(g, eps=0.02):
    """Drop slivers thinner than about eps."""
    return g.buffer(-eps, join_style=MITRE).buffer(eps, join_style=MITRE)


def polys(g):
    if g.is_empty:
        return []
    return [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area > 1e-6]


def room_shape(room):
    return rects(room["rects"]) if "rects" in room else rect(room["rect"])


def outline(level):
    return rects(level.get("outline", []))


def rooms_union(level):
    return unary_union([room_shape(r) for r in level.get("rooms", [])]) if level.get("rooms") else Polygon()


def walls(level):
    return clean(outline(level).difference(rooms_union(level)))


def cut_rect(o, half=HALF_CUT):
    a, b = sorted(o["span"])
    if o["run"] == "x":
        return box(a, o["at"] - half, b, o["at"] + half)
    return box(o["at"] - half, a, o["at"] + half, b)


def all_openings(level):
    """Every hole in the walls of a level, each with kind door | window | opening."""
    out = []
    for kind, key in (("door", "doors"), ("window", "windows"), ("opening", "openings")):
        for o in level.get(key, []):
            out.append({**o, "kind": kind})
    return out


def to_boxes(g):
    """Split a rectilinear shape into non-overlapping rectangles (x0, y0, x1, y1)."""
    out = []
    for p in polys(g):
        xs = sorted({round(x, 4) for ring in [p.exterior, *p.interiors] for x, _ in ring.coords})
        ys = sorted({round(y, 4) for ring in [p.exterior, *p.interiors] for _, y in ring.coords})
        for j in range(len(ys) - 1):
            run = None
            for i in range(len(xs) - 1):
                inside = p.contains(box(xs[i], ys[j], xs[i + 1], ys[j + 1]).centroid)
                if inside and run is None:
                    run = xs[i]
                if run is not None and (not inside or i == len(xs) - 2):
                    out.append((run, ys[j], xs[i + 1] if inside else xs[i], ys[j + 1]))
                    run = None
    out.sort(key=lambda b: (b[0], b[2], b[1]))          # stack boxes that sit exactly on top of each other
    merged = []
    for b in out:
        m = merged[-1] if merged else None
        if m and m[0] == b[0] and m[2] == b[2] and abs(m[3] - b[1]) < 1e-6:
            merged[-1] = (m[0], m[1], m[2], b[3])
        else:
            merged.append(b)
    return merged


def level(house, lid):
    for lv in house["levels"]:
        if lv["id"] == lid:
            return lv
    return None


# ---------------------------------------------------------------- compare with the existing house
def compare(existing, variant):
    """Per level id: kept, demolished and new wall shapes, and the added floor area shape."""
    out = {}
    for lv in variant["levels"]:
        old = level(existing, lv["id"]) if existing else None
        new_w = walls(lv)
        old_w = walls(old) if old else Polygon()
        old_o = outline(old) if old else Polygon()
        out[lv["id"]] = {
            "kept": clean(new_w.intersection(old_w)),
            "demolished": clean(old_w.difference(new_w)),
            "new": clean(new_w.difference(old_w)),
            "added_floor": clean(outline(lv).difference(old_o)),
            "removed_floor": clean(old_o.difference(outline(lv))),
        }
    return out


# ---------------------------------------------------------------- checks
MIN_SIDE = {"bedroom": 8.0, "bath": 5.0, "office": 7.0, "living": 11.0, "dining": 9.0, "kitchen": 8.0, "hall": 3.0, "stair": 3.0}
NEEDS_WINDOW = {"bedroom", "living", "dining", "office", "kitchen"}


def checks(house, project=None, existing=None):
    """A list of {level, check, ok, detail}. These are planning checks, not code compliance."""
    res = []

    def add(lid, name, ok, detail=""):
        res.append({"level": lid, "check": name, "ok": bool(ok), "detail": detail})

    for lv in house["levels"]:
        lid, out_ = lv["id"], outline(lv)
        shapes = [(r, room_shape(r)) for r in lv.get("rooms", [])]
        for r, s in shapes:
            if s.difference(out_).area > 0.05:
                add(lid, f"{r['id']} inside the outline", False, f"{s.difference(out_).area:.1f} sq ft outside")
        for i, (ra, sa) in enumerate(shapes):
            for rb, sb in shapes[i + 1:]:
                if sa.intersection(sb).area > 0.05:
                    add(lid, f"{ra['id']} and {rb['id']} do not overlap", False,
                        f"{sa.intersection(sb).area:.1f} sq ft shared")
        holes = all_openings(lv)
        for r, s in shapes:
            x0, y0, x1, y1 = s.bounds
            need = MIN_SIDE.get(r.get("type", ""))
            if need:
                side = min(x1 - x0, y1 - y0)
                add(lid, f"{r['id']} at least {need:g} ft wide", side >= need - 0.01, f"narrow side {ftin(side)}")
            ways = [o for o in holes if o["kind"] != "window" and cut_rect(o).intersects(s)]
            add(lid, f"{r['id']} can be entered", bool(ways) or r.get("type") in ("void", "porch"),
                f"{len(ways)} door or opening")
            if r.get("type") in NEEDS_WINDOW:
                wins = [o for o in holes if o["kind"] == "window" and cut_rect(o).intersects(s)]
                glazed = [o for o in holes if o["kind"] == "door" and o.get("glazed") and cut_rect(o).intersects(s)]
                add(lid, f"{r['id']} has a window", bool(wins or glazed), f"{len(wins)} windows, {len(glazed)} glazed doors")
        w = walls(lv)
        for o in holes:
            if cut_rect(o).intersection(w).area < 0.05:
                add(lid, f"{o['kind']} {o.get('id', '')} sits in a wall", False,
                    f"run {o['run']} at {o['at']} span {o['span']} touches no wall")

    lvls = house["levels"]
    if len(lvls) > 1:
        add("all", "stair drawn", bool(house.get("stair")), "a stair is needed between floors")
        for lo, hi in zip(lvls, lvls[1:]):
            over = outline(hi).difference(outline(lo).union(rects([p["rect"] for p in house.get("porches", [])])))
            add(hi["id"], f"sits over {lo['id']}", over.area < 0.5, f"{over.area:.0f} sq ft overhangs the floor below")
            # walls above carried by walls below (planning flag for the engineer, not a calculation)
            carried = walls(hi).intersection(walls(lo)).area / max(walls(hi).area, 1e-6)
            add(hi["id"], "note: share of walls standing on a wall below", True, f"{carried:.0%}")

    lot = (project or {}).get("lot") or {}
    a = areas(house)
    if lot.get("area_sqft"):
        cov = a["covered_sqft"] / lot["area_sqft"]
        lim = lot.get("max_coverage")
        add("lot", "lot coverage", lim is None or cov <= lim + 1e-9,
            f"{cov:.1%} of the lot" + (f" against a limit of {lim:.0%}" if lim else " (no limit set in project.json)"))
        far = a["floor_area_sqft"] / lot["area_sqft"]
        lim = lot.get("max_floor_area_ratio")
        add("lot", "floor-area ratio", lim is None or far <= lim + 1e-9,
            f"{far:.2f}" + (f" against a limit of {lim:.2f}" if lim else " (no limit set in project.json)"))
    return res


# ---------------------------------------------------------------- areas and cost
def areas(house):
    per = {}
    for lv in house["levels"]:
        per[lv["id"]] = {
            "gross_sqft": round(outline(lv).area, 1),
            "rooms": {r["id"]: round(room_shape(r).area, 1) for r in lv.get("rooms", [])},
        }
    porch = rects([p["rect"] for p in house.get("porches", [])])
    footprint = unary_union([outline(lv) for lv in house["levels"]])
    return {
        "levels": per,
        "floor_area_sqft": round(sum(v["gross_sqft"] for v in per.values()), 1),
        "footprint_sqft": round(footprint.area, 1),
        "porch_sqft": round(porch.area, 1),
        "covered_sqft": round(footprint.union(porch).area, 1),
    }


def cost(variant, existing, rates):
    """One expected-cost figure. Every line is a quantity times a rate from rates.json, or an
    item typed into the variant ("cost_items"). Fees and contingency are applied to all of it."""
    cmp_ = compare(existing, variant)
    r = rates["rates"]
    lines = []

    def line(label, qty, unit, key):
        if qty > 0.5:
            rate = r[key]
            lines.append({"label": label, "quantity": round(qty, 1), "unit": unit, "rate": rate["value"],
                          "amount": round(qty * rate["value"]), "source": rate.get("source", "not sourced"),
                          "guess": bool(rate.get("guess", False))})

    old_ids = {lv["id"] for lv in existing["levels"]} if existing else set()
    for lv in variant["levels"]:
        c = cmp_[lv["id"]]
        added = c["added_floor"].area
        if lv["id"] in old_ids and lv is variant["levels"][0]:
            line(f"New ground-floor area ({lv['id']})", added, "sq ft", "addition_ground_sqft")
        else:
            line(f"New upper-floor area ({lv['id']})", added, "sq ft", "addition_upper_sqft")
        old = level(existing, lv["id"]) if existing else None
        if old:
            touched = 0.0
            changed = c["demolished"].union(c["new"]).buffer(0.3)
            for room in lv.get("rooms", []):
                s = room_shape(room).intersection(outline(old))
                scope = room.get("scope") or ("gut" if s.area and s.intersects(changed) else "refresh")
                if scope == "gut":
                    touched += s.area
            line(f"Rooms rebuilt inside the existing house ({lv['id']})", touched, "sq ft", "gut_remodel_sqft")
            line(f"Rooms refreshed ({lv['id']})", outline(old).intersection(outline(lv)).area - touched, "sq ft", "refresh_sqft")
            line(f"Walls taken down ({lv['id']})", c["demolished"].area / max(variant.get("wall", {}).get("interior", 0.4), 0.1),
                 "ft of wall", "wall_demolition_ft")
        for room in lv.get("rooms", []):
            s = room_shape(room)
            is_new = not old or s.intersection(outline(old)).area < 0.5 * s.area or room.get("scope") == "gut" \
                or (old and s.intersects(cmp_[lv["id"]]["demolished"].union(cmp_[lv["id"]]["new"]).buffer(0.3)))
            if is_new and room.get("type") == "kitchen":
                line(f"Kitchen fit-out ({room['id']})", 1, "each", "kitchen_each")
            if is_new and room.get("type") == "bath":
                line(f"Bathroom fit-out ({room['id']})", 1, "each", "bath_each")
    old_porch = rects([p["rect"] for p in (existing or {}).get("porches", [])])
    line("New porch", rects([p["rect"] for p in variant.get("porches", [])]).difference(old_porch).area, "sq ft", "porch_sqft")
    if variant.get("stair") and not (existing or {}).get("stair"):
        line("New stair", 1, "each", "stair_each")
    for it in variant.get("cost_items", []):
        lines.append({"label": it["label"], "quantity": 1, "unit": "item", "rate": it["amount"], "amount": round(it["amount"]),
                      "source": it.get("source", "guess"), "guess": bool(it.get("guess", True))})

    construction = sum(l["amount"] for l in lines)
    mult = 1 + sum(rates["on_top"].values())
    total = round(construction * mult, -2)
    guessed = sum(l["amount"] for l in lines if l["guess"])
    return {
        "total": int(total),
        "construction": int(construction),
        "on_top": rates["on_top"],
        "guessed_share_of_construction": round(guessed / construction, 3) if construction else 0.0,
        "lines": lines,
        "note": "An estimate from the rates in rates.json, not a bid. Replace the rates with local ones.",
    }


def roof_rise(roof):
    x0, x1, y0, y1 = roof["rect"]
    span = (y1 - y0) if roof.get("ridge", "x") == "x" else (x1 - x0)
    pitch = roof.get("pitch", 6) / 12
    kind = roof.get("type", "gable")
    if kind == "flat":
        return 0.0
    return span * pitch if kind == "shed" else span / 2 * pitch


def top_of_house(house):
    return max((ro["base"] + roof_rise(ro) for ro in house.get("roofs", [])), default=max(
        lv["floor"] + lv["ceiling"] for lv in house["levels"]))


def north_label(project):
    """Which way +Y points, from project.json's north_from_plus_y_deg (clockwise)."""
    a = (project or {}).get("north_from_plus_y_deg")
    return None if a is None else math.radians(a)
