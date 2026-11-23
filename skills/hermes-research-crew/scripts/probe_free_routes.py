#!/usr/bin/env python3
"""List live free model ids, then probe each one through Hermes itself.

No model id is hardcoded. Free means the catalog id ends in ``:free``; the
OpenRouter auto-router is skipped because its model family changes per call.

The probe runs a real Hermes one-shot on the candidate route and asks it to read
a file that holds a random token. Only a model that actually called the file tool
can answer with the token. Hermes uses its own stored credential: this script
never reads a key, an .env file, or an auth file. The route that answered is
taken from that run's lines in agent.log, so a silent fallback to another model
is caught (it is a FAIL, never a PASS).

    python3 probe_free_routes.py list --provider openrouter
    python3 probe_free_routes.py list --provider local
    python3 probe_free_routes.py list --file catalog.json
    python3 probe_free_routes.py probe --provider openrouter <id> [<id> ...]

Each probe spends one or two requests of the provider's free quota. At most
--max-probes ids (default 4) per call. A daily rate limit stops the batch.

Exit 0 when every probed id passed; 1 when a probe ran and failed; 2 on bad
arguments or when hermes is not on PATH. ``list`` exits 0 even if the catalog is empty.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
CALL = re.compile(r"API call #\d+: model=(\S+) provider=(\S+)")
FALLBACK = re.compile(r"Fallback (to|activated)")
# Hermes prints the session id on stderr, never mixed with the model's reply (stdout).
PRINTED_SID = re.compile(r"^session_id:\s*(local-[0-9a-f]{16,}|\d{8}_\d{6}_[0-9a-f]{6})\s*$", re.M)
TOOL_DONE = re.compile(r"\btool read_file completed\b")
HINTS = {
    "ok": "assignable",
    "no_tool": "drop_id",
    "fallback": "route_failed_silently",
    "no_call": "check_provider_auth",
    "exit_error": "read_hermes_error",
    "silence": "drop_id",
    "rate_minute": "wait_one_minute",
    "rate_day": "stop_for_utc_day",
}


def family_of(model_id: str) -> str:
    if "/" not in model_id:
        return "unknown"
    return model_id.split("/", 1)[0].lower()


def is_free_id(model_id: str) -> bool:
    return model_id.endswith(":free") or model_id.endswith("/free")


def is_router(model_id: str) -> bool:
    """An auto-router has no stable trainer. Not a desk route."""
    return model_id.split("/", 1)[-1] in {"free", "free:free"}


def free_rows(payload) -> list[dict]:
    """Catalog JSON (OpenAI-style ``data`` list, or a bare list) -> row dicts."""
    if isinstance(payload, dict):
        items = payload.get("data") or payload.get("models") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    rows, seen = [], set()
    for item in items:
        if isinstance(item, str):
            mid = item.strip()
        elif isinstance(item, dict):
            mid = str(item.get("id") or item.get("name") or "").strip()
        else:
            continue
        if not mid or mid in seen or not is_free_id(mid):
            continue
        seen.add(mid)
        rows.append({"id": mid, "family": family_of(mid), "router": is_router(mid)})
    rows.sort(key=lambda r: r["id"])
    return rows


def fetch_catalog(url: str, timeout: float) -> list[dict]:
    """The public catalog needs no key."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return free_rows(json.loads(resp.read().decode("utf-8", errors="replace")))


def local_rows() -> list[dict]:
    if not shutil.which("ollama"):
        return []
    try:
        proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=20,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in (proc.stdout or "").splitlines()[1:]:
        name = line.split()[0] if line.split() else ""
        if name and re.match(r"^[A-Za-z0-9_.:/-]+$", name):
            rows.append({"id": name, "family": "local", "router": False})
    return rows


def print_rows(rows: list[dict], limit: int) -> None:
    shown = 0
    for row in rows:
        if row["router"]:
            print(f"router {row['id']} skip=unstable-family")
        elif shown < limit:
            print(f"free {row['id']} family={row['family']}")
            shown += 1
    print(f"free_count={shown}")


def same_model(want: str, logged: str) -> bool:
    """Exact id, or a bare id on one side matching the other's name. Two vendor prefixes must agree."""
    if logged == want:
        return True
    if "/" in logged and "/" in want:
        return False
    return logged.split("/", 1)[-1] == want.split("/", 1)[-1]


def classify(*, timed_out: bool, token_seen: bool, calls: list[tuple[str, str]], fallback: bool,
             want_model: str, want_provider: str, log_text: str, tool_ran: bool = True,
             exit_ok: bool = True) -> str:
    """Score one probe from what Hermes printed and what its log recorded."""
    low = log_text.lower()
    if "429" in low or "rate limit" in low:
        if "per-day" in low or "per day" in low or "daily" in low:
            return "rate_day"
        if not token_seen:
            return "rate_minute"
    if timed_out:
        return "silence"
    if not calls:
        return "no_call"
    on_route = all(p == want_provider and same_model(want_model, m) for m, p in calls)
    if fallback or not on_route:
        return "fallback"
    if not (token_seen and tool_ran):
        return "no_tool"
    return "ok" if exit_ok else "exit_error"


