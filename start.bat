@echo off
setlocal
cd /d "%~dp0"
set "PYTHONIOENCODING=utf-8"
chcp 65001 >nul
title BDS Kiosk

echo.
echo [1] PC 전용
echo [2] 아이폰 시연 - PC 키오스크와 주방 포함
echo [3] 종료
choice /c 123 /n /m "실행 모드를 선택하세요 [1/2/3]: "
if errorlevel 3 exit /b 0
if errorlevel 2 (
    set "BDS_LAUNCH_MODE=mobile-demo"
) else (
    set "BDS_LAUNCH_MODE=launcher"
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -c "import customtkinter, fastapi, uvicorn, requests, cryptography, pydantic, pywebpush" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" app.py --mode %BDS_LAUNCH_MODE%
if errorlevel 1 goto failed
endlocal
exit /b 0

:failed
echo.
echo Failed to start. Check the error above.
pause
exit /b 1
