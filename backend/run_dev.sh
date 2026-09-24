#!/bin/bash

# Script para ejecutar el servidor de desarrollo
echo "Iniciando servidor de desarrollo FastAPI..."

# Activar entorno virtual si existe
if [ -d "venv" ]; then
    echo "Activando entorno virtual..."
    source venv/bin/activate
fi

# Instalar dependencias si no están instaladas
echo "Verificando dependencias..."
pip install -r requirements.txt

# Ejecutar el servidor
echo "Iniciando servidor en http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
