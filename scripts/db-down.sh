#!/usr/bin/env bash
# Detiene el contenedor de PostgreSQL
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Deteniendo PostgreSQL..."
docker compose stop postgres
echo "Contenedor detenido."
