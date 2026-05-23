@echo off
title MicroAgent
cd /d "%~dp0"

:: Install dependencies if missing
pip show rich >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing dependencies...
    pip install requests rich
    echo.
)

python agent.py
pause
