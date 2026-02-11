@echo off
echo Starting Solana Market Maker...
echo.

echo Starting Backend Server...
start "Market Maker Backend" cmd /k "python -m uvicorn backend.main:app --reload --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Frontend Server...
start "Market Maker Frontend" cmd /k "npm run dev"

echo.
echo Both servers are starting...
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
pause
