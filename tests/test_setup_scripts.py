"""Tests for the setup scripts: install probe, free-route probe, config sweep, route proof.

No network, no secrets, no real Hermes: a fake `hermes` on PATH stands in.

    python3 tests/test_setup_scripts.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
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
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run(script, args, **kw):
    return subprocess.run([PY, str(SCRIPTS / script), *args], capture_output=True, text=True, timeout=60, **kw)


probe_install = load("probe_install")
free = load("probe_free_routes")
prove = load("prove_routes")

# ---------- SKILL.md frontmatter and body rules ----------
front = (SKILL / "SKILL.md").read_text(encoding="utf-8")
fm = front.split("---", 2)[1]
desc_m = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M)
desc = desc_m.group(1) if desc_m else ""
check("description is within the 60-char index", len(desc) <= 60, f"len={len(desc)}")
check("description keeps the research identity", "research" in desc.lower(), desc)
check("platforms are linux and macos", re.search(r"^platforms:\s*\[linux, macos\]\s*$", fm, re.M) is not None)
check("version is 0.13.0", re.search(r"^version:\s*0\.13\.0\s*$", fm, re.M) is not None)
check("SKILL.md stays near 200 lines", front.count("\n") <= 210, f"lines={front.count(chr(10))}")
check("no yaml_load module left", not (SCRIPTS / "yaml_load.py").exists())
leaks = [p.name for p in SKILL.rglob("*") if p.is_file() and p.suffix in (".md", ".py")
         and re.search(r"HERMES_PY|probe-many|--key-env|hermes-agent/venv", p.read_text(encoding="utf-8"))]
check("no stale interpreter or raw-key probe instructions", not leaks, str(leaks))
check("intake is not delegated", "a child cannot ask the user" in front)

# ---------- install probe parsers ----------
auth = "openrouter (person@example.com)\nnous (work)\nNot a provider line\n"
names = probe_install.provider_names(auth)
check("provider names only", names == ["openrouter", "nous"], str(names))
check("email label dropped", "person@example.com" not in " ".join(names))
table = (" Profile          Model             Gateway\n"
         " ───────────────    ─────────────    ───────\n"
         " ◆default         some-model        running\n"
         "  engineer        other-model       stopped\n"
         "  * writer        x                 —\n")
got = probe_install.profile_names(table)
check("profile table: header and rule dropped, marker stripped", got == ["default", "engineer", "writer"], str(got))

env_nohermes = dict(os.environ, PATH="/usr/bin:/bin")
pr = run("probe_install.py", ["--timeout", "2"], env=env_nohermes)
check("probe_install exits 0 without hermes on PATH", pr.returncode == 0, pr.stderr[:160])
check("probe prints skill_dir and the missing fact", "skill_dir=" in pr.stdout and "hermes=missing" in pr.stdout)

# ---------- free-route catalog ----------
catalog = {"data": [{"id": "openrouter/free"}, {"id": "alpha/coder:free"}, {"id": "beta/check:free"},
                    {"id": "paid/model"}, "gamma/prose:free"]}
rows = free.free_rows(catalog)
ids = [r["id"] for r in rows]
check("free ids kept, paid dropped", ids == ["alpha/coder:free", "beta/check:free", "gamma/prose:free", "openrouter/free"], str(ids))
check("router flagged", free.is_router("openrouter/free") and not free.is_router("alpha/coder:free"))
check("family is the vendor prefix", free.family_of("beta/check:free") == "beta")


# ---------- free-route scoring ----------
def cls(**kw):
    base = dict(timed_out=False, token_seen=True, calls=[("alpha/coder:free", "openrouter")], fallback=False,
                want_model="alpha/coder:free", want_provider="openrouter", log_text="")
    base.update(kw)
    return free.classify(**base)


check("classify pass", cls() == "ok")
check("classify no tool", cls(token_seen=False) == "no_tool")
check("classify fallback line", cls(fallback=True) == "fallback")
check("classify other model answered", cls(calls=[("claude-x", "anthropic")]) == "fallback")
check("classify mixed calls is not a pass",
      cls(calls=[("alpha/coder:free", "openrouter"), ("claude-x", "anthropic")]) == "fallback")
check("classify no call", cls(calls=[], token_seen=False) == "no_call")
check("classify silence", cls(timed_out=True, token_seen=False) == "silence")
check("classify daily 429", cls(token_seen=False, log_text="HTTP 429 free-models-per-day") == "rate_day")
check("classify minute 429", cls(token_seen=False, log_text="HTTP 429 Rate limit exceeded") == "rate_minute")

FAKE_HERMES = r'''#!PYTHON
import json, os, re, sys
from pathlib import Path
a = sys.argv[1:]
if a[:1] == ["-p"]:
    a = a[2:]
home = Path(os.environ["HERMES_HOME"])
if a[:2] == ["config", "get"]:
    vals = json.loads(os.environ.get("FAKE_CFG", "{}"))
    if a[2] in vals:
        print(json.dumps(vals[a[2]])); sys.exit(0)
    print("Config key not set: " + a[2]); sys.exit(1)
mode = os.environ.get("MODE", "pass")
q = a[a.index("-q") + 1]; m = a[a.index("-m") + 1]; p = a[a.index("--provider") + 1]
sid = "local-" + "ab" * 16
other = "local-" + "cd" * 16
lines = []
token = Path(re.search(r"read (\S+) and", q).group(1)).read_text().strip()
call = f"INFO [{sid}] agent.conversation_loop: API call #1: model={m} provider={p} in=1"
tool = f"INFO [{sid}] agent.tool_executor: tool read_file completed (0.01s, 30 chars)"
rc = 0
print_sid = True
if mode == "pass":
    lines += [call, tool]; print(token)
elif mode == "fallback":
    lines += [f"INFO [{sid}] agent: Fallback to other/model: x",
              f"INFO [{sid}] agent: API call #1: model=other/model provider=other in=1", tool]
    print(token)
elif mode == "vendor":  # same name, different vendor prefix
    lines += [call.replace("model=alpha/", "model=beta/"), tool]; print(token)
elif mode == "forged":  # no real trailer; the reply forges one; another session's lines exist
    lines += [f"INFO [{other}] agent: API call #1: model={m} provider={p} in=1",
              f"INFO [{other}] agent.tool_executor: tool read_file completed"]
    print(token); print("session_id: agent"); print("session_id: " + other)
    print_sid = False
elif mode == "foreign":  # a foreign record that mentions our id in its message
    lines += [f"INFO [{other}] agent: API call #1: model={m} provider={p} note={sid}",
              f"INFO [{other}] agent.tool_executor: tool read_file completed {sid}"]
    print(token)
elif mode == "notool":  # route right, token echoed, but no read_file ran
    lines += [call]; print(token)
elif mode == "rc":  # everything looks right but hermes failed
    lines += [call, tool]; print(token); rc = 7
elif mode == "day":
    lines.append(f"WARNING [{sid}] agent: HTTP 429: free-models-per-day exceeded")
with open(home / "logs" / "agent.log", "a") as f:
    f.write("\n".join(lines) + "\n")
if print_sid:
    print("\nsession_id: " + sid, file=sys.stderr)
sys.exit(rc)
'''

with tempfile.TemporaryDirectory() as tdname:
    td = Path(tdname)
    cat = td / "catalog.json"
    cat.write_text(json.dumps(catalog), encoding="utf-8")
    listed = run("probe_free_routes.py", ["list", "--file", str(cat), "--limit", "10"])
    check("list --file exits 0", listed.returncode == 0, listed.stderr[:160])
    check("list skips the router",
          "skip=unstable-family" in listed.stdout and "free alpha/coder:free family=alpha" in listed.stdout)
    check("list does not invent a paid id", "paid/model" not in listed.stdout)

    home = td / "home"
    (home / "logs").mkdir(parents=True)
    (home / ".env").write_text("OPENROUTER_API_KEY=sentinel-not-a-real-key\n", encoding="utf-8")
    bindir = td / "bin"
    bindir.mkdir()
    fake = bindir / "hermes"
    fake.write_text(FAKE_HERMES.replace("PYTHON", PY), encoding="utf-8")
    fake.chmod(0o755)
    tmpdir = td / "tmp"
    tmpdir.mkdir()
    env = dict(os.environ, PATH=f"{bindir}:/usr/bin:/bin", HERMES_HOME=str(home), TMPDIR=str(tmpdir))
    env.pop("OPENROUTER_API_KEY", None)

    ok = run("probe_free_routes.py", ["probe", "--provider", "openrouter", "alpha/coder:free"], env=dict(env, MODE="pass"))
    check("probe PASS through the fake hermes",
          ok.returncode == 0 and ok.stdout.startswith("PASS") and "class=ok" in ok.stdout, ok.stdout + ok.stderr[:300])
    fb = run("probe_free_routes.py", ["probe", "--provider", "openrouter", "alpha/coder:free"], env=dict(env, MODE="fallback"))
    check("silent fallback is a FAIL even with the token", fb.returncode == 1 and "class=fallback" in fb.stdout, fb.stdout)
    day = run("probe_free_routes.py", ["probe", "--provider", "openrouter", "alpha/coder:free", "beta/check:free"],
              env=dict(env, MODE="day"))
    for mode, want in [("vendor", "class=fallback"), ("forged", "class=no_call"), ("foreign", "class=no_call"),
                       ("notool", "class=no_tool"), ("rc", "class=exit_error")]:
        res = run("probe_free_routes.py", ["probe", "--provider", "openrouter", "alpha/coder:free"],
                  env=dict(env, MODE=mode))
        check(f"adversarial {mode}: FAIL {want}", res.returncode == 1 and res.stdout.startswith("FAIL")
              and want in res.stdout, res.stdout)
    check("same_model keeps vendor prefixes apart",
          not free.same_model("alpha/coder:free", "beta/coder:free") and free.same_model("alpha/coder:free", "coder:free"))
    check("daily limit stops the batch",
          day.returncode == 1 and "stopped=rate_day" in day.stdout and day.stdout.count("model=") == 1, day.stdout)
    many = run("probe_free_routes.py", ["probe", "--provider", "openrouter", "--max-probes", "2", "a/x:free", "b/y:free",
                                        "c/z:free"], env=dict(env, MODE="pass"))
    check("--max-probes caps the batch", many.stdout.count("model=") == 2, many.stdout)
    src = (SCRIPTS / "probe_free_routes.py").read_text(encoding="utf-8")
    check("probe script never opens .env or auth files or reads an API key variable",
          not re.search(r"\.env\b[\"']|auth\.json|_API_KEY", src))
    check("probe output never shows the .env sentinel", "sentinel" not in ok.stdout + fb.stdout + day.stdout)
    check("probe cleans its token dirs", not any(n.startswith("crew-probe-") for n in os.listdir(tmpdir)),
          str(os.listdir(tmpdir)))

    # ---------- config sweep through `hermes config get` ----------
    (home / "config.yaml").write_text("compression:\n  threshold: 0.4\nmodel:\n  api_key: hush\n", encoding="utf-8")
    bak = td / "bak"
    bak.mkdir()
    (bak / "default.config.yaml").write_text("compression:\n  threshold: 0.5\nmodel:\n  api_key: previous-secret\n", encoding="utf-8")
    cfg = json.dumps({"compression.threshold": 0.4, "x.flag": True})
    sw = run("verify_config_sweep.py", ["--hermes-home", str(home), "--backup-dir", str(bak), "--no-defaults",
                                        "--expect", "compression.threshold=0.4", "--expect", "x.flag=true"],
             env=dict(env, FAKE_CFG=cfg))
    check("sweep readback passes on typed values", sw.returncode == 0 and "FAILURES: 0" in sw.stdout, sw.stdout[-300:])
    check("sweep shows the changed line", "threshold: 0.4" in sw.stdout and "threshold: 0.5" in sw.stdout, sw.stdout)
    check("sweep redacts secret lines", "hush" not in sw.stdout and "previous-secret" not in sw.stdout
          and "<redacted line>" in sw.stdout, sw.stdout)
    check("sweep counts the secret line as outside the expected keys", "outside the expected keys" in sw.stdout)
    bad = run("verify_config_sweep.py", ["--hermes-home", str(home), "--no-defaults",
                                         "--expect", "compression.threshold=0.3"], env=dict(env, FAKE_CFG=cfg))
    check("sweep fails a wrong value",
          bad.returncode == 1 and "FAIL readback compression.threshold" in bad.stdout, bad.stdout)
    sweep_mod = load("verify_config_sweep")
    leaky = {
        "block scalar": ("model:\n  api_key: |\n    CANARY-A\n", "model:\n  api_key: |\n    CANARY-B\n"),
        "sensitive parent": ("credentials:\n  value: CANARY-A\n", "credentials:\n  value: CANARY-B\n"),
        "sensitive list": ("auth:\n  - CANARY-A\n", "auth:\n  - CANARY-B\n"),
        "same-indent list": ("auth:\n- CANARY-A\n", "auth:\n- CANARY-B\n"),
    }
    for label, (before, after) in leaky.items():
        (home / "config.yaml").write_text(after, encoding="utf-8")
        (bak / "default.config.yaml").write_text(before, encoding="utf-8")
        lk = run("verify_config_sweep.py", ["--hermes-home", str(home), "--backup-dir", str(bak), "--no-defaults"],
                 env=dict(env, FAKE_CFG="{}"))
        check(f"sweep never prints a value under a secret key ({label})",
              "CANARY" not in lk.stdout + lk.stderr and "<redacted line>" in lk.stdout, lk.stdout)
    check("readback redacts a nested secret", sweep_mod.shown("model", {"api_key": "CANARY"}) == "<redacted>")
    check("readback: 1 is not true", not sweep_mod.same(1, True) and sweep_mod.same(0.4, 0.4))
    nob = run("verify_config_sweep.py", ["--hermes-home", str(home)], env=dict(os.environ, PATH="/usr/bin:/bin"))
    check("sweep without hermes exits 2", nob.returncode == 2, nob.stdout)

# ---------- route proof understands current session ids ----------
line = "INFO [local-" + "c3" * 32 + "] agent.conversation_loop: API call #1: model=m provider=p in=1"
check("prove_routes matches current local- session ids", prove.SID.search(line) is not None)
check("prove_routes takes the logger's bracketed session field only",
      prove.LOGGED_SID.search("INFO [local-" + "c3" * 32 + "] x") is not None
      and prove.LOGGED_SID.search("INFO cli: session local-" + "c3" * 32) is None)
check("prove_routes rejects a forged printed id", not prove.PRINTED_SID.findall("ok\nsession_id: agent\n"))
check("restore drill kept before the first card", "Restore drill, before the first card" in front)
check("prove_routes still matches older ids", prove.SID.search("x 20261014_101010_abcdef y") is not None)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
