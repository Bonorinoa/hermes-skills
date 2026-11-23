#!/usr/bin/env python3
"""List live free model ids and score one cheap capability probe.

No model id is hardcoded. Free means the catalog id ends in ``:free`` or is
the OpenRouter auto-router (skipped: its family changes per call). A pass is
one tool call, on time. Anything else is a class plus a fixed hint.

The key is read from the named environment variable or from HERMES_HOME/.env
and is never printed. Response bodies are scrubbed before they are shown.
At most one retry, and only for a per-minute limit. A daily limit stops the
batch: failed attempts can spend the free-tier quota.

    python3 probe_free_routes.py list --file catalog.json
    python3 probe_free_routes.py list --provider openrouter
    python3 probe_free_routes.py probe --model <id> --base-url <url>
    python3 probe_free_routes.py probe-many --base-url <url> --max-probes 4 <id>...

Exit 0 when every probed id passed. Exit 1 when a probe ran and failed.
Exit 2 on bad arguments or a missing key when a probe was requested.
``list`` alone exits 0 even if the catalog is empty.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

OPENROUTER_MODELS = "https://openrouter.ai/api/v1/models"
HINTS = {
    "ok": "assignable",
    "no_tool": "drop_id",
    "silence": "drop_id",
    "rate_minute": "wait_one_minute_once",
    "rate_day": "stop_for_utc_day",
    "rate_upstream": "try_other_family",
    "gated": "drop_id",
    "retired": "refresh_catalog",
    "billing": "stop_free_until_credit",
    "transport": "drop_id",
}


def family_of(model_id: str) -> str:
    if "/" not in model_id:
        return "unknown"
    return model_id.split("/", 1)[0].lower()


def is_free_id(model_id: str) -> bool:
    return model_id.endswith(":free") or model_id.endswith("/free")


def is_router(model_id: str) -> bool:
    """An auto-router has no stable trainer. Not a desk route."""
    tail = model_id.split("/", 1)[-1]
    return tail in {"free", "free:free"}


def free_rows(payload) -> list[dict]:
    """Catalog JSON (OpenAI-style ``data`` list, or a bare list) -> row dicts."""
    if isinstance(payload, dict):
        items = payload.get("data") or payload.get("models") or []
    elif isinstance(payload, list):
        items = payload
    else:
        return []
    rows = []
    seen: set[str] = set()
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
        rows.append({
            "id": mid,
            "family": family_of(mid),
            "router": is_router(mid),
        })
    rows.sort(key=lambda r: r["id"])
    return rows


def classify(status: int, body: str, elapsed: float | None, tool_called: bool,
             timed_out: bool, timeout: float) -> str:
    if timed_out or elapsed is None:
        return "silence"
    low = (body or "").lower()
    if status == 429:
        if "per-day" in low or "per day" in low or "daily" in low:
            return "rate_day"
        if "provider returned" in low or "upstream" in low:
            return "rate_upstream"
        return "rate_minute"
    if status == 403:
        return "gated"
    if status == 404:
        return "retired"
    if status == 402:
        return "billing"
    if status != 200:
        return "transport" if status == 0 else f"http_{status}"
    if elapsed > timeout:
        return "silence"
    if not tool_called:
        return "no_tool"
    return "ok"


def tool_called_in(payload) -> bool:
    if not isinstance(payload, dict):
        return False
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return False
    message = choices[0].get("message") or {}
    if message.get("tool_calls") or message.get("function_call"):
        return True
    return False


def scrub(text: str, secrets: list[str]) -> str:
    out = text or ""
    for secret in secrets:
        if secret and len(secret) >= 4:
            out = out.replace(secret, "<redacted>")
    out = re.sub(r"sk-[A-Za-z0-9_\-]{8,}", "<redacted>", out)
    out = re.sub(r"Bearer\s+\S+", "Bearer <redacted>", out, flags=re.I)
    return re.sub(r"\s+", " ", out).strip()[:180]


def read_key(name: str, home: Path) -> str:
    if name in ("", "-"):
        return ""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = home / ".env"
    if not env_path.is_file():
        return ""
    prefix = name + "="
    try:
        lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix):].strip().strip('"').strip("'")
    return ""


def probe_request(model_id: str) -> dict:
    return {
        "model": model_id,
        "max_tokens": 64,
        "messages": [{
            "role": "user",
            "content": "Call the ping tool now. Do not answer with prose.",
        }],
        "tools": [{
            "type": "function",
            "function": {
                "name": "ping",
                "description": "Signal that the route can call a tool.",
                "parameters": {"type": "object", "properties": {}},
            },
        }],
    }


def http_post(url: str, body: dict, key: str, timeout: float) -> tuple[int, str, float | None, bool]:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.monotonic() - start
            return resp.status, raw, elapsed, False
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        elapsed = time.monotonic() - start
        return exc.code, raw, elapsed, False
    except (TimeoutError, urllib.error.URLError, OSError):
        return 0, "", None, True


def score_body(status: int, raw: str, elapsed, timed_out: bool, timeout: float) -> tuple[str, bool]:
    called = False
    if status == 200 and raw:
        try:
            called = tool_called_in(json.loads(raw))
        except json.JSONDecodeError:
            called = False
    kind = classify(status, raw, elapsed, called, timed_out, timeout)
    return kind, called


def format_row(model_id: str, kind: str, called: bool, elapsed) -> str:
    ms = "-" if elapsed is None else str(int(elapsed * 1000))
    hint = HINTS.get(kind, "drop_id")
    return (
        f"{'PASS' if kind == 'ok' else 'FAIL'} model={model_id} family={family_of(model_id)} "
        f"ms={ms} class={kind} tool={'yes' if called else 'no'} hint={hint}"
    )


def load_catalog(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return free_rows(payload)


def fetch_catalog(url: str, timeout: float) -> list[dict]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    return free_rows(payload)


def print_rows(rows: list[dict], limit: int) -> None:
    shown = 0
    for row in rows:
        if row["router"]:
            print(f"router {row['id']} skip=unstable-family")
            continue
        if shown >= limit:
            continue
        print(f"free {row['id']} family={row['family']}")
        shown += 1
    print(f"free_count={shown}")


def local_rows() -> list[dict]:
    if not shutil.which("ollama"):
        return []
    try:
        proc = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=20, stdin=subprocess.DEVNULL,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in (proc.stdout or "").splitlines()[1:]:
        name = line.split()[0] if line.split() else ""
        if name and re.match(r"^[A-Za-z0-9_.:/-]+$", name):
            rows.append({"id": name, "family": "local", "router": False})
    return rows


def run_one(model_id: str, base_url: str, key: str, timeout: float, pause) -> tuple[str, bool, float | None]:
    url = base_url.rstrip("/") + "/chat/completions"
    status, raw, elapsed, timed_out = http_post(url, probe_request(model_id), key, timeout)
    kind, called = score_body(status, raw, elapsed, timed_out, timeout)
    if kind == "rate_minute":
        pause()
        status, raw, elapsed, timed_out = http_post(url, probe_request(model_id), key, timeout)
        kind, called = score_body(status, raw, elapsed, timed_out, timeout)
        if kind == "rate_minute":
            kind = "rate_minute"
    if kind != "ok":
        detail = scrub(raw, [key])
        if detail and kind not in ("silence",):
            print(f"detail={detail}", file=sys.stderr)
    return kind, called, elapsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ls = sub.add_parser("list")
    ls.add_argument("--file")
    ls.add_argument("--provider", choices=("openrouter", "local"), default="openrouter")
    ls.add_argument("--limit", type=int, default=40)
    ls.add_argument("--timeout", type=float, default=20)

    pr = sub.add_parser("probe")
    pr.add_argument("--model", required=True)
    pr.add_argument("--base-url", required=True)
    pr.add_argument("--key-env", default="OPENROUTER_API_KEY")
    pr.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", "~/.hermes"))
    pr.add_argument("--timeout", type=float, default=20)

    many = sub.add_parser("probe-many")
    many.add_argument("models", nargs="+")
    many.add_argument("--base-url", required=True)
    many.add_argument("--key-env", default="OPENROUTER_API_KEY")
    many.add_argument("--hermes-home", default=os.environ.get("HERMES_HOME", "~/.hermes"))
    many.add_argument("--timeout", type=float, default=20)
    many.add_argument("--max-probes", type=int, default=4)

    args = ap.parse_args()
    if args.cmd == "list":
        if args.limit < 1:
            print("limit must be >= 1", file=sys.stderr)
            return 2
        try:
            if args.file:
                rows = load_catalog(Path(args.file))
            elif args.provider == "local":
                rows = local_rows()
            else:
                rows = fetch_catalog(OPENROUTER_MODELS, args.timeout)
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"catalog=unavailable error={type(exc).__name__}")
            return 1
        print_rows(rows, args.limit)
        return 0

    home = Path(args.hermes_home).expanduser()
    key = read_key(args.key_env, home)
    if args.key_env not in ("", "-") and not key:
        print(f"key=missing env={args.key_env}")
        return 2

    def pause():
        time.sleep(min(60.0, max(1.0, 61 - (time.time() % 60))))

    ids = [args.model] if args.cmd == "probe" else list(args.models)[: args.max_probes]
    if args.cmd == "probe-many" and args.max_probes < 1:
        print("max-probes must be >= 1", file=sys.stderr)
        return 2
    failed = 0
    for mid in ids:
        kind, called, elapsed = run_one(mid, args.base_url, key, args.timeout, pause)
        print(format_row(mid, kind, called, elapsed))
        if kind != "ok":
            failed += 1
        if kind == "rate_day":
            print("stopped=rate_day")
            break
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
