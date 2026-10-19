# Branch: consolidating an existing install

For users whose S1 answer is "clean up an install I already have": many profiles
(often one per project), drifted config, projects with no remote. Run this
between the fit verdict and the plan, then design the team on the cleaned install.

## 1. Snapshot (copies only; ask first)

This is the one write allowed before the plan (SKILL.md, Rule zero): it copies
config files into a new backup folder and changes nothing in the install.

```bash
B=~/.hermes/config-backups/$(date +%F)-migration; mkdir -p "$B"
cp ~/.hermes/config.yaml "$B/default.config.yaml"
for d in ~/.hermes/profiles/*/; do p=$(basename "$d"); [ -f "$d/config.yaml" ] && cp "$d/config.yaml" "$B/$p.config.yaml"; done
cp ~/.hermes/projects.db "$B/" 2>/dev/null
```

The `<profile>.config.yaml` naming is what `scripts/verify_config_sweep.py`
expects. Inventory with full listings; a truncated listing once hid 369 of 480
files and nearly produced a lossy copy. Verify any bulk move with a name-and-size
comparison.

## 2. Decide each profile's fate with the user

For each profile: keep as a specialist, keep as a thin project desk, or retire.
Show its route, its last use, and the projects it carried. The user decides.

## 3. Retire safely (destructive: explicit approval per profile)

1. **Credential scan first**, reported as file names and counts only: `.env`,
   `auth.json`, `state-snapshots/*/.env`, `*token*`, `*.pem`. Deleting a profile
   deletes credential material, which is a security decision for the user.
2. **Sessions do not migrate.** They live in the profile's own `state.db`.
   Deleting the profile hides them while the project rows remain, so a project
   can later show zero sessions. Record what the profile carried.
3. Export, then confirm the archive is readable:

   ```bash
   hermes profile export <name>
   tar -tzf ~/.hermes/profile-exports/<name>-*.tar.gz | grep -E 'SOUL.md|config.yaml|state.db'
   ```

4. Delete, then confirm the roster shrank:

   ```bash
   hermes profile delete <name> -y && hermes profile list
   ```

There is no `archive` verb; the lifecycle is export, then delete. Keep the
tarballs until the user confirms nothing is missing.

## 4. Back up unbacked projects

For each project without a remote, with the user's approval:

1. Write `.gitignore` before `git init`: model weights, raw or licensed data, and
   `.env`. Small datasets may be tracked on purpose; ask.
2. Stage, then run a secret pre-flight that reports counts, never matched text:

   ```bash
   PATTERN='BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9]{20,}|gh[pous]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-'
   git diff --cached --name-only | while IFS= read -r f; do
     n=$(git show ":$f" 2>/dev/null | grep -cE "$PATTERN" || true)
     [ "${n:-0}" -gt 0 ] && printf '%s\t%s match(es)\n' "$f" "$n"
   done
   ```

3. Create the repository private by default:
   `gh repo create <name> --private --source=. --remote=origin --push`.
   Public is the user's explicit choice.

`.gitignore` only affects future commits. It does not untrack files git already
has, and it does nothing to pushed history.

## 5. Sweep config, then verify

Apply the keys from `config-keys.md` to every kept profile with
`hermes -p <p> config set`, then run:

```bash
"$HERMES_PY" scripts/verify_config_sweep.py --backup-dir "$B" \
  --expect 'auxiliary/vision/provider=<provider>'
```

The drift list must contain only keys you meant to change. Changes you did not
make usually mean another session is editing the install at the same time. That
is common. Stop and look before overwriting anything.
