@echo off
title Market Maker - Starting Services
color 0A

echo ========================================
echo   Solana Market Maker
echo   Starting All Services...
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    pause
    exit /b 1
)

REM Check if Node is available
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed or not in PATH!
    pause
    exit /b 1
)

REM Change to script directory
cd /d "%~dp0"

echo [1/2] Starting Backend Server...
start "Market Maker Backend" cmd /k "python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"

echo [2/2] Starting Frontend Server...
timeout /t 3 /nobreak >nul
start "Market Maker Frontend" cmd /k "npm run dev"

echo.
echo ========================================
echo   Services Started!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Both windows will stay open.
echo Close them to stop the services.
echo.
echo Opening browser in 5 seconds...
timeout /t 5 /nobreak >nul
start http://localhost:3000

echo.
echo Browser opened! You can close this window.
timeout /t 3 >nul
