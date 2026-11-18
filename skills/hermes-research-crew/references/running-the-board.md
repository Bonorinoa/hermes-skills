# Running the board

Operating notes for after setup. Each one is a failure that cost real time.

## Dispatch

- Board cards run on the assignee profile's own route. `delegate_task` children
  run on the orchestrator's delegation model; use them for the orchestrator's read-only fan-out, not
  for specialist work.
- Before a card fan-out, read every assignee's live route and probe it
  (`scripts/prove_routes.py`), so no card lands on a dead seat.
- `hermes kanban swarm` builds parallel workers, then a verifier, then a
  synthesizer in one command.
- **Who dispatches.** If `hermes config get kanban.dispatch_in_gateway` is
  `true`, the gateway dispatches ready cards on an interval, so cards run only
  while `hermes gateway status` shows it running. Install it as a background
  service with `hermes gateway install`. Otherwise run `hermes kanban daemon`,
  after checking with `ps` that no other dispatcher is running.
- **Overnight on a laptop.** The machine must stay awake and plugged in. On
  macOS, `caffeinate -i -s` for the night, and keep the lid open (a closed lid
  sleeps unless an external display is attached). On Linux, `systemd-inhibit`.
  A sleeping laptop looks like a stuck board in the morning.
- **Attended-only work.** See `team-design.md`, Mechanism: attended mode turns
  the background dispatcher off; attended-only profiles get parked cards.
- **Restricted data overnight.** Hosted agents prepare and test the user's
  scripts on fake data by day; the real-data run overnight is the user's own
  scheduled script, not a card.

## Choose the review topology before dispatch

The verifier gate can run two ways. Pick one per chain, write it in the card's
Acceptance, and do not mix their closing moves.

| | Same-card review | Downstream verifier card |
|---|---|---|
| Shape | one card: implementer works, then hands it to the verifier | two cards: build card, then a verifier card created with `--parent <build>` |
| Implementer ends with | `hermes kanban request-review <id> --reviewer verifier --summary "..."` | `complete` (only when its own criteria hold), which releases the child |
| Verifier ends with | `complete` (ACCEPT) or `request-changes <id> "<findings>"`, which returns it to the implementer | `complete` with ACCEPT or BLOCK and evidence in the summary |
| Needs | `kanban.review_dispatch` true (the default), so the dispatcher works the review lane | nothing extra |
| Best for | small fixes; a back-and-forth on one artifact | several producers feeding one check; a swarm |

- Same-card review records who implemented and who reviewed, so requested
  changes route back to the right profile.
- In either shape, final acceptance waits for the verifier's verdict, not the
  implementer's completion.
- Static validation and persona dry runs complement but never replace running
  the helper scripts and a planted-failure fixture.

## Size cards to fit one run

- A worker dies at its profile's `agent.max_turns`, not at the card's
  `--max-runtime`. A notice that reads like a zero-second timeout can be turn-cap
  exhaustion; read the run error for `Iteration budget exhausted`.
- Each retry starts with a fresh context and re-reads the whole card. Have workers
  append progress to a named file after each sub-step, so a retry resumes.
- Split large work into chained cards (`--parent`): implement, then screenshots
  or acceptance runs, then the verifier. Each card ends with working, checked code.
- After a turn-cap death, replace the card body with a short resume checklist
  ("resume, do not redo"), comment it, then reclaim. A running process keeps the
  old body until it exits.
- `agent.max_turns: 0` means unlimited, not disabled. Raise caps per profile,
  record the old value, and restore it after the card.

## Audit a returned card before relaying it

A card summary is a self-report.

1. Check the fence: `find <fenced dirs> -newer <the card's first artifact> -type f`,
   minus your own edits.
2. Re-check the three or four load-bearing claims against the files and raw
   outputs. Recompute one number yourself.
3. Look at any design deliverable yourself (render or screenshot it).
4. When relaying, put the worker's premise challenges first, separate decisions
   that belong to the user, and give your own lean.
5. Do not edit files the verifier is examining while its card runs; queue your
   nits for after the verdict.
6. After any edit of your own, re-run the project's whole test suite on the
   final commit. A content edit made after the verdict can break a test the card
   never named (a word cap, a string assertion).
7. When a card changes a displayed string or a constant, search the other
   places that state it (tests, tools, copies in templates) for the old value.
8. Findings from read-only audit subagents come from reading code, not running
   it. Reproduce each BLOCK yourself before it becomes a card, and put
   "reproduce first; drop what you cannot reproduce" in that card.
9. A failure that then passes on retry shows the test is intermittent, nothing
   more. Reproduce the cause before naming it or changing the product. Run heavy
   browser suites one at a time with a time limit, and stop a leftover browser
   only after checking its PID, working directory and that this run started it.
10. Accept a design card on measurements (sizes read from the page, screenshots
    at agreed widths and themes) that the card named in advance, not on a word
    like "cleaner".

## Prove which model served a card

A mid-session fallback leaves the worker's `-m` flag unchanged. Count that
session's calls in the assignee's log:

```bash
grep <session_id> ~/.hermes/profiles/<p>/logs/agent.log \
  | grep -oE "API call #[0-9]+: model=[^ ]+ provider=[^ ]+" | awk '{print $4,$5}' | sort | uniq -c
```

Any model other than the pinned one means the seat fell back.

## Recovering

- **Pin before reclaim.** `set-model` applies on the next dispatch. Reclaim
  first, and the respawn uses the profile default, which may be the dead seat.
- **After any fallback,** diff the card's artifacts against the last commit, and
  list files newer than the fallback time, before resuming or closing the card.
- **If unfinished work was sent to review,** read the card's real state and its
  review topology before restarting anything. Pin a working model and comment a
  resume brief. In same-card review, use `request-changes` to return it to the
  implementer; in the downstream shape, the implementer finishes with
  `complete`. Never skip the verifier to avoid another implementer run.
- **A second block auto-decomposes a card.** Its children inherit no model
  override. Pin every child that has not started.
- **A timeout event after `done` is not a retry.** If the row is `done` and no
  process holds it, do not spawn another run.
- **A worker that crashed after its outputs reached disk is finished, not
  failed.** Assemble the report from the files and complete the card. Do not
  `promote` or `unblock` a card you mean to close; both respawn a worker.
- **Kill a stray worker by the pid in the card's `spawned` event**, never by a
  pattern such as `pkill -f "-p <profile>"`, which can match the user's own
  sessions.
- **A credential block goes to the user.** Re-auth happens on the assignee
  profile, by the user. Do not borrow another profile's token.

## Agent messaging

If the session has no `message_agent` tool, an `@profile` request becomes a card
for that profile with the five fields. Say that direct messaging is unavailable.

## After a chain finishes: hygiene

Hermes cleans the managed workspace of a card it created when that card
completes. Output a desk wrote inside the project Root does not go away by
itself, so producers write throwaway output under `<Root>/.scratch/<card-id>/`
and the hygiene desk (`hygiene.md`) clears it later. Its evidence is kept and its
deletions are written to a ledger.

## Telling the user when a chain finishes

Use a no-agent cron script that reads `hermes kanban --board <b> show <id> --json`
and prints only when a card is blocked or the final card is done. It costs no
model calls. Dry-run it first: it must print nothing while the chain is healthy.
