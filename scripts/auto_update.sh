#!/usr/bin/env sh
set -eu

REPO_DIR="${HOST_PROJECT_PATH:-$(pwd)}"
REMOTE="${UPDATE_REMOTE:-origin}"
BRANCH="${UPDATE_BRANCH:-main}"
LOG_FILE="${AUTO_UPDATE_LOG_FILE:-$REPO_DIR/data/auto_update.log}"

mkdir -p "$(dirname "$LOG_FILE")"
{
  echo "[$(date '+%F %T')] [AUTO_UPDATE] start repo=$REPO_DIR remote=$REMOTE branch=$BRANCH"
  cd "$REPO_DIR"
  git config --global --add safe.directory "$REPO_DIR" >/dev/null 2>&1 || true
  git fetch "$REMOTE" --tags --prune
  git pull --ff-only "$REMOTE" "$BRANCH"
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose up -d --build
  elif docker compose version >/dev/null 2>&1; then
    docker compose up -d --build
  else
    echo "[$(date '+%F %T')] [AUTO_UPDATE] docker compose not found"
    exit 1
  fi
  echo "[$(date '+%F %T')] [AUTO_UPDATE] done"
} >> "$LOG_FILE" 2>&1
