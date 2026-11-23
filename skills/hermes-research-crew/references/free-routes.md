# Free routes

A free model is a primary route, chosen by a probe, not a leftover. Do not type model ids from memory or from this file. Catalogs change. An id that 404s is retired.

$0 here means OpenRouter free-tier variants, Nous Portal's free models, or a model already on this machine. A ChatGPT or Claude subscription is not this path.

## What a pass is

`scripts/probe_free_routes.py probe` runs one real Hermes one-shot on the candidate route. It asks the model to read a file holding a random token, with only the file tool available. A model can return the token only by calling the tool. Hermes uses its own stored credential; the script never reads a key or an `.env` file. The answering route is read from that run's lines in `agent.log`.

- **PASS** (`class=ok`): Hermes exited 0, the token came back, the session's log records a completed `read_file`, and every API call in that session was the candidate id on the named provider. The session is the id Hermes printed on stderr, matched exactly against each log record's session field. It may hold a desk.
- **FAIL** `no_tool`: the route answered without the token, or no `read_file` ran. Do not assign it to a desk that must use tools.
- **FAIL** `exit_error`: Hermes itself exited non-zero. Read its error before retrying.
- **FAIL** `fallback`: another model answered (`saw=` names it). The profile's fallback hid a failure of the candidate. Treat the candidate as failed, and note that the profile has a silent fallback (constraint 3).
- **FAIL** `no_call`: no API call was logged for the run. Usually the provider has no credential in Hermes yet: the user runs `hermes auth add <provider>`.
- **FAIL** `silence`: timeout (default 150s). Drop the id.
- **FAIL** `rate_minute`: a 429 in the run's log. Wait a minute before the next probe.
- **FAIL** `rate_day`: a daily limit. The script prints `stopped=rate_day` and stops. No more free calls until the next UTC day.

A retired id shows up as `no_call` or `fallback`; refresh the catalog rather than retrying it.

No automatic second model takes over a card. The card blocks. After it blocks, classify the error and either wait, drop the id, or ask the user before pointing the profile at a different id that already passed.

## Quotas, checked against the provider docs

OpenRouter, for an id ending in `:free` (their limits page, https://openrouter.ai/docs/api_reference/limits):

| Credits ever purchased | Per minute | Per UTC day |
|---|---|---|
| Less than 10 | 20 | 50 |
| At least 10 | 20 | 1000 |

The higher daily cap starts one credit under the printed 10, to absorb rounding. Extra accounts do not raise it. OpenRouter's pricing page says failed attempts count toward the daily cap, so a retry is a spent call. The user can see the counter on the OpenRouter dashboard.

Nous Portal's free plan is $0 and serves whatever the portal currently marks free, with its own standard rate limits (https://hermes-agent.nousresearch.com/ai-models). The list changes. Read it live. Do not copy ids out of a blog post.

A local model has no per-call price. It may run unattended only after the first card passes (`team-design.md`). Until then it is attended.

The OpenRouter id `openrouter/free` is a router. The script prints `skip=unstable-family`. Do not assign it: the family can change per call, which makes the verifier's independence claim false.

## How many calls setup may spend

A new OpenRouter key has 50 free calls a day. Setup may spend about 8 of them (4 probes, each one or two calls).

0. The provider needs a credential in Hermes first. If `probe_install.py` printed an empty `providers=` line, the user runs `hermes auth add openrouter` (or `nous`) themselves. You never see the key.

1. List, which is not a model call and needs no key:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py list --provider openrouter`

   `<SKILL_DIR>` is the `skill_dir=` line from `probe_install.py`. Nous and any other catalog: save the provider's model JSON and pass `--file`. Local models already pulled:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py list --provider local`

2. Pick at most 4 ids from different families. Prefer two families so the verifier is not the engineer.

3. Probe them through Hermes:

   `python3 <SKILL_DIR>/scripts/probe_free_routes.py probe --provider openrouter <id> <id>`

   Each probe is a short Hermes session on the default profile (or `--profile <name>`); it writes nothing but that session's log lines. A local model is probed the same way once the user has added it as a Hermes provider (`hermes model`).

4. Assign PASS ids. Engineer: a PASS id that called the tool. Verifier: a PASS id whose `family=` differs. Writer: a PASS id, the engineer's family is allowed. Orchestrator: a PASS id the user can stand to talk to. If only one family passed, build the roster anyway and write "same-family review" in the plan. If none passed, the verdict is Not yet.

5. `scripts/prove_routes.py` is the later check, after config is set. It proves the profile's live log, not the catalog.

## Desk rules that stay

- Unattended dispatch to a free route is forbidden (intake hard limit 1). The roster can still be the full team. `kanban.dispatch_in_gateway` stays false. You run `hermes kanban --board <slug> dispatch --max 1` while the user is present.
- Hygiene deletes files. On a free route it runs only while the user is present.
- Fallback for a card-working profile is empty, or a same-tier paid route the user named. Never a free id in `fallback_providers`. Interactive chat may keep a fast free fallback, because a person sees every reply.
