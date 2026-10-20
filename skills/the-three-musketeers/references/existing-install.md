# Branch: consolidating an existing install

For users whose S1 answer is "clean up an install I already have": many profiles
(often one per project), drifted config, projects with no remote.

This branch changes *when* writes may happen: nothing does. Inventory and
verdicts are read-only and part of planning. Every write — the insurance
archive, the snapshot, profile deletion, repo creation, config changes —
happens **after the user approves the plan** (SKILL.md, Rule zero), and each
destructive step still gets its own separate yes.

## 1. Inventory (read-only, during planning)

For each profile, show its route, its last use, and the projects it carried.
The user decides for each: keep as a specialist, keep as a thin project desk,
or retire.

Run a credential scan **first**, reported as file names and match counts only:
`.env`, `auth.json`, `state-snapshots/*/.env`, `*token*`, `*.pem`. Deleting a
profile deletes credential material, which is a security decision for the
user — record it in the plan's undo checklist.

Sessions do not migrate. They live in the profile's own `state.db`, and
deleting the profile hides them while project rows remain, so a project can
later show zero sessions. Record what each profile carried.

## 2. The plan

Fill `templates/setup-plan.md`. Its sections 3 (Roster), 6 (Projects, with the
Backup column), and 9 (Insurance and rollback) carry the per-profile verdicts,
the insurance choice, and the undo checklist. Approve the plan before any write.

## 3. Build (post-approval; destructive steps each get a separate yes)

1. **Insurance archive** (the first write — this is the "am I stuck?" question
   answered up front):

   ```bash
   bash scripts/insurance_backup.sh --out ~/hermes-backups --retain <forever|N>
   ```

   The script asks keep-forever vs auto-delete after N days (a cron job; offer
   `--install-cron`), prints the restore command, and the archive contains
   credentials — local only, never uploaded.

2. **Config snapshot** (the fine-grained diff for the sweep, after the archive):

   ```bash
   B=~/.hermes/config-backups/$(date +%F)-migration; mkdir -p "$B"
   cp ~/.hermes/config.yaml "$B/default.config.yaml"
   for d in ~/.hermes/profiles/*/; do p=$(basename "$d"); [ -f "$d/config.yaml" ] && cp "$d/config.yaml" "$B/$p.config.yaml"; done
   cp ~/.hermes/projects.db "$B/" 2>/dev/null
   ```

   The `<profile>.config.yaml` naming is what `scripts/verify_config_sweep.py`
   expects. Verify any bulk move with a name-and-size comparison.

3. **Retire profiles** (destructive: one approval per profile):

   ```bash
   hermes profile export <name>
   tar -tzf ~/.hermes/profile-exports/<name>-*.tar.gz | grep -E 'SOUL.md|config.yaml|state.db'
   hermes profile delete <name> -y && hermes profile list
   ```

   There is no `archive` verb; the lifecycle is export, then delete. Keep the
   tarballs until the user confirms nothing is missing.

4. **Back up unbacked projects** (each project approved):

   - Write `.gitignore` before `git init`: model weights, raw or licensed data,
     and `.env`. Small datasets may be tracked on purpose; ask.
   - Stage, then run a secret pre-flight that reports counts, never matched text:

     ```bash
     PATTERN='BEGIN [A-Z ]*PRIVATE KEY|sk-[A-Za-z0-9]{20,}|gh[pous]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|xox[baprs]-'
     git diff --cached --name-only | while IFS= read -r f; do
       n=$(git show ":$f" 2>/dev/null | grep -cE "$PATTERN" || true)
       [ "${n:-0}" -gt 0 ] && printf '%s\t%s match(es)\n' "$f" "$n"
     done
     ```

   - Create the repository private by default:
     `gh repo create <name> --private --source=. --remote=origin --push`.
     Public is the user's explicit choice.

   `.gitignore` only affects future commits. It does not untrack files git
   already has, and it does nothing to pushed history.

5. **Sweep config, then verify:**

   Apply the keys from `config-keys.md` to every kept profile with
   `hermes -p <p> config set`, then run:

   ```bash
   "$HERMES_PY" scripts/verify_config_sweep.py --backup-dir "$B" \
     --expect 'auxiliary/vision/provider=<provider>'
   ```

   The drift list must contain only keys you meant to change. Changes you did
   not make usually mean another session is editing the install at the same
   time. That is common. Stop and look before overwriting anything.

6. **Record the undo checklist** in the plan's section 9: profiles retired
   (export tarballs), profiles created, config keys changed (old values live
   in the snapshot), directories created, boards, remote repositories, the
   retention cron job if installed, and the gateway service if installed.
   The checklist plus the insurance archive is the whole rollback story.

## After Build

Design the team on the cleaned install — the main flow continues at step 5.
