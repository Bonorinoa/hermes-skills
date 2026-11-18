"""Fixture tests for the hermes-research-crew helper scripts. Synthetic data only.

    python3 tests/test_skill_scripts.py [skill-dir]      (default: skills/hermes-research-crew)

Covers insurance_backup.py (live-WAL snapshot, permissions, exclusions, restore,
retention validation, per-archive cron with a fake crontab, absolute paths) and
hygiene_scan.py (stale vs fresh scratch, untracked large files, read-only).
Exit 0 when every check passes.
"""
import json, os, sqlite3, stat, subprocess, sys, tarfile, tempfile, threading, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO / "skills/hermes-research-crew"
BACKUP = SKILL / "scripts/insurance_backup.py"
SCAN = SKILL / "scripts/hygiene_scan.py"
PY = sys.executable
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


def run(args, **kw):
    return subprocess.run([PY, *map(str, args)], capture_output=True, text=True, timeout=120, **kw)


with tempfile.TemporaryDirectory(prefix="crew-fixture-") as td:
    t = Path(td)
    # ---------- synthetic Hermes home ----------
    home = t / "home" / ".hermes"
    (home / "profiles/engineer").mkdir(parents=True)
    (home / "hermes-agent/venv").mkdir(parents=True)
    (home / "cache").mkdir()
    (home / "config.yaml").write_text("model:\n  provider: fake\n")
    (home / ".env").write_text("FAKE_KEY=synthetic-not-a-secret\n")
    (home / "profiles/engineer/SOUL.md").write_text("role: engineer\n")
    (home / "hermes-agent/venv/big.bin").write_bytes(b"x" * 1000)
    (home / "cache/junk.txt").write_text("cache\n")
    db = home / "kanban.db"
    con = sqlite3.connect(db)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("CREATE TABLE t(i INTEGER)")
    con.commit()

    stop = threading.Event()

    def writer():  # committed rows sit in the WAL while the backup runs
        w = sqlite3.connect(db, timeout=30)
        i = 0
        while not stop.is_set():
            w.execute("INSERT INTO t VALUES (?)", (i,)); w.commit(); i += 1
            time.sleep(0.002)
        w.close()

    th = threading.Thread(target=writer); th.start()
    time.sleep(0.3)
    out = t / "backups"
    r = run([BACKUP, "--hermes-home", home, "--out", out, "--retain", "forever", "--yes"])
    stop.set(); th.join(); con.close()
    check("backup exits 0 with a live WAL writer", r.returncode == 0, r.stderr.strip()[:200])
    arcs = sorted(out.glob("hermes-home-backup-*.tar.gz"))
    check("exactly one archive", len(arcs) == 1, str(len(arcs)))
    a = arcs[0]
    check("archive mode 600", stat.S_IMODE(a.stat().st_mode) == 0o600, oct(stat.S_IMODE(a.stat().st_mode)))
    check("out dir mode 700", stat.S_IMODE(out.stat().st_mode) == 0o700, oct(stat.S_IMODE(out.stat().st_mode)))
    with tarfile.open(a) as tf:
        names = tf.getnames()
    check("runtime and cache excluded", not any("/hermes-agent" in n or "/cache" in n for n in names))
    check("config, .env, profiles included",
          all(any(n.endswith(s) for n in names) for s in ("config.yaml", ".env", "profiles/engineer/SOUL.md")))
    check("no -wal/-shm side files", not any(n.endswith(("-wal", "-shm")) for n in names))

    restore = t / "restore"; restore.mkdir()
    with tarfile.open(a) as tf:
        tf.extractall(restore, filter="data")
    rc = sqlite3.connect(restore / ".hermes/kanban.db")
    integ = rc.execute("PRAGMA integrity_check").fetchone()[0]
    rows = rc.execute("SELECT count(*) FROM t").fetchone()[0]
    rc.close()
    check("restored db passes integrity_check", integ == "ok", integ)
    check("restored db has the WAL-committed rows", rows > 0, f"rows={rows}")
    check("restored config byte-identical",
          (restore / ".hermes/config.yaml").read_bytes() == (home / "config.yaml").read_bytes())

    # ---------- retention validation ----------
    for bad in ("14oops", "0", "-3", "1.5", "", "forever "):
        rb = run([BACKUP, "--hermes-home", home, "--out", t / "bad", "--retain", bad, "--yes"])
        check(f"rejects retention {bad!r} with exit 2", rb.returncode == 2, f"exit={rb.returncode}")
    check("no archive written for bad retention",
          not any((t / "bad").glob("*.tar.gz")) if (t / "bad").exists() else True)

    # ---------- per-archive cron with a fake crontab (buffers stdin like the real one) ----------
    fakebin = t / "bin"; fakebin.mkdir()
    tab = t / "crontab.txt"
    tab.write_text("15 4 * * * /usr/bin/unrelated-job\n")
    (fakebin / "crontab").write_text(
        f"#!/bin/sh\nif [ \"$1\" = \"-l\" ]; then cat '{tab}'; exit 0; fi\n"
        f"if [ \"$1\" = \"-\" ]; then cat > '{tab}.new' && mv '{tab}.new' '{tab}'; exit 0; fi\nexit 1\n")
    (fakebin / "crontab").chmod(0o755)
    env = dict(os.environ, PATH=f"{fakebin}:{os.environ['PATH']}")
    outs = []
    for _ in range(2):
        outs.append(run([BACKUP, "--hermes-home", home, "--out", t / "cron", "--retain", "14",
                         "--install-cron", "--yes"], env=env))
        time.sleep(1.1)  # distinct timestamps
    check("two cron installs exit 0", all(o.returncode == 0 for o in outs), "; ".join(o.stderr[-120:] for o in outs))
    lines = tab.read_text().splitlines()
    tagged = [l for l in lines if "hermes-home-backup:" in l]
    check("unrelated cron job preserved", "15 4 * * * /usr/bin/unrelated-job" in lines)
    check("one cron line per archive (2 archives -> 2 lines)", len(tagged) == 2, str(len(tagged)))
    archives = sorted((t / "cron").glob("*.tar.gz"))
    check("each cron line names exactly its own archive",
          len(archives) == 2 and all(sum(arc.name in l for l in tagged) == 1 for arc in archives))
    check("cron line targets a single file, not a glob", all("-name" not in l for l in tagged))

    # the cron body deletes its expired archive and removes only its own line
    first = archives[0]
    body = next(l for l in tagged if first.name in l).split(" ", 5)[5]
    expired = time.time() - 30 * 86400
    os.utime(first, (expired, expired))
    rb = subprocess.run(["sh", "-c", body], env=env, capture_output=True, text=True, timeout=30)
    after = tab.read_text().splitlines()
    check("cron body deletes its expired archive", rb.returncode == 0 and not first.exists())
    check("cron body removes only its own line",
          "15 4 * * * /usr/bin/unrelated-job" in after
          and sum("hermes-home-backup:" in l for l in after) == 1
          and not any(first.name in l for l in after))

    before_rel = tab.read_text().splitlines()
    rr = run([BACKUP, "--hermes-home", home, "--out", "relout", "--retain", "5", "--install-cron", "--yes"],
             env=env, cwd=t)
    new = [l for l in tab.read_text().splitlines() if l not in before_rel]
    check("relative --out gives an absolute path in cron",
          rr.returncode == 0 and len(new) == 1 and f'find "{(t / "relout").resolve()}/' in new[0],
          new[0][:120] if new else rr.stderr[:120])

    # ---------- hygiene_scan ----------
    proj = t / "proj"
    (proj / ".scratch/card-old").mkdir(parents=True); (proj / ".scratch/card-new").mkdir()
    (proj / ".scratch/_evidence/card-old").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    (proj / ".gitignore").write_text(".scratch/\noutputs/\n")
    (proj / "tracked_big.bin").write_bytes(b"\0" * (2 * 1024 * 1024))
    subprocess.run(["git", "-C", str(proj), "add", ".gitignore", "tracked_big.bin"], check=True)
    subprocess.run(["git", "-C", str(proj), "-c", "user.email=f@f", "-c", "user.name=f",
                    "commit", "-qm", "x"], check=True)
    (proj / "outputs").mkdir(); (proj / "outputs/sim_draws.npy").write_bytes(b"\0" * (3 * 1024 * 1024))
    (proj / ".scratch/card-old/log.txt").write_text("old\n")
    (proj / ".scratch/card-new/log.txt").write_text("new\n")
    old = time.time() - 10 * 86400
    for p in [proj / ".scratch/card-old/log.txt", proj / ".scratch/card-old"]:
        os.utime(p, (old, old))
    before = sorted(str(p) for p in proj.rglob("*"))
    rs = run([SCAN, "--root", proj, "--big-mb", "1", "--json"])
    check("scan exits 0", rs.returncode == 0, rs.stderr[:200])
    rep = json.loads(rs.stdout)["roots"][0]
    sc = {Path(s["path"]).name: s["stale"] for s in rep["scratch"]}
    check("old scratch STALE, new fresh, _evidence not listed", sc == {"card-old": True, "card-new": False}, str(sc))
    big = [Path(f["path"]).name for f in rep["large_untracked"]]
    check("ignored large output listed, tracked large file not", big == ["sim_draws.npy"], str(big))
    check("scan deleted nothing", before == sorted(str(p) for p in proj.rglob("*")))
    check("missing root exits 2", run([SCAN, "--root", t / "nope"]).returncode == 2)
    check("negative ttl exits 2", run([SCAN, "--root", proj, "--ttl-days", "-1"]).returncode == 2)

failed = [n for n, ok in results if not ok]
print(f"\n{len(results) - len(failed)}/{len(results)} passed")
sys.exit(1 if failed else 0)
