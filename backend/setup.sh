#!/usr/bin/env bash
# Configura el entorno de desarrollo del backend (se puede ejecutar desde cualquier directorio)
set -e

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$BACKEND_DIR")"
cd "$BACKEND_DIR"

echo "Configurando el backend de online-otp..."

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi
source venv/bin/activate

echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt -r requirements-dev.txt maturin

if [ ! -f ".env" ]; then
    echo "Creando .env a partir de .env.example (con SECRET_KEY aleatoria)..."
    SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
    sed "s|^SECRET_KEY=.*|SECRET_KEY=\"$SECRET\"|" .env.example > .env
fi

echo "Compilando e instalando el motor de fórmulas (Rust)..."
if command -v cargo > /dev/null 2>&1; then
    (cd "$PROJECT_ROOT/engine/otp-formula-py" && maturin develop --release)
else
    echo "  AVISO: cargo no está instalado; el backend arrancará sin motor de fórmulas."
fi

echo "Levantando PostgreSQL..."
"$PROJECT_ROOT/scripts/db-up.sh"

echo "Aplicando migraciones y datos semilla..."
alembic upgrade head
python -c "from app.db.init_db import init_db; init_db()"
python -m app.db.seed_reglas

chmod +x run_dev.sh

echo ""
echo "Configuración completa!"
echo "Para ejecutar el servidor: ./backend/run_dev.sh"
