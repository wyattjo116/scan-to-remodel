"""One entry point for every script.

    uv run pipeline.py list                         stages and what each needs
    uv run pipeline.py check                        what can run on this machine, and which keys are set
    uv run pipeline.py run plans model render       named stages, in pipeline order
    uv run pipeline.py run --all                    everything except manual stages
    uv run pipeline.py run render -- a-rear-wing-up --style sage --quick
    uv run pipeline.py --project examples/sample-house run plans

Each step runs from scripts/ in a pinned environment from requirements/*.txt, so the same commit
gives the same result on another machine. It needs only uv: no system Python, no Blender install.
The project folder is --project, else $REMODEL_PROJECT, else ./house.

Manual stages are never part of --all: they cost money, call an outside service, or overwrite
something checked by hand. Stages that need raw scans are skipped by --all when there are none.

To add a tool: write scripts/<name>.py, add a step to a stage below, add any new package to
requirements/<env>.in and run `uv run pipeline.py lock`.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
REQ = ROOT / "requirements"

ENVS = {"py": ("3.12", "py.txt"), "blender": ("3.11", "blender.txt")}

# name, summary, needs ("raw" | "frame" | "existing" | None), manual, steps [(env, script, args)]
STAGES = [
    ("sample-scan", "Make two made-up phone scans of the sample house (overwrites scans/sample-*.ply)", "existing", True,
     [("py", "make_sample_scan.py", [])]),
    ("scan", "Raw phone scans -> thinned, squared to the walls, all in one frame in feet", "raw", False,
     [("py", "scan_prep.py", []), ("py", "scan_register.py", [])]),
    ("trace", "Draft existing/house.draft.json and the plan slice from the scans", "frame", False,
     [("py", "scan_trace.py", [])]),
    ("scan-check", "How far existing/house.json is from the scans, with a picture", "frame", False,
     [("py", "scan_check.py", [])]),
    ("plans", "Floor plans (PNG, DXF), areas, checks and the cost estimate", "existing", False,
     [("py", "plans.py", [])]),
    ("model", "Blender model (house.blend, house.glb) of the existing house and each variant", "existing", False,
     [("blender", "blender_build.py", [])]),
    ("ifc", "IFC model for Bonsai, FreeCAD or any BIM tool", "existing", False,
     [("py", "ifc_export.py", [])]),
    ("render", "Cycles renders and line drawings (a few minutes per variant on a CPU)", "existing", False,
     [("blender", "render.py", [])]),
    ("picture", "AI picture from a render and its line drawing through OpenAI (network; costs money per picture)", "existing", True,
     [("py", "image_pass.py", [])]),
    ("drift", "How far an AI picture drifted from the model: a number and an overlay", "existing", True,
     [("py", "drift_check.py", [])]),
]
NAMES = [s[0] for s in STAGES]


def project_dir(a: list[str]) -> tuple[Path, list[str]]:
    p = os.environ.get("REMODEL_PROJECT", "house")
    if "--project" in a:
        i = a.index("--project")
        p = a[i + 1]
        a = a[:i] + a[i + 2:]
    p = Path(p)
    return (p if p.is_absolute() else ROOT / p), a


def have(needs: str | None, pdir: Path) -> tuple[bool, str]:
    if needs == "raw":
        scans = json.loads((pdir / "project.json").read_text(encoding="utf-8")).get("scans", []) if (pdir / "project.json").exists() else []
        ok = any((pdir / s["file"]).exists() for s in scans)
        return ok, "raw scans listed in project.json" + ("" if ok else " MISSING")
    if needs == "frame":
        ok = (pdir / "scans" / "derived" / "model_frame.npz").exists()
        return ok, "scans/derived/model_frame.npz" + ("" if ok else " MISSING (run the scan stage)")
    if needs == "existing":
        ok = (pdir / "existing" / "house.json").exists()
        return ok, "existing/house.json" + ("" if ok else " MISSING (draft it with the trace stage, or write it by hand)")
    return True, "nothing"


def run_step(env: str, script: str, args: list[str], pdir: Path) -> None:
    py, lock = ENVS[env]
    cmd = ["uv", "run", "--no-project", "--python", py, "--with-requirements", str(REQ / lock), script, "--project", str(pdir), *args]
    print(f"\n--- {script} {' '.join(args)}  [{env}]", flush=True)
    t = time.time()
    r = subprocess.run(cmd, cwd=SCRIPTS)
    if r.returncode:
        sys.exit(f"FAILED: {script} (exit {r.returncode})")
    print(f"--- ok in {time.time() - t:.0f}s", flush=True)


def main() -> None:
    pdir, a = project_dir(sys.argv[1:])
    cmd = a[0] if a else "list"
    if cmd == "list":
        for name, summary, needs, manual, steps in STAGES:
            print(f"{name:12} {'manual' if manual else '      '}  {summary}")
            print(f"{'':20}needs {have(needs, pdir)[1]}; runs {', '.join(s[1] for s in steps)}")
    elif cmd == "check":
        print(f"project {pdir}" + ("" if (pdir / "project.json").exists() else "   (no project.json here)"))
        for name, _, needs, manual, steps in STAGES:
            ok, why = have(needs, pdir)
            print(f"{'ok     ' if ok else 'BLOCKED'} {name:12} needs {why}")
        r = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        print(f"tool    {r.stdout.strip() or 'uv not found'}")
        sys.path.insert(0, str(SCRIPTS))
        import keys                              # which keys are set; never their values
        print("\n".join(keys.report()))
    elif cmd == "lock":
        for py, lock in ENVS.values():
            src = REQ / lock.replace(".txt", ".in")
            subprocess.run(["uv", "pip", "compile", "-q", "--universal", "--python-version", py, str(src), "-o", str(REQ / lock)], check=True)
            print("locked", lock)
    elif cmd == "run":
        extra = a[a.index("--") + 1:] if "--" in a else []
        want = a[1:a.index("--")] if "--" in a else a[1:]
        everything = "--all" in want
        want = [w for w in want if w != "--all"]
        bad = [w for w in want if w not in NAMES]
        if bad or not (want or everything):
            sys.exit(f"unknown or missing stage: {bad}. Stages: {', '.join(NAMES)}")
        if extra and len(want) != 1:
            sys.exit("arguments after -- go to one stage's last step; name exactly one stage")
        for name, _, needs, manual, steps in STAGES:
            if everything and manual:
                print(f"skip {name}: manual stage")
                continue
            if not everything and name not in want:
                continue
            ok, why = have(needs, pdir)
            if not ok:
                if everything:
                    print(f"skip {name}: needs {why}")
                    continue
                sys.exit(f"{name} cannot run: needs {why}")
            print(f"\n=== {name}")
            for i, (env, script, args) in enumerate(steps):
                run_step(env, script, args + (extra if i == len(steps) - 1 else []), pdir)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
