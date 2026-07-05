#!/usr/bin/env bash
# deploy-measureos — 本番デプロイ（GitHub から pull のみ。コードの直接編集は禁止）
#
# インストール例:
#   sudo install -m 755 /var/www/measureos-site/scripts/deploy-measureos.sh /usr/local/bin/deploy-measureos
#
# 環境変数（任意）:
#   MEASUREOS_APP_DIR   既定: /var/www/measureos-site
#   MEASUREOS_BRANCH    既定: milestone/package-a-phase1
#   MEASUREOS_SERVICE   既定: measureos.service

set -euo pipefail

APP_DIR="${MEASUREOS_APP_DIR:-/var/www/measureos-site}"
BRANCH="${MEASUREOS_BRANCH:-milestone/package-a-phase1}"
SERVICE="${MEASUREOS_SERVICE:-measureos.service}"

log() {
  printf '[deploy-measureos] %s\n' "$*"
}

fail() {
  log "ERROR: $*"
  exit 1
}

restart_service() {
  log "restart ${SERVICE}"
  systemctl restart "${SERVICE}"
  systemctl status "${SERVICE}" --no-pager -l || true
}

cd "${APP_DIR}" || fail "app dir not found: ${APP_DIR}"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "not a git repository: ${APP_DIR}"
fi

current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "${current_branch}" != "${BRANCH}" ]]; then
  fail "expected branch ${BRANCH} but on ${current_branch}"
fi

if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  log "tracked files with local changes:"
  git status --short --untracked-files=no || true
  fail "local changes detected. Do not edit code on the server. Fix via GitHub, then redeploy."
fi

log "git fetch origin ${BRANCH}"
git fetch origin "${BRANCH}"

log "git pull --ff-only origin ${BRANCH}"
if ! git pull --ff-only origin "${BRANCH}"; then
  fail "git pull failed. ${SERVICE} was NOT restarted."
fi

restart_service
log "deploy complete"
