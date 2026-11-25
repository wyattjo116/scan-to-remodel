---
name: plan-variant
description: Draw a remodel variant as a plan - a variant.json of rooms, doors and windows on each floor - and get its floor plans, areas, checks and one cost figure, judged against the brief. Use when the owner asks for a new scheme or option, a change to a layout ("move the stair", "make the kitchen bigger"), a comparison of variants, or a cost for a plan.
---

# Plan a variant

A variant is one folder, `<project>/variants/<id>/`, holding `variant.json`: the whole house as it would be, in the same format as `existing/house.json` (read the docstring of `scripts/house_geom.py`). Everything else in the folder is built from it.

## Before drawing

1. Read `brief/brief.md`, `brief/glossary.md` and the newest entries of `brief/decisions.md`. If the brief has not been through the `grill-brief` skill, do that first; a variant drawn on a thin brief gets thrown away.
2. Read `existing/house.json` and look at `existing/plan-main.png`.
3. Say in two or three sentences what this variant tries (its concept) and which Stated lines of the brief it is aimed at. One idea per variant: if two ideas compete, draw two variants.

## Draw

- Copy the nearest starting point: `existing/house.json` for a first variant, or another variant's file. Name the folder with a letter and a few words: `a-rear-wing-up`, `b-attic-rooms`. Set `name`, `title` and `concept`.
- Rooms are rectangles `[x0, x1, y0, y1]` of clear inside space, in feet; use `"rects"` for an L-shaped room. Leave 0.4 ft between rooms for an inside wall and 0.5 ft to the outline for an outside wall, or whatever the existing file uses. Whatever is inside the outline and not a room is wall.
- **Keep what you can.** A room rectangle left exactly as in the existing file keeps its walls. Moving a room edge by an inch demolishes and rebuilds that wall on paper, and the cost follows. Change coordinates on purpose.
- To extend, enlarge or add rectangles to `outline`. To add a floor, add a level with its own `floor` height, outline and rooms, a `stair` (the same rectangle on both floors, typed `stair`), and a roof for each part.
- Give every room a door or an opening, and every bedroom, living room, kitchen and office a window. Openings name the wall they are in by its centre line.
- `roofs` and `porches` are explicit lists. Update them when the outline changes.
- Anything the plan needs that has no rate (structural work, a special stair, site work) goes in `cost_items` with an amount and `"guess": true`. It is counted in the total, never held outside it.
- Set `"scope": "gut"` or `"refresh"` on a room to override the automatic choice (a room is costed as rebuilt when a wall touching it changes).

## Build and read the result

```bash
uv run pipeline.py run plans -- <id>
```

Then look at `plan-<level>.png` with the Read tool: grey walls are kept, blue are new, red hatch is taken down. Check by eye that it is the plan you meant. Read `summary.json` and the variant's `README.md`.

- **Checks.** Fix every FAIL or say why it stands. The checks are planning checks (rooms overlap, a room with no door, minimum widths, the upper floor overhanging, lot coverage and floor-area ratio against `project.json`). They are not building-code compliance.
- **One cost figure.** Lead with `cost.total` from `summary.json` and nothing beside it. Say it is an estimate from the rates in `rates.json`, not a bid, and what share rests on guesses (`guessed_share_of_construction`). If `rates.json` still holds the placeholder rates, say the figure is only good for comparing variants with each other.
- **Against the brief.** Go down the Stated lines one by one: met, not met, or cannot tell from a plan. Say so plainly when the variant breaks one, including the budget ceiling.

## Report

Findings first: the one cost figure, floor area, what it does well, which brief lines it misses, failed checks, and what is still open. Attach the plans. State the limits: a planning study, not a design; not checked against the zoning code or by an engineer; dimensions as good as the existing-house model.

Changing a variant after feedback: edit `variant.json`, rebuild, and say what changed. Record a choice between variants with `record-decision`.

Next: the `design-model` skill for the 3D model and BIM file, then `render-pictures`.
