#!/usr/bin/env bash
# Ejecuta el servidor de desarrollo (se puede ejecutar desde cualquier directorio)
set -e

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo "Error: entorno virtual no encontrado. Ejecuta primero: ./backend/setup.sh"
    exit 1
fi
source venv/bin/activate

echo "Iniciando servidor en http://localhost:8000"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
