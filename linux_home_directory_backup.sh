#!/bin/bash
# Backup script for the home directory
TIMESTAMP=$(date '+%Y-%m-%d_%H:%M')
DEST_DIR="$HOME/backups"
SOURCE_DIR="$HOME"
# Create the final backup directory if it doesn't exist
mkdir -p "$DEST_DIR"
# Create a backup directly in the final
tar -czvf "$SOURCE_DIR/home_backup_$TIMESTAMP.tar.gz" -C "$DEST_DIR" .
echo -e "\nBackup of $SOURCE_DIR completed at $DEST_DIR/home_backup_$TIMESTAMP.tar.gz\n"
