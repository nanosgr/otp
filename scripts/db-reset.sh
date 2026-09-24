#!/usr/bin/env bash
# Elimina y recrea los contenedores y volúmenes de base de datos (DESTRUCTIVO)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "ADVERTENCIA: Esto eliminará todos los datos de la base de datos."
read -rp "¿Continuar? (s/N): " confirm
[[ "$confirm" =~ ^[sS]$ ]] || { echo "Cancelado."; exit 0; }

echo "Eliminando contenedores y volúmenes..."
docker compose down -v --remove-orphans

echo "Reiniciando desde cero..."
bash "$SCRIPT_DIR/db-up.sh"
