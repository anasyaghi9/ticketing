#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/ticketing}"
KEEP_DAYS="${KEEP_DAYS:-14}"
C="docker compose -f docker-compose.prod.yml"

PGU=$(grep '^POSTGRES_USER=' .env.prod | cut -d= -f2-)
PGD=$(grep '^POSTGRES_DB=' .env.prod | cut -d= -f2-)

mkdir -p "$BACKUP_DIR"

F="$BACKUP_DIR/ticketing_$(date +%Y%m%d_%H%M%S).dump"

$C exec -T db pg_dump -U "$PGU" -d "$PGD" -Fc > "$F.tmp"

$C exec -T db pg_restore --list < "$F.tmp" > /dev/null

mv "$F.tmp" "$F"

find "$BACKUP_DIR" -name 'ticketing_*.dump' -mtime +"$KEEP_DAYS" -delete

echo "OK $F ($(du -h "$F" | cut -f1))"
