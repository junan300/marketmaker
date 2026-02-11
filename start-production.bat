@echo off
echo ========================================
echo  Market Maker - Production Startup
echo ========================================
echo.

REM Check if PM2 is installed
where pm2 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo PM2 is not installed. Installing...
    npm install -g pm2
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install PM2. Please install manually: npm install -g pm2
        pause
        exit /b 1
    )
)

REM Create logs directory
if not exist logs mkdir logs

REM Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH!
    pause
    exit /b 1
)

REM Check if Node is available
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Node.js is not installed or not in PATH!
    pause
    exit /b 1
)

echo Starting Market Maker with PM2...
echo.

REM Stop existing instances
pm2 delete all 2>nul

REM Start with PM2
pm2 start ecosystem.config.js

echo.
echo ========================================
echo  Market Maker Started!
echo ========================================
echo.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Useful commands:
echo   pm2 status          - Check status
echo   pm2 logs            - View logs
echo   pm2 monit           - Monitor resources
echo   pm2 stop all        - Stop all services
echo   pm2 restart all     - Restart all services
echo.
echo Services will auto-restart on failure.
echo Press any key to open PM2 monitor...
pause >nul

pm2 monit
