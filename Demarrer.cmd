@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installer.ps1"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" app.py %*
if errorlevel 1 (
    echo.
    echo Le demarrage a echoue. Essayez Demarrer-Navigateur.cmd ou consultez logs\musicar.log.
    pause
)

