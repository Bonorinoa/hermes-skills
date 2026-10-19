# Profiles

Who runs what. The live config is the truth; re-read it after any routing change
and update this file in the same change.

| Profile | Role | Route (provider / model) | Fallback | Dispatch | How to send it work |
|---|---|---|---|---|---|
| default | PM (d'Artagnan) | | | interactive | you talk to it |
| engineer | builder (Athos) | | none | unattended / attended-only | card on the project board, `--assignee engineer` |
| verifier | checker (Porthos) | | | unattended / attended-only | card with Artifact + Acceptance, `--assignee verifier` |
| writer | voice (Aramis) | | none | unattended / attended-only | card, `--assignee writer` |

## Checks

- Routes proven with `scripts/prove_routes.py` on <date>: <PASS / results>.
- Independence: <checker family> vs <producer families>.

## Attended-only seats

<profile: reason (for example, institution terms unconfirmed). Its cards are
created parked and released when the user is present.>

## Open items

<anything unresolved: a seat awaiting confirmation, a route to re-test>
