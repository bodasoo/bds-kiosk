@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul
title BDS Mobile Pickup Demo
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -c "import customtkinter, fastapi, uvicorn, requests, cryptography, pydantic, pywebpush" >nul 2>&1
if errorlevel 1 (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app.py --mode mobile-demo
if errorlevel 1 goto failed
exit /b 0
:failed
echo Failed to start. Check the error above.
pause
exit /b 1
