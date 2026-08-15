@echo off
echo ================================================
echo    ANPR AI Parking System - Windows Startup (RTSP/live)
echo ================================================
echo.

REM Move to the detection/ directory (this script lives in detection/scripts/)
cd /d "%~dp0\.."

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Ensure a .env file exists (secrets are loaded from it)
if not exist ".env" (
    echo WARNING: No .env file found in the detection/ folder.
    echo Copy .env.example to .env and fill in your credentials first.
    echo.
    set /p start_anyway="Continue anyway? (y/n): "
    if /i not "%start_anyway%"=="y" (
        pause
        exit /b 1
    )
)

REM Install requirements if needed
echo Installing/checking Python dependencies...
pip install -r requirements.txt

echo.
echo Starting the ANPR AI Parking System...
echo The dashboard will be available at: http://localhost:5000
echo Press Ctrl+C to stop the system
echo.

python app.py

pause
