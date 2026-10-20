# hermes-skills

Skills for [Hermes Agent](https://hermes-agent.nousresearch.com), written for researchers who build tools and run several projects at once.

This is one repository for many skills. Each skill lives in its own folder under `skills/`. More may be added later.

## Skills in this repo

| Skill | Version | What it does |
|---|---|---|
| [the-three-musketeers](skills/the-three-musketeers/) | 0.10.0 (pre-release) | Set up a Hermes agent team for research projects. |

## Install

```
hermes skills install Bonorinoa/hermes-skills/the-three-musketeers
```

This installs the skill with its references, templates, and scripts, after Hermes runs its security scan. To see every skill in this repository, browse the [`skills/`](skills/) folder.

## Use

In a Hermes chat, say:

```
Set up the-three-musketeers
```

The agent starts an intake. It changes nothing until you approve a written plan. If you are cleaning up an existing install, it inventories your install read-only during planning; every write, including the backups, happens after approval, and destructive steps each get a separate yes.

## Repo checks

Every skill in this repo is checked structurally before a push: frontmatter parses, `description` fits the loader's limit, every `references/`, `templates/`, and `scripts/` path named in the body exists, code fences balance, markdown tables keep their column count, and scripts compile.

```
python3 scripts/check_repo.py     # the Hermes runtime python has PyYAML
```

It runs on every push and pull request in `.github/workflows/check.yml`.

## What the-three-musketeers does

It is for researchers, PhD students, and scientists who build tools and juggle several projects, often with flat-rate or institutional (EDU) model access rather than pay-per-token budgets.

It sets up:

- one project manager, d'Artagnan, which is the `default` profile;
- three specialists: a builder (Athos, `engineer`), a checker (Porthos, `verifier`), and a voice (Aramis, `writer` or `creative`);
- one Kanban board per project;
- project truth kept on disk, not in an agent's memory. The check is the "wipe test": can an agent with no memory rebuild the project's state from its files?

It also fixes where a fact goes, which is the part most setups get wrong:

| Store | Holds |
|---|---|
| memory | the person: role, preferences, standing conventions |
| skills | procedures, pitfalls, commands that actually ran |
| the project's spine (a status file, a decision log) | where the project is now, and the why, dated |
| the workspace registry | one row per project: root, spine pointer, phase, locks |

The board holds work in flight and the transcript holds conversation; neither is the record. When they disagree with the project's files, the files win.

How the intake works:

1. You say "Set up the-three-musketeers".
2. The agent probes your install. This step is read-only.
3. It asks short multiple-choice questions, in up to three rounds.
4. It gives a fit verdict: Not yet, Single profile, Small team, or Full team.
5. It writes a plan, starting with a plain-language summary.
6. It changes nothing until you approve the plan. The backups are no exception: the insurance archive and the config snapshot are the first writes of the build, after approval.

The skill is model-agnostic. It carries the constraints, and the intake picks the providers.

Constraints the skill holds, in brief:

- The checker runs on a different model family from the producers. When your access allows no second family, the plan says so plainly and calls it a same-family review.
- No free-tier fallback on profiles that work cards.
- Institutional seats stay attended-only until you confirm that automation is allowed.
- Published results get a reproducibility lock.
- Restricted data is handled the way you choose. By default, hosted agents work only on fake or sample data and never open the real files.
- Secrets and account emails are never printed.
- Trying it is reversible. Before anything changes, the agent archives your whole Hermes home (the insurance backup) and asks whether to keep it forever or auto-delete it after a set number of days; the plan records an undo checklist.

## When it will tell you not to use it

The intake may conclude that a team is not worth it. It checks these in order, and the first match wins:

- **Not yet.** You won't review what the agents produce, or you have no working model access. It explains what would change the answer.
- **Single profile.** One project, nothing to publish, no restricted data. One well-configured profile beats a team.
- **Small team.** One project with stakes, only free-tier models, or no account you may run unattended. A manager and a checker, used while you are present.
- **Full team.** Everything else.

The agent gives the verdict with its reason. You can override it, but some limits hold regardless: nothing runs unattended on free-tier models, on a seat you haven't confirmed may be automated, or for someone who won't review the results. If you agree that a team is not worth it, the intake can end there.

## What it costs

The skill itself is free. The team runs on whatever model access you have. Pay-per-token routes cost money, so set a spend cap at the provider.

## Terms

You are responsible for checking your model providers' terms. For institutional seats, you are also responsible for checking your institution's terms on automated or third-party agent use.

The skill asks about this and defaults to attended-only when unsure. It never infers permission from an email domain or a plan label.

## Safety and scripts

The skill includes three scripts.

- `scripts/prove_routes.py` sends each profile one short probe message (one model call per profile), using the `hermes` CLI as a subprocess. It then checks that profile's `agent.log` to confirm the profile answered on its configured provider and model, with no silent fallback.
- `scripts/verify_config_sweep.py` reads config back and diffs it against a pre-change snapshot. Values under secret-looking keys are never printed.
- `scripts/insurance_backup.sh` archives the whole Hermes home before a migration, prints the restore command, and can install a cron job that auto-deletes the archive after a chosen number of days. It is plain `bash` and `tar`; it makes no model calls.

The Hermes security scan of the skill returned the verdict SAFE. Its MEDIUM findings are calls to `hermes` via subprocess, and documentation that mentions `uv run` and `pip install pyyaml`.

## Status

Version 0.9.0 is pre-release. It has been tested with simulated users, not yet with real ones.

To give feedback, open a GitHub issue on this repository.

## Authors and license

Augusto González-Bonorino and Claude (Anthropic), working together in Hermes.

MIT license. See [LICENSE](LICENSE). The copyright line names Augusto, since an AI cannot hold copyright.
