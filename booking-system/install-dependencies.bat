@echo off
echo ================================================
echo    Booking System - Install Dependencies
echo ================================================
echo.

echo Installing server dependencies...
cd server
npm install
if errorlevel 1 (
    echo ❌ Failed to install server dependencies
    pause
    exit /b 1
)
echo ✅ Server dependencies installed successfully

echo.
echo Installing client dependencies...
cd ..\client
npm install
if errorlevel 1 (
    echo ❌ Failed to install client dependencies
    pause
    exit /b 1
)
echo ✅ Client dependencies installed successfully

echo.
echo ================================================
echo    All dependencies installed successfully!
echo ================================================
echo.
echo You can now start the systems:
echo - Server: npm run dev (in server directory)
echo - Client: npm start (in client directory)
echo - Or use: start_both_systems.bat
echo.
pause 