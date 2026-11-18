# The hygiene desk (Planchet, `hygiene`)

Hygiene keeps projects and the machine free of run residue without destroying
evidence. Residue means scratch files, intermediate simulation output, stale
worktrees, caches, and stray processes left by agent runs, simulations and
statistical jobs.

## Why a desk and not only a script

The mechanical parts are scripts: `scripts/hygiene_scan.py` (read-only
inventory) and each tool's own prune command. The part that needs judgement is
classification: is this file residue, an artifact, or evidence a paper depends
on? It needs its own charter (what it may delete) and its own permissions, and
it should run apart from the work it cleans up after. Those are the
tests for a desk in `architecture.md` §4.

Add hygiene when cards, simulations or statistical runs happen unattended.
Interactive-only setups can run the scan by hand instead.

## The scratch convention (what makes cleanup safe)

Cleanup is only safe when temporary output is declared, not guessed. Every
producer desk follows this rule, which is in the shared working agreement
(`templates/role-souls.md`):

- Temporary output goes under `<Root>/.scratch/<card-id>/`, and `.scratch/` is
  in the project's `.gitignore`.
- Anything the card's **Artifact** field names is kept.
- Simulation and statistical runs: results that feed a table, figure or
  decision are artifacts (for example `outputs/` or `data/derived/`).
  Intermediate chains, checkpoints and per-seed dumps are scratch, unless a
  manifest or freeze record pins them.

## Three tiers

### Tier A: clean without asking

- `<Root>/.scratch/<card-id>/` for cards that are done or archived, older than
  the TTL (default 3 days). **Before deleting, copy the run's small text
  evidence** (logs, verdicts, manifests, summaries under 1 MB) to
  `<Root>/.scratch/_evidence/<card-id>/`, unless the same files already exist in
  the spine or on the card. Check that the copies are identical, then delete the
  rest.
- Package and download caches, through their own tools only: `uv cache prune`,
  `npm cache clean --force`, `brew cleanup -s`, `pip cache purge`. Never
  `rm -rf` a cache root.
- Worktrees that git itself reports as prunable: `git worktree prune`.

### Tier B: propose; the user decides

The user gets all of these at once as one lettered decision list
(`D1 keep, D2 delete, ...`). Delete nothing from this list until the user
answers.

- Large untracked or ignored files inside project roots: simulation outputs,
  checkpoints, figures nothing refers to.
- Worktrees or branches with uncommitted changes, or already merged.
- Stray processes: parent is 1, running for many hours, high CPU, working
  directory under a scratch folder or a worktree. Report the name, PID, age,
  CPU and working directory, never the raw command line, which can contain
  secrets.
- Costly caches (model weights, dataset caches), old profile exports, old
  insurance archives, large logs of archived cards.
- `.scratch/<card-id>/` folders of cards that are still blocked or whose status
  is unknown.

### Tier C: never

- Credentials: `.env`, `auth.json`, keys, tokens. Personal documents.
- Raw or licensed data, frozen inputs, and anything a manifest, freeze record or
  run record pins.
- Git history, tags, remotes. Other profiles' memories and sessions.
- Anything inside the Root of a card that is running now.

## Rules

1. **Inventory first, delete second.** Run the scan and read the board, then
   act.
2. **Never work beside a live run.** Skip every Root that has a `running` card
   (`hermes kanban --board <b> list`).
3. **Prefer the trash to `rm`** where it exists (`/usr/bin/trash` on macOS 15+,
   `gio trash` on Linux), except for caches cleaned by their own tools.
4. **Processes are always Tier B.** Before sending a signal that the user
   approved, check the PID's executable and working directory again, because
   PIDs are reused. Send SIGTERM only, and never stop Hermes services, the
   gateway, or the user's own sessions.
5. **Measure, don't add up.** Report the free-space change on the data volume
   (`df`), rounded, and do not claim space freed by something else.
6. **Write a ledger.** Append to `<workspace>/HYGIENE.md`: date, what was
   removed (paths and sizes), the measured disk change, what was kept and why,
   and what was proposed.

## Cadence

- **Daily, no model call:** a no-agent cron runs
  `scripts/hygiene_scan.py --root <project> ... --json` and notifies only when a
  threshold is crossed. Dry-run it first: on a clean workspace it must print
  nothing worth sending.
- **Weekly, or when the scan crosses a threshold:** one hygiene card. The desk
  scans, does Tier A, writes the ledger, and then either completes (Tier B is
  empty) or blocks with the decision list.

## Route and permissions

- Model: careful, literal instruction following matters more than raw
  capability; a mid-tier model is fine. It runs unattended, so no free tier.
  It does not need to be a different family from the others.
- Tools: terminal and file. No web, no browser.
- Turn cap: 40.
- Its own config lists only hygiene, file-handling and Kanban-worker skills.

## Commands

```bash
"$HERMES_PY" scripts/hygiene_scan.py --root ~/research/proj-a --root ~/research/proj-b
"$HERMES_PY" scripts/hygiene_scan.py --root ~/research/proj-a --ttl-days 7 --big-mb 500 --json
df -h /System/Volumes/Data      # macOS data volume; on Linux, df -h on the home filesystem
ps -axo pid=,ppid=,etime=,%cpu=,comm=     # processes without full command lines
```
