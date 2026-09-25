#!/usr/bin/env bash
# Aplica las migraciones de Alembic y carga los datos semilla
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"

cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo "Error: entorno virtual no encontrado. Ejecuta primero:"
    echo "  ./backend/setup.sh"
    exit 1
fi

source venv/bin/activate

echo "Aplicando migraciones Alembic..."
alembic upgrade head

echo ""
echo "Cargando datos semilla..."
python -c "from app.db.init_db import init_db; init_db()"

echo ""
echo "Usuarios disponibles:"
echo "  superadmin / admin123   (Super Admin)"
echo "  admin      / admin123   (Admin)"
echo "  manager    / manager123 (Manager)"
echo "  user       / user123    (User)"
