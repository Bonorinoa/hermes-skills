#!/usr/bin/env python3
"""Verify a Hermes config sweep: read-back expectations + a line diff against a backup.

Two independent checks per profile:
  1. EXPECTED - every key in the expected set (the neutral EXPECT map below, plus
                any --expect overrides) reads back at its expected value, through
                `hermes config get <key> --json`. Hermes parses its own config, so
                this script needs no YAML library and runs on plain python3.
  2. DRIFT    - a line diff of config.yaml against a pre-change backup. Every
                changed line is shown. Lines whose key is not one of the expected
                keys are counted as "outside the expected keys": read them.

Scope note: this checks the keys it is told about. It is not a general config
auditor and carries no provider- or user-specific values; pass those with
--expect. Lines under secret-looking keys (key, token, secret, password, auth, ...)
are never printed.

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

# Lines or keys matching this are never printed, only counted.
SENSITIVE = re.compile(r"key|token|secret|passw|credential|auth|cookie|bearer", re.I)
LINE_KEY = re.compile(r"^\s*-?\s*[\"']?([A-Za-z_][A-Za-z0-9_.-]*)[\"']?\s*:")
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


def secret_lines(text: str) -> list[bool]:
    """Per line: True when the line sits under a secret-looking key at any depth.

    Tracks the YAML key path by indentation, so a block scalar, a nested map or a
    list under `api_key:`, `auth:` or `credentials:` is secret even on lines that
    do not name the key themselves. Errs toward redacting.
    """
    flags: list[bool] = []
    stack: list[tuple[int, bool]] = []  # (indent, secret) of the open keys
    for line in text.splitlines():
        body = line.strip()
        if not body or body.startswith("#"):
            flags.append(any(s for _, s in stack))
            continue
        indent = len(line) - len(line.lstrip(" "))
        # A list item may sit at its parent key's indent ("auth:\n- value").
        item = body.startswith("-")
        inherited = any(s for i, s in stack if i < indent or (item and i == indent))
        m = LINE_KEY.match(line)
        if m and not inherited:
            while stack and stack[-1][0] >= indent:
                stack.pop()
            secret = bool(SENSITIVE.search(m.group(1)))
            stack.append((indent, secret))
            flags.append(secret or bool(SENSITIVE.search(line)))
        else:
            # a value line (block scalar, list item) or anything below a secret key
            flags.append(inherited or bool(SENSITIVE.search(line)))
    return flags


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
    if isinstance(got, numbers) and isinstance(want, numbers) \
            and not isinstance(got, bool) and not isinstance(want, bool):
        return abs(got - want) < 1e-9
    return got == want


def changed_lines(before: str, after: str) -> list[tuple[str, str, bool]]:
    """(sign, line, secret) for every removed or added line."""
    old, new = before.splitlines(), after.splitlines()
    old_secret, new_secret = secret_lines(before), secret_lines(after)
    out: list[tuple[str, str, bool]] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        out += [("-", old[i], old_secret[i]) for i in range(i1, i2)]
        out += [("+", new[j], new_secret[j]) for j in range(j1, j2)]
    return out


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
    leaf_names = {k.rsplit(".", 1)[-1] for k in expect}

    profiles = args.profiles
    if not profiles:
        if backup_dir and backup_dir.is_dir():
            profiles = sorted(p.name[: -len(".config.yaml")] for p in backup_dir.glob("*.config.yaml"))
        else:
            profiles = ["default"] + sorted(p.parent.name for p in (home / "profiles").glob("*/config.yaml"))
    if not profiles:
        print("no profiles to check (no backups and no configs found)")
        return 1

    failures = outside_total = 0
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
                lines = changed_lines(backup.read_text(encoding="utf-8"), cfg.read_text(encoding="utf-8"))
                outside = 0
                print(f"   drift: {len(lines)} changed line(s)")
                for sign, line, secret in lines:
                    m = LINE_KEY.match(line)
                    if secret or not (m and m.group(1) in leaf_names):
                        outside += 1
                    print(f"     {sign} {'<redacted line>' if secret else line[:90]}")
                if outside:
                    outside_total += outside
                    print(f"   note: {outside} changed line(s) outside the expected keys "
                          "(reported, not failed; review them)")
        print()

    print(f"checked {len(expect)} expected key(s) across {len(profiles)} profile(s)")
    if outside_total:
        print(f"UNEXPECTED CHANGES: {outside_total} line(s) (see notes above)")
    print("FAILURES:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
