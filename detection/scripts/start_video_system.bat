@echo off
echo ============================================================
echo ANPR AI Parking System - Video / Demo Mode
echo ============================================================
echo Starting video-based parking detection system...
echo.

REM Move to the detection/ directory (this script lives in detection/scripts/)
cd /d "%~dp0\.."

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python and try again
    pause
    exit /b 1
)

REM Ensure a .env file exists (secrets are loaded from it)
if not exist ".env" (
    echo WARNING: No .env file found. Copy .env.example to .env first.
)

echo.
echo NOTE: Set VIDEO_SOURCE in your .env / config_video.py to a local video file.
echo The YOLOv8 model (yolov8n.pt) downloads automatically on first run.
echo The dashboard will be available at: http://localhost:5000
echo Press Ctrl+C to stop the system
echo.

python app_video.py

echo.
echo System stopped.
pause
