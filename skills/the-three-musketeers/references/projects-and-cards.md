# Projects and cards

## Where things live

Four stores. Each question is a test the agent applies before it writes
anything down, and each test fails visibly in one store and silently in the
other.

| Store | Holds | Test | Failure if misused |
|---|---|---|---|
| **memory** | the person: role, preferences, standing conventions, stable environment facts | Still true next month, in every project? | Fills its character budget and starts evicting the facts that matter, with no record of what was lost |
| **skills** | procedures, pitfalls, exact commands, and the checks that prove they ran | Would it change how a task gets done? | A procedure buried in memory loads on every turn and is applied out of context |
| **the project's spine** | a status file (phase, what is blocked, what changed last) and a decision log (the why, dated, with who decided) | Does doing the work make it stale? | A status line in memory outlives its truth and nothing marks it as expired |
| **the workspace registry** | one row per project: root, spine pointer, phase, locks | Is this a pointer rather than a record? | The registry becomes a second status file, and the two disagree |

Two more places hold work instead of truth:

- The **Kanban board** holds work in flight. A card's done state, its summary,
  and its comments describe an attempt, and a summary is a self-report.
- The **session transcript** holds conversation. It is searchable but is not
  the record; a decision that only exists in a transcript is lost to any agent
  that starts a new session.

**Truth order.** Git remote, then the project's spine, then memory. When two
disagree, the higher one wins and the lower one is corrected, not argued with.
A card may never overrule the spine, and memory may never overrule a file.

### Names are the user's

The contract specifies what must be *findable*, not where it is written. Before
proposing any file, look for the project's existing spine: `README`,
`AGENTS.md`, `STATUS.md`, `DECISIONS.md`, `docs/decisions/`, a lab notebook.
Record the pointer in `PROJECTS.md` and leave the layout alone. Only a project
with no spine gets a proposed minimal `AGENTS.md` answering the six questions,
and that proposal is a question, not a write — many people will not want a new
file in a repository that is already framed for a paper.

The same applies inside the workspace: `PROJECTS.md`, `PACKAGING_CONTRACT.md`,
and `PROFILES.md` are conventional names, and a user who already keeps a
portfolio file keeps theirs.

### Misfilings agents actually make

| Written | Where it belongs | Why |
|---|---|---|
| "Provider X is serving again after the rebuild (probe, today)" | the status file | a dated observation, not a standing fact |
| "OpenRouter credits exhausted, recharged" | nowhere; it is gone | an event with no future use |
| "Use `env -u PYTHONPATH` for project Python" | a skill's pitfalls | a procedure that changes how the task runs |
| "The checker accepted card 47" | the board | an attempt, not portfolio state |
| "User prefers control over convenience unless quality differs a lot" | memory | durable and task-independent |
| "User's name, timezone, and that the institutional seat is attended-only" | memory | standing facts every session needs |

A useful symptom to name for the user: a memory file near its character limit
is almost always a project notebook that has been growing in the wrong store.
Move the dated lines to the status files and the procedures to a skill; nothing
is lost, and the next session stops re-reading stale state.

## The wipe test

A project is set up when an agent with zero memory can answer six questions from
the project root alone:

1. What is this, and what is it for?
2. Where do the code and data live?
3. What phase is it in, and what is blocked?
4. What were the last few decisions, and why?
5. What artifacts exist, and how do I verify each one is real?
6. Which decisions belong to the user, and which to the agent?

The test specifies what must be **findable**, not where it is written. A project
that already has a spine (`AGENTS.md`, a README with status, a decision log)
keeps it. Record the pointer; do not normalize layouts. If a project has no
spine, propose a minimal `AGENTS.md` that answers the six questions, and ask
before writing it into the repository.

## Workspace files (written once, at the workspace root)

| File | From | Purpose |
|---|---|---|
| `PROJECTS.md` | `templates/PROJECTS.md` | The PM's card catalogue. About five lines per project: root, spine, phase, locks. Longer means the registry is becoming the record. |
| `PACKAGING_CONTRACT.md` | `templates/PACKAGING_CONTRACT.md` | The wipe test, the card fields, the acceptance rule, the checker gate. |
| `PROFILES.md` | `templates/PROFILES.md`, filled from the approved plan | Who runs what, each route, attended-only flags, how to send each desk work. |

Specialists cannot see the PM's memory or its `hermes project` entries (project
state is per-profile). These files are how they find anything.

## Registering a project

```bash
hermes project create <name> <abs-root>               # in the PM profile
hermes kanban boards create <slug> --default-workdir <abs-root>
```

One board per project keeps unrelated work in separate queues. Read
`hermes project --help` for multi-folder projects (one project can span repos).

## The five-field card

Every card the PM writes carries five fields. A card missing one is rewritten,
not dispatched.

| Field | Why |
|---|---|
| **Root** | Absolute path. Workers know nothing; "the project" means nothing to them. |
| **Acceptance** | What done means, checkably: "`pytest tests/test_x.py` exits 0", not "improve the tests". |
| **Artifact** | The exact path the work must produce, which the checker will inspect. |
| **Fence** | What must not be touched. Scope creep is silent otherwise. |
| **Locks** | Project rules that override convenience (below). |

End every card with: "If the premise looks wrong, say so before building." That
line regularly produces the most valuable output of a run.

```markdown
Root: /home/me/research/climate-panel
Acceptance: `uv run pytest tests/test_merge.py` exits 0; merged panel has 35 countries
Artifact: src/panel/merge.py, tests/test_merge.py
Fence: data/raw/ is read-only; do not touch paper/
Locks: results feeding paper tables run on pinned code only; data/raw is licensed, never sent to hosted models
If the premise looks wrong, say so before building.
```

## The acceptance rule

Work is accepted only when all four hold:

1. A real file exists at the stated path, verified by reading it.
2. Its content is checkable against the acceptance criterion.
3. The verification command's actual exit code was captured, not through a pipe:
   `pytest | tail` returns `tail`'s status.
4. The model route that produced it is recorded, from `agent.log`.

## The checker gate

```text
builder -> artifact + evidence -> CHECKER (other family; sees artifact + acceptance, not the builder's rationale)
                                    |-- accept -> done
                                    `-- block  -> PM round 1 (fix or rebut) -> checker -> PM round 2 -> still blocked? -> user
```

- A block must cite evidence: a path, a command with its exit code, a count that
  does not match. "This looks wrong" is not a block.
- The PM gets two rounds to fix or rebut. A block that survives goes to the user
  with both positions and the artifact.
- The checker never edits the artifact.
- When the checker refutes the PM, check its file:line evidence. If it holds,
  concede in writing.

## Locks for research projects

Offer these during planning; the user picks and edits them per project.

| Lock | Use when |
|---|---|
| Published numbers come from pinned, versioned code and models; agent seats do tooling only. | Any project heading to publication |
| Licensed or human-subjects data is handled exactly as the user chose in the intake. Default: agents write and test code against fake or sample data; only the user's own scripts (or a local model, if allowed) read the real files; no hosted agent opens, prints, or summarizes them. Derived outputs (counts, tables, figures) count as data until the user releases them. Keep the real data **outside every card's Root** (so checkpoints and worktrees never copy it) and name its path in the Fence. The lock is a rule, not a sandbox: agents have a terminal, so physical separation is what makes it hold. | Restricted data, IRB protocols, data-use agreements |
| No push, tag, release, or publish without a task-specific decision from the user. | Every project |
| Never loosen a threshold or drop observations to obtain a result. | Empirical work |
| Tagged releases and frozen inputs are immovable. | Projects with released versions or frozen data |
