@echo off
REM Enciende la tienda en esta computadora (doble clic).
REM La configuracion (por ejemplo DATABASE_URL de PostgreSQL) se lee del archivo .env
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo No se encontro el entorno virtual .venv
  echo Crealo primero: py -m venv .venv  y luego  .venv\Scripts\python -m pip install -r backend\requirements-dev.txt
  pause
  exit /b 1
)
cd backend
"..\.venv\Scripts\python.exe" manage.py migrate
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5000"
"..\.venv\Scripts\python.exe" manage.py run
pause
