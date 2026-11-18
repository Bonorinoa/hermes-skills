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
    (top-level hermes-agent/, cache/, scratch/, installs/, tmp/); symlinks are
    kept as links, never followed;
  - copies every SQLite database through SQLite's online backup API, so a
    database that Hermes is writing to is captured consistently; the live
    -wal/-shm files are not copied (the snapshot already contains them). A
    database that cannot be snapshotted is copied raw with its -wal/-shm files,
    and a WARNING says so;
  - writes the archive owner-only (0600) into an owner-only folder (0700); an
    existing --out folder that other users can read is refused.

The printed restore and cron commands quote every path. A cron line is only
offered when the archive path has no characters cron or the shell would misread
(%, quotes, $, `, \\); otherwise delete the archive by hand.

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
import shlex
import sqlite3
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.parse
from pathlib import Path

EXCLUDED_TOP = {"hermes-agent", "cache", "scratch", "installs", "tmp"}
SIDE_FILES = ("-wal", "-shm", "-journal")
SQLITE_MAGIC = b"SQLite format 3\x00"
MARKER = "hermes-home-backup"
# Characters a cron line can carry safely once single-quoted (no %, quotes, $, `, \).
CRON_SAFE = re.compile(r"[A-Za-z0-9 ._/+,:@~-]+")


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
    """Consistent copy through SQLite's online backup API (includes WAL content)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Percent-encode the path: '?', '#' and '%' would otherwise be parsed as URI syntax
    # and open a different (empty) database.
    uri = "file:" + urllib.parse.quote(str(src)) + "?mode=ro"
    source = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        opened = source.execute("PRAGMA database_list").fetchone()[2]
        if os.path.realpath(opened) != os.path.realpath(src):
            raise sqlite3.OperationalError(f"opened {opened!r} instead of {str(src)!r}")
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
            # os.walk does not descend into symlinked directories; keep them as links.
            for d in [d for d in dirnames if (here / d).is_symlink()]:
                try:
                    tar.add(here / d, arcname=f"{arc_dir}/{d}", recursive=False)
                    stats["files"] += 1
                except FileNotFoundError:
                    stats["vanished"] += 1
            dirnames[:] = [d for d in dirnames if not (here / d).is_symlink()]
            names = set(filenames)
            raw_dbs: set[str] = set()
            for name in sorted(filenames):
                path = here / name
                arcname = f"{arc_dir}/{name}"
                if any(name.endswith(s) and name[: -len(s)] in names for s in SIDE_FILES):
                    continue  # covered by the snapshot (or added below with a raw copy)
                try:
                    if not path.is_symlink() and is_sqlite(path):
                        copy = Path(stage) / arcname
                        try:
                            snapshot_sqlite(path, copy)
                            stats["databases"] += 1
                        except sqlite3.Error:
                            copy = path  # locked or damaged: keep the raw bytes, and say so
                            stats["db_fallbacks"] += 1
                            raw_dbs.add(name)
                        tar.add(copy, arcname=arcname, recursive=False)
                    else:
                        tar.add(path, arcname=arcname, recursive=False)
                    stats["files"] += 1
                except FileNotFoundError:
                    stats["vanished"] += 1
            # A raw database copy needs its -wal/-shm/-journal files too.
            for name in sorted(raw_dbs):
                for s in SIDE_FILES:
                    side = here / (name + s)
                    if side.exists():
                        try:
                            tar.add(side, arcname=f"{arc_dir}/{name}{s}", recursive=False)
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
    if out.exists():
        if not out.is_dir():
            print(f"--out exists and is not a folder: {out}", file=sys.stderr)
            return 1
        mode = stat.S_IMODE(out.stat().st_mode)
        if mode & 0o077:
            print(f"--out {out} is readable by other users (mode {mode:o}); the archive holds credentials.\n"
                  f"Use a private folder, or run: chmod 700 {shlex.quote(str(out))}", file=sys.stderr)
            return 1
    else:
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

    q = shlex.quote
    print(f"""
Restore (only to undo this migration):
  mv {q(str(home))} {q(str(home) + '-migrated')}          # keep the changed one aside
  tar -xzf {q(str(archive))} -C {q(str(home.parent))}   # puts {home.name} back
Then reinstall the Hermes runtime (it is not in the archive) and restart.
Undo changes outside this folder with the plan's undo checklist (section 9).
When you are sure the new setup is good, delete the archive:
  rm -P {q(str(archive))}      # macOS; on Linux: shred -u""")

    if retain != "forever":
        a = str(archive)
        if not CRON_SAFE.fullmatch(a):
            print(f"\nNo cron line: the archive path contains characters cron or the shell would\n"
                  f"misread (allowed: letters, digits, space and . _ / + , : @ ~ -). Delete it by hand\n"
                  f"after {retain} days, or rerun with a plainer --out.")
            return 0
        tag = f"{MARKER}:{archive.name}"
        line = (f"0 3 * * * find {q(a)} -mtime +{retain} -delete 2>/dev/null; "
                f"[ -e {q(a)} ] || (crontab -l | grep -vF {q(tag)} | crontab -)"
                f"  # {tag}")
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
