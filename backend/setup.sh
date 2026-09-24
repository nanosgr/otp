#!/bin/bash

echo "Configurando el backend de online-otp..."

# Crear entorno virtual
echo "Creando entorno virtual..."
python3 -m venv venv

# Activar entorno virtual
echo "Activando entorno virtual..."
source venv/bin/activate

# Instalar dependencias
echo "Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

# Crear la base de datos PostgreSQL (asumiendo que PostgreSQL está instalado)
echo "Configurando base de datos..."
echo "Por favor, asegúrate de que PostgreSQL esté ejecutándose y crea la base de datos 'otp_db'"
echo "Puedes usar: createdb otp_db"

# Inicializar la base de datos
echo "Inicializando base de datos..."
alembic upgrade head
python -c "from app.db.init_db import init_db; init_db()"

# Hacer el script ejecutable
chmod +x run_dev.sh

echo "Configuración completa!"
echo "Para ejecutar el servidor: ./run_dev.sh"
echo "O manualmente: uvicorn app.main:app --reload"
