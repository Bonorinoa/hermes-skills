# Architecture: why the team is shaped this way

This file explains the system design behind the skill: which parts exist, why
these roles and not others, how big the team should be, and how one role (a
**desk**) is built out of plain Hermes parts. Read it before changing the roster.

Evidence status: this is a design rationale plus the authors' daily use. It is
not a controlled comparison against a single agent or another roster. Where a
claim is a hypothesis, it says so.

## 1. The problem

One agent in one long session fails in recognisable ways on long or complex
work:

| Failure | What happens |
|---|---|
| Window exhaustion | Build logs, test results and the chat itself fill one window; compaction drops the thread. |
| Self-grading | The agent that wrote the code also declares it done. Plausible but false results pass. |
| One route for everything | The model that is pleasant to talk to is not always the best coder, checker or designer, and a single billing route carries every call. |
| Blocking | A two-hour task occupies the conversation the user wanted to keep using. |
| State in the transcript | Decisions and status live in chat history; a new session starts blind. |
| Residue | Every run leaves scratch files, caches, worktrees and stray processes that nobody owns. |

Each part of the design answers one row.

## 2. The parts

```text
                  +---------------------------------+
   user <-chat->  | orchestrator  (`default`)       |  talks, plans, writes cards,
                  |                                 |  audits returns, keeps pointers
                  +----------------+----------------+
                                   | five-field cards (Root, Acceptance,
                                   | Artifact, Fence, Locks)
                  +----------------v----------------+
                  | project board  (one per project)|  task lifecycle:
                  |                                 |  todo > ready > running >
                  +--+-------------+-------------+--+  review | blocked > done
                     |  dispatcher starts `hermes -p <desk>` per ready card
          +----------v--+   +------v------+   +--v----------+
          | engineer    |   | writer      |   | creative    |   producers
          +----------+--+   +------+------+   +--+----------+
                     +---- artifact + evidence --+
                                   |
                          +--------v--------+
                          | verifier        |  other model family;
                          |                 |  ACCEPT or BLOCK with evidence
                          +-----------------+

   hygiene: scheduled scan > safe cleanup + a decision list > ledger   (off the critical path)

  ==== project disk: spine (status, decisions), artifacts, registry ====   <- the truth
```

- **Orchestrator.** The user's main Hermes agent (the `default` profile). It
  holds the conversation and the plan. It may do small things itself; anything
  long, risky or worth checking becomes a card.
- **Board.** One Kanban board per project. It owns the *task lifecycle*: what is
  queued, running, blocked, in review, done. It does not own project state.
- **Dispatcher.** Starts a fresh worker for each ready card, on that desk's own
  route, in the card's workspace. Exactly one process dispatches.
- **Desks.** Profiles with one job each. A desk run starts from the card and the
  files on disk, not from the orchestrator's conversation.
- **Project disk.** The spine (status file, decision log), the artifacts, and
  the workspace registry. When anything disagrees with these files, the files
  win.

Hermes also documents an "orchestrator profile lane" whose toolset is limited to
Kanban. This skill's orchestrator is broader on purpose: it is the agent the user
already talks to, with full tools. A user who wants a strict router can remove
its terminal and file toolsets; the rest of the design is unchanged.

## 3. Five design principles

1. **Separation of duties.** Whoever produces an artifact does not accept it.
   The verifier runs on a different model family, sees the artifact and the
   acceptance criterion, and never sees the producer's reasoning, which is where
   independence is usually lost.
2. **Context partitioning.** The card is the boundary between contexts. A
   five-field card is a deliberately complete summary of what the worker needs,
   so each desk run starts clean and the orchestrator's window holds the
   conversation, not the build log.
3. **One route per job.** A profile is a route (provider, model, billing,
   fallback policy). Splitting work across desks lets each job use the model and
   the billing that suit it, and lets a dead route block one desk instead of the
   whole team.
4. **Least privilege.** Each desk gets the tools and the fence its job needs.
   The verifier is read-only. Hygiene may delete only what its tier rules allow.
5. **Truth on disk.** Memory holds the person; skills hold procedures; the
   project spine holds project state; the board holds task lifecycle. Nothing
   that matters lives only in a transcript.

## 4. Why these roles

A desk exists when one job has its own **verb**, its own **way of failing**, and
benefits from its **own model or permissions**.

| Desk (profile) | Verb | Failure it is built to catch | Capability that matters most |
|---|---|---|---|
| orchestrator (`default`) | decide and route | scope drift, lost context, unchecked relays | conversation, planning, long context |
| engineer | build | untested changes, edits outside the fence | long tool-using runs, code |
| verifier | refute | self-grading, plausible but false claims | scepticism, reproducing claims, a different family |
| writer | explain | invented citations or numbers, claims lost in a rewrite | prose, preserving claims |
| creative | show | visuals nobody looked at | visual judgement, vision input, rendering |
| hygiene | clean up | residue, leaked disk and processes, deleted evidence | careful, literal instruction following |

**The test for a new desk.** Before adding one, ask four questions:

