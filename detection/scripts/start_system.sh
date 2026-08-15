#!/bin/bash

echo "================================================"
echo "   ANPR AI Parking System - Linux/macOS Startup (RTSP/live)"
echo "================================================"
echo

# Move to the detection/ directory (this script lives in detection/scripts/)
cd "$(dirname "$0")/.." || exit 1

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed or not in PATH"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Check Python version
python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
required_version="3.8"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "ERROR: Python 3.8 or higher is required"
    echo "Current version: $python_version"
    exit 1
fi
echo "✅ Python version: $python_version"

# Ensure a .env file exists (secrets are loaded from it)
if [ ! -f ".env" ]; then
    echo "WARNING: No .env file found in the detection/ folder."
    echo "Copy .env.example to .env and fill in your credentials first."
    echo
    read -p "Continue anyway? (y/n): " start_anyway
    if [[ ! $start_anyway =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install requirements if needed
echo "Installing/checking Python dependencies..."
pip3 install -r requirements.txt

echo
echo "Starting the ANPR AI Parking System..."
echo "The dashboard will be available at: http://localhost:5000"
echo "Press Ctrl+C to stop the system"
echo

python3 app.py
