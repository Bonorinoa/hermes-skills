#!/usr/bin/env python3
"""Read-only inventory of run residue in project roots. Deletes nothing.

For each --root it reports:
  1. scratch folders  <root>/<scratch>/<card-id>/  with size and age; STALE when
     older than --ttl-days (the _evidence folder is never listed);
  2. large files not tracked by git (untracked or ignored), above --big-mb;
  3. worktrees that git reports as prunable.

The hygiene desk decides what to do with the report (references/hygiene.md).
Exit 0 after a report, 2 on bad arguments.

    python3 hygiene_scan.py --root ~/research/proj-a --root ~/research/proj-b
    python3 hygiene_scan.py --root ~/research/proj-a --ttl-days 7 --big-mb 500 --json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

SKIP_DIRS = {".git"}


def tree_stats(path: Path) -> tuple[int, float]:
    """Total bytes and newest mtime under path (path, subfolders and files)."""
    total, newest = 0, path.stat().st_mtime
    for dirpath, dirnames, filenames in os.walk(path):
        for name in [*dirnames, *filenames]:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except FileNotFoundError:
                continue
            if name in filenames:
                total += st.st_size
            newest = max(newest, st.st_mtime)
    return total, newest


def git(root: Path, *args: str) -> str | None:
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def scan_root(root: Path, scratch: str, ttl_days: float, big_bytes: int) -> dict:
    now = time.time()
    report: dict = {"root": str(root), "scratch": [], "large_untracked": [], "prunable_worktrees": []}

    sdir = root / scratch
    if sdir.is_dir():
        for child in sorted(p for p in sdir.iterdir() if p.is_dir() and p.name != "_evidence"):
            size, newest = tree_stats(child)
            age = (now - newest) / 86400
            report["scratch"].append({"path": str(child), "bytes": size,
                                      "age_days": round(age, 2), "stale": age > ttl_days})

    tracked_out = git(root, "ls-files", "-z")
    is_repo = tracked_out is not None
    tracked = set(tracked_out.split("\0")) if tracked_out else set()
    report["git_repo"] = is_repo
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = Path(dirpath) / name
            try:
                st = full.lstat()
            except FileNotFoundError:
                continue
            if st.st_size < big_bytes or full.is_symlink():
                continue
            rel = full.relative_to(root).as_posix()
            if rel in tracked:
                continue
            report["large_untracked"].append({"path": str(full), "bytes": st.st_size})

    if is_repo:
        porcelain = git(root, "worktree", "list", "--porcelain") or ""
        current = None
        for line in porcelain.splitlines():
            if line.startswith("worktree "):
                current = line[len("worktree "):]
            elif line.startswith("prunable") and current:
                report["prunable_worktrees"].append(current)
    return report


def human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", action="append", required=True, help="project root (repeatable)")
    ap.add_argument("--scratch", default=".scratch", help="scratch folder name inside each root")
    ap.add_argument("--ttl-days", type=float, default=3.0)
    ap.add_argument("--big-mb", type=float, default=200.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if (not (math.isfinite(args.ttl_days) and math.isfinite(args.big_mb))
            or args.ttl_days < 0 or args.big_mb < 0 or args.big_mb > 1e9):
        ap.error("--ttl-days must be a finite number >= 0; --big-mb a number from 0 to 1e9")

    roots = [Path(r).expanduser().resolve() for r in args.root]
    missing = [str(r) for r in roots if not r.is_dir()]
    if missing:
        print(f"not a directory: {', '.join(missing)}", file=sys.stderr)
        return 2

    big = int(args.big_mb * 1024 * 1024)
    reports = [scan_root(r, args.scratch, args.ttl_days, big) for r in roots]

    if args.json:
        print(json.dumps({"ttl_days": args.ttl_days, "big_mb": args.big_mb, "roots": reports}, indent=2))
        return 0

    for rep in reports:
        print(f"== {rep['root']}" + ("" if rep["git_repo"] else "  (not a git repo)"))
        stale = [s for s in rep["scratch"] if s["stale"]]
        print(f"   scratch: {len(rep['scratch'])} folder(s), {len(stale)} stale")
        for s in rep["scratch"]:
            print(f"     {'STALE' if s['stale'] else 'fresh'}  {human(s['bytes']):>8}  "
                  f"{s['age_days']:6.1f} d  {s['path']}")
        print(f"   large untracked files (>= {args.big_mb:g} MB): {len(rep['large_untracked'])}")
        for f in sorted(rep["large_untracked"], key=lambda x: -x["bytes"]):
            print(f"     {human(f['bytes']):>8}  {f['path']}")
        print(f"   prunable worktrees: {len(rep['prunable_worktrees'])}")
        for w in rep["prunable_worktrees"]:
            print(f"     {w}")
    print("\nread-only: nothing was deleted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
