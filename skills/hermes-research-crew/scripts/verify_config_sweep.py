#!/usr/bin/env python3
"""Verify a Hermes config sweep: read-back expectations + where the config changed.

Two independent checks per profile:
  1. EXPECTED - every key in the expected set (the neutral EXPECT map below, plus
                any --expect overrides) reads back at its expected value, through
                `hermes config get <key> --json`. Hermes parses its own config and
                masks credential values, so this script needs no YAML library.
  2. DRIFT    - which lines of config.yaml differ from a pre-change backup:
                a count and line numbers only. The text of a changed line is never
                printed, because a config file can hold keys in YAML forms that no
                line-based filter can recognise reliably. Open both files yourself
                to read the changes.

Scope note: this checks the keys it is told about. It is not a general config
auditor and carries no provider- or user-specific values; pass those with --expect.

Usage:
    python3 <SKILL_DIR>/scripts/verify_config_sweep.py \\
        --backup-dir ~/.hermes/config-backups/<date> \\
        --expect 'auxiliary.vision.provider=nous'

Exit 0 when every expectation reads back; 1 on a failure; 2 when hermes is not on PATH.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Readback values under a key matching this are never printed.
SENSITIVE = re.compile(r"key|token|secret|passw|credential|auth|cookie|bearer", re.I)
ABSENT = "<ABSENT>"

# Portable defaults only: no provider or model ids. Dotted key -> expected value.
# Use --expect for anything installation-specific.
EXPECT: dict[str, object] = {
    "compression.threshold": 0.40,
    "compression.target_ratio": 0.20,
    "compression.protect_last_n": 40,
    "compression.protect_first_n": 5,
    "tool_loop_guardrails.hard_stop_enabled": True,
    "sessions.auto_prune": True,
    "checkpoints.enabled": True,
    "curator.consolidate": True,
}


def shown(key: str, value) -> str:
    """Printable form of a value: redacted when the key, or any key inside it, looks secret."""
    if value == ABSENT:
        return value
    text = json.dumps(value)
    if SENSITIVE.search(key) or (isinstance(value, (dict, list)) and SENSITIVE.search(text)):
        return "<redacted>"
    return text[:40]


def profile_home(home: Path, profile: str) -> Path:
    return home if profile == "default" else home / "profiles" / profile


def config_get(hermes: str, profile: str, key: str, timeout: int):
    """Resolved value of one key, as Hermes itself reads it. ABSENT when not set."""
    argv = [hermes] + ([] if profile == "default" else ["-p", profile]) + ["config", "get", key, "--json"]
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return ABSENT
    if r.returncode != 0 or not r.stdout.strip():
        return ABSENT
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return r.stdout.strip()


def coerce(raw: str):
    """--expect values: JSON literals (true, 40, 0.4, null) are typed; anything else is a string."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_expect(items: list[str]) -> dict[str, object]:
    out: dict[str, object] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--expect needs KEY=VALUE, got: {item!r}")
        key, value = item.split("=", 1)
        out[key.strip().replace("/", ".")] = coerce(value.strip())
    return out


def same(got, want) -> bool:
    if isinstance(got, bool) != isinstance(want, bool):
        return False
    numbers = (int, float)
    if isinstance(got, numbers) and isinstance(want, numbers):
        return abs(got - want) < 1e-9
    return got == want


def span(a: int, b: int) -> str:
    """1-based inclusive line range for the half-open index range [a, b)."""
    return str(a + 1) if b - a == 1 else f"{a + 1}-{b}"


def changed_ranges(before: str, after: str) -> tuple[int, list[str], list[str]]:
    """(changed line count, backup line ranges, current line ranges). No line text."""
    old, new = before.splitlines(), after.splitlines()
    count, old_r, new_r = 0, [], []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        count += (i2 - i1) + (j2 - j1)
        if i2 > i1:
            old_r.append(span(i1, i2))
        if j2 > j1:
            new_r.append(span(j1, j2))
    return count, old_r, new_r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", "~/.hermes"),
                    help="where the config files are read for the diff; must be the home Hermes itself uses")
    ap.add_argument("--backup-dir", help="dir of <profile>.config.yaml snapshots")
    ap.add_argument("--expect", action="append", default=[], metavar="KEY=VALUE",
                    help="extra expectation, dotted key, e.g. 'auxiliary.vision.provider=nous'. Repeatable.")
    ap.add_argument("--profile", action="append", dest="profiles",
                    help="profile name (repeatable). Default: those with backups, else every profile found.")
    ap.add_argument("--no-defaults", action="store_true", help="check only the --expect keys")
    ap.add_argument("--timeout", type=int, default=30, help="seconds per `hermes config get`")
    args = ap.parse_args()

    hermes = shutil.which("hermes")
    if not hermes:
        print("hermes=missing: install Hermes or put it on PATH")
        return 2
    home = Path(args.hermes_home).expanduser()
    backup_dir = Path(args.backup_dir).expanduser() if args.backup_dir else None
    expect = {} if args.no_defaults else dict(EXPECT)
    expect.update(parse_expect(args.expect))

    profiles = args.profiles
    if not profiles:
        if backup_dir and backup_dir.is_dir():
            profiles = sorted(p.name[: -len(".config.yaml")] for p in backup_dir.glob("*.config.yaml"))
        else:
            profiles = ["default"] + sorted(p.parent.name for p in (home / "profiles").glob("*/config.yaml"))
    if not profiles:
        print("no profiles to check (no backups and no configs found)")
        return 1

    failures = changed_total = 0
    for profile in profiles:
        phome = profile_home(home, profile)
        cfg = phome / "config.yaml"
        if not cfg.exists():
            print(f"-- {profile}: NO CONFIG at {cfg}")
            failures += 1
            continue
        print(f"== {profile}")
        for key, want in expect.items():
            got = config_get(hermes, profile, key, args.timeout)
            if not same(got, want):
                print(f"   FAIL readback {key}: got {shown(key, got)} want {shown(key, want)}")
                failures += 1

        if backup_dir:
            backup = backup_dir / f"{profile}.config.yaml"
            if not backup.exists():
                print(f"   (no backup at {backup}; skipping drift check)")
            else:
                count, old_r, new_r = changed_ranges(backup.read_text(encoding="utf-8"),
                                                     cfg.read_text(encoding="utf-8"))
                changed_total += count
                print(f"   drift: {count} changed line(s)")
                if count:
                    print(f"     backup lines:  {', '.join(old_r) or '-'}")
                    print(f"     current lines: {', '.join(new_r) or '-'}")
        print()

    print(f"checked {len(expect)} expected key(s) across {len(profiles)} profile(s)")
    if changed_total:
        print(f"CHANGED LINES: {changed_total}. Open each backup and config.yaml yourself to read them; "
              "the files may hold keys, so do not paste them into a chat.")
    print("FAILURES:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
