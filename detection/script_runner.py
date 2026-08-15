#!/usr/bin/env python3
"""
Script Runner for AI Parking System
This module runs the appropriate script based on OCR method selection
"""

import subprocess
import sys
import os
import logging
import threading
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

def run_easyocr_script():
    """Run the livedetect.py script (EasyOCR)"""
    try:
        logging.info("Starting EasyOCR script (livedetect.py)...")
        
        # Run the livedetect.py script
        result = subprocess.run([sys.executable, 'livedetect.py'], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logging.info("EasyOCR script completed successfully")
        else:
            logging.error(f"EasyOCR script failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logging.info("EasyOCR script stopped (timeout)")
    except Exception as e:
        logging.error(f"Error running EasyOCR script: {e}")

def run_openai_script():
    """Run the openai_smart.py script (OpenAI)"""
    try:
        logging.info("Starting OpenAI script (openai_smart.py)...")
        
        # Run the openai_smart.py script
        result = subprocess.run([sys.executable, 'openai_smart.py'], 
                              capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logging.info("OpenAI script completed successfully")
        else:
            logging.error(f"OpenAI script failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logging.info("OpenAI script stopped (timeout)")
    except Exception as e:
        logging.error(f"Error running OpenAI script: {e}")

def run_script_with_method(ocr_method):
    """Run the appropriate script based on OCR method"""
    if ocr_method.lower() == "easyocr":
        run_easyocr_script()
    elif ocr_method.lower() == "openai":
        run_openai_script()
    else:
        logging.error(f"Unknown OCR method: {ocr_method}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script_runner.py [easyocr|openai]")
        sys.exit(1)
    
    method = sys.argv[1]
    run_script_with_method(method) 