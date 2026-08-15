#!/usr/bin/env python3
"""
Smart Parking System - Connection Diagnostic Tool
Quickly identify and troubleshoot connection issues
"""

import requests
import socket
import subprocess
import time
import sys
import os
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

# Camera connection details come from the environment (see .env.example)
RTSP_URL = os.getenv("RTSP_URL", "")
CAMERA_HOST = urlparse(RTSP_URL).hostname if RTSP_URL else ""

def print_header():
    print("=" * 60)
    print("🔧 Smart Parking System - Connection Diagnostic")
    print("=" * 60)

def test_ping(host):
    """Test if a host is reachable via ping"""
    try:
        if os.name == 'nt':  # Windows
            result = subprocess.run(['ping', '-n', '1', host], 
                                  capture_output=True, text=True, timeout=10)
        else:  # Linux/Mac
            result = subprocess.run(['ping', '-c', '1', host], 
                                  capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except:
        return False

def test_http_connection(url, timeout=5):
    """Test HTTP connection to a URL"""
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code, response.text[:100]
    except requests.exceptions.ConnectionError:
        return None, "Connection Error"
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)

def test_rtsp_connection(rtsp_url):
    """Test RTSP connection"""
    try:
        import cv2
        cap = cv2.VideoCapture(rtsp_url)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            return ret
        else:
            return False
    except Exception as e:
        return False

def check_ports():
    """Check if required ports are in use"""
    ports = [5000, 5001, 80]
    results = {}
    
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            results[port] = result == 0
        except:
            results[port] = False
    
    return results

def main():
    print_header()
    
    print("\n🔍 Testing Network Connectivity...")
    print("-" * 40)
    
    # Test P10 Display
    print("1. Testing P10 LED Display (ESP32)...")
    p10_ping = test_ping("192.168.8.130")
    p10_http = test_http_connection("http://192.168.8.130/setText")
    
    if p10_ping:
        print("   ✅ ESP32 is reachable via ping")
    else:
        print("   ❌ ESP32 is not reachable via ping")
    
    if p10_http[0] == 200:
        print("   ✅ P10 Display HTTP connection successful")
    else:
        print(f"   ❌ P10 Display HTTP failed: {p10_http[1]}")
    
    # Test Camera
    print("\n2. Testing Camera Connection...")
    camera_ping = test_ping(CAMERA_HOST) if CAMERA_HOST else False
    
    if camera_ping:
        print("   ✅ Camera is reachable via ping")
    else:
        print("   ❌ Camera is not reachable via ping")
    
    # Test RTSP
    rtsp_url = RTSP_URL
    rtsp_test = test_rtsp_connection(rtsp_url) if rtsp_url else False
    
    if rtsp_test:
        print("   ✅ RTSP stream is accessible")
    else:
        print("   ❌ RTSP stream is not accessible")
    
    # Test Booking System
    print("\n3. Testing Booking System...")
    booking_health = test_http_connection("http://localhost:5000/api/health")
    
    if booking_health[0] == 200:
        print("   ✅ Booking system is running")
    else:
        print(f"   ❌ Booking system is not responding: {booking_health[1]}")
    
    # Test OpenAI API
    print("\n4. Testing OpenAI API...")
    openai_test = test_http_connection("https://api.openai.com", timeout=10)
    
    if openai_test[0] == 200:
        print("   ✅ OpenAI API is accessible")
    else:
        print(f"   ❌ OpenAI API is not accessible: {openai_test[1]}")
    
    # Check Ports
    print("\n5. Checking Port Usage...")
    port_status = check_ports()
    
    for port, in_use in port_status.items():
        if in_use:
            print(f"   ✅ Port {port} is in use")
        else:
            print(f"   ❌ Port {port} is not in use")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    issues = []
    
    if not p10_ping:
        issues.append("ESP32 (P10 Display) not reachable")
    if not p10_http[0] == 200:
        issues.append("P10 Display HTTP connection failed")
    if not camera_ping:
        issues.append("Camera not reachable")
    if not rtsp_test:
        issues.append("RTSP stream not accessible")
    if not booking_health[0] == 200:
        issues.append("Booking system not running")
    if not openai_test[0] == 200:
        issues.append("OpenAI API not accessible")
    if not port_status[5000]:
        issues.append("Port 5000 not in use (booking system)")
    
    if not issues:
        print("✅ All connections are working properly!")
        print("🎉 Your Smart Parking System is ready for presentation!")
    else:
        print("❌ Found the following issues:")
        for i, issue in enumerate(issues, 1):
            print(f"   {i}. {issue}")
        
        print("\n🔧 Quick Fix Suggestions:")
        if "ESP32" in str(issues):
            print("   • Check ESP32 power and WiFi connection")
            print("   • Verify IP address: 192.168.8.130")
        if "Camera" in str(issues):
            print("   • Check camera power and network connection")
            print("   • Verify RTSP credentials")
        if "Booking system" in str(issues):
            print("   • Start booking system: cd booking-system/server && npm start")
        if "OpenAI" in str(issues):
            print("   • Check internet connection")
            print("   • Verify OpenAI API key")
    
    print("\n" + "=" * 60)
    print("For detailed troubleshooting, see: CONNECTION_TROUBLESHOOTING.md")
    print("=" * 60)

if __name__ == "__main__":
    main()

