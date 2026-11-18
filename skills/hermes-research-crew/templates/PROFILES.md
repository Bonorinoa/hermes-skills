# Profiles

Who runs what. The live config is the truth; re-read it after any routing change
and update this file in the same change. Keep only the desks the plan approved.

| Profile | Role (persona) | Route (provider / model) | Fallback | Dispatch | How to send it work |
|---|---|---|---|---|---|
| default | orchestrator (d'Artagnan) | | | interactive | you talk to it |
| engineer | engineer (Athos) | | none | unattended / attended-only | card on the project board, `--assignee engineer` |
| verifier | verifier (Porthos) | | | unattended / attended-only | card with Artifact + Acceptance, `--assignee verifier`, or `request-review --reviewer verifier` |
| writer | writer (Aramis) | | none | unattended / attended-only | card, `--assignee writer` |
| creative | creative (Bazin), optional | | none | unattended / attended-only | card, `--assignee creative` |
| hygiene | hygiene (Planchet), optional | | none | unattended / attended-only | weekly card, `--assignee hygiene`; daily no-agent scan |

## Checks

- Routes proven with `scripts/prove_routes.py` on <date>: <PASS / results>.
- Independence: <verifier family> vs <producer families, orchestrator included>.

## Attended-only seats

<profile: reason (for example, institution terms unconfirmed). Its cards are
created parked and released when the user is present.>

## Open items

<anything unresolved: a seat awaiting confirmation, a route to re-test>
