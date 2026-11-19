@echo off
REM Doble clic para arrancar el programa en Windows. Crea su propio
REM entorno aislado la primera vez (venv), asi no pelea con permisos
REM del Python del sistema.
cd /d "%~dp0"

if not exist venv (
    echo Primera vez: creando entorno aislado ^(venv^)...
    python -m venv venv
)

call venv\Scripts\activate.bat
pip install -q --upgrade pip
pip install -q -r requirements.txt
python app.py
pause
