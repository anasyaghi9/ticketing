#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_DIR="${BACKUP_DIR:-$HOME/backups/ticketing}"
C="docker compose -f docker-compose.prod.yml"

PGU=$(grep '^POSTGRES_USER=' .env.prod | cut -d= -f2-)
PGD=$(grep '^POSTGRES_DB=' .env.prod | cut -d= -f2-)

T=restore_test

LATEST=$(ls -1t "$BACKUP_DIR"/ticketing_*.dump | head -1)

Q="select count(*) from information_schema.tables where table_schema='public'"

$C exec -T db psql -U "$PGU" -d postgres \
  -c "DROP DATABASE IF EXISTS $T" \
  -c "CREATE DATABASE $T"

$C exec -T db pg_restore -U "$PGU" -d "$T" --no-owner < "$LATEST"

SRC=$($C exec -T db psql -U "$PGU" -d "$PGD" -tA -c "$Q")

DST=$($C exec -T db psql -U "$PGU" -d "$T" -tA -c "$Q")

$C exec -T db psql -U "$PGU" -d postgres -c "DROP DATABASE $T"

[ "$SRC" = "$DST" ] && [ "$DST" -gt 0 ] && \
  echo "RESTORE OK: $DST tables from $LATEST" || \
  { echo "RESTORE FAILED: src=$SRC restored=$DST"; exit 1; }
