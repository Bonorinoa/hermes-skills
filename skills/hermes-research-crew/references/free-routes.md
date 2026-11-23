# Free routes

A free model is a primary route, chosen by a probe, not a leftover. Do not type model ids from memory or from this file. Catalogs change. An id that 404s is retired.

$0 here means OpenRouter free-tier variants, Nous Portal's free models, or a model already on this machine. A ChatGPT or Claude subscription is not this path.

## What a pass is

`scripts/probe_free_routes.py` sends one short chat with a single tool, `ping`.

- **PASS** (`class=ok`, `tool=yes`): the model called the tool before the timeout (default 20s). It may hold a desk.
- **FAIL** `no_tool`: prose came back, no tool call. Do not assign it to a desk that must use tools.
- **FAIL** `silence`: timeout or an empty body. Drop the id.
- **FAIL** `retired` (404): refresh the catalog. Do not reuse the id.
- **FAIL** `gated` (403): region block, a closed free variant, or a negative balance. Drop the id.
- **FAIL** `billing` (402): stop free calls until the user adds credit.
- **FAIL** `rate_minute` (429, per minute): the script already waited once and retried once. If it still fails, stop probing this minute.
- **FAIL** `rate_day` (429, per day): stop. The script prints `stopped=rate_day`. Do not send another free call until the next UTC day.
- **FAIL** `rate_upstream` (429 from the provider behind the router): try a different family. Do not hammer the same id.

No automatic second model takes over a card. The card blocks. After it blocks, classify the error and either wait, drop the id, or ask the user before pointing the profile at a different id that already passed.

## Quotas, checked against the provider docs

OpenRouter, for an id ending in `:free` (their limits page, https://openrouter.ai/docs/api_reference/limits):

| Credits ever purchased | Per minute | Per UTC day |
|---|---|---|
| Less than 10 | 20 | 50 |
| At least 10 | 20 | 1000 |

The higher daily cap starts one credit under the printed 10, to absorb rounding. Extra accounts do not raise it. OpenRouter's pricing page says failed attempts count toward the daily cap, so a retry is a spent call. `GET /api/v1/key` field `free_model_daily_requests` shows the counter. Do not print the key.

Nous Portal's free plan is $0 and serves whatever the portal currently marks free, with its own standard rate limits (https://hermes-agent.nousresearch.com/ai-models). The list changes. Read it live. Do not copy ids out of a blog post.

A local model has no per-call price. It may run unattended only after the first card passes (`team-design.md`). Until then it is attended.

The OpenRouter id `openrouter/free` is a router. The script prints `skip=unstable-family`. Do not assign it: the family can change per call, which makes the verifier's independence claim false.

## How many calls setup may spend

A new OpenRouter key has 50 free calls a day. Setup may spend 4 of them.

1. List, which is not a model call:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py list --provider openrouter`

   `<SKILL_DIR>` is the `skill_dir=` line from `probe_install.py`. Nous and any other catalog: save the provider's model JSON and pass `--file`. Local models already pulled:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py list --provider local`

2. Pick at most 4 ids from different families. Prefer two families so the verifier is not the engineer.

3. Probe, one tool call each:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py probe-many --base-url https://openrouter.ai/api/v1 --max-probes 4 <id> <id>`

   The key is `OPENROUTER_API_KEY` in the environment or in `~/.hermes/.env`. The script reads it and does not print it. Do not `cat` the env file. For a local OpenAI-compatible server pass `--key-env -` and that server's base URL.

4. Assign PASS ids. Engineer: a PASS id that called the tool. Verifier: a PASS id whose `family=` differs. Writer: a PASS id, the engineer's family is allowed. Orchestrator: a PASS id the user can stand to talk to. If only one family passed, build the roster anyway and write "same-family review" in the plan. If none passed, the verdict is Not yet.

5. `scripts/prove_routes.py` is the later check, after config is set. It proves the profile's live log, not the catalog.

## Desk rules that stay

- Unattended dispatch to a free route is forbidden (intake hard limit 1). The roster can still be the full team. `kanban.dispatch_in_gateway` stays false. You run `hermes kanban --board <slug> dispatch --max 1` while the user is present.
- Hygiene deletes files. On a free route it runs only while the user is present.
- Fallback for a card-working profile is empty, or a same-tier paid route the user named. Never a free id in `fallback_providers`. Interactive chat may keep a fast free fallback, because a person sees every reply.
