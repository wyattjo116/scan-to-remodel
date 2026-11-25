"""Paths and small helpers shared by every script.

Every script takes --project <folder> (default: the REMODEL_PROJECT environment variable,
else ./house). A project folder holds one house:

    project.json            name, lot, north, the scans to read
    scans/                  raw scans from the phone (never in git)
    scans/derived/          what the scan steps write (never in git)
    existing/house.json     the house as it stands
    brief/                  brief.md, glossary.md, decisions.md
    rates.json              cost rates
    variants/<id>/          variant.json and everything built from it
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import house_geom as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FT = 0.3048


def parser(doc: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--project", default=os.environ.get("REMODEL_PROJECT", "house"),
                   help="project folder (default: $REMODEL_PROJECT or ./house)")
    return p


def project_dir(args) -> Path:
    p = Path(args.project)
    p = p if p.is_absolute() else ROOT / p
    if not (p / "project.json").exists():
        sys.exit(f"No project.json in {p}. Copy examples/sample-house/project.json to start one, or pass --project.")
    return p


def project(args) -> tuple[Path, dict]:
    p = project_dir(args)
    return p, G.load(p / "project.json")


def targets(pdir: Path, which: list[str]) -> list[tuple[str, Path, Path]]:
    """Resolve names to (id, house file, output folder). 'existing', a variant id, or 'all'."""
    out = []
    names = which or ["all"]
    vdir = pdir / "variants"
    every = sorted(d.name for d in vdir.iterdir() if (d / "variant.json").exists()) if vdir.exists() else []
    for n in names:
        if n in ("existing", "all") and (pdir / "existing" / "house.json").exists():
            out.append(("existing", pdir / "existing" / "house.json", pdir / "existing"))
        if n == "all":
            out += [(v, vdir / v / "variant.json", vdir / v) for v in every]
        elif n != "existing":
            if n not in every:
                sys.exit(f"No variant '{n}' in {vdir}. Found: {', '.join(every) or 'none'}")
            out.append((n, vdir / n / "variant.json", vdir / n))
    seen, uniq = set(), []
    for t in out:
        if t[0] not in seen:
            seen.add(t[0])
            uniq.append(t)
    return uniq


def existing_of(pdir: Path) -> dict | None:
    f = pdir / "existing" / "house.json"
    return G.load(f) if f.exists() else None


def resolve(p) -> Path:
    """A path typed by a person: as given if it exists, else relative to the repo root."""
    p = Path(p)
    return p if p.is_absolute() or p.exists() else ROOT / p
