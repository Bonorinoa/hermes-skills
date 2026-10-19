# Environment traps

Failures that look like project bugs but come from the Hermes runtime, the
shell, or the account behind a route.

## PYTHONPATH shadowing

**Symptom:** a project's tests die on import inside a correct virtualenv, for
example `No module named 'numpy._core._multiarray_umath'`.

**Cause:** the Hermes process environment can carry a `PYTHONPATH` for its own
tooling. Subprocesses inherit it, and it precedes the project venv on
`sys.path`, so one interpreter imports another environment's packages.

**Check:** read which directory the failing module loaded from.

**Fix:** `env -u PYTHONPATH uv run python <script>`. Rebuilding the venv does not
help. Put this line in each role SOUL that runs Python.

## A dead account looks like a broken agent

Every delegated child or card worker dies within seconds. Check
`hermes auth list` for an `exhausted` marker and the provider's balance page.
Delegation, the main model, and auxiliary tasks are separate keys; repoint each
one that uses the dead route.

## Switching providers leaves the old endpoint

After `config set model.provider`, read back `model.base_url` and
`model.api_mode`. If they belong to the old provider, the new model is sent to
the old host. Model ids are not portable either: the same model can carry a
different id on another provider. Check the provider's live model list first.

## A commented key is not a credential

`# OPENROUTER_API_KEY=...` in a `.env` does nothing. Confirm an uncommented
assignment exists (`grep -c '^OPENROUTER_API_KEY=' .env`) without printing it.

## Clones carry the source's identity

`hermes profile create --clone-from <src>` copies `SOUL.md`, memories, and
skills. Overwrite the SOUL and replace the memory file before the first real
session, or the new desk starts with someone else's role and history. A "no API
keys" warning after cloning a seat-login profile is expected; logins live in the
root auth store.

## The curated catalog is not the model list

Catalog entries can carry only an id. For modality, price, and context length,
query the provider's live model endpoint. A model missing from the catalog may
still be served.

## Shell traps that fabricate results

- macOS has no `timeout` binary. `timeout 60 cmd | tail` fails, and the pipeline
  returns `tail`'s exit 0. Capture `${PIPESTATUS[0]}` or run the command bare.
- `xargs -I` combined with `-0` returns nothing instead of an error, so a scan can
  report "no matches" falsely. Enumerate in Python, or use a `read -r -d ''` loop.

## Config changes and running sessions

A running session may keep routes it resolved at startup. If a probe contradicts
the config, start a new session before believing either.

## Concurrent writers

Several sessions can edit one install, which is normal. Before broad changes,
look for other agent processes and recently modified files. Never overwrite
another session's work.
