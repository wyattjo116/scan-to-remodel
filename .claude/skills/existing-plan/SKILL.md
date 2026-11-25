---
name: existing-plan
description: Turn registered scans (or tape measurements) into the existing-conditions house file, floor plan and 3D model - draft the plan from the scans, correct it by eye against the scan slice, measure how well it fits, and build the plans, Blender model and IFC. Use after the scan stage, when someone asks for the existing floor plan or as-built model, or when a room, door or window in existing/house.json is wrong.
---

# The house as it stands

Everything downstream reads one file: `<project>/existing/house.json`. This skill gets it right. Read the docstring at the top of `scripts/house_geom.py` for the format before editing it.

## 1. Draft from the scans

```bash
uv run pipeline.py run trace
```

This writes `existing/house.draft.json` and `scans/derived/refs/plan-slice.png` (wall points from above, with a foot grid and the wall faces it found), plus an elevation picture of each outside wall. It never overwrites `house.json`.

No scans? Skip to step 2 and type the file from tape measurements, using `examples/sample-house/existing/house.json` as the pattern.

## 2. Correct it by eye

Look at `plan-slice.png` (use the Read tool; it is a picture) next to the draft, then copy the draft to `existing/house.json` and fix it. The draft is good at plain rectangular rooms and bad at everything else. Go through this list:

- **Rooms.** One per real room? Two rooms joined means the wall between them was hidden; one room split means furniture or a mirror made a false wall. Name each room (`id`, `label`) and give it a `type`: `living`, `dining`, `kitchen`, `bedroom`, `bath`, `office`, `hall`, `stair`, `closet`, `utility`. Ask the person what each room is; do not guess from size.
- **Closets and small spaces.** Often missed (under 6 sq ft is dropped). Add them.
- **Outline.** The draft uses one bounding rectangle. If the house steps in or out, replace it with several rectangles that follow the red points.
- **Doors, openings, windows.** Every span is marked `"estimated": true`. Check each against the slice and the elevation pictures; remove false ones (a gap where a bookcase hid the wall), add missing ones. Sill and head heights are guesses: read them off the elevation pictures or ask.
- **Porches, the roof, the floor height above the ground.** The scan does not give these. Ask, or read the outside elevations, and say in the file which values are guesses.
- **Second storey.** The draft handles one floor. For more, scan each floor separately, draft each as its own project run, and merge the levels by hand.
- Remove `"estimated": true` from a value only when it has been checked.

Walls are whatever lies between rooms inside the outline, so set room rectangles to the clear inside of each room and the walls follow. Everything is axis-aligned rectangles: say so if the house has angled or curved walls, and draw the nearest rectangle.

## 3. Measure the fit

```bash
uv run pipeline.py run scan-check
```

Read `existing/scan-check.png`: orange is the plan, black and red are scan points, magenta marks scan wall points more than 6 inches from any drawn wall. A magenta line is a wall you missed or a wall in the wrong place; magenta specks are furniture. Fix and rerun until what is left is explained.

Report the numbers from `existing/scan-check.json` (median and 90th-percentile distance) and compare the person's tape measurements with the same dimensions in the plan. Those two things are the plan's accuracy; say them wherever a dimension is quoted.

## 4. Build

```bash
uv run pipeline.py run plans model ifc -- existing     # one stage at a time if passing "-- existing"
uv run pipeline.py run render -- existing --quick
```

- `plans`: `existing/plan-<level>.png` and `.dxf` (layers `A-WALL`, `A-DOOR`, `A-GLAZ`, `A-AREA`, `A-ANNO-TEXT`), `summary.json` with areas.
- `model`: `house.blend`, `house.glb`. `ifc`: `house.ifc`.

Arguments after `--` go to one stage only, so run `plans`, `model` and `ifc` as three commands when naming `existing`.

Open the plan and one render and compare them with the slice before saying it is done. Commit `existing/house.json` and what was built from it; never the scans.

## Limits to state

- Accuracy is the scan-check numbers plus the scan's own drift. Typical for a phone scan: outside walls to an inch or two, inside partitions to about half a foot.
- The roof is a guess unless measured another way.
- This is a measured sketch for planning, not a survey or as-built drawings.

Next: the `grill-brief` skill.
