# Quick reference

Load this when a command or a term is needed. It is not part of the setup path.

`<SKILL_DIR>` is the `skill_dir=` line printed by `scripts/probe_install.py`. Every script is `python3 <SKILL_DIR>/scripts/<name>.py`, from any working directory.

## Commands

```text
hermes profile create <name> [--clone-from <src>]   # a clone copies SOUL + memories: overwrite both
hermes -p <name> config set <key> <value>           # never hand-edit config.yaml
hermes -p <name> config get model.provider          # configured route, not proof of use
python3 <SKILL_DIR>/scripts/insurance_backup.py --retain 14 --install-cron
# restore: mv ~/.hermes ~/.hermes-migrated && tar -xzf <archive> -C ~/
python3 <SKILL_DIR>/scripts/hygiene_scan.py --root <project-root>
python3 <SKILL_DIR>/scripts/probe_install.py
python3 <SKILL_DIR>/scripts/probe_free_routes.py list --provider openrouter
python3 <SKILL_DIR>/scripts/prove_routes.py engineer verifier writer
python3 <SKILL_DIR>/scripts/verify_config_sweep.py --backup-dir <dir>
hermes auth list                                    # provider names; do not echo labels
hermes auth add <provider>                          # the USER runs this
hermes project create <name> <folder>
hermes kanban boards create <slug> --default-workdir <abs-path>
hermes kanban --board <slug> create "<title>" --assignee engineer --body-file card.md
hermes kanban --board <slug> show <id>
hermes kanban --board <slug> set-model <id> <model> --provider <p>
hermes kanban --board <slug> create "<title>" --assignee verifier --initial-status blocked
hermes kanban unblock <id>
hermes config set kanban.dispatch_in_gateway false
hermes kanban --board <slug> dispatch --max 1
hermes config set kanban.max_in_progress 1
hermes kanban request-review <id> --reviewer verifier --summary "..."
```

## Stores

| Store | Holds | Test |
|---|---|---|
| memory | the person: role, preferences, stable environment facts | Still true in a month, in every project? |
| skills | procedures and the commands that actually ran | Would it change how a task gets done? |
| the project's spine | status now, and a dated decision log | Does doing the work make it stale? |
| the workspace registry | one row per project: root, spine pointer, phase, locks | Is this a pointer, not a record? |

The board and the transcript are not truth. When they disagree with the project's files, the files win. Order: git remote, then the spine, then memory.

Misfilings, said out loud once:

- "Provider X answered again after the rebuild" is a status line, not memory.
- "Run project Python with `env -u PYTHONPATH`" is a skill instruction.
- "Prefers ISO dates and metric units" is memory.
- "The verifier accepted card 47" belongs on the board, never in the registry.

## Glossary

Use a term with the user only after saying it in plain words.

| Term | Meaning |
|---|---|
| profile | A separate Hermes agent with its own model, memory, and instructions. |
| desk | A profile with one job. |
| route | The provider plus model a profile calls. |
| seat | A subscription login used as a route. |
| family | The vendor that trained the model. The id's prefix (`org/` in `org/model:free`) is the probe's stand-in. |
| card | One task on a project's board, assigned to a desk. |
| attended / unattended | Whether the user is present. Unattended means the dispatcher starts the card. |
| fence | What a card must not touch. |
| lock | A project rule that overrides convenience. |
| spine | The project's own files that explain it. |
| wipe test | Can an agent with no memory rebuild the project's state from its files? |
