# hermes-skills

Skills for [Hermes Agent](https://hermes-agent.nousresearch.com), written for researchers who build tools and run several projects at once.

This is one repository for many skills. Each skill lives in its own folder under `skills/`. More may be added later.

## Skills in this repo

| Skill | Version | What it does |
|---|---|---|
| [the-three-musketeers](skills/the-three-musketeers/) | 0.9.0 (pre-release) | Set up a Hermes agent team for research projects. |

## Install

```
hermes skills tap add Bonorinoa/hermes-skills
hermes skills install <INSTALL_ID>
```

## Use

In a Hermes chat, say:

```
Set up the-three-musketeers
```

The agent starts an intake. It changes nothing until you approve a written plan.

## What the-three-musketeers does

It is for researchers, PhD students, and scientists who build tools and juggle several projects, often with flat-rate or institutional (EDU) model access rather than pay-per-token budgets.

It sets up:

- one project manager, d'Artagnan, which is the `default` profile;
- three specialists: a builder (Athos, `engineer`), a checker (Porthos, `verifier`), and a voice (Aramis, `writer` or `creative`);
- one Kanban board per project;
- project truth kept on disk, not in an agent's memory. The check is the "wipe test": can an agent with no memory rebuild the project's state from its files?

How the intake works:

1. You say "Set up the-three-musketeers".
2. The agent probes your install. This step is read-only.
3. It asks short multiple-choice questions, in up to three rounds.
4. It gives a fit verdict: Not yet, Single profile, Small team, or Full team.
5. It writes a plan, starting with a plain-language summary.
6. It changes nothing until you approve the plan.

The skill is model-agnostic. It carries the constraints, and the intake picks the providers.

Constraints the skill holds, in brief:

- The checker runs on a different model family from the producers.
- No free-tier fallback on profiles that work cards.
- Institutional seats stay attended-only until you confirm that automation is allowed.
- Published results get a reproducibility lock.
- Restricted data is kept out of hosted agents.
- Secrets and account emails are never printed.

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

The skill includes two scripts.

- `scripts/prove_routes.py` sends each profile one short probe message (one model call per profile), using the `hermes` CLI as a subprocess. It then checks that profile's `agent.log` to confirm the profile answered on its configured provider and model, with no silent fallback.
- `scripts/verify_config_sweep.py` reads config back and diffs it against a pre-change snapshot.

The Hermes security scan of the skill returned the verdict SAFE. Its MEDIUM findings are calls to `hermes` via subprocess, and documentation that mentions `uv run` and `pip install pyyaml`.

## Status

Version 0.9.0 is pre-release. It has been tested with simulated users, not yet with real ones.

To give feedback, open a GitHub issue on this repository.

## Authors and license

Augusto González-Bonorino and Claude (Anthropic), working together in Hermes.

MIT license. See [LICENSE](LICENSE). The copyright line names Augusto, since an AI cannot hold copyright.
