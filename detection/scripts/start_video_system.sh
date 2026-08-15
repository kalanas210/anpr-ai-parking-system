#!/bin/bash

echo "============================================================"
echo "ANPR AI Parking System - Video / Demo Mode"
echo "============================================================"
echo "Starting video-based parking detection system..."
echo

# Move to the detection/ directory (this script lives in detection/scripts/)
cd "$(dirname "$0")/.." || exit 1

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 is not installed or not in PATH"
    echo "Please install Python3 and try again"
    exit 1
fi

# Ensure a .env file exists (secrets are loaded from it)
if [ ! -f ".env" ]; then
    echo "WARNING: No .env file found. Copy .env.example to .env first."
fi

echo
echo "NOTE: Set VIDEO_SOURCE in your .env / config_video.py to a local video file."
echo "The YOLOv8 model (yolov8n.pt) downloads automatically on first run."
echo "The dashboard will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop the system"
echo

python3 app_video.py

echo
echo "System stopped."
