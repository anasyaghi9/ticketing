#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
C="docker compose -f docker-compose.prod.yml"
BRANCH="${BRANCH:-main}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health/}"

[ -f .env.prod ] || { echo "ERROR: .env.prod missing"; exit 1; }
[ -z "$(git status --porcelain --untracked-files=no)" ] || { echo "ERROR: local changes on server, refusing to deploy"; exit 1; }

PREV=$(git rev-parse HEAD)
echo "==> Current: $PREV"

echo "==> Backup before deploy"
./scripts/backup.sh

echo "==> Pull $BRANCH"
git fetch origin "$BRANCH"
git merge --ff-only "origin/$BRANCH"
NEW=$(git rev-parse HEAD)
[ "$NEW" = "$PREV" ] && echo "==> Already up to date, redeploying anyway"

rollback() {
  echo "!!! Deploy failed, rolling back to $PREV"
  $C logs --tail=40 web || true
  git reset --hard "$PREV"
  $C up -d --build --wait --wait-timeout 300 || echo "!!! Rollback stack is also unhealthy, check manually"
  exit 1
}

echo "==> Build and start"
$C up -d --build --wait --wait-timeout 300 || rollback

echo "==> Health check"
for i in $(seq 1 15); do
  if curl -fsS "$HEALTH_URL" > /dev/null; then OK=1; break; fi
  sleep 3
done
[ "${OK:-0}" = "1" ] || rollback

docker image prune -f > /dev/null
echo "==> Deployed $NEW"
