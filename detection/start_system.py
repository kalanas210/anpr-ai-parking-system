#!/usr/bin/env python3
"""
AI Parking System Startup Script
This script helps users start the system with proper checks and setup.
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        print(f"Current version: {sys.version}")
        return False
    print(f"✅ Python version: {sys.version.split()[0]}")
    return True

def check_dependencies():
    """Check if required packages are installed"""
    required_packages = [
        'flask', 'flask-cors', 'flask-socketio', 'pymongo',
        'opencv-python', 'numpy', 'ultralytics', 'easyocr',
        'inference-sdk', 'requests', 'python-dotenv'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"❌ {package} - Missing")
    
    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing_packages)
            print("✅ All packages installed successfully")
        except subprocess.CalledProcessError:
            print("❌ Failed to install packages. Please run: pip install -r requirements.txt")
            return False
    
    return True

def check_mongodb():
    """Check if MongoDB Atlas connection is working"""
    try:
        from pymongo import MongoClient
        mongo_uri = os.getenv('MONGO_URI', '')
        if not mongo_uri:
            print("❌ MONGO_URI is not set. Copy .env.example to .env and fill it in.")
            return False
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        print("✅ MongoDB Atlas connection successful")
        return True
    except Exception as e:
        print("❌ MongoDB Atlas connection failed")
        print(f"Error: {e}")
        print("Please check your internet connection and MongoDB Atlas credentials")
        return False

def check_video_file():
    """Check if video file exists"""
    video_files = ['new1.mp4', 'new2.mp4', 'new.mp4']
    for video_file in video_files:
        if os.path.exists(video_file):
            print(f"✅ Video file found: {video_file}")
            return True
    
    print("❌ No video file found")
    print("Please ensure one of these files exists: new1.mp4, new2.mp4, new.mp4")
    print("Or update the video_source variable in app.py to use your webcam (0)")
    return False

def check_api_keys():
    """Check if API keys are configured via environment variables (.env)"""
    if os.getenv('OPENAI_API_KEY'):
        print("✅ OpenAI API key configured")
    else:
        print("⚠️  OPENAI_API_KEY not set (see .env.example)")

    if os.getenv('ROBOFLOW_API_KEY'):
        print("✅ Roboflow API key configured")
    else:
        print("⚠️  ROBOFLOW_API_KEY not set (see .env.example)")

def start_system():
    """Start the AI parking system"""
    print("\n🚀 Starting AI Parking System...")
    
    try:
        # Start the Flask application
        subprocess.Popen([sys.executable, 'app.py'])
        
        # Wait a moment for the server to start
        time.sleep(3)
        
        # Check if server is running
        try:
            response = requests.get('http://localhost:5000/api/parking-status', timeout=5)
            if response.status_code == 200:
                print("✅ Server started successfully!")
                print("\n🌐 Access the admin panel at: http://localhost:5000")
                print("📖 Check the README.md for usage instructions")
                return True
        except requests.RequestException:
            print("⚠️  Server may still be starting up...")
            print("🌐 Try accessing: http://localhost:5000")
            return True
            
    except Exception as e:
        print(f"❌ Failed to start system: {e}")
        return False

def main():
    """Main startup function"""
    print("=" * 50)
    print("🤖 AI Parking System Startup")
    print("=" * 50)
    
    # Run checks
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("MongoDB", check_mongodb),
        ("Video File", check_video_file),
        ("API Keys", check_api_keys),
    ]
    
    failed_checks = []
    for check_name, check_func in checks:
        print(f"\n🔍 Checking {check_name}...")
        if not check_func():
            failed_checks.append(check_name)
    
    if failed_checks:
        print(f"\n❌ Failed checks: {', '.join(failed_checks)}")
        print("Please fix the issues above before starting the system.")
        return False
    
    print("\n✅ All checks passed!")
    
    # Ask user if they want to start the system
    response = input("\n🚀 Start the AI Parking System? (y/n): ").lower().strip()
    if response in ['y', 'yes']:
        return start_system()
    else:
        print("👋 System startup cancelled")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1) 