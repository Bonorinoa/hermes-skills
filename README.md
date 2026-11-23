# hermes-skills

A Hermes research team that runs at **$0**: OpenRouter's free tier, Nous Portal's free models, or a model already on your machine. Same price as ChatGPT or Claude free, with a verifier on a second model family, a board per project, and files that stay the record when the chat is gone.

The skill is written for the agent that sets it up. You install Hermes, install the skill, and paste the prompt below. A free model can do the rest. It changes nothing until you approve a written plan.

## Paste this

```
Set up hermes-research-crew. Use the free, $0 path if I have no paid model. Follow the skill. Do not write anything until I approve the plan.
```

## Prerequisites

- [Hermes Agent](https://hermes-agent.nousresearch.com) installed (`hermes --version` works), on macOS or Linux. The skill declares those platforms. The backup locks its crontab with a POSIX call Windows does not have.
- `git`.
- One model credential, which you add yourself. The agent must not type the key.
  - OpenRouter free: `hermes auth add openrouter`, then `hermes model`.
  - Nous Portal free: `hermes auth add` for the Portal provider, then `hermes model`.
  - A local runtime (Ollama or another server Hermes already talks to).
- Optional: `uv` (the desks fall back to `python3`), `gh` (private backups of project repos), a GPU if you want a local verifier.

## Install

Hermes installs this skill from GitHub directly. The skill lives under `skills/` in the repo, and that directory is part of the identifier:

```
hermes skills install Bonorinoa/hermes-skills/skills/hermes-research-crew
```

`Bonorinoa/hermes-skills/hermes-research-crew` is not a file path, so the direct GitHub source returns 404 for it. Hermes looks for `SKILL.md` at the path you give.

To browse the repo from the skills hub, add the tap first. `tap add` defaults to a `skills/` directory, which is where this repo keeps its skills:

```
hermes skills tap add Bonorinoa/hermes-skills
hermes skills install Bonorinoa/hermes-skills/skills/hermes-research-crew
```

Hermes runs its security scan before the install. The copy includes the references, templates, and scripts.

## What you get

An orchestrator that plans with you, an engineer, a verifier on a different model family, and a writer. Two optional desks: creative (figures and slides) and hygiene (clears run residue, keeps evidence). Persona names exist and stay off unless you ask for them.

One Kanban board per project. The check that the project is real is the wipe test: an agent with no memory can rebuild the state from the files.

Free routes are a normal outcome, not a demo mode. If the only models you have are free, and they pass a short tool-call probe, you get that full roster with dispatch left off. Cards run one at a time while you are there. A new OpenRouter free key is 20 requests a minute and 50 a day (1,000 a day after you have bought $10 of credit). The skill's probe spends at most 4 of those calls and stops on a daily 429.

| Store | Holds |
|---|---|
| memory | the person: role, preferences, standing conventions |
| skills | procedures, pitfalls, commands that actually ran |
| the project's spine | where the project is now, and the why, dated |
| the workspace registry | one row per project: root, spine pointer, phase, locks |

The board is work in flight. The transcript is conversation. When either disagrees with the project's files, the files win.

## When it will tell you not to use it

The intake checks these in order. The first match wins.

- **Not yet.** You will not review what the agents produce, or no route answered a tool call in time. It says what would change the answer.
- **Single profile.** Mostly short tasks, done while you are present, nothing to publish, no restricted data. One profile beats a team.
- **Small team.** Short tasks that have stakes, or no probed model can use tools. An orchestrator and a verifier, while you are present.
- **Full team, attended.** Long or many-step work on free models, local models, or a seat you have not cleared for automation. The full roster. Nothing starts in the background.
- **Full team.** The same work, with at least one route you may run while you are away.

You can override the verdict. A few limits hold anyway: nothing runs unattended on a free route, on a seat you have not confirmed, or for someone who will not review the results. If you agree a team is not worth it, stop there.

## What the setup holds to

- The verifier is a different model family from the producers. When your access has only one family, the plan says "same-family review" and does not pretend otherwise.
- A free model may be the model a desk runs on. It may not silently replace a desk mid-card. A failure blocks the card.
- Institutional seats stay attended-only until you confirm automation is allowed.
- Published results get a reproducibility lock.
- Restricted data is handled the way you choose. The default is that hosted agents see fake or sample data and never open the real files.
- Secrets and account emails are never printed.
- Before anything else is written, the agent archives your Hermes home and asks whether to keep that archive.

Why these desks, and how each one is built: [`references/architecture.md`](skills/hermes-research-crew/references/architecture.md).

## Terms

You check your providers' terms. For an institutional seat, you also check whether that institution allows automated or third-party agent use. The skill asks, and it stays attended-only when you are unsure. It does not infer permission from an email domain or a plan name.

## Safety and scripts

Six scripts. None of them deletes project files. None of them needs a pip install. YAML is read with ruamel.yaml if the Hermes runtime has it, otherwise PyYAML, otherwise a small parser in the standard library.

- `scripts/probe_install.py` is read-only. It prints a short install snapshot from any working directory: version, provider names, tools. It does not print account labels.
- `scripts/probe_free_routes.py` lists live free model ids from a catalog and scores one tool-call probe per id. It does not contain model names. The API key is read from the environment or `~/.hermes/.env` and is not printed. Listing OpenRouter's public catalog is the only call that needs the network besides a probe you asked for.
- `scripts/prove_routes.py` sends each profile one short probe (one model call per profile) and checks that profile's `agent.log` for the configured provider and model, with no silent fallback. A log line it cannot attribute is a fail.
- `scripts/verify_config_sweep.py` reads config back and diffs it against a snapshot. Values under secret-looking keys are not printed.
- `scripts/insurance_backup.py` archives the Hermes home before a migration. Databases are snapshotted, the archive is owner-only, and it prints the restore command. A retention of N days can install a cron line that deletes that one archive and then removes itself. It restores the Hermes home only.
- `scripts/hygiene_scan.py` is read-only. It lists stale scratch folders, large untracked files, and prunable worktrees.

The Hermes security scan of version 0.11.0 returned SAFE (no high findings). Install scans the copy you actually install. This 0.13.0 tree has not been given a separate scan verdict here.

## Repo checks

Every skill is checked before a push: frontmatter parses, `description` fits the index, `platforms` is a known list when it is set, every `references/`, `templates/`, and `scripts/` path named in the body exists, code fences balance, markdown tables keep their column count, and scripts compile. A script that imports `fcntl` without `platforms` is a warning.

```
python3 scripts/check_repo.py
python3 tests/test_skill_scripts.py
python3 tests/test_setup_scripts.py
```

`check_repo.py` does not need PyYAML; it uses the same loader as the skill. CI installs PyYAML so the PyYAML branch of that loader is exercised too. The workflow is `.github/workflows/check.yml`.

## Status

Version 0.13.0. The 0.12.0 research locks (rival card, specification lock, transcription checks) are unchanged.

Renamed in 0.11.0: this skill was `the-three-musketeers` through 0.10.0. If you installed that name, uninstall it (`hermes skills uninstall the-three-musketeers`) and install `hermes-research-crew`.

| Skill | Version | What it does |
|---|---|---|
| [hermes-research-crew](skills/hermes-research-crew/) | 0.13.0 | Set up a checked Hermes research team, free models included. |

Feedback: open a GitHub issue on this repository.

## Authors and license

Augusto González-Bonorino and Claude (Anthropic), working together in Hermes.

MIT license. See [LICENSE](LICENSE). The copyright line names Augusto, since an AI cannot hold copyright.
