"""Tests for probe, free-route scoring, and the YAML loader. No network, no secrets.

    python3 tests/test_setup_scripts.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "hermes-research-crew"
SCRIPTS = SKILL / "scripts"
PY = sys.executable
results: list[tuple[str, bool]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(script, args, **kw):
    return subprocess.run([PY, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=30, **kw)


yaml_load = load("yaml_load")
probe_install = load("probe_install")
free = load("probe_free_routes")

# ---------- YAML subset ----------
sample = """
# comment
model:
  provider: openrouter
  default: "org/example:free"
compression:
  threshold: 0.40
  protect_last_n: 40
tool_loop_guardrails:
  hard_stop_enabled: true
fallback_providers: []
extra:
  - provider: local
    model: example
platforms: [linux, macos]
"""
tree = yaml_load.load_text(sample, loader="stdlib")
check("stdlib nested map and float", tree["compression"]["threshold"] == 0.4 and tree["compression"]["protect_last_n"] == 40)
check("stdlib bool and empty list", tree["tool_loop_guardrails"]["hard_stop_enabled"] is True and tree["fallback_providers"] == [])
check("stdlib list of maps", tree["extra"] == [{"provider": "local", "model": "example"}])
check("stdlib flow list", tree["platforms"] == ["linux", "macos"])
check("stdlib quoted scalar", tree["model"]["default"] == "org/example:free")
try:
    yaml_load.load_text("note: |\n  hello\n", loader="stdlib")
    check("stdlib rejects block scalar", False)
except yaml_load.UnsupportedYAML:
    check("stdlib rejects block scalar", True)

front = (SKILL / "SKILL.md").read_text(encoding="utf-8")
fm = front.split("---", 2)[1]
parsed = yaml_load.load_text(fm, loader="stdlib")
desc = str(parsed.get("description", "")).strip()
check("description is within the 60-char index", len(desc) <= 60, f"len={len(desc)}")
check("platforms are linux and macos", parsed.get("platforms") == ["linux", "macos"])
check("version bumped", str(parsed.get("version")) == "0.13.0")
body_lines = front.split("---", 2)[2].count("\n")
# frontmatter plus body; the whole file should stay near 200 lines
check("SKILL.md stays near 200 lines", front.count("\n") <= 210, f"lines={front.count(chr(10))}")
check("no oxblood example", "oxblood" not in front.lower())
check("no HERMES_PY in SKILL.md", "HERMES_PY" not in front)
for rel in SKILL.rglob("*.md"):
    text = rel.read_text(encoding="utf-8")
    if "HERMES_PY" in text or "$HERMES_PY" in text:
        check(f"no HERMES_PY in {rel.name}", False)
        break
else:
    check("no HERMES_PY left in the skill", True)

# ---------- install probe parsers ----------
auth = "openrouter (person@example.com)\nnous (work)\nNot a provider line\n"
names = probe_install.provider_names(auth)
check("provider names only", names == ["openrouter", "nous"], str(names))
check("email label dropped", "person@example.com" not in " ".join(names))
check("profile names skip a header", "engineer" in probe_install.profile_names("NAME\nengineer\n* writer\n"))

env = dict(os.environ, PATH="/usr/bin:/bin")
pr = run("probe_install.py", ["--timeout", "2"], env=env)
check("probe_install exits 0 without hermes on PATH", pr.returncode == 0, pr.stderr[:160])
out = pr.stdout
check("probe prints skill_dir and yaml loader", "skill_dir=" in out and "yaml_loader=" in out)
check("probe does not echo the email fixture", "example.com" not in out)
check("missing hermes is a fact", "hermes=missing" in out or "hermes=ok" in out)

# ---------- free-route scoring ----------
catalog = {
    "data": [
        {"id": "openrouter/free"},
        {"id": "alpha/coder:free"},
        {"id": "beta/check:free"},
        {"id": "paid/model"},
        "gamma/prose:free",
    ]
}
rows = free.free_rows(catalog)
ids = [r["id"] for r in rows]
check("free ids kept, paid dropped", ids == ["alpha/coder:free", "beta/check:free", "gamma/prose:free", "openrouter/free"], str(ids))
check("router flagged", free.is_router("openrouter/free") and not free.is_router("alpha/coder:free"))
check("family is the vendor prefix", free.family_of("beta/check:free") == "beta")
check("classify tool call", free.classify(200, "{}", 0.2, True, False, 20) == "ok")
check("classify no tool", free.classify(200, "{}", 0.2, False, False, 20) == "no_tool")
check("classify daily 429", free.classify(429, "free-models-per-day", 0.1, False, False, 20) == "rate_day")
check("classify minute 429", free.classify(429, "Rate limit exceeded", 0.1, False, False, 20) == "rate_minute")
check("classify upstream 429", free.classify(429, "Provider returned error", 0.1, False, False, 20) == "rate_upstream")
check("classify 403 and 404", free.classify(403, "", 0.1, False, False, 20) == "gated" and free.classify(404, "", 0.1, False, False, 20) == "retired")
check("classify silence", free.classify(0, "", None, False, True, 20) == "silence")
check("scrub drops the key", "sk-secretvalue" not in free.scrub("err sk-secretvalue more", ["sk-secretvalue"]))
body = {"choices": [{"message": {"tool_calls": [{"id": "1", "type": "function", "function": {"name": "ping", "arguments": "{}"}}]}}]}
check("tool_calls detected", free.tool_called_in(body))

import tempfile

with tempfile.TemporaryDirectory() as td:
    catalog_path = Path(td) / "catalog.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    listed = run("probe_free_routes.py", ["list", "--file", str(catalog_path), "--limit", "10"])
    check("list --file exits 0", listed.returncode == 0, listed.stderr[:160])
    check("list skips the router", "skip=unstable-family" in listed.stdout and "free alpha/coder:free family=alpha" in listed.stdout)
    check("list does not invent a paid id", "paid/model" not in listed.stdout)

    home = Path(td) / "hermes"
    home.mkdir()
    (home / ".env").write_text('OPENROUTER_API_KEY="sk-testsecretvalue"\n', encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            Handler.hits += 1
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            if Handler.mode == "pass":
                payload = json.dumps(body).encode()
                self.send_response(200)
            elif Handler.mode == "day":
                payload = b'{"error":{"message":"Rate limit exceeded: free-models-per-day. sk-testsecretvalue"}}'
                self.send_response(429)
            else:
                payload = b'{"error":{"message":"no"}}'
                self.send_response(403)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    Handler.hits = 0
    Handler.mode = "pass"
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/v1"
    try:
        ok = run("probe_free_routes.py", [
            "probe", "--model", "alpha/coder:free", "--base-url", base,
            "--key-env", "OPENROUTER_API_KEY", "--hermes-home", str(home), "--timeout", "5",
        ], env=dict(os.environ, OPENROUTER_API_KEY=""))
        # empty env var: read_key falls through to the file when the value is empty
        # os.environ copy may still contain a real key; force the file by unsetting
        env = dict(os.environ)
        env.pop("OPENROUTER_API_KEY", None)
        ok = run("probe_free_routes.py", [
            "probe", "--model", "alpha/coder:free", "--base-url", base,
            "--key-env", "OPENROUTER_API_KEY", "--hermes-home", str(home), "--timeout", "5",
        ], env=env)
        check("probe PASS from a local server", ok.returncode == 0 and "PASS" in ok.stdout and "class=ok" in ok.stdout, ok.stdout + ok.stderr)
        check("probe does not print the key", "sk-testsecretvalue" not in ok.stdout + ok.stderr)

        Handler.mode = "day"
        Handler.hits = 0
        stopped = run("probe_free_routes.py", [
            "probe-many", "--base-url", base, "--max-probes", "4",
            "--key-env", "OPENROUTER_API_KEY", "--hermes-home", str(home), "--timeout", "5",
            "alpha/coder:free", "beta/check:free",
        ], env=env)
        check("daily 429 stops the batch", stopped.returncode == 1 and "stopped=rate_day" in stopped.stdout and Handler.hits == 1,
              f"hits={Handler.hits} out={stopped.stdout}")
        check("daily 429 detail is scrubbed", "sk-testsecretvalue" not in stopped.stdout + stopped.stderr)

        missing = run("probe_free_routes.py", [
            "probe", "--model", "alpha/coder:free", "--base-url", base,
            "--key-env", "MISSING_KEY_FOR_TEST", "--hermes-home", str(home),
        ], env=env)
        check("missing key exits 2 without a value", missing.returncode == 2 and "key=missing" in missing.stdout)
    finally:
        server.shutdown()

# config sweep still runs on the stdlib loader when asked indirectly: a simple file
with tempfile.TemporaryDirectory() as td:
    home = Path(td) / ".hermes"
    (home).mkdir()
    (home / "config.yaml").write_text(sample, encoding="utf-8")
    backup = Path(td) / "bak"
    backup.mkdir()
    (backup / "default.config.yaml").write_text("model:\n  provider: old\n", encoding="utf-8")
    sweep = subprocess.run(
        [PY, str(SCRIPTS / "verify_config_sweep.py"), "--hermes-home", str(home.parent / ".hermes"),
         "--backup-dir", str(backup), "--profile", "default"],
        capture_output=True, text=True, timeout=30,
    )
    # expectations in the script will fail readback; we only need it to parse and exit 1, not crash
    check("verify_config_sweep parses without PyYAML required", sweep.returncode in (0, 1) and "Traceback" not in sweep.stderr,
          sweep.stderr[:200])
    bad = Path(td) / "badhome" / ".hermes"
    bad.mkdir(parents=True)
    (bad / "config.yaml").write_text("note: |\n  hello\n", encoding="utf-8")
    # Only the stdlib loader rejects this. When ruamel or PyYAML is installed the file is valid.
    if yaml_load.which_loader() == "stdlib":
        refused = subprocess.run(
            [PY, str(SCRIPTS / "verify_config_sweep.py"), "--hermes-home", str(bad), "--profile", "default"],
            capture_output=True, text=True, timeout=30,
        )
        check("block scalar exits 2 on the stdlib loader", refused.returncode == 2, refused.stderr[:160])
    else:
        check("block scalar exits 2 on the stdlib loader", True, f"skipped; loader={yaml_load.which_loader()}")

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
