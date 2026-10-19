#!/usr/bin/env python3
"""Prove each Hermes profile answers on its configured route, with no fallback.

For each profile:
  1. read the configured model.provider and model.default;
  2. send a one-line probe as a one-shot chat (one short model call);
  3. read ONLY the agent.log lines written by that probe's session, and check
     every API call's provider/model plus the absence of a fallback line.

The configured route is not proof of use: fallback is silent. This script
checks the call that actually happened.

Usage:
    python3 prove_routes.py engineer verifier writer
    python3 prove_routes.py --all

Exit 0 only when every profile passes. A profile with a concurrent session
that makes attribution ambiguous is reported AMBIGUOUS (non-zero), not passed.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
PROBE = "Reply with exactly seat-ok and no other words."
SID = re.compile(r"\b(\d{8}_\d{6}_[0-9a-f]{6})\b")
CALL = re.compile(r"API call #\d+: model=(\S+) provider=(\S+)")
FALLBACK = re.compile(r"Fallback (to|activated)")


def log_path(profile: str) -> Path:
    if profile == "default":
        return HOME / "logs" / "agent.log"
    return HOME / "profiles" / profile / "logs" / "agent.log"


def config_get(profile: str, key: str) -> str:
    r = subprocess.run(["hermes", "-p", profile, "config", "get", key],
                       capture_output=True, text=True)
    return r.stdout.strip()


def all_profiles() -> list[str]:
    root = HOME / "profiles"
    names = sorted(d.name for d in root.iterdir() if (d / "config.yaml").exists()) if root.is_dir() else []
    return ["default"] + names


def same_model(configured: str, logged: str) -> bool:
    """Providers may log a bare id for a prefixed config id (or vice versa)."""
    c, l = configured.strip(), logged.strip()
    return c == l or c.endswith("/" + l) or l.endswith("/" + c)


def probe(profile: str, timeout: int) -> dict:
    want_provider = config_get(profile, "model.provider")
    want_model = config_get(profile, "model.default")
    lp = log_path(profile)
    start = lp.stat().st_size if lp.exists() else 0

    try:
        r = subprocess.run(
            ["hermes", "-p", profile, "chat", "-q", PROBE, "-Q", "--max-turns", "1"],
            capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL,
        )
        out, rc = (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired:
        out, rc = "", "timeout"
    time.sleep(1.0)  # let the log flush

    new = ""
    if lp.exists():
        with open(lp, "r", encoding="utf-8", errors="replace") as f:
            f.seek(start)
            new = f.read()
    lines = new.splitlines()

    call_sids = {SID.search(l).group(1) for l in lines if CALL.search(l) and SID.search(l)}
    printed = {m.group(1) for m in SID.finditer(out)}
    candidates = (printed & call_sids) or call_sids

    res = {"profile": profile, "want": f"{want_provider}/{want_model}", "rc": rc,
           "answer_ok": "seat-ok" in out, "calls": [], "fallback": False, "status": ""}
    if len(candidates) != 1:
        res["status"] = "NO-CALL" if not candidates else "AMBIGUOUS"
        return res

    sid = candidates.pop()
    mine = [l for l in lines if sid in l]
    res["session"] = sid
    res["calls"] = [m.groups() for l in mine if (m := CALL.search(l))]
    res["fallback"] = any(FALLBACK.search(l) for l in mine)
    on_route = all(p == want_provider and same_model(want_model, m) for m, p in res["calls"])
    res["status"] = "PASS" if (rc == 0 and res["calls"] and on_route and not res["fallback"]) else "FAIL"
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("profiles", nargs="*")
    ap.add_argument("--all", action="store_true", help="probe every profile")
    ap.add_argument("--timeout", type=int, default=180, help="seconds per probe")
    args = ap.parse_args()

    profiles = all_profiles() if args.all else args.profiles
    if not profiles:
        ap.error("name at least one profile, or pass --all")

    failures = 0
    for p in profiles:
        r = probe(p, args.timeout)
        seen = sorted({f"{prov}/{model}" for model, prov in r["calls"]}) or ["-"]
        print(f"{r['status']:9s} {p:16s} want={r['want']}  saw={','.join(seen)}  "
              f"fallback={'yes' if r['fallback'] else 'no'}  answer={'ok' if r['answer_ok'] else 'unexpected'}  "
              f"session={r.get('session', '-')}  rc={r['rc']}")
        failures += r["status"] != "PASS"

    print(f"\n{len(profiles) - failures}/{len(profiles)} profiles on their configured route")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
