#!/usr/bin/env python3
"""
AI Parking System - Video Mode Startup Script
This script starts the parking system configured for video file processing.
"""

import os
import sys
import subprocess
import time
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

def check_dependencies():
    """Check if all required dependencies are installed"""
    # Simplified check - just verify we can import the main modules
    try:
        import cv2
        import flask
        import pymongo
        import ultralytics
        logging.info("All dependencies are installed")
        return True
    except ImportError as e:
        logging.error(f"Missing dependency: {e}")
        logging.info("Please install missing packages using: pip install -r requirements.txt")
        return False

def check_video_files():
    """Check if video files exist"""
    video_files = ['new.mp4', 'new1.mp4', 'new2.mp4']
    available_videos = []
    
    for video_file in video_files:
        if os.path.exists(video_file):
            available_videos.append(video_file)
    
    if not available_videos:
        logging.error("No video files found. Please ensure at least one of new.mp4, new1.mp4, or new2.mp4 exists.")
        return False
    
    logging.info(f"Found video files: {', '.join(available_videos)}")
    return True

def check_ai_models():
    """Check if AI models are available"""
    if not os.path.exists('yolov8n.pt'):
        logging.error("YOLO model (yolov8n.pt) not found. Please download it.")
        return False
    
    logging.info("AI models are available")
    return True

def create_debug_directories():
    """Create necessary debug directories"""
    directories = ['debug_cars', 'debug_plates', 'error_vehicles', 'ocr_tests']
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logging.info(f"Created/verified directory: {directory}")

def start_video_system():
    """Start the video parking system"""
    try:
        logging.info("=== AI Parking System - Video Mode ===")
        logging.info("Starting video-based parking detection system...")
        
        # Check prerequisites
        if not check_dependencies():
            return False
        
        if not check_video_files():
            return False
        
        if not check_ai_models():
            return False
        
        create_debug_directories()
        
        # Start the Flask application
        logging.info("Starting Flask web server...")
        
        # Use the video-specific app
        app_script = "app_video.py"
        
        if not os.path.exists(app_script):
            logging.error(f"Video app script {app_script} not found!")
            return False
        
        # Start the Flask app directly
        try:
            logging.info("Starting Flask web server...")
            logging.info("The system will be available at: http://localhost:5000")
            logging.info("Press Ctrl+C to stop the system")
            subprocess.run([sys.executable, app_script], check=True)
        except KeyboardInterrupt:
            logging.info("System stopped by user")
        except subprocess.CalledProcessError as e:
            logging.error(f"Error running Flask app: {e}")
            return False
        
        return True
        
    except Exception as e:
        logging.error(f"Error starting video system: {e}")
        return False

def main():
    """Main function"""
    print("=" * 60)
    print("AI Parking System - Video Mode")
    print("=" * 60)
    print("This system will process video files for parking detection.")
    print("Make sure you have:")
    print("1. Video files (new.mp4, new1.mp4, or new2.mp4)")
    print("2. All dependencies installed")
    print("3. YOLO model (yolov8n.pt)")
    print("=" * 60)
    
    # Ask for confirmation
    response = input("Do you want to start the video system? (y/n): ").lower().strip()
    if response not in ['y', 'yes']:
        print("System startup cancelled.")
        return
    
    success = start_video_system()
    
    if success:
        logging.info("Video system started successfully!")
    else:
        logging.error("Failed to start video system. Please check the errors above.")

if __name__ == "__main__":
    main() 