1. Does it produce a distinct kind of work?
2. Does it fail in a way that needs its own rules in its charter?
3. Would it benefit from a different model, billing route or tool permissions?
4. Does the work recur often enough to pay for the setup?

If the answers to 2 and 3 are no, the job is a **skill** loaded by an existing
desk, not a new desk. A "data scientist" is usually analysis skills on the
engineer. A "literature reviewer" is usually search skills on the writer.

## 5. Why this number

The core crew is three specialists. Three functions cover most research work:
**produce** (engineer), **check** (verifier) and **communicate** (writer). With
the orchestrator they form the smallest team in which nobody grades their own
work and the user talks to one agent.

The other two desks are support, added when their workload exists:

- **creative**, when figures, slides or interfaces are a regular product;
- **hygiene**, when cards, simulations or statistical runs happen unattended
  and leave residue.

The optional persona names come from *The Three Musketeers*, which this skill
was first called: three musketeers, d'Artagnan who joins and leads them, and
their valets for the support desks. The profile names are canonical.

| Profile | Persona | Why the name fits |
|---|---|---|
| `default` | d'Artagnan | joins the three and leads |
| `engineer` | Athos | the steady builder |
| `verifier` | Porthos | the strong one; holds the line |
| `writer` | Aramis | the poet |
| `creative` | Bazin | Aramis's valet; supports the voice |
| `hygiene` | Planchet | d'Artagnan's valet; keeps the house in order |

**Every desk has a cost.** It adds a route to prove, a charter to maintain and
a full config copy (profiles do not inherit config). It also adds pressure on a
shared usage window and another handoff where latency and drift enter. That is
why the skill's rule is the smallest team that fits.

Hypothesis, not measurement: most of the gain comes from less context
rebuilding, clearer handoffs and fewer interruptions, more than from any one
model. `team-design.md` (Comparing models) describes how to test that on your
own work.

## 6. Anatomy of a desk

A desk is an ordinary Hermes profile, defined by eight settings:

| Part | Where it lives | What it decides |
|---|---|---|
| Route | `model.provider`, `model.default` | which model answers and who bills it |
| Fallback policy | `fallback_providers` | what happens when the route fails (often: nothing, the card blocks) |
| Charter | the role block in `SOUL.md` (`templates/role-souls.md`) | mission, authority, what it refuses |
| Skills | `skills.disabled` (hide what the desk should not load) | which procedures it can load |
| Tools | `hermes -p <desk> tools enable/disable <toolset>` | what it is allowed to touch |
| Turn cap | `agent.max_turns` | how long one run may go |
| Memory | the profile's `memories/` | the person only; never project state |
| Dispatch mode | `PROFILES.md` plus card parking | whether its cards may run unattended |

Each card run must end in exactly one lifecycle action: **complete**, **request
review**, or **block**.

Defaults per desk (the plan may change them):

| Desk | Writes files? | Tools | Turn cap | Usual ending | Fallback |
|---|---|---|---|---|---|
| orchestrator | yes | all | 60 | (interactive) | a fast cheap model is acceptable |
| engineer | inside the Root | terminal, file, code | 75 | complete, then a verifier card | none, or same tier |
| verifier | no (its report only) | terminal, file (read) | 100 | complete with ACCEPT or BLOCK | none, or another non-producer family |
| writer | inside the Root | file, web | 60 | complete, then a verifier card | none, or same tier |
| creative | a variants folder | file, terminal, vision, browser | 60 | complete with rendered previews | none, or same tier |
| hygiene | deletes by tier only | terminal, file | 40 | complete, or block with a decision list | none, or same tier |

## 7. One card's path

1. The user asks for something non-trivial.
2. The orchestrator writes a card, or a chain of cards (`--parent`): build, then
   check.
3. The dispatcher claims the ready card and starts the desk in the card's
   workspace.
4. The desk works inside the Root, keeps temporary output under
   `<Root>/.scratch/<card-id>/`, writes the artifact, and ends with complete,
   request review, or block.
5. The verifier card (or a same-card review) checks the artifact against the
   acceptance criterion.
6. The orchestrator audits what came back, relays it to the user with the
   decisions that are the user's, and updates the spine pointer.
7. Later, hygiene removes the card's declared scratch, keeps its evidence, and
   records what it did.

## 8. Failure model

| Failure | Caught by |
|---|---|
| Silent fallback to another model | `scripts/prove_routes.py`; the desk's `agent.log` |
| A false self-report | the verifier; the orchestrator's audit of the return |
| A worker dying at its turn cap | card sizing; progress written to a file |
| A dead seat | no free-tier fallback, so the card blocks |
| Edits outside the task | the fence; a `find -newer` audit |
| Run residue and runaway processes | hygiene |
| Project state lost between sessions | the spine and the wipe test |

## 9. What this design does not do

- It does not make weak models strong. It makes their failures easier to see.
- It does not sandbox anything. Fences and locks are rules followed by agents
  with a terminal. Physical separation (data outside the Root, read-only
  permissions) is what enforces them.
- It does not remove the user from decisions about scope, locks, publication
  or deletion.
