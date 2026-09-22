#!/bin/bash
# Nightly backup of the production Postgres database.
# Dumps locally, uploads to DigitalOcean Spaces, and prunes old copies in
# both places (local kept 14 days, remote kept 90 days — remote is the
# real safety net so it gets a longer retention window).
#
# Run via cron:
#   0 3 * * * /var/www/propos-api/scripts/backup_db.sh >> /var/log/propos/backup_db.log 2>&1

set -euo pipefail

BACKUP_DIR="/var/backups/propos"
REMOTE="spaces:propos-backups"
LOCAL_RETENTION_DAYS=14
REMOTE_RETENTION_DAYS=90
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
FILENAME="propos-${TIMESTAMP}.dump"

# Pull DATABASE_URL out of the app's .env without sourcing the whole file
DATABASE_URL=$(grep '^DATABASE_URL=' /var/www/propos-api/.env | cut -d '=' -f2-)

if [ -z "$DATABASE_URL" ]; then
  echo "$(date -Iseconds) ERROR: DATABASE_URL not found in .env, aborting backup"
  exit 1
fi

echo "$(date -Iseconds) Starting backup: ${FILENAME}"

pg_dump --format=custom --file="${BACKUP_DIR}/${FILENAME}" "$DATABASE_URL"

echo "$(date -Iseconds) Local dump complete ($(du -h "${BACKUP_DIR}/${FILENAME}" | cut -f1))"

rclone copy "${BACKUP_DIR}/${FILENAME}" "$REMOTE" --quiet

echo "$(date -Iseconds) Uploaded to ${REMOTE}"

# Prune local backups older than LOCAL_RETENTION_DAYS
find "$BACKUP_DIR" -name 'propos-*.dump' -mtime +${LOCAL_RETENTION_DAYS} -delete

# Prune remote backups older than REMOTE_RETENTION_DAYS
rclone delete "$REMOTE" --min-age "${REMOTE_RETENTION_DAYS}d" --quiet

echo "$(date -Iseconds) Backup complete, old copies pruned"
