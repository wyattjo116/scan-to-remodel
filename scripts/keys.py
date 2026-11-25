"""Find an API key without printing it or writing it anywhere.

Every script that calls an outside service gets its key here. It looks, in this order, in:

  1. the process environment
  2. on Windows, the user environment in the registry. `setx NAME "value"` writes there, and a
     terminal that was already open does not see it, but this lookup does
  3. a KEY=value file given with --env-file

Keep keys out of the repo: no .env file in the project folder, nothing pasted into chat.

    uv run pipeline.py check        # ends with which keys are present, never their values
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

KNOWN = {"OPENAI_API_KEY": "stage picture (optional AI pictures)"}


def find(name: str, env_file: str | None = None) -> tuple[str, str]:
    """Return (value, where it was found). Both are empty if the key is not set."""
    value = os.environ.get(name, "").strip()
    if value:
        return value, "process environment"
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                value = str(winreg.QueryValueEx(k, name)[0]).strip()
        except OSError:
            value = ""
        if value:
            return value, "Windows user environment"
    if env_file:
        for line in Path(env_file).read_text(encoding="utf-8").splitlines():
            n, _, v = line.strip().removeprefix("export ").partition("=")
            if n.strip() == name and v.strip().strip("\"'"):
                return v.strip().strip("\"'"), "--env-file"
    return "", ""


def get(name: str, env_file: str | None = None) -> str:
    value, _ = find(name, env_file)
    if not value:
        how = f'setx {name} "..."' if sys.platform == "win32" else f"export {name}=...   (in your shell profile)"
        sys.exit(f"{name} not found. Set it once, in your own terminal:  {how}")
    return value


def report() -> list[str]:
    lines = []
    for name, used_by in KNOWN.items():
        _, where = find(name)
        lines.append(f"key     {name:18} {'present (' + where + ')' if where else 'not set'}; used by {used_by}")
    return lines


if __name__ == "__main__":
    print("\n".join(report()))
