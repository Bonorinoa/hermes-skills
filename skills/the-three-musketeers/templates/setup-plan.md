# Setup plan: <user> / <date>

Status: DRAFT. Nothing below has been written yet.

**Short form** (Single profile, Small team): fill sections 0, 1, 2, 3, 5, 8, 9, 10.
**Full team**: fill every section.

## 0. In plain words

<Three to five sentences a non-expert can approve: which agents you will have,
what each does, which accounts they use, what runs while you are away and what
waits for you, and what will never happen without asking.>

## 1. Intake

| Slot | Answer | Source |
|---|---|---|
| S1 Goal | | user |
| S2 Work shape | | user |
| S3 Model access | <provider: family, billing> | probe + user |
| S4 Metered budget | | user |
| S5 Institutional seat and terms | <provider: yes / no / unsure> | user |
| S6 Publication / restricted data | <and the chosen data-handling rule> | user |
| S7 Review habit | | user |
| S8 Desks | | user / default |
| S9 Workspace | | probe + user |
| S10 Platform | | probe + user |
| S11 Existing status / decision records | <file names per project, or "none"> | probe + user |

## 2. Fit verdict

<Not yet / Single profile / Small team / Full team / Full team, attended checks>,
because <reason>. User override, if any: <...>. Hard limits that still apply: <...>

## 3. Roster

| Profile | Role | Primary route (provider / exact model id, family) | Fallback | Dispatch | max_turns | Why |
|---|---|---|---|---|---|---|
| default | PM (d'Artagnan) | | | interactive | 60 | |
| engineer | builder (Athos) | | none | unattended / attended-only | 75 | |
| verifier | checker (Porthos) | | | unattended / attended-only | 100 | |
| writer or creative | voice (Aramis) | | none | unattended / attended-only | 60 | |

**Independence:** checker family = <...>; producer families (PM included) = <...>.
<Independent | Weak check (small local model, must catch the planted error) | Same-family review, accepted because ...>

Single profile: keep only the `default` row. Model ids are `UNVERIFIED` at
approval (the `hermes model` picker writes config, so it runs after approval);
step 6 (Prove) validates them before the first card.

## 4. Credentials the user must add

<provider: `hermes auth add <provider>`, run by the user> (or "none")

## 5. Config applied to every profile

Insurance archive first, then snapshot, both after approval
(`~/.hermes/config-backups/<date>-setup/<profile>.config.yaml`).
<keys and values from config-keys.md, with any changes>

## 6. Projects

| Project | Root | Board slug | Spine (existing or proposed) | Backup (remote / none: offer a private repo, separate yes) | Locks |
|---|---|---|---|---|---|

## 7. Dispatch

- Mode: <unattended | attended mode (background dispatch off) | mixed (attended-only profiles parked)>.
- Dispatcher: <gateway (installed as a service: a persistent change) / kanban daemon / none>.
- Concurrency: <cap, if desks share one subscription>.
- Overnight: <always-on machine / laptop awake, lid open, plugged in>.
- Attended-only cards are created parked and released by the PM when you are present.

## 8. What will be written, and what will not

Written: profiles <list>; `<workspace>/PROJECTS.md`, `PACKAGING_CONTRACT.md`,
`PROFILES.md`; a SOUL.md per profile; boards <list>; config keys (section 5);
<gateway service install, if chosen>.

Not done without a separate yes: push, publish, repository creation, unattended
dispatch to attended-only seats, <anything else the user excluded>.

## 9. Insurance and rollback

Insurance archive: `bash scripts/insurance_backup.sh --out <dir>` — retention:
<forever | auto-delete after N days, cron installed: yes/no>; restore:
<the command from its output>.

Config snapshots at <path>. Undo checklist:
- profiles created: <list> -> `hermes profile delete <name>`
- profiles retired (existing-install): export tarballs at <path>; full restore via the archive
- config keys changed: <list> (old values in the snapshot)
- directories created: <list> -> remove only after the archive is confirmed readable
- boards: <list> -> `hermes kanban boards rm <slug>`
- remote repositories: <list> -> `gh repo delete <name>` (only if the user asks)
- retention cron job (if installed): remove with `crontab -l | grep -v 'hermes-home-backup' | crontab -`
- gateway service (if installed): remove with `hermes gateway uninstall`

## 10. Approval

- [ ] I understand that checking my providers' and my institution's terms is my
      responsibility, and the plan reflects what I told it.

Approve / Change something / Stop. Recorded answer: <...>
