#!/usr/bin/env python3
"""Read-only snapshot of a Hermes install. Compact lines, no secrets.

Run from any working directory. Paths come from this file's location and from
HERMES_HOME (default ~/.hermes), never from the current directory.

Prints provider names only. Account labels from `hermes auth list` can be
email addresses and are dropped. Exit 0 when the probe itself ran. A missing
`hermes` binary is a fact (`hermes=missing`), not a crash.
"""
from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import yaml_load  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parents[1]
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
PROVIDER_RE = re.compile(r"^([a-z0-9][a-z0-9_-]*)\b")
TOOLS = ("git", "gh", "uv", "docker", "ollama")


def provider_names(text: str) -> list[str]:
    """First token of each auth-list row, when it looks like a provider id."""
    found: list[str] = []
    for line in text.splitlines():
        head = line.strip().split("(", 1)[0]
        if "@" in head:
            continue
        match = PROVIDER_RE.match(head.strip())
        if match:
            found.append(match.group(1))
    return found


def profile_names(text: str) -> list[str]:
    names: list[str] = []
    for line in text.splitlines():
        token = line.strip().split()[0] if line.strip() else ""
        token = token.strip("*|-")
        if NAME_RE.match(token) and token not in {"name", "profile", "NAME"}:
            names.append(token)
    return names


def _run(argv: list[str], timeout: int) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 124, ""
    out = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, out


def _clip(text: str, limit: int = 80) -> str:
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    line = re.sub(r"\s+", " ", line)
    return line[:limit]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", "~/.hermes"))
    ap.add_argument("--timeout", type=int, default=20)
    args = ap.parse_args()
    if args.timeout < 1:
        print("timeout must be >= 1", file=sys.stderr)
        return 2

    home = Path(args.hermes_home).expanduser()
    hermes = shutil.which("hermes")
    present = [t for t in TOOLS if shutil.which(t)]
    missing = [t for t in TOOLS if t not in present]
    gpu = "none"
    if shutil.which("nvidia-smi"):
        code, out = _run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            args.timeout,
        )
        gpu = _clip(out) if code == 0 and out.strip() else "present"

    print(f"skill_dir={SKILL_DIR}")
    print(f"python={sys.version.split()[0]}")
    print(f"yaml_loader={yaml_load.which_loader()}")
    print(f"os={platform.system()}")
    print(f"hermes={'ok' if hermes else 'missing'}")
    print(f"tools={','.join(present) or 'none'}")
    print(f"tools_missing={','.join(missing) or 'none'}")
    print(f"gpu={gpu}")

    if not hermes:
        print("hermes_version=missing")
        print("providers=")
        print("profiles=")
        print("boards=unknown")
        print("dispatch_in_gateway=unknown")
        print("gateway=unknown")
        return 0

    code, ver = _run([hermes, "--version"], args.timeout)
    print(f"hermes_version={_clip(ver) if code == 0 else 'unknown'}")

    _code, auth = _run([hermes, "auth", "list"], args.timeout)
    names = provider_names(auth)
    print(f"providers={','.join(names)}")

    _code, prof = _run([hermes, "profile", "list"], args.timeout)
    prof_names = profile_names(prof)[:20]
    print(f"profiles={','.join(prof_names)}")

    bcode, boards = _run([hermes, "kanban", "boards", "list"], args.timeout)
    if bcode == 0:
        count = sum(1 for line in boards.splitlines() if line.strip())
        print(f"boards={count}")
    else:
        print("boards=unknown")

    dcode, dispatch = _run([hermes, "config", "get", "kanban.dispatch_in_gateway"], args.timeout)
    print(f"dispatch_in_gateway={_clip(dispatch, 40) if dcode == 0 else 'unknown'}")

    gcode, _gw = _run([hermes, "gateway", "status"], args.timeout)
    print(f"gateway={'up' if gcode == 0 else 'down'}")
    if home.is_dir():
        print(f"hermes_home=present")
    else:
        print("hermes_home=absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
