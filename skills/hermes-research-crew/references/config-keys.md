# Config keys worth setting

Read with `hermes -p <p> config get <key>`. Write with
`hermes -p <p> config set <key> <value>`. Never hand-edit `config.yaml`; the file
tools refuse it by design.

## Profiles do not inherit config

Each profile holds a complete copy. There is no `include:` and no base overlay. A
value is either written in that profile or falls back to the built-in default.
"Set it globally" means setting it in every profile, then proving no drift with
`scripts/verify_config_sweep.py`.

## Recommended set

| Key | Shipped default | Suggested | Why |
|---|---|---|---|
| `compression.threshold` | `0.50` | `0.40` | When compaction fires, as a fraction of the window. Lower adds margin and costs fidelity. |
| `compression.target_ratio` | `0.20` | `0.20` | Where compaction lands. Keep it well below the threshold. |
| `compression.protect_last_n` | `20` | `40` | Recent turns kept verbatim. The main lever for not losing the thread. |
| `compression.protect_first_n` | `3` | `5` | The original task framing survives compaction. |
| `tool_loop_guardrails.hard_stop_enabled` | `false` | `true` | Loop guardrails ship disarmed. |
| `sessions.auto_prune` | `false` | `true` | Retention exists but never runs, so session stores grow without bound. |
| `checkpoints.enabled` | `false` | `true` | Rollback for agents editing real repositories. |
| `curator.consolidate` | `false` | `true` | Keeps memory tight instead of raising its limit. |
| `auxiliary.vision.provider` / `.model` | auto | an explicit, working pair | Pin both. Some providers have no default vision model, and an unpinned route fails quietly. |
| `delegation.provider` / `.model` | inherits | a cheap route | `delegate_task` children use this, not the profile's main model. |
| `agent.max_turns` | varies | per role (see `team-design.md`) | The worker's real time limit on cards. |
| `fallback_providers` | `[]` | per role (see `team-design.md`) | Decides whether a dead seat blocks or silently degrades. |

Defaults shift between releases. Read the live value before claiming one.

## Compaction

Compaction is lossy and invalidates the prompt cache each time it fires, so the
number of compactions matters, not only their size. Raising `protect_last_n` is
cheap. Pushing `threshold` very low compacts constantly and is hard to justify.

## `fallback_providers`

A list of dicts, tried in order:

```yaml
fallback_providers:
  - provider: <provider-id>
    model: <model-id>
```

- An entry missing `provider` or `model` is dropped silently. A typo looks like
  "fallback doesn't work".
- `[]` disables fallback. `hermes fallback list|add|remove|clear` manages it.
- Fallback fires on rate-limit, overload, connection, **and billing** errors
  (spending-limit 403s and usage-limit 429s have been observed rolling over). A
  dead primary is therefore silent; only `Fallback to` in `agent.log` shows it.
- On card-working profiles, follow the fallback policy in `team-design.md`:
  no free tiers.

## Leave alone

`agent.verify_on_stop`: recent Hermes config migrations turn it off. Treat the
stock value as intentional unless you have evidence otherwise.
