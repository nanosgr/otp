#!/usr/bin/env bash
# Muestra los logs del contenedor de PostgreSQL
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

docker compose logs -f postgres
