#!/usr/bin/env bash
# Abre una sesión psql dentro del contenedor de PostgreSQL
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "Conectando a PostgreSQL (otp_db)..."
docker compose exec postgres psql -U otp_user -d otp_db
