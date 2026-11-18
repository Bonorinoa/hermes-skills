#!/usr/bin/env python3
"""Insurance backup: archive a Hermes home before a migration changes anything.

    python3 insurance_backup.py [--hermes-home PATH] [--out DIR]
                                [--retain forever|N] [--install-cron] [--yes]

  --hermes-home  home to archive (default $HERMES_HOME or ~/.hermes)
  --out          folder for the archive (default ~/hermes-backups)
  --retain       "forever", or a whole number of days. With N days, a cron line
                 that deletes THIS archive after N days is printed;
                 --install-cron installs it (after a yes, unless --yes).
  --yes          no prompts. Without --retain and without --yes, it asks.

What it does:
  - archives the home, skipping the reinstallable runtime and caches
    (top-level hermes-agent/, cache/, scratch/, installs/, tmp/);
  - copies every SQLite database through SQLite's online backup API, so a
    database that Hermes is writing to is captured consistently; the live
    -wal/-shm files are not copied (the snapshot already contains them);
  - writes the archive with owner-only permissions (0600).

The archive CONTAINS CREDENTIALS (auth.json, .env). Keep it on this machine and
never upload it. It restores the Hermes home only; other changes (profiles on
other machines, a gateway service, boards, remote repositories) are undone with
the plan's undo checklist (section 9).

Standard library only. Exit 0 on success, 1 on failure, 2 on bad arguments.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

EXCLUDED_TOP = {"hermes-agent", "cache", "scratch", "installs", "tmp"}
SIDE_FILES = ("-wal", "-shm", "-journal")
SQLITE_MAGIC = b"SQLite format 3\x00"
MARKER = "hermes-home-backup"


def parse_retain(value: str) -> str:
    if value == "forever" or re.fullmatch(r"[1-9][0-9]*", value):
        return value
    raise ValueError(f"bad retention value {value!r}: use 'forever' or a whole number of days")


def is_sqlite(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def snapshot_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def build_archive(home: Path, archive: Path) -> dict:
    stats = {"files": 0, "databases": 0, "db_fallbacks": 0, "vanished": 0}
    parent, base = home.parent, home.name
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as raw, tarfile.open(fileobj=raw, mode="w:gz") as tar, \
            tempfile.TemporaryDirectory(prefix="hermes-backup-") as stage:
        for dirpath, dirnames, filenames in os.walk(home):
            here = Path(dirpath)
            if here == home:
                dirnames[:] = [d for d in dirnames if d not in EXCLUDED_TOP]
            dirnames.sort()
            arc_dir = here.relative_to(parent).as_posix()
            try:
                tar.add(here, arcname=arc_dir, recursive=False)
            except FileNotFoundError:
                stats["vanished"] += 1
                continue
            names = set(filenames)
            for name in sorted(filenames):
                path = here / name
                arcname = f"{arc_dir}/{name}"
                if any(name.endswith(s) and name[: -len(s)] in names for s in SIDE_FILES):
                    continue  # covered by the snapshot of the main database file
                try:
                    if not path.is_symlink() and is_sqlite(path):
                        copy = Path(stage) / arcname
                        try:
                            snapshot_sqlite(path, copy)
                            stats["databases"] += 1
                        except sqlite3.Error:
                            copy = path  # locked or damaged: keep the raw bytes, and say so
                            stats["db_fallbacks"] += 1
                        tar.add(copy, arcname=arcname, recursive=False)
                    else:
                        tar.add(path, arcname=arcname, recursive=False)
                    stats["files"] += 1
                except FileNotFoundError:
                    stats["vanished"] += 1
    return stats


def install_cron(line: str, archive_name: str) -> bool:
    current = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    lines = current.stdout.splitlines() if current.returncode == 0 else []
    tag = f"{MARKER}:{archive_name}"
    kept = [l for l in lines if tag not in l]
    subprocess.run(["crontab", "-"], input="\n".join(kept + [line]) + "\n", text=True, check=True)
    check = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return check.returncode == 0 and tag in check.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", "~/.hermes"))
    ap.add_argument("--out", default="~/hermes-backups")
    ap.add_argument("--retain")
    ap.add_argument("--install-cron", action="store_true")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    home = Path(args.hermes_home).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()  # absolute: cron runs from $HOME
    if not home.is_dir():
        print(f"no such Hermes home: {home}", file=sys.stderr)
        return 1

    retain = args.retain
    if retain is None:
        if args.yes:
            retain = "forever"
        else:
            retain = input("Keep this backup forever, or delete it after N days? [forever / 7 / 14 / 30]: ").strip() or "forever"
    try:
        retain = parse_retain(retain)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2

    os.umask(0o077)
    if not out.exists():
        out.mkdir(parents=True, mode=0o700)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = out / f"{MARKER}-{stamp}.tar.gz"
    n = 2
    while archive.exists():
        archive = out / f"{MARKER}-{stamp}-{n}.tar.gz"
        n += 1

    print(f"Archiving {home} -> {archive} (runtime and caches skipped; databases snapshotted)")
    try:
        stats = build_archive(home, archive)
    except Exception as exc:  # noqa: BLE001 - report, never leave a partial archive behind
        archive.unlink(missing_ok=True)
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1

    with tarfile.open(archive, "r:gz") as tar:
        members = len(tar.getmembers())
    if members == 0:
        archive.unlink(missing_ok=True)
        print("empty archive; aborting", file=sys.stderr)
        return 1

    size_mb = archive.stat().st_size / 1024 / 1024
    print(f"Archive: {archive}  ({size_mb:.1f} MB, {members} entries, mode 600)")
    print(f"  files {stats['files']}, databases snapshotted {stats['databases']}, "
          f"databases copied raw {stats['db_fallbacks']}, vanished during the walk {stats['vanished']}")
    if stats["db_fallbacks"]:
        print("  WARNING: some databases could not be snapshotted and were copied raw; "
              "they may be inconsistent if Hermes was writing to them.")

    print(f"""
Restore (only to undo this migration):
  mv "{home}" "{home}-migrated"          # keep the changed one aside
  tar -xzf "{archive}" -C "{home.parent}"   # puts "{home.name}" back
Then reinstall the Hermes runtime (it is not in the archive) and restart.
Undo changes outside this folder with the plan's undo checklist (section 9).
When you are sure the new setup is good, delete the archive:
  rm -P "{archive}"      # macOS; on Linux: shred -u""")

    if retain != "forever":
        a = str(archive)
        line = (f'0 3 * * * find "{a}" -mtime +{retain} -delete 2>/dev/null; '
                f'[ -e "{a}" ] || (crontab -l | grep -v "{MARKER}:{archive.name}" | crontab -)'
                f'  # {MARKER}:{archive.name}')
        print(f"\nDelete this archive after {retain} days (the line removes itself afterwards):\n  {line}")
        if args.install_cron:
            answer = "yes" if args.yes else (input("Install this cron job? [y/N]: ").strip() or "no")
            if answer.lower() in {"y", "yes"}:
                try:
                    ok = install_cron(line, archive.name)
                except (OSError, subprocess.CalledProcessError) as exc:
                    print(f"cron install failed: {exc}", file=sys.stderr)
                    return 1
                if not ok:
                    print("cron install could not be confirmed; the line above stays available.", file=sys.stderr)
                    return 1
                print("cron installed (check with: crontab -l).")
            else:
                print("cron not installed; the line above stays available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
