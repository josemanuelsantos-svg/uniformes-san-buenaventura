#!/usr/bin/env bash
# Script de inicio para la aplicación de uniformes Colegio San Buenaventura

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual e instalando dependencias..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install flask
fi

echo "Iniciando servidor de Uniformes San Buenaventura en http://localhost:5050 ..."
./venv/bin/python3 app.py
