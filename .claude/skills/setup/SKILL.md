---
name: setup
description: Set up this repo on a new machine or for a new house - install uv, check the pipeline runs on the sample house, start a project folder, and walk through the optional tools (Blender app, Bonsai, FreeCAD, Unreal, an OpenAI key). Use when someone has just cloned the repo, asks "how do I start", a stage fails because a tool is missing, or they want one of the optional tools.
---

# Setup

Work through the steps in order. Run each check yourself and report what you found; ask before installing anything, and install only what the person says yes to. Everything in step 1 and 2 is needed. Everything in step 4 is optional: say what each one adds and let them pick.

## 1. The one required tool: uv

Every script runs through `uv`, which downloads the right Python and packages by itself. There is no need for a system Python or a Blender install: the `bpy` package is Blender as a Python library.

```bash
uv --version
```

If it is missing, offer the official installer and run it only on a yes:

- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

Never call `python` or `pip` directly in this repo.

## 2. Prove it works on the sample house

```bash
uv run pipeline.py --project examples/sample-house check
uv run pipeline.py --project examples/sample-house run plans model ifc
uv run pipeline.py --project examples/sample-house run render -- a-rear-wing-up --views street --quick
```

The first run downloads about 400 MB (Blender as a library) and takes a few minutes. Open `examples/sample-house/variants/a-rear-wing-up/plan-main.png` and the quick render and show them. If a stage fails, read the error, fix the cause and rerun only that stage.

To try the scan steps with no phone: `run sample-scan`, then `run scan trace scan-check` on the same project.

## 3. Start a project for a real house

1. Ask whether this clone is private. A real house's files (scans, address, budget) must not go to a public repo. If they used GitHub's "Use this template" to make a private copy, delete the `/house/` line from `.gitignore` so the project is saved with the repo. If the clone is public, leave that line in.
2. Copy `templates/house/` to `house/` and fill in `house/project.json` with them: a name (not the address), which way north is, the lot size, and any zoning limits they already know. Leave what they do not know as `null` and list it as an open question in `house/brief/brief.md`.
3. `uv run pipeline.py check` should now show the project and which stages are blocked on what.

Next step: the `scan-house` skill.

## 4. Optional tools

| Tool | What it adds | Needed for |
|---|---|---|
| Blender app (4.2 or later; 5.x tested) | Open `house.blend` and move things by hand | Looking at and editing models on screen |
| Bonsai (a Blender extension) | Open `house.ifc` as a BIM model; cut dimensioned plans, sections and sheets | Architect-style drawings |
| FreeCAD 1.0 or later | Another way to open `house.ifc` and make drawings with TechDraw | People who prefer FreeCAD |
| OpenAI API key | Photograph-like pictures from renders (`picture` stage); costs money per picture | AI pictures |
| Unreal Engine 5 | Much faster renders on a strong GPU | Large batches of pictures. Not scripted in this repo yet |

Install commands, to offer and not to assume:

- **Blender**: from blender.org, or `winget install BlenderFoundation.Blender` (Windows), `brew install --cask blender` (macOS), `snap install blender --classic` (Linux).
- **Bonsai**: with Blender installed, `blender --online-mode --command extension install bonsai -s -e`. Or in Blender: Edit > Preferences > Get Extensions > search "Bonsai". Then File > Open IFC Project and pick a `house.ifc`.
- **FreeCAD**: from freecad.org, or `winget install FreeCAD.FreeCAD`, `brew install --cask freecad`. Open `house.ifc` with File > Open in the BIM workbench.
- **OpenAI key**: the person makes the key on OpenAI's site and sets it themselves, in their own terminal. Windows: `setx OPENAI_API_KEY "..."`. macOS and Linux: add `export OPENAI_API_KEY=...` to the shell profile. Never ask them to paste a key into chat, never print one, never write one to a file in the repo. `uv run pipeline.py check` says whether it is present.
- **Unreal**: through the Epic Games Launcher. Import `house.glb`. There is no script for it here; say so.

After each install, run its check (`blender --version`, open the sample `house.ifc`, `pipeline.py check`) and report the result.

## 5. Finish

Tell them what is installed, what was skipped, and the next step. Record any choice that later work depends on (for example "no AI pictures on this project") with the `record-decision` skill.
