#!/usr/bin/env bash
# insurance_backup.sh — full-home "insurance" backup before a Hermes migration
# changes anything (the-three-musketeers plan approval, or any cleanup).
#
#   bash scripts/insurance_backup.sh [--hermes-home PATH] [--out DIR]
#                                     [--retain forever|N] [--install-cron] [--yes]
#
#   --hermes-home  Hermes home to archive (default $HERMES_HOME or ~/.hermes)
#   --out          where the tarball goes (default ~/hermes-backups)
#   --retain       forever (default) or N days. With N, an auto-delete cron line
#                  is printed; add --install-cron to install it after a yes.
#   --yes          no prompts. With --retain given, nothing is asked.
#
# Excluded from the archive (reinstallable or prunable): the hermes runtime
# (hermes-agent/), caches, scratch, installs, tmp. Everything else — config,
# profiles, skills, auth.json, .env, kanban.db, logs, snapshots — is included,
# so the archive can restore the exact pre-migration install. It therefore
# CONTAINS CREDENTIALS: keep it on this machine, never upload it, and remove it
# with `rm -P` when you are done with it.
set -euo pipefail

HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
OUT_DIR="$HOME/hermes-backups"
RETAIN="forever"
INSTALL_CRON=0
YES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --hermes-home) HOME_DIR="$2"; shift 2 ;;
    --out) OUT_DIR="$2"; shift 2 ;;
    --retain) RETAIN="$2"; shift 2 ;;
    --install-cron) INSTALL_CRON=1; shift ;;
    --yes) YES=1; shift ;;
    -h|--help)
      sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ -d "$HOME_DIR" ] || { echo "no such Hermes home: $HOME_DIR" >&2; exit 1; }
mkdir -p "$OUT_DIR"
BASE=$(basename "$HOME_DIR"); PARENT=$(dirname "$HOME_DIR")
STAMP=$(date +%Y%m%d-%H%M%S)
ARCHIVE="$OUT_DIR/hermes-home-backup-$STAMP.tar.gz"

if [ "$RETAIN" = "forever" ] && [ "$YES" -eq 0 ]; then
  printf 'Keep this backup forever, or auto-delete after N days? [forever / 7 / 14 / 30]: '
  read -r RETAIN; RETAIN=${RETAIN:-forever}
fi
case "$RETAIN" in forever|[0-9]*) : ;; *) echo "bad --retain value: $RETAIN" >&2; exit 2 ;; esac

echo "Archiving $HOME_DIR -> $ARCHIVE (runtime, caches and scratch excluded)"
tar -czf "$ARCHIVE" -C "$PARENT" \
  --exclude "$BASE/hermes-agent" \
  --exclude "$BASE/cache" \
  --exclude "$BASE/scratch" \
  --exclude "$BASE/installs" \
  --exclude "$BASE/tmp" \
  "$BASE"

N=$(tar -tzf "$ARCHIVE" | wc -l | tr -d ' ')
SIZE=$(du -sh "$ARCHIVE" | cut -f1)
echo "Archive: $ARCHIVE  ($SIZE, $N entries)"
[ "$N" -gt 0 ] || { echo "empty archive - aborting" >&2; exit 1; }

cat <<EOF

Restore (only to undo this migration):
  mv "$HOME_DIR" "$HOME_DIR-migrated"      # keep the changed one aside
  tar -xzf "$ARCHIVE" -C "$PARENT"         # puts "$BASE" back exactly
Then reinstall the Hermes runtime (it is excluded from the archive) and
restart. When you are sure the new setup is good, remove the archive with
  rm -P "$ARCHIVE"
EOF

if [ "$RETAIN" != "forever" ]; then
  CRON="0 3 * * * find \"$OUT_DIR\" -name 'hermes-home-backup-*' -mtime +${RETAIN} -delete"
  echo
  echo "Auto-delete after ${RETAIN} days. Cron line:"
  echo "  $CRON"
  if [ "$INSTALL_CRON" -eq 1 ]; then
    if [ "$YES" -eq 0 ]; then printf 'Install this cron job? [y/N]: '; read -r A; A=${A:-no}; else A=yes; fi
    case "$A" in
      y|Y|yes) ( crontab -l 2>/dev/null | grep -v "hermes-home-backup" ; echo "$CRON" ) | crontab -
        echo "cron installed. (verify: crontab -l)" ;;
      *) echo "cron not installed; the line above stays available." ;;
    esac
  fi
fi
