#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: SYNTHETIC_PASSWORD=<min-12-chars> bash demo-reset.sh --purge"
  echo "  --purge  Delete the Compose PostgreSQL volume, migrate, import 45 question forms, and seed 30 synthetic candidates + 5 employers/needs."
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
password="${SYNTHETIC_PASSWORD:-}"
if [[ "$purge" != true || ${#password} -lt 12 ]]; then
  usage >&2
  exit 2
fi

"${compose[@]}" down -v

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
"${compose[@]}" run --rm -e SYNTHETIC_PASSWORD -e CONFIRM_SYNTHETIC_RESET=RESET_FSP_DEMO_ONLY api python -m app.commands.populate_taxonomy_demo_db
"${compose[@]}" up -d api web mailpit
