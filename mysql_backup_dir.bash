#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/db"
REMOTE="spaces:your-bucket/db-backups"
DATE=$(date +%F)
DAY=$(date +%u)   # 1=Monday, 7=Sunday
WEEK=$(date +%V)
MONTH=$(date +%d)

# Always create daily dump
mysqldump --single-transaction --all-databases | gpg -c --batch --passphrase-file /etc/backup.key > 
"${BACKUP_DIR}/daily-${DATE}.sql.gpg"
#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/db"
REMOTE="spaces:your-bucket/db-backups"
DATE=$(date +%F)
DAY=$(date +%u)   # 1=Monday, 7=Sunday
WEEK=$(date +%V)
MONTH=$(date +%d)

# Always create daily dump
mysqldump --single-transaction --all-databases | gpg -c --batch --passphrase-file /etc/backup.key > "${BACKUP_DIR}/daily-${DATE}.sql.gpg"

# Weekly copy on Sunday
if [ "$DAY" -eq 7 ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/weekly-${WEEK}.sql.gpg"
fi#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/var/backups/db"
REMOTE="spaces:your-bucket/db-backups"
DATE=$(date +%F)
DAY=$(date +%u)   # 1=Monday, 7=Sunday
WEEK=$(date +%V)
MONTH=$(date +%d)

# Always create daily dump
mysqldump --single-transaction --all-databases | gpg -c --batch --passphrase-file /etc/backup.key > "${BACKUP_DIR}/daily-${DATE}.sql.gpg"

# Weekly copy on Sunday
if [ "$DAY" -eq 7 ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/weekly-${WEEK}.sql.gpg"
fi

# Monthly copy on the 1st
if [ "$MONTH" -eq "01" ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/monthly-$(date +%Y-%m).sql.gpg"
fi

# Prune old files
find "${BACKUP_DIR}" -name "daily-*.sql.gpg"   | sort | head -n -7  | xargs -r rm
find "${BACKUP_DIR}" -name "weekly-*.sql.gpg"  | sort | head -n -4  | xargs -r rm
find "${BACKUP_DIR}" -name "monthly-*.sql.gpg" | sort | head -n -3  | xargs -r rm

# Sync to remote
rclone sync "${BACKUP_DIR}/" "${REMOTE}/"

# Monthly copy on the 1st
if [ "$MONTH" -eq "01" ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/monthly-$(date +%Y-%m).sql.gpg"
fi

# Prune old files
find "${BACKUP_DIR}" -name "daily-*.sql.gpg"   | sort | head -n -7  | xargs -r rm
find "${BACKUP_DIR}" -name "weekly-*.sql.gpg"  | sort | head -n -4  | xargs -r rm
find "${BACKUP_DIR}" -name "monthly-*.sql.gpg" | sort | head -n -3  | xargs -r rm

# Sync to remote
rclone sync "${BACKUP_DIR}/" "${REMOTE}/"
# Weekly copy on Sunday
if [ "$DAY" -eq 7 ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/weekly-${WEEK}.sql.gpg"
fi

# Monthly copy on the 1st
if [ "$MONTH" -eq "01" ]; then
  cp "${BACKUP_DIR}/daily-${DATE}.sql.gpg" "${BACKUP_DIR}/monthly-$(date +%Y-%m).sql.gpg"
fi

# Prune old files
find "${BACKUP_DIR}" -name "daily-*.sql.gpg"   | sort | head -n -7  | xargs -r rm
find "${BACKUP_DIR}" -name "weekly-*.sql.gpg"  | sort | head -n -4  | xargs -r rm
find "${BACKUP_DIR}" -name "monthly-*.sql.gpg" | sort | head -n -3  | xargs -r rm

# Sync to remote
rclone sync "${BACKUP_DIR}/" "${REMOTE}/"
