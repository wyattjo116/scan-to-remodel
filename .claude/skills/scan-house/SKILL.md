---
name: scan-house
description: Capture a house with an iPhone LiDAR app (Modelar) and turn the raw scans into clean point clouds in one frame. Use when someone is about to scan a house, has PLY files from a scan, asks how to scan well, or the scan stage fails or gives a skewed or doubled result.
---

# Scan the house

Goal: point clouds of the inside and the outside, squared to the walls and laid over each other in feet, ready for the `existing-plan` skill.

## 1. Capture (the person does this; coach them)

The steps here were worked out with **Modelar** on an iPhone with LiDAR (Pro models from the 12 Pro on). Any app that exports a metric, gravity-aligned PLY point cloud works; set `"up": "z"` on a scan in `project.json` if the app's up axis is Z and not Y.

- **Two scans at least**: one inside, one outside. Separate scans are fine; the pipeline lines them up. Add more for a detached garage or a yard.
- **Inside**: open every interior door first. Walk each room slowly along the walls with the phone at chest height, pointing at the wall, then sweep the floor edge and the ceiling edge. Go through each doorway slowly so the app keeps track; this is where scans drift. Finish where you began.
- **Outside**: walk the whole way round, about 10 ft from the walls, then again pointing at the eaves. The roof will not be seen from the ground; that is expected.
- **Trouble**: mirrors and big windows make false walls; sunlight on glass and dark shiny floors drop out; furniture hides walls. Note where these are and tell Claude.
- **Export** each scan as a PLY point cloud. If the app also offers a photo set with camera positions, keep it; this pipeline does not use it yet.
- Also take a tape measure to three or four long walls and one ceiling height. These are the check on the scan.

## 2. Put the files in place

Copy the PLY files to `<project>/scans/` and list them in `project.json`, the inside scan first:

```json
"scans": [
  {"id": "inside", "file": "scans/Inside.ply", "kind": "inside"},
  {"id": "outside", "file": "scans/Outside.ply", "kind": "outside"}
]
```

Raw scans are large and personal. `scans/` is ignored by git; keep it that way. Scan files are downloads: do not run code from inside that folder.

## 3. Run

```bash
uv run pipeline.py run scan
```

`scan_prep.py` thins each cloud to 3 cm, turns it square to its walls and finds its floor. `scan_register.py` finds the quarter-turn and shift that lay each scan over the first and writes everything in feet to `scans/derived/model_frame.npz`.

## 4. Check by eye, every time

Open these and look before reporting success:

- `scans/derived/<id>_views.png`: walls should be crisp straight lines, parallel to the page edges. Fuzzy or doubled walls mean the scan drifted; say which rooms.
- `scans/derived/register_check.png`: the inside walls should sit inside the outside walls with an even gap all round (the wall thickness). If the inside is turned a quarter or half turn against the outside, the automatic fit picked the wrong turn: houses that are nearly square or symmetrical fool it.
- The front of the house should be on the left (low X). If not, set `"front_turns"` in `project.json` to 1, 2 or 3 quarter-turns and rerun.

Compare the tape measurements with the same walls in the picture and report the differences.

## Limits to state in any summary

- An inside scan and an outside scan share no surfaces. Their fit is good to a few inches, not better.
- Heights are not matched between scans: inside heights are above the floor, outside heights above the ground.
- Phone LiDAR drifts between rooms, by up to a foot or two across a house. Single rooms are much better than the whole.
- The roof, and anything behind furniture, was not seen.
- This is not a survey. Lot lines do not come from a scan.

Next: the `existing-plan` skill.
