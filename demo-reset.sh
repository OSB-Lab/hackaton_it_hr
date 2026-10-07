#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: bash demo-reset.sh [--purge]"
  echo "  --purge  Stop all services and delete Compose volumes before reset."
}

purge=false
case "${1:-}" in
  "") ;;
  --purge) purge=true ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if (( $# > 1 )); then
  usage >&2
  exit 2
fi

cd "$(dirname "${BASH_SOURCE[0]}")"
compose=(docker compose -f infra/docker-compose.yml)

if [[ "$purge" == true ]]; then
  "${compose[@]}" down -v
fi

"${compose[@]}" up -d postgres

# Poll the existing pg_isready healthcheck, with a bounded wait.
healthy=false
for (( attempt=0; attempt<60; attempt++ )); do
  container_id=$("${compose[@]}" ps -q postgres)
  if [[ -z "$container_id" ]]; then
    echo "PostgreSQL container is not running." >&2
    exit 1
  fi
  status=$(docker inspect --format '{{.State.Health.Status}}' "$container_id")
  if [[ "$status" == healthy ]]; then
    healthy=true
    break
  fi
  sleep 1
done

if [[ "$healthy" != true ]]; then
  echo "PostgreSQL did not become healthy within 60 seconds." >&2
  "${compose[@]}" logs postgres >&2
  exit 1
fi

"${compose[@]}" run --build --rm api alembic upgrade head
"${compose[@]}" run --rm api python -m app.commands.seed_demo
