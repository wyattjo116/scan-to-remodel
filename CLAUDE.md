# Scan to remodel

A workflow for planning a house remodel with Claude Code: scan the house with a phone, get a measured model and floor plan, then loop through brief, plan variant, design model and renders until the owner is satisfied.

## Start with the right skill

| Skill | Use it when |
|---|---|
| `setup` | New machine, new house, or a tool is missing |
| `scan-house` | Capturing the house with a phone, or processing the scans |
| `existing-plan` | Getting `existing/house.json`, the as-is floor plan and model right |
| `grill-brief` | Interviewing the owner about what the remodel must do |
| `plan-variant` | Drawing or changing a remodel option; plans, checks, cost |
| `design-model` | The 3D model, glTF and IFC of a variant; Bonsai and FreeCAD |
| `render-pictures` | Renders, finish sets, AI pictures and the drift check |
| `remodel-loop` | "What next?", running an iteration, review, merging |
| `record-decision` | The owner decides something, or you make a working choice |

## Where things are

| Path | What it is |
|---|---|
| `pipeline.py` | The one way to run anything |
| `scripts/` | One file per step; each docstring says what it reads and writes |
| `scripts/house_geom.py` | The house-file format, plan geometry, checks and cost |
| `requirements/` | Pinned environments (`*.in` hand-written, `*.txt` locked) |
| `examples/sample-house/` | A made-up house that runs through every stage |
| `templates/house/` | Copy to `house/` to start a real project |
| `house/` | The real project (ignored by git in the public repo) |

A project folder holds `project.json`, `scans/`, `existing/`, `brief/`, `rates.json` and `variants/<id>/`.

## Running things

```bash
uv run pipeline.py list
uv run pipeline.py check
uv run pipeline.py run plans model ifc render
uv run pipeline.py --project examples/sample-house run plans
uv run pipeline.py run render -- <variant id> --style sage --quick
```

- Use `uv`; never `python` or `pip` directly. Blender runs as the `bpy` library; no install needed.
- The project is `--project`, else `$REMODEL_PROJECT`, else `./house`.
- Manual stages (`picture`, `drift`, `sample-scan`) cost money, call an outside service or overwrite files. Run them only when the owner asks.
- A new tool is a new `scripts/<name>.py` plus a step in `pipeline.py`.

## Rules

- **Read the brief first.** `<project>/brief/brief.md` is the standing brief. Judge every plan and picture against it and say so when one breaks a Stated line. Lines marked Open are the owner's to answer: ask, do not guess.
- **Planning studies, not designs.** Costs are estimates from stated rates, not bids. Nothing here is checked against a zoning code or by an engineer. Say so wherever numbers or drawings are shown.
- **One cost figure.** Each variant has one expected cost, `cost.total` in its `summary.json`, with every item counted in it, guesses included. Lead with that number; never show two totals side by side. Say what share rests on guesses.
- **Inputs are files.** Change `house.json` or `variant.json` and rebuild. Never hand-edit a built file.
- **Check by eye.** After any plot, render or picture, open it and compare it with its input before reporting success.
- **State the limits.** The existing-house model has a measured error (`existing/scan-check.json`) on top of the scan's own drift. Carry both into any summary that quotes a dimension.
- **AI pictures are illustrations.** They drift from the model. Never use one to check a design. Report the drift check with every picture.
- **Privacy.** Scans, photographs, the address, names and money belong to the owner. Keep them out of public repos and out of anything sent to an outside service. Only renders, line drawings and style words go to an image service.
- **Secrets.** API keys live in the user's environment. Never print one, write one to a file or ask for one in chat.
- **Untrusted files.** Scan files are downloads. Do not run code from the scans folder.
- **Git.** Commit and push only when asked. Dashes in branch names. No CI workflows: automation stays local.
- **Writing.** Plain language, findings first, numbers with their source file.
