#!/usr/bin/env python3
"""Verify a Hermes config sweep: read-back expectations + leaf-level drift proof.

Two independent checks per profile:
  1. EXPECTED - every key in the expected set (the neutral EXPECT map below, plus
                any --expect overrides) reads back at its expected value.
  2. DRIFT    - a leaf-level diff against a pre-change backup shows ONLY the
                intended keys moved (any extra change is surfaced, not hidden).

Scope note: this checks the keys it is told about. It is not a general config
auditor, and it deliberately carries no provider- or user-specific values --
supply those with --expect. Values under secret-looking keys (key, token,
secret, password, auth, ...) are never printed. Changes outside the expected
keys are reported and counted, not failed: read them.

Usage:
    ~/.hermes/hermes-agent/venv/bin/python verify_config_sweep.py \
        --backup-dir ~/.hermes/config-backups/2026-10-14-migration \
        --expect 'auxiliary/vision/provider=nous' \
        --expect 'auxiliary/vision/model=google/gemini-3.8-flash'

Requires PyYAML. The Hermes runtime python has it; a bare system python3 often
does not.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required (it ships with Hermes): pip install pyyaml")

# Values under any key matching this are never printed, only reported as changed.
SENSITIVE = re.compile(r"key|token|secret|passw|credential|auth|cookie|bearer", re.I)


def shown(path: tuple[str, ...], value) -> str:
    """Printable form of a config value: redacted when any path part looks secret."""
    if value == "<ABSENT>":
        return value
    if any(SENSITIVE.search(part) for part in path):
        return "<redacted>"
    return str(value)[:28]

# Portable defaults only -- no provider or model ids baked in. Dotted path ->
# expected value. Use --expect for anything installation-specific.
EXPECT: dict[tuple[str, ...], object] = {
    ("compression", "threshold"): 0.40,
    ("compression", "target_ratio"): 0.20,
    ("compression", "protect_last_n"): 40,
    ("compression", "protect_first_n"): 5,
    ("tool_loop_guardrails", "hard_stop_enabled"): True,
    ("sessions", "auto_prune"): True,
    ("checkpoints", "enabled"): True,
    ("curator", "consolidate"): True,
}


def config_path(home: Path, profile: str) -> Path:
    if profile == "default":
        return home / "config.yaml"
    return home / "profiles" / profile / "config.yaml"


def leaves(obj, prefix: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    """Flatten a nested mapping to {path_tuple: value}; lists stay whole."""
    out: dict[tuple[str, ...], object] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(leaves(value, prefix + (str(key),)))
    else:
        out[prefix] = obj
    return out


def get(tree, path: tuple[str, ...]):
    cur = tree
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def profiles_from_backup(backup_dir: Path) -> list[str]:
    """<profile>.config.yaml in the backup dir -> profile names."""
    return sorted(p.name[: -len(".config.yaml")] for p in backup_dir.glob("*.config.yaml"))


def coerce(raw: str):
    """Parse an --expect value the way YAML would, so true/1/0.4 compare right."""
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError:
        return raw


def parse_expect(items: list[str]) -> dict[tuple[str, ...], object]:
    out: dict[tuple[str, ...], object] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--expect needs KEY=VALUE, got: {item!r}")
        key, value = item.split("=", 1)
        out[tuple(key.strip().split("/"))] = coerce(value)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hermes-home", default="~/.hermes")
    ap.add_argument("--backup-dir", help="dir of <profile>.config.yaml snapshots")
    ap.add_argument(
        "--expect", action="append", default=[], metavar="KEY=VALUE",
        help="extra expectation as dotted/path=value, e.g. "
             "'auxiliary/vision/provider=nous'. Repeatable.",
    )
    ap.add_argument(
        "--profile", action="append", dest="profiles",
        help="profile name (repeatable). Default: those with backups, else every profile found.",
    )
    args = ap.parse_args()

    home = Path(args.hermes_home).expanduser()
    backup_dir = Path(args.backup_dir).expanduser() if args.backup_dir else None
    expect = dict(EXPECT)
    expect.update(parse_expect(args.expect))

    profiles = args.profiles
    if not profiles:
        if backup_dir and backup_dir.is_dir():
            profiles = profiles_from_backup(backup_dir)
        else:
            profiles = ["default"] + sorted(
                p.parent.name for p in (home / "profiles").glob("*/config.yaml")
            )
    if not profiles:
        print("no profiles to check (no backups and no configs found)")
        return 1

    failures = 0
    unexpected_total = 0
    for profile in profiles:
        path = config_path(home, profile)
        if not path.exists():
            print(f"-- {profile}: NO CONFIG at {path}")
            failures += 1
            continue

        tree = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        print(f"== {profile}")

        for dotted, want in expect.items():
            got = get(tree, dotted)
            if got != want:
                print(f"   FAIL readback {'/'.join(dotted)}: got {shown(dotted, got)} want {shown(dotted, want)}")
                failures += 1

        if backup_dir:
            backup = backup_dir / f"{profile}.config.yaml"
            if not backup.exists():
                print(f"   (no backup at {backup}; skipping drift check)")
            else:
                before = leaves(yaml.safe_load(backup.read_text(encoding="utf-8")) or {})
                after = leaves(tree)
                changed = [
                    (k, before.get(k, "<ABSENT>"), after.get(k, "<ABSENT>"))
                    for k in set(before) | set(after)
                    if before.get(k, "<ABSENT>") != after.get(k, "<ABSENT>")
                ]
                print(f"   drift: {len(changed)} leaf change(s)")
                for key, old, new in sorted(changed):
                    print(f"     {'/'.join(key):44s} {shown(key, old):30s} -> {shown(key, new)}")
                unexpected = [k for k, _, _ in changed if k not in expect]
                if unexpected:
                    unexpected_total += len(unexpected)
                    print(f"   note: {len(unexpected)} change(s) outside the expected keys "
                          "(reported, not failed; review them)")
        print()

    print(f"checked {len(expect)} expected key(s) across {len(profiles)} profile(s)")
    if unexpected_total:
        print(f"UNEXPECTED CHANGES: {unexpected_total} (see notes above)")
    print("FAILURES:", failures)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