def log_path(profile: str | None) -> Path:
    home = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
    if profile and profile != "default":
        home = home / "profiles" / profile
    return home / "logs" / "agent.log"


def probe_one(hermes: str, model_id: str, provider: str, profile: str | None, timeout: int) -> dict:
    lp = log_path(profile)
    start = lp.stat().st_size if lp.exists() else 0
    work = Path(tempfile.mkdtemp(prefix="crew-probe-"))
    token = "crew-" + secrets.token_hex(8)
    try:
        (work / "token.txt").write_text(token + "\n", encoding="utf-8")
        prompt = (f"Use the read_file tool to read {work / 'token.txt'} "
                  "and reply with only the text inside it.")
        argv = [hermes] + (["-p", profile] if profile else []) + [
            "chat", "--oneshot", "-q", prompt, "-m", model_id, "--provider", provider,
            "-t", "file", "--max-turns", "3", "-Q"]
        began = time.monotonic()
        try:
            r = subprocess.run(argv, cwd=work, capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL)
            out, err, rc, timed_out = r.stdout or "", r.stderr or "", r.returncode, False
        except subprocess.TimeoutExpired:
            out, err, rc, timed_out = "", "", None, True
        elapsed = time.monotonic() - began
    finally:
        shutil.rmtree(work, ignore_errors=True)
    time.sleep(1.0)  # let the log flush

    new = ""
    if lp.exists():
        with open(lp, encoding="utf-8", errors="replace") as f:
            f.seek(start)
            new = f.read()
    found = PRINTED_SID.findall(err)
    sid = found[-1] if found else ""
    # Only records whose logger session field is exactly this session.
    mine = [l for l in new.splitlines() if sid and f"[{sid}]" in l]
    calls = [(m.group(1), m.group(2)) for l in mine if (m := CALL.search(l))]
    kind = classify(timed_out=timed_out, token_seen=token in out, calls=calls,
                    fallback=any(FALLBACK.search(l) for l in mine), want_model=model_id,
                    want_provider=provider, log_text="\n".join(mine),
                    tool_ran=any(TOOL_DONE.search(l) for l in mine), exit_ok=rc == 0)
    return {"id": model_id, "kind": kind, "calls": calls, "elapsed": elapsed, "session": sid or "-"}


def format_row(res: dict) -> str:
    seen = sorted({f"{p}/{m}" for m, p in res["calls"]}) or ["-"]
    return (f"{'PASS' if res['kind'] == 'ok' else 'FAIL'} model={res['id']} family={family_of(res['id'])} "
            f"s={res['elapsed']:.0f} class={res['kind']} hint={HINTS.get(res['kind'], 'drop_id')} "
            f"saw={','.join(seen)} session={res['session']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="free ids from the live catalog (no key needed)")
    ls.add_argument("--file")
    ls.add_argument("--provider", choices=("openrouter", "local"), default="openrouter")
    ls.add_argument("--limit", type=int, default=40)
    ls.add_argument("--timeout", type=float, default=20)
    pr = sub.add_parser("probe", help="one Hermes one-shot per id, scored from agent.log")
    pr.add_argument("models", nargs="+")
    pr.add_argument("--provider", required=True, help="Hermes provider name, e.g. openrouter or nous")
    pr.add_argument("--profile", help="profile to run the probe in (default: the active one)")
    pr.add_argument("--max-probes", type=int, default=4)
    pr.add_argument("--timeout", type=int, default=150, help="seconds per probe")
    args = ap.parse_args()

    if args.cmd == "list":
        if args.limit < 1:
            ap.error("--limit must be >= 1")
        try:
            if args.file:
                rows = free_rows(json.loads(Path(args.file).read_text(encoding="utf-8")))
            elif args.provider == "local":
                rows = local_rows()
            else:
                rows = fetch_catalog(OPENROUTER_MODELS, args.timeout)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"catalog=unavailable error={type(exc).__name__}")
            return 1
        print_rows(rows, args.limit)
        return 0

    if args.max_probes < 1 or args.timeout < 1:
        ap.error("--max-probes and --timeout must be >= 1")
    hermes = shutil.which("hermes")
    if not hermes:
        print("hermes=missing")
        return 2
    failed = 0
    for mid in args.models[: args.max_probes]:
        res = probe_one(hermes, mid, args.provider, args.profile, args.timeout)
        print(format_row(res), flush=True)
        failed += res["kind"] != "ok"
        if res["kind"] == "rate_day":
            print("stopped=rate_day")
            break
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
