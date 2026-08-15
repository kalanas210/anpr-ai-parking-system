@echo off
echo ================================================
echo    Restarting Booking System Server
echo ================================================
echo.

echo Stopping any existing Node server processes...
taskkill /f /im node.exe >nul 2>&1

echo.
echo Starting Booking System Server on port 5001...
echo.

REM This script lives in booking-system/ ; move into the server folder
cd /d "%~dp0\server"

REM Set the PORT environment variable explicitly
set PORT=5001

REM Start the server (reads other secrets from server/.env)
npm run dev

pause
