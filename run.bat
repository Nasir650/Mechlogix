@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
  )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
  echo Failed to activate virtual environment.
  pause
  exit /b 1
)

echo Installing requirements...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies.
  pause
  exit /b 1
)

echo Starting Mechlogix on http://127.0.0.1:5000
python app.py

if errorlevel 1 (
  echo App exited with an error.
)

pause
