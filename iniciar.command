#!/bin/bash
# Doble clic para arrancar el programa en macOS/Linux (o "bash iniciar.command"
# desde la Terminal). Crea su propio entorno aislado la primera vez, así no
# pelea con los permisos del Python del sistema.
cd "$(dirname "$0")"

if [ ! -d "venv" ]; then
    echo "Primera vez: creando entorno aislado (venv)..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
python3 app.py
