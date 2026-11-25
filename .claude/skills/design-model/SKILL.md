---
name: design-model
description: Build the 3D design of a variant - the Blender model, the glTF, and the IFC file for Bonsai, FreeCAD or an architect's BIM software - and check it. Use after a variant's plan is settled, when someone asks for a 3D model, a BIM or IFC file, drawings to hand an architect, or wants to open or edit the model in Blender, Bonsai or FreeCAD.
---

# Design: the 3D model and the BIM file

One command each, all built from the variant's `variant.json`:

```bash
uv run pipeline.py run model -- <id>     # house.blend, house.glb
uv run pipeline.py run ifc -- <id>       # house.ifc
```

Neither needs Blender or FreeCAD installed.

## What you get

| File | What it is | Opens in |
|---|---|---|
| `house.blend` | Boxes and roof slabs in named collections: one per floor, its ceiling, Roof, Porches, Stair, Site. Metres in the file, shown in feet. Materials are named `Finish.<role>` (`wall_kept`, `wall_new`, `roof`, `glass`, ...) | Blender 4.2 or later |
| `house.glb` | The same, for viewers and game engines | Any glTF viewer, Unreal, a web page |
| `house.ifc` | IFC4: site, building, a storey per floor, walls tagged `kept` or `new` (property set `Remodel`), slabs, rooms as spaces with names and areas, doors and windows as panels, roofs | Bonsai, FreeCAD, Revit, ArchiCAD, Vectorworks |
| `plan-<level>.dxf` | From the `plans` stage; layers `A-WALL`, `A-WALL-NEW`, `A-WALL-DEMO`, `A-DOOR`, `A-GLAZ`, `A-AREA` | Any CAD program |

## Check it

1. Render a quick look and read the pictures: `uv run pipeline.py run render -- <id> --quick --no-lines`. Look at `street`, `rear`, `aerial` and each `cutaway-<level>`. The cutaway should match the plan room for room.
2. Things that go wrong: a roof whose `base` is below the wall top (walls poke through); a roof `rect` that no longer matches a changed outline; an upper floor with no roof; an opening whose `at` is not inside a wall (it cuts nothing; `plans` reports it).
3. Fix `variant.json` and rebuild. Do not hand-edit `house.blend` and expect it to last: a rebuild overwrites it. Save hand edits under another name.

## Drawings with Bonsai or FreeCAD (optional tools; see the `setup` skill)

- **Bonsai** (in Blender): File > Open IFC Project > `house.ifc`. The storeys, walls, rooms and their names are there. Use Bonsai's drawing tools to cut plans, sections and elevations, add dimensions and put them on sheets. Save under a new name: a rebuild of `house.ifc` overwrites the original.
- **FreeCAD**: open `house.ifc` in the BIM workbench; make sheets with TechDraw.
- Both were tried on the project this repo grew out of. Scripted, dimensioned sheets came out of both, with Bonsai's the better drawings and both needing a person to tidy text that collides. Those scripts are not in this repo yet; today the drawings are made by hand in the app from the IFC this repo writes.

## Limits to state when handing the model on

- Walls are plain boxes cut round the openings: no layers, no studs, no structure. Twenty slightly different wall thicknesses are the survey's uncertainty, not construction.
- Doors have no swing direction. Stairs are a block of steps, not a designed stair.
- Roofs are simple gable, hip, shed or flat slabs with no framing. Gable walls above the top plate are filled in the Blender model and missing from the IFC.
- It is a planning model for an architect to open, measure and draw over. An architect and an engineer replace it; it does not replace them.

Next: the `render-pictures` skill.
