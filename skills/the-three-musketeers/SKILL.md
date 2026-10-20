---
name: the-three-musketeers
description: "Set up a Hermes agent team for research projects."
version: 0.9.0
author: Augusto González-Bonorino and Claude (Anthropic)
license: MIT
metadata:
  hermes:
    tags: [Hermes, Profiles, Kanban, Research, Setup, Verification, Reproducibility]
    related_skills: [hermes-agent]
---

# The Three Musketeers

A starter setup for researchers and tool-builders who run several projects at
once. It has one project manager (d'Artagnan) and three specialists: a
**builder**, a **checker**, and a **voice**. They coordinate through one Kanban
board per project, and every project's truth is kept on disk, not in an agent's
memory.

The skill is model-agnostic. It carries the constraints. An intake questionnaire
supplies the providers, budget, and preferences, and decides whether the setup
is worth building at all.

## When to Use

- "Set up the-three-musketeers", "/the-three-musketeers", "set up a Hermes team
  for my projects".
- "Is a multi-agent setup worth it for me?" (the intake answers this, and may
  answer no).
- A researcher juggling several projects, some heading to publication.
- An existing install with one profile per project that should become a team.
- Adding one project to a team built with this skill: skip to the S2/S6
  questions for that project.

## Rule zero: intake before any write

Do not create a profile, set a config key, or write a file until:

1. the intake is complete;
2. you have given a fit verdict;
3. the user has approved a written plan.

That includes backups: the insurance archive and the config snapshot are the
first writes of the build, after approval. In the existing-install branch,
destructive steps additionally get their own separate yes. The intake exists
so the setup works for *this* user. Skipping it produces a confident setup on
credentials the user does not have, or on a seat they are not allowed to
automate.

## The flow

| Step | What happens | Load |
|---|---|---|
| 1 Probe | Read what the install already shows: version, profiles, credential providers, OS, tools. Read-only. | `references/intake.md` |
| 2 Ask | Fill only the decision slots the probe could not. At most 5 questions per round, 3 rounds. | `references/intake.md` |
| 3 Fit verdict | Say plainly: full team, smaller team, single profile, or not yet. Stop if the user agrees it is not worth it. | `references/intake.md` |
| 4 Plan | Derive roster, routes, fallbacks, locks. Fill `templates/setup-plan.md`. Get approval. | `references/team-design.md` |
| 5 Build | Insurance archive (plan section 9), then profiles, SOULs, config, contract, registry, one board per project. | `references/projects-and-cards.md` |
| 6 Prove | Each profile answers on its intended route; config reads back. | Verification below |
| 7 First card | One small real card through builder then checker, end to end. | `references/running-the-board.md` |

A user with an existing install (several profiles, drifted config, unbacked
projects) takes the branch in `references/existing-install.md` between steps 4
and 5: inventory during planning, every write after approval.

## The team

```text
d'Artagnan  PM       `default`               talks to the user, writes cards, audits returns, holds pointers
Athos       builder  `engineer`              code, analysis scripts, tests
Porthos     checker  `verifier`              independent verification; may block
Aramis      voice    `writer` or `creative`  prose, figures, docs
```

Three specialists is a starting point. Add a fourth desk (data, notebooks) only
when the intake shows that work is the bottleneck. One project with light needs
may need only d'Artagnan and Porthos.

## Words used here

Use these terms with the user only after explaining them in plain words.

| Term | Meaning |
|---|---|
| profile | A separate Hermes agent with its own model, memory, and instructions. |
| desk | A profile with one job (builder, checker, voice). |
| route | The provider plus model a profile calls. |
| seat | A subscription login (personal or institutional) used as a route. |
| family | The vendor that trained a model. Independence is judged by family. |
| card | One task on a project's Kanban board, assigned to a desk. |
| attended / unattended | Whether the user is present when a card runs. Unattended means the dispatcher starts it on its own. |
| fence | What a card must not touch. |
| lock | A project rule that overrides convenience, such as "no hosted model reads the restricted data". |
| spine | The project's own files that explain it (README, AGENTS.md, decision log). |
| wipe test | Can an agent with no memory rebuild the project's state from its files? |

## Constraints the agent must hold

Each rule prevents a failure observed while running this setup in production.

1. **The checker runs on a different model family from the producers**, and the
   PM counts as a producer for anything it writes itself. The same model
   through two providers is one family; two sizes of one vendor's model are one
   family. If the user's access allows no second family, say so and label the
   check "same-family review", never "independent".
2. **No free-tier fallback on profiles that work cards.** A free model that
   takes over mid-card can delete finished sections, write to wrong paths, or
   file a review on unfinished work. A dead seat should block the card.
   Interactive profiles, where a human watches, may keep a fast free fallback.
3. **Fallback is silent.** It fires on rate-limit, overload, connection, and
   billing errors, and the profile keeps answering. The configured model is not
   proof of the model that answered; that profile's `agent.log` is.
4. **A subscription login is not automatically licensed for automation.** Ask
   whether an institutional seat's institution permits agent use, and note that
   provider terms can restrict third-party tools on any consumer login. Until
   the user confirms, an institutional seat is **attended-only**: its cards are
   created parked (`--initial-status blocked`) and released by the PM while the
   user is present. Never infer entitlement from an email domain or plan label.
5. **Reproducibility lock.** If a project produces published numbers, the
   pipeline behind them runs on pinned, versioned, preferably open-weight models
   and code. Agent seats do the tooling, refactors, docs, and literature triage
   around it. Record this as a project lock and pass it on every card.
6. **Secrets and identities stay out of the transcript.** Report provider names
   and credential types only. `hermes auth list` prints account labels, which
   can be email addresses; do not echo them. Never print a key value, and let the
   user run `hermes auth add` themselves.
7. **Config changes go through `hermes config set`**, and every change is read
   back. Profiles do not inherit config from each other; each holds a full copy.
8. **Projects hold the truth; the PM holds pointers.** A project is set up when
   an agent with zero memory can reconstruct it from disk (the wipe test).
9. **Claimed work without a path is not work.** Acceptance needs a real file, a
   checkable criterion, a captured exit code (never through a pipe), and the
   model route that produced it.
10. **Smallest team that fits.** Add a desk only from an observed need.

The user may override the fit verdict, but not the five **hard limits** in
`references/intake.md` (no unattended free tiers, no unattended attended-only
seats, no unattended pipeline without review, restricted-data rule, reproducibility
lock). Say so plainly when an override collides with one.

## When not to use this

The intake walks these top to bottom and the first match wins (full rules in
`references/intake.md`):

1. **Not yet**: the user will not review agent output, or has no working model
   access. Explain what would change the answer; offer one attended profile.
2. **Single profile**: one project, no publication stakes, no restricted data.
   A single profile with good skills beats a team. Offer that, using the plan's
   short form.
3. **Small team**: one project with stakes, only free or local models, or no
   route allowed to run unattended. PM + checker, attended, no unattended
   dispatch.

Everything else gets the full team.

## Quick reference

```text
hermes profile create <name> [--clone-from <src>]   # a clone copies SOUL + memories: overwrite both
hermes -p <name> config set <key> <value>           # never hand-edit config.yaml
hermes -p <name> config get model.provider          # configured route, not proof of use
bash scripts/insurance_backup.sh --retain 14 --install-cron  # full-home archive; first write of Build, after approval
# restore: mv ~/.hermes ~/.hermes-migrated && tar -xzf <archive> -C ~/   (runtime reinstalled after)
hermes auth list                                    # provider names; do not echo labels
hermes auth add <provider>                          # the USER runs this; never type a key for them
hermes project create <name> <folder>
hermes kanban boards create <slug> --default-workdir <abs-path>   # one board per project
hermes kanban --board <slug> create "<title>" --assignee engineer --body-file card.md
hermes kanban --board <slug> show <id>
hermes kanban --board <slug> set-model <id> <model> --provider <p>   # pin BEFORE reclaim
hermes kanban --board <slug> create "<title>" --assignee verifier --initial-status blocked ...  # parked at birth
hermes kanban unblock <id>                                          # release while the user is present
hermes config set kanban.dispatch_in_gateway false                  # attended mode: no background dispatch
hermes kanban --board <slug> dispatch --max 1                       # start one ready card, user present
hermes config get kanban.dispatch_in_gateway ; hermes gateway status # who dispatches, and is it up
hermes kanban swarm "<goal>" --worker engineer:"<title>" --verifier verifier --synthesizer writer
```

## Verification

`HERMES_PY` below is the Python inside the Hermes install (often
`~/.hermes/hermes-agent/venv/bin/python`). A bare system `python3` may lack
PyYAML.

1. **Routes.** `"$HERMES_PY" scripts/prove_routes.py engineer verifier writer`
   sends each profile a one-line probe and reads only that session's
   `agent.log` lines. Exit 0 means every profile answered on its configured
   provider and model with no fallback. Each probe costs one short call.
2. **Config.** `"$HERMES_PY" scripts/verify_config_sweep.py --backup-dir <dir>`
   reads keys back and prints a leaf diff against the pre-change snapshot.
3. **Insurance.** `bash scripts/insurance_backup.sh --out <dir>` archives the
   home and prints a restore command; test it once on a throwaway copy of the
   home before the first card so restore is proven, not assumed.
3. **First card.** A small real task (for example, one tested function in a
   real project) goes through builder then checker. Accept it only when the
   checker's verdict cites the artifact path and a captured exit code.
4. **Wipe test.** In a fresh session with no memory, point an agent at the
   registry and ask it the six questions for one project.

## Pitfalls

- **`delegate_task` children run on the PM's delegation model, not on a
  specialist's seat.** To use a specialist, create a card for it or run
  `hermes -p <name> chat -q`.
- **`agent.max_turns` kills a worker before the card's runtime clock does.**
  Size cards to fit one run, and have workers append progress to a file.
- **A card summary is a self-report.** Check the fence (files changed outside
  it) and re-check two or three load-bearing claims before relaying.
- **After switching a profile's provider, read back `model.base_url` and
  `model.api_mode`.** A leftover endpoint sends the new model to the old host.
- **A profile whose terminal runs in a container cannot see host paths.** Route
  host-path cards to a profile with a local terminal.

## References

Load on demand with
`skill_view(name="the-three-musketeers", file_path="references/<file>")`.

- `references/intake.md`: slots, probes, question rounds, fit rules. Load first, every time.
- `references/team-design.md`: from answers to roster, routes, fallbacks, cost tiers; worked examples.
- `references/projects-and-cards.md`: wipe test, registry, five-field cards, acceptance, checker gate, research locks.
- `references/running-the-board.md`: day-to-day Kanban: sizing, auditing, reclaiming, recovering.
- `references/existing-install.md`: consolidating an install that already has profile sprawl.
- `references/config-keys.md`: recommended config values and why.
- `references/environment-traps.md`: failures that look like project bugs but come from the environment.
- `templates/setup-plan.md`, `templates/PACKAGING_CONTRACT.md`, `templates/PROJECTS.md`, `templates/PROFILES.md`, `templates/role-souls.md`
- `scripts/prove_routes.py`, `scripts/verify_config_sweep.py`, `scripts/insurance_backup.sh`
