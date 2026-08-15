from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from pymongo import MongoClient
from datetime import datetime, timedelta
import json
import os
import logging
import threading
import time
import base64
import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
from inference_sdk import InferenceHTTPClient
import requests
import re
import subprocess
import sys
import pytz
import psutil
from dotenv import load_dotenv

# Load secrets/configuration from a local .env file (never commit it — see .env.example)
load_dotenv()

# Import P10 Display Manager
try:
    from p10_display_manager import get_p10_display
    # Try to load P10 configuration
    try:
        from config_p10 import ESP32_IP, ESP32_KEY
    except ImportError:
        # Fallback to default values
        ESP32_IP = "192.168.8.130"  # Change this to your ESP32's IP address
        ESP32_KEY = "uom"  # Change this to match your ESP32 key
    
    p10_display = get_p10_display(ESP32_IP, ESP32_KEY)
    P10_ENABLED = True
    logging.info(f"P10 Display Manager loaded successfully for ESP32 at {ESP32_IP}")
except ImportError as e:
    logging.warning(f"P10 Display Manager not available: {e}")
    p10_display = None
    P10_ENABLED = False

# Import Booking Integration
try:
    from booking_integration import get_booking_integration
    from config_booking import BOOKING_MODE, BOOKING_API_URL
    
    # Configure booking integration based on mode
    if BOOKING_MODE == "mock":
        booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=True)
        logging.info("Booking integration loaded in MOCK mode for testing")
    elif BOOKING_MODE == "real":
        booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=False)
        logging.info("Booking integration loaded in REAL mode")
    else:  # auto mode
        booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=False)
        logging.info("Booking integration loaded in AUTO mode (will fallback to mock if needed)")
    
    BOOKING_ENABLED = True
except ImportError as e:
    logging.warning(f"Booking integration not available: {e}")
    booking_integration = None
    BOOKING_ENABLED = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or os.urandom(24).hex()
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = "parking_system"
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
parking_records = db.parking_records
unknown_vehicles = db.unknown_vehicles
system_status = db.system_status

# Sri Lanka timezone
SRI_LANKA_TZ = pytz.timezone('Asia/Colombo')

def get_sri_lanka_time():
    """Get current time in Sri Lanka timezone"""
    return datetime.now(SRI_LANKA_TZ)

# AI Models Configuration
try:
    reader = easyocr.Reader(['en'], gpu=False)
    logging.info("EasyOCR initialized successfully")
except Exception as e:
    logging.error(f"Error initializing EasyOCR: {e}")
    reader = None

CAR_DETECTION_MODEL = YOLO('yolov8n.pt')
VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle']

# Roboflow config
ROBOFLOW_CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=os.getenv("ROBOFLOW_API_KEY", "")
)
LICENSE_PLATE_MODEL_ID = "license-plate-recognition-rxg4e/11"

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# Parking slots configuration - use config file
try:
    from config import PARKING_SLOTS
    logging.info("Parking slots loaded from config file")
except ImportError:
    # Fallback coordinates if config file not available
    PARKING_SLOTS = {
        '1': [(276, 118), (2, 358), (396, 436), (489, 148)],
        '2': [(545, 121), (513, 459), (957, 466), (824, 122)],
    }
    logging.warning("Using fallback parking slot coordinates")

# Global variables
current_ocr_method = "EasyOCR"  # or "OpenAI"
slot_status = {
    slot_id: {
        "occupied": False,
        "entry_time": None,
        "license_plate": None,
        "vehicle_type": None,
        "vehicle_image": None,
        "parking_duration": None,
        "last_updated": None
    } for slot_id in PARKING_SLOTS
}

# Video capture - use config file
try:
    from config import VIDEO_SOURCE
    video_source = VIDEO_SOURCE
except ImportError:
    video_source = 'new2.mp4'  # RTSP URL 
cap = None
is_detection_running = False

def clear_slot_status_on_startup():
    """Clear slot status and remove old JSON file on startup"""
    global slot_status
    
    # Reset slot status to initial state
    for slot_id in slot_status:
        slot_status[slot_id] = {
            "occupied": False,
            "entry_time": None,
            "license_plate": None,
            "vehicle_type": None,
            "vehicle_image": None,
            "parking_duration": None,
            "last_updated": None
        }
    
    # Remove old JSON file if it exists
    json_file = "slot_status.json"
    if os.path.exists(json_file):
        try:
            os.remove(json_file)
            logging.info("Removed old slot status JSON file")
        except Exception as e:
            logging.error(f"Error removing old JSON file: {e}")
    
    # Clear debug folders more aggressively
    for folder in ['debug_cars', 'debug_plates', 'error_vehicles', 'debug_frames']:
        if os.path.exists(folder):
            try:
                for file in os.listdir(folder):
                    file_path = os.path.join(folder, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logging.debug(f"Removed old file: {file}")
                logging.info(f"Cleared debug folder: {folder}")
            except Exception as e:
                logging.error(f"Error clearing debug folder {folder}: {e}")
    
    # Force immediate status save and P10 update
    try:
        serialized_status = serialize_slot_status(slot_status)
        with open("slot_status.json", "w") as f:
            json.dump(slot_status, f, indent=2, default=str)
        logging.info("Fresh slot status saved to JSON file")
    except Exception as e:
        logging.error(f"Error saving fresh slot status: {e}")

    # Initialize P10 display
    if P10_ENABLED:
        try:
            p10_display.display_system_ready()
            # Start the display cycle with current slot status
            p10_display.start_display_cycle(slot_status)
            logging.info("P10 display initialized with system ready message and display cycle started")
        except Exception as e:
            logging.error(f"Error initializing P10 display: {e}")
    
    logging.info("Slot status cleared and system initialized")

def initialize_video():
    """Initialize video capture"""
    global cap
    if cap is not None:
        cap.release()
    
    if video_source.isdigit():
        cap = cv2.VideoCapture(int(video_source))
    else:
        cap = cv2.VideoCapture(video_source)
    
    if not cap.isOpened():
        logging.error(f"Error opening video source: {video_source}")
        return False
    return True

def encode_image_to_base64(image):
    """Convert OpenCV image to base64 string"""
    try:
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer.tobytes()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image to base64: {e}")
        return ""

def read_plate_with_openai(image):
    """Performs OCR using OpenAI GPT-4o-mini"""
    try:
        base64_image = encode_image_to_base64(image)
        if not base64_image:
            return "UNREADABLE"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please read the license plate number from this image, following the Sri Lankan format (2-3 letters followed by 4 digits, e.g., 'JV 1287' or 'ABC 1234'). Return only the alphanumeric characters in the format 'JV1287' or 'ABC1234' (no spaces or dashes). If unreadable, return 'UNREADABLE'."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }

        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            plate_text = result['choices'][0]['message']['content'].strip()
            plate_text = re.sub(r'[^A-Z0-9]', '', plate_text.upper())
            
            if re.match(r'^[A-Z]{2,3}[0-9]{4}$', plate_text):
                # Format the plate with a space between letters and numbers
                letters = re.match(r'^[A-Z]{2,3}', plate_text).group()
                numbers = plate_text[len(letters):]
                formatted_plate = f"{letters} {numbers}"
                return formatted_plate
            else:
                return "UNREADABLE"
        else:
            logging.error(f"OpenAI API error: {response.status_code}")
            return "UNREADABLE"

    except Exception as e:
        logging.error(f"Error during OpenAI OCR: {e}")
        return "UNREADABLE"

def read_plate_with_easyocr(image):
    """Performs OCR using EasyOCR"""
    try:
        if reader is None:
            return "UNREADABLE"
        
        results = reader.readtext(image)
        if not results:
            return "UNREADABLE"
        
        # Process results to find the best plate match
        for (bbox, text, confidence) in results:
            if isinstance(confidence, (int, float)) and confidence > 0.3:
                cleaned_text = re.sub(r'[^A-Z0-9]', '', text.upper())
                if re.match(r'^[A-Z]{2,3}[0-9]{4}$', cleaned_text):
                    return cleaned_text
        
        return "UNREADABLE"
    except Exception as e:
        logging.error(f"Error during EasyOCR: {e}")
        return "UNREADABLE"

def detect_license_plate(image):
    """Detect license plate in image using Roboflow"""
    try:
        # Convert image to base64
        _, buffer = cv2.imencode('.jpg', image)
        image_base64 = base64.b64encode(buffer.tobytes()).decode('utf-8')
        
        # Call Roboflow API
        result = ROBOFLOW_CLIENT.infer(image_base64, model_id=LICENSE_PLATE_MODEL_ID)
        
        if result and isinstance(result, dict) and 'predictions' in result:
            predictions = result['predictions']
            if predictions and len(predictions) > 0:
                # Get the prediction with highest confidence
                best_prediction = max(predictions, key=lambda x: x.get('confidence', 0))
                
                confidence = best_prediction.get('confidence', 0)
                if isinstance(confidence, (int, float)) and confidence > 0.4:
                    # Extract coordinates
                    x = best_prediction.get('x', 0)
                    y = best_prediction.get('y', 0)
                    width = best_prediction.get('width', 0)
                    height = best_prediction.get('height', 0)
                    
                    # Convert to pixel coordinates
                    h, w = image.shape[:2]
                    x1 = int((x - width/2) * w)
                    y1 = int((y - height/2) * h)
                    x2 = int((x + width/2) * w)
                    y2 = int((y + height/2) * h)
                    
                    # Ensure coordinates are within image bounds
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(w, x2)
                    y2 = min(h, y2)
                    
                    if x2 > x1 and y2 > y1:
                        plate_crop = image[y1:y2, x1:x2]
                        return plate_crop
        
        return None
    except Exception as e:
        logging.error(f"Error in license plate detection: {e}")
        return None

def serialize_slot_status(status_dict):
    """Convert slot status to JSON-serializable format"""
    serialized = {}
    for slot_id, status in status_dict.items():
        serialized[slot_id] = {
            "occupied": status["occupied"],
            "entry_time": status["entry_time"].isoformat() if status["entry_time"] else None,
            "license_plate": status["license_plate"],
            "vehicle_type": status.get("vehicle_type", "Unknown"),
            "vehicle_image": status["vehicle_image"],
            "parking_duration": str(status["parking_duration"]) if status["parking_duration"] else None,
            "last_updated": status["last_updated"].isoformat() if status["last_updated"] else None
        }
    return serialized

def log_system_resources():
    """Log current system resource usage"""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        logging.info(f"📊 System Resources - CPU: {cpu_percent}%, Memory: {memory.percent}%, Disk: {disk.percent}%")
        logging.info(f"   Memory: {memory.used / 1024**3:.1f}GB / {memory.total / 1024**3:.1f}GB")
        logging.info(f"   Disk: {disk.used / 1024**3:.1f}GB / {disk.total / 1024**3:.1f}GB")
        
        # Log active threads
        active_threads = threading.active_count()
        logging.info(f"   Active threads: {active_threads}")
        
    except Exception as e:
        logging.error(f"Error logging system resources: {e}")

def cleanup_old_debug_files():
    """Clean up old debug files to prevent accumulation"""
    try:
        import glob
        from datetime import datetime, timedelta
        
        # Clean files older than 30 minutes
        cutoff_time = datetime.now() - timedelta(minutes=30)
        
        for folder in ['debug_frames', 'debug_plates', 'debug_cars', 'error_vehicles']:
            if os.path.exists(folder):
                for file_path in glob.glob(os.path.join(folder, '*')):
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_time < cutoff_time:
                            os.remove(file_path)
                            logging.debug(f"Cleaned up old debug file: {file_path}")
                    except Exception as e:
                        logging.warning(f"Error cleaning file {file_path}: {e}")
                        
    except Exception as e:
        logging.error(f"Debug file cleanup error: {e}")

def cleanup_old_vehicle_images(slot_id: str):
    """Clean up old vehicle images for a specific slot"""
    try:
        # Clean debug_cars folder
        debug_cars_dir = "debug_cars"
        if os.path.exists(debug_cars_dir):
            for file in os.listdir(debug_cars_dir):
                if file.startswith(f"slot_{slot_id}_"):
                    file_path = os.path.join(debug_cars_dir, file)
                    try:
                        os.remove(file_path)
                        logging.info(f"Cleaned up old vehicle image: {file}")
                    except Exception as e:
                        logging.warning(f"Could not remove {file}: {e}")
        
        # Clean debug_plates folder
        debug_plates_dir = "debug_plates"
        if os.path.exists(debug_plates_dir):
            for file in os.listdir(debug_plates_dir):
                if file.startswith(f"slot_{slot_id}_"):
                    file_path = os.path.join(debug_plates_dir, file)
                    try:
                        os.remove(file_path)
                        logging.info(f"Cleaned up old plate image: {file}")
                    except Exception as e:
                        logging.warning(f"Could not remove {file}: {e}")
                        
    except Exception as e:
        logging.error(f"Error in cleanup_old_vehicle_images: {e}")

# Add resource monitoring to the periodic status update
def periodic_status_update():
    """Periodically update frontend with current status"""
    while is_detection_running:
        try:
            # Log system resources every 30 seconds
            if int(time.time()) % 30 == 0:
                log_system_resources()
            
            # Clean up old debug files every 2 minutes
            if int(time.time()) % 120 == 0:
                cleanup_old_debug_files()
            
            # Check for stuck slots every 5 minutes
            if int(time.time()) % 300 == 0:
                force_reset_stuck_slots()
            
            # Force slot status sync every 10 seconds
            if int(time.time()) % 10 == 0:
                force_slot_status_sync()
            
            # Update parking duration for occupied slots
            for slot_id, status in slot_status.items():
                if status["occupied"] and status["entry_time"]:
                    duration = datetime.now() - status["entry_time"]
                    status["parking_duration"] = duration
                    status["last_updated"] = datetime.now()
            
            # Emit updated status to frontend
            serialized_status = serialize_slot_status(slot_status)
            socketio.emit('parking_status_update', serialized_status)
            
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            logging.error(f"Error in periodic status update: {e}")
            time.sleep(5)

def process_vehicle_detection():
    """Main vehicle detection and OCR processing loop"""
    global is_detection_running, slot_status
    
    logging.info(f"Starting vehicle detection with {current_ocr_method}...")
    
    # Run the appropriate script using subprocess in background
    try:
        if current_ocr_method == "EasyOCR":
            script_name = 'livedetect.py'
        else:
            script_name = 'openai_smart.py'
        
        logging.info(f"Executing script: {script_name}")
        
        # Create debug folders if they don't exist
        for folder in ['debug_cars', 'debug_plates', 'error_vehicles', 'debug_frames']:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logging.info(f"Created debug folder: {folder}")
        
        # Start periodic status update thread
        status_thread = threading.Thread(target=periodic_status_update)
        status_thread.daemon = True
        status_thread.start()
        
        # Run the script with improved error handling and environment
        env = os.environ.copy()
        env['PYTHONPATH'] = os.getcwd()  # Ensure current directory is in Python path
        
        # Use different subprocess approach for better compatibility
        if os.name == 'nt':  # Windows
            # Avoid PIPEs to prevent deadlocks when child writes a lot to stdout/stderr
            process = subprocess.Popen(
                [sys.executable, script_name],
                stdout=None,
                stderr=None,
                env=env,
                creationflags=subprocess.CREATE_NEW_CONSOLE  # Open in new console window
            )
        else:  # Linux/Mac
            process = subprocess.Popen(
                [sys.executable, script_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                env=env
            )
        
        logging.info(f"Script process started with PID: {process.pid}")
        
        # Give the script a moment to start
        time.sleep(5)  # Increased from 3 to 5 seconds
        
        # Monitor the process and update status with reduced frequency
        last_status_check = time.time()
        status_check_interval = 5  # Check status every 5 seconds instead of 2
        
        while is_detection_running and process.poll() is None:
            current_time = time.time()
            
            # Check for new data in debug folders less frequently
            if current_time - last_status_check >= status_check_interval:
                try:
                    update_slot_status_from_debug_folders()
                    last_status_check = current_time
                except Exception as e:
                    logging.warning(f"Error updating slot status: {e}")
            
            time.sleep(1)  # Reduced from 2 to 1 second
        
        # If process ended, check why
        if process.poll() is not None:
            exit_code = process.returncode
            if exit_code == 0:
                logging.info("Detection script completed successfully")
            else:
                logging.error(f"Detection script ended with exit code {exit_code}")
            is_detection_running = False
            
    except Exception as e:
        logging.error(f"Error running detection script: {e}")
        import traceback
        logging.error(f"Full traceback: {traceback.format_exc()}")
        is_detection_running = False
    
    logging.info("Vehicle detection loop stopped")

def update_p10_display():
    """Update P10 display with current parking status using new display manager."""
    if P10_ENABLED and p10_display:
        try:
            # Force immediate update of P10 display
            p10_display.update_slot_status(slot_status)
            logging.info("P10 display updated with current slot status")
        except Exception as e:
            logging.error(f"Error updating P10 display: {e}")
            # Try to restart display cycle if update fails
            try:
                p10_display.start_display_cycle(slot_status)
                logging.info("P10 display cycle restarted after update failure")
            except Exception as restart_error:
                logging.error(f"Failed to restart P10 display cycle: {restart_error}")

def force_reset_stuck_slots():
    """Force reset slots that might be stuck in occupied state"""
    global slot_status
    
    try:
        current_time = datetime.now()
        reset_count = 0
        
        for slot_id, status in slot_status.items():
            if status["occupied"] and status["entry_time"]:
                # Check if vehicle has been in slot for more than 2 hours (likely stuck)
                time_in_slot = current_time - status["entry_time"]
                if time_in_slot.total_seconds() > 7200:  # 2 hours
                    logging.warning(f"Slot {slot_id} stuck for {time_in_slot.total_seconds()/3600:.1f} hours, forcing reset")
                    
                    # Reset slot completely
                    slot_status[slot_id] = {
                        "occupied": False,
                        "entry_time": None,
                        "license_plate": None,
                        "vehicle_type": None,
                        "vehicle_image": None,
                        "parking_duration": None,
                        "last_updated": current_time
                    }
                    reset_count += 1
        
        if reset_count > 0:
            logging.info(f"Force reset {reset_count} stuck slots")
            # Save updated status and emit to frontend
            serialized_status = serialize_slot_status(slot_status)
            socketio.emit('parking_status_update', serialized_status)
            try:
                with open("slot_status.json", "w") as f:
                    json.dump(slot_status, f, indent=2, default=str)
            except Exception as e:
                logging.error(f"Error writing slot status after force reset: {e}")
                
    except Exception as e:
        logging.error(f"Error in force_reset_stuck_slots: {e}")

def force_slot_status_sync():
    """Force synchronization of slot status with JSON file"""
    try:
        json_file = "slot_status.json"
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r') as f:
                    script_status = json.load(f)
                
                # Check if our local status differs from script status
                status_changed = False
                for slot_id, script_data in script_status.items():
                    if slot_id in slot_status:
                        local_occupied = slot_status[slot_id]["occupied"]
                        script_occupied = script_data.get("occupied", False)
                        
                        if local_occupied != script_occupied:
                            logging.info(f"Slot {slot_id} status mismatch: local={local_occupied}, script={script_occupied}")
                            status_changed = True
                            
                            # Update local status to match script
                            if not script_occupied:
                                # Slot is free in script, clear it locally
                                slot_status[slot_id] = {
                                    "occupied": False,
                                    "entry_time": None,
                                    "license_plate": None,
                                    "vehicle_type": None,
                                    "vehicle_image": None,
                                    "parking_duration": None,
                                    "last_updated": datetime.now()
                                }
                            else:
                                # Slot is occupied in script, update local status
                                slot_status[slot_id]["occupied"] = True
                                slot_status[slot_id]["last_updated"] = datetime.now()
                
                if status_changed:
                    logging.info("Slot status synchronized with script")
                    # Emit updated status to frontend
                    serialized_status = serialize_slot_status(slot_status)
                    socketio.emit('parking_status_update', serialized_status)
                    # Update P10 display
                    update_p10_display()
                    
            except Exception as e:
                logging.debug(f"Could not read slot status file for sync: {e}")
                
    except Exception as e:
        logging.error(f"Error in force_slot_status_sync: {e}")

def display_vehicle_event(event_type: str, slot_id: str, plate_number: str = None):
    """Display vehicle event on P10 display with correct message logic."""
    if P10_ENABLED and p10_display:
        try:
            if event_type == "entering":
                # The new display manager handles entering events automatically
                # Just trigger the display update
                p10_display.update_slot_status(slot_status)
            elif event_type == "exiting":
                # The new display manager handles exiting events automatically
                # Just trigger the display update
                p10_display.update_slot_status(slot_status)
            elif event_type == "plate_detected" and plate_number:
                # The new display manager handles plate detection automatically
                # Just trigger the display update
                p10_display.update_slot_status(slot_status)
            elif event_type == "processing":
                p10_display.display_processing()
            elif event_type == "both_entering":
                p10_display.send_single_row_message("BOTH ENTERING")
        except Exception as e:
            logging.error(f"Error displaying vehicle event on P10: {e}")

def update_slot_status_from_debug_folders():
    """Update slot status by reading JSON file created by scripts with cautious exit confirmation."""
    global slot_status

    try:
        # Read slot status from JSON file created by the scripts
        json_file = "slot_status.json"
        if os.path.exists(json_file):
            try:
                # Simple file reading with error handling
                with open(json_file, 'r') as f:
                    script_status = json.load(f)
            except (IOError, OSError, json.JSONDecodeError) as e:
                # File might be locked or corrupted, skip this update
                logging.debug(f"Could not read slot status file: {e}")
                return
            
            # Check for file modification time to avoid reading stale data
            file_mtime = os.path.getmtime(json_file)
            current_time = time.time()
            
            # If file is older than 10 seconds, it might be stale
            if current_time - file_mtime > 10:
                logging.warning(f"Slot status file is stale (age: {current_time - file_mtime:.1f}s), skipping update")
                return

            # Update our slot status with data from the script
            for slot_id, script_data in script_status.items():
                if slot_id in slot_status:
                    is_occupied = bool(script_data.get("occupied", False))
                    was_occupied = bool(slot_status[slot_id]["occupied"])

                    # Entering
                    if is_occupied and not was_occupied:
                        slot_status[slot_id]["occupied"] = True
                        slot_status[slot_id]["entry_time"] = datetime.now()
                        slot_status[slot_id]["last_updated"] = datetime.now()
                        # Clear any pending exit
                        if isinstance(slot_status[slot_id], dict):
                            slot_status[slot_id].pop('exit_confirmation_time', None)

                        if script_data.get("vehicle_type"):
                            slot_status[slot_id]["vehicle_type"] = script_data["vehicle_type"]
                        display_vehicle_event("entering", str(slot_id))
                        logging.info(f"Vehicle detected in slot {slot_id}")

                    # Still occupied: update plate/vehicle type
                    if is_occupied:
                        if script_data.get("license_plate") and script_data["license_plate"] != slot_status[slot_id]["license_plate"]:
                            slot_status[slot_id]["license_plate"] = script_data["license_plate"]
                            slot_status[slot_id]["last_updated"] = datetime.now()
                            if script_data.get("vehicle_type"):
                                slot_status[slot_id]["vehicle_type"] = script_data["vehicle_type"]
                            plate_number = script_data["license_plate"] or ""
                            display_vehicle_event("plate_detected", str(slot_id), str(plate_number))
                            # Save parking record if license plate is valid
                            lp = script_data["license_plate"]
                            if lp and not (str(lp).upper().startswith("UNKNOWN") or str(lp).upper() == "UNREADABLE"):
                                save_parking_record(slot_id, lp, slot_status[slot_id].get("vehicle_type", "Unknown"), slot_status[slot_id].get("vehicle_image"))
                                
                                # Audio alert: trigger when unauthorized vehicle occupies a booked slot
                                try:
                                    if BOOKING_ENABLED and booking_integration and P10_ENABLED and p10_display:
                                        # Skip unauthorized check for OCR failures
                                        if lp and not (str(lp).upper().startswith("UNKNOWN") or str(lp).upper() == "UNREADABLE"):
                                            validation_result = booking_integration.validate_vehicle_arrival(slot_id, lp)
                                            if not validation_result.get("valid") and validation_result.get("booking"):
                                                logging.warning(f"🚨 UNAUTHORIZED VEHICLE DETECTED - Slot {slot_id}")
                                                logging.warning(f"   Expected: {validation_result['booking'].license_plate}")
                                                logging.warning(f"   Detected: {lp}")
                                                logging.warning(f"   Booking ID: {validation_result['booking'].order_id}")
                                                logging.warning(f"   Customer: {validation_result['booking'].customer_name}")
                                                try:
                                                    p10_display.trigger_unauthorized_audio_alert()
                                                    logging.info("🔊 Audio alert triggered for unauthorized vehicle")
                                                except Exception as e:
                                                    logging.error(f"Error triggering audio alert: {e}")
                                        else:
                                            logging.info(f"ℹ️ Skipping unauthorized vehicle check for slot {slot_id} - OCR failure (plate: '{lp}')")
                                except Exception as e:
                                    logging.error(f"Error during unauthorized audio check: {e}")

                    # Exiting (cautious confirmation)
                    if (not is_occupied) and was_occupied:
                        # If the stay was very short, require an extra small delay
                        short_stay_guard_seconds = 3  # Reduced from 5 to 3 seconds
                        short_stay_threshold_seconds = 20  # Reduced from 30 to 20 seconds

                        now = datetime.now()
                        entry_time = slot_status[slot_id]["entry_time"]
                        time_in_slot = (now - entry_time).total_seconds() if entry_time else 0

                        if time_in_slot < short_stay_threshold_seconds:
                            # Start or check the exit confirmation timer
                            pending_key = 'exit_confirmation_time'
                            pending_since = slot_status[slot_id].get(pending_key)
                            if not pending_since:
                                slot_status[slot_id][pending_key] = now
                                logging.info(f"Delaying exit confirmation for slot {slot_id} (short stay: {time_in_slot:.1f}s)")
                                continue
                            elif (now - pending_since).total_seconds() < short_stay_guard_seconds:
                                # Still waiting for guard window
                                continue
                            else:
                                # Guard elapsed, proceed to confirm exit
                                slot_status[slot_id].pop(pending_key, None)

                        # Confirm exit
                        last_plate = slot_status[slot_id]["license_plate"]
                        if last_plate and (str(last_plate).upper().startswith("UNKNOWN") or str(last_plate).upper() == "UNREADABLE"):
                            save_unknown_vehicle(slot_id, slot_status[slot_id].get("vehicle_image"))
                        elif last_plate and last_plate not in ["Unknown", "UNREADABLE"]:
                            duration = now - slot_status[slot_id]["entry_time"] if slot_status[slot_id]["entry_time"] else timedelta(0)
                            update_parking_record(slot_id, duration)

                        display_vehicle_event("exiting", str(slot_id), str(last_plate) if last_plate is not None else "")
                        
                        # Clear ALL slot data completely
                        slot_status[slot_id] = {
                            "occupied": False,
                            "entry_time": None,
                            "license_plate": None,
                            "vehicle_type": None,
                            "vehicle_image": None,  # Clear the old vehicle image
                            "parking_duration": None,
                            "last_updated": now
                        }
                        
                        # Clean any pending key
                        if isinstance(slot_status[slot_id], dict):
                            slot_status[slot_id].pop('exit_confirmation_time', None)

                        logging.info(f"Slot {slot_id} set to FREE in backend. Emitting update and writing to slot_status.json.")
                        # Immediately emit updated status to frontend and write to JSON
                        serialized_status = serialize_slot_status(slot_status)
                        socketio.emit('parking_status_update', serialized_status)
                        try:
                            with open("slot_status.json", "w") as f:
                                json.dump(slot_status, f, indent=2, default=str)
                            logging.info(f"slot_status.json written after slot {slot_id} set to FREE.")
                        except Exception as e:
                            logging.error(f"Error writing slot status to JSON after freeing slot: {e}")
                        
                        # Force immediate P10 display update
                        update_p10_display()
                        
                        # Clean up old images immediately
                        try:
                            cleanup_old_vehicle_images(slot_id)
                        except Exception as e:
                            logging.warning(f"Error cleaning up old images for slot {slot_id}: {e}")
                        
                        logging.info(f"Vehicle left slot {slot_id}")
            
    except Exception as e:
        logging.error(f"Error reading slot status JSON file: {e}")
    
    # Also check debug_cars folder for vehicle images
    debug_cars_dir = "debug_cars"
    if os.path.exists(debug_cars_dir):
        car_files = [f for f in os.listdir(debug_cars_dir) if f.endswith(('.jpg', '.png'))]
        for car_file in car_files:
            # Parse filename to get slot info (e.g., "slot_1_timestamp.jpg")
            if car_file.startswith("slot_"):
                parts = car_file.split('_')
                if len(parts) >= 2:
                    slot_id = parts[1]
                    if slot_id in slot_status and slot_status[slot_id]["occupied"]:
                        # Read and encode the image if we don't have one yet
                        if not slot_status[slot_id]["vehicle_image"]:
                            image_path = os.path.join(debug_cars_dir, car_file)
                            try:
                                with open(image_path, 'rb') as f:
                                    image_data = f.read()
                                    base64_image = base64.b64encode(image_data).decode('utf-8')
                                    slot_status[slot_id]["vehicle_image"] = base64_image
                                    logging.info(f"Updated vehicle image for slot {slot_id}")
                            except Exception as e:
                                logging.error(f"Error reading car image {car_file}: {e}")
                    else:
                        # If slot is not occupied but we have an old image file, clean it up
                        if slot_id in slot_status and not slot_status[slot_id]["occupied"]:
                            try:
                                image_path = os.path.join(debug_cars_dir, car_file)
                                os.remove(image_path)
                                logging.info(f"Cleaned up old vehicle image for free slot {slot_id}: {car_file}")
                            except Exception as e:
                                logging.warning(f"Could not remove old image {car_file}: {e}")
    
    # Update parking duration for occupied slots
    for slot_id, status in slot_status.items():
        if status["occupied"] and status["entry_time"]:
            duration = datetime.now() - status["entry_time"]
            status["parking_duration"] = duration
            status["last_updated"] = datetime.now()
            
    # Immediately emit updated status to frontend
    serialized_status = serialize_slot_status(slot_status)
    socketio.emit('parking_status_update', serialized_status)
    # Save updated slot_status to JSON file
    try:
        with open("slot_status.json", "w") as f:
            json.dump(slot_status, f, indent=2, default=str)
    except Exception as e:
        logging.error(f"Error writing slot status to JSON: {e}")
    # Update P10 display after all slot status changes
    update_p10_display()

def save_parking_record(slot_id, license_plate, vehicle_type, vehicle_image):
    """Save parking record to MongoDB with vehicle type and image using Sri Lanka timezone"""
    try:
        # Handle vehicle image - it could be base64 string or numpy array
        vehicle_image_b64 = ""
        if vehicle_image is not None:
            if isinstance(vehicle_image, str):
                # Already a base64 string
                vehicle_image_b64 = vehicle_image
            elif hasattr(vehicle_image, 'size') and hasattr(vehicle_image, 'shape'):
                # Numpy array - convert to base64
                vehicle_image_b64 = encode_image_to_base64(vehicle_image)
            else:
                # Unknown type, try to convert to base64 if possible
                try:
                    vehicle_image_b64 = encode_image_to_base64(vehicle_image)
                except:
                    vehicle_image_b64 = ""
        
        # Use Sri Lanka timezone
        current_time = get_sri_lanka_time()
        
        # Check if a record already exists for this slot with no exit time
        existing_record = parking_records.find_one({
            "slot_id": slot_id,
            "exit_time": None
        })
        
        if existing_record:
            logging.warning(f"⚠️ Parking record already exists for slot {slot_id}, skipping new record creation")
            logging.info(f"   Existing record: {existing_record.get('license_plate', 'Unknown')} - {existing_record.get('entry_time', 'No entry time')}")
            return
        
        # Booking validation - Skip validation for OCR failures
        booking_info = None
        if BOOKING_ENABLED and booking_integration:
            # Get booking info for debugging
            try:
                active_bookings = booking_integration.get_active_bookings()
                current_booking = active_bookings.get(slot_id)
            except Exception as e:
                logging.warning(f"⚠️ Could not get booking info for debugging: {e}")
                current_booking = None
            
            # Log OCR debug information
            log_ocr_debug_info(slot_id, license_plate, current_booking)
            
            # Skip booking validation if license plate is unknown/unreadable (OCR failure)
            if license_plate and not (str(license_plate).upper().startswith("UNKNOWN") or str(license_plate).upper() == "UNREADABLE"):
                logging.info(f"🔍 Starting booking validation for slot {slot_id} with plate '{license_plate}'")
                validation_start_time = time.time()
                validation_result = booking_integration.validate_vehicle_arrival(slot_id, license_plate)
                validation_time = time.time() - validation_start_time
                
                if validation_result["valid"]:
                    booking_info = validation_result["booking"]
                    logging.info(f"✅ Vehicle {license_plate} matches booking {booking_info.order_id} for slot {slot_id} (validation time: {validation_time:.2f}s)")
                    
                    # Update booking with arrival time
                    if booking_integration.update_booking_arrival(slot_id, booking_info):
                        logging.info(f"✅ Updated booking {booking_info.order_id} with arrival time")
                    
                elif validation_result["booking"]:
                    # Booking exists but plate doesn't match
                    booking_info = validation_result["booking"]
                    logging.warning(f"⚠️ License plate mismatch for slot {slot_id} (validation time: {validation_time:.2f}s)")
                    logging.warning(f"   Expected: {booking_info.license_plate}")
                    logging.warning(f"   Detected: {license_plate}")
                    logging.warning(f"   Booking: {booking_info.order_id} - {booking_info.customer_name}")
                else:
                    logging.info(f"ℹ️ No booking found for slot {slot_id} - vehicle {license_plate} (validation time: {validation_time:.2f}s)")
            else:
                logging.info(f"ℹ️ Skipping booking validation for slot {slot_id} - OCR failure detected (plate: '{license_plate}')")
        else:
            logging.info(f"ℹ️ Booking validation disabled for slot {slot_id} - vehicle {license_plate}")
        
        record = {
            "slot_id": slot_id,
            "license_plate": license_plate,
            "vehicle_type": vehicle_type,
            "vehicle_image": vehicle_image_b64,
            "entry_time": current_time,
            "exit_time": None,
            "duration": None,
            "ocr_method": current_ocr_method,
            "created_at": current_time,
            "updated_at": current_time,
            "booking_info": {
                "order_id": booking_info.order_id if booking_info else None,
                "customer_name": booking_info.customer_name if booking_info else None,
                "is_pre_booked": booking_info.is_pre_booked if booking_info else False,
                "booking_status": validation_result.get("reason", "No booking") if BOOKING_ENABLED else "Booking system disabled"
            } if BOOKING_ENABLED else None
        }
        
        result = parking_records.insert_one(record)
        
        if result.inserted_id:
            logging.info(f"✅ Successfully saved parking record for slot {slot_id}")
            logging.info(f"   Vehicle: {vehicle_type} - {license_plate}")
            logging.info(f"   Entry time: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            logging.info(f"   Record ID: {result.inserted_id}")
            
            if booking_info:
                logging.info(f"   Booking: {booking_info.order_id} - {booking_info.customer_name}")
            
            # Notify frontend about new record
            socketio.emit('new_parking_record', {
                "slot_id": slot_id,
                "license_plate": license_plate,
                "vehicle_type": vehicle_type,
                "entry_time": current_time.isoformat(),
                "booking_info": record["booking_info"]
            })
        else:
            logging.error(f"❌ Failed to save parking record for slot {slot_id}")
            
    except Exception as e:
        logging.error(f"Error saving parking record for slot {slot_id}: {e}")
        # Log the full error details for debugging
        import traceback
        logging.error(f"Full error traceback: {traceback.format_exc()}")

def save_unknown_vehicle(slot_id, vehicle_image):
    """Save unknown vehicle record to MongoDB"""
    try:
        # Handle vehicle image - it could be base64 string or numpy array
        vehicle_image_b64 = ""
        if vehicle_image is not None:
            if isinstance(vehicle_image, str):
                # Already a base64 string
                vehicle_image_b64 = vehicle_image
            elif hasattr(vehicle_image, 'size') and hasattr(vehicle_image, 'shape'):
                # Numpy array - convert to base64
                vehicle_image_b64 = encode_image_to_base64(vehicle_image)
            else:
                # Unknown type, try to convert to base64 if possible
                try:
                    vehicle_image_b64 = encode_image_to_base64(vehicle_image)
                except:
                    vehicle_image_b64 = ""
        
        # If no image provided, try to find it in error_vehicles folder
        if not vehicle_image_b64:
            error_vehicles_dir = "error_vehicles"
            if os.path.exists(error_vehicles_dir):
                # Look for the most recent error image for this slot
                error_files = [f for f in os.listdir(error_vehicles_dir) 
                              if f.startswith(f"slot_{slot_id}_unknown_") and f.endswith(('.jpg', '.png'))]
                if error_files:
                    # Sort by modification time to get the most recent
                    error_files.sort(key=lambda x: os.path.getmtime(os.path.join(error_vehicles_dir, x)), reverse=True)
                    latest_error_file = error_files[0]
                    image_path = os.path.join(error_vehicles_dir, latest_error_file)
                    try:
                        with open(image_path, 'rb') as f:
                            image_data = f.read()
                            vehicle_image_b64 = base64.b64encode(image_data).decode('utf-8')
                            logging.info(f"Found error vehicle image for slot {slot_id}: {latest_error_file}")
                    except Exception as e:
                        logging.error(f"Error reading error vehicle image {latest_error_file}: {e}")
        
        record = {
            "slot_id": slot_id,
            "vehicle_image": vehicle_image_b64,
            "detection_time": datetime.now(),
            "ocr_method": current_ocr_method,
            "created_at": datetime.now()
        }
        unknown_vehicles.insert_one(record)
        logging.info(f"Saved unknown vehicle record for slot {slot_id}")
    except Exception as e:
        logging.error(f"Error saving unknown vehicle record: {e}")

def update_parking_record(slot_id, duration):
    """Update parking record with exit time and duration using Sri Lanka timezone"""
    try:
        # Use Sri Lanka timezone
        exit_time = get_sri_lanka_time()
        
        # First, find the record to update - look for records without exit_time
        record = parking_records.find_one({
            "slot_id": slot_id,
            "exit_time": None
        })
        
        if record:
            # Booking departure update
            if BOOKING_ENABLED and booking_integration:
                booking_info = record.get('booking_info', {})
                if booking_info and booking_info.get('order_id'):
                    # Try to update booking departure
                    try:
                        from booking_integration import BookingInfo
                        booking = BookingInfo(
                            order_id=booking_info['order_id'],
                            slot_number=slot_id,
                            license_plate=record.get('license_plate', ''),
                            customer_name=booking_info.get('customer_name', ''),
                            start_time='',
                            end_time='',
                            date='',
                            status='',
                            is_pre_booked=booking_info.get('is_pre_booked', False)
                        )
                        
                        if booking_integration.update_booking_departure(slot_id, booking):
                            logging.info(f"✅ Updated booking {booking_info['order_id']} with departure time")
                    except Exception as e:
                        logging.error(f"Error updating booking departure: {e}")
            
            # Update the record with exit time and duration
            result = parking_records.update_one(
                {"_id": record["_id"]},
                {
                    "$set": {
                        "exit_time": exit_time,
                        "duration": str(duration),
                        "updated_at": exit_time
                    }
                }
            )
            
            if result.modified_count > 0:
                logging.info(f"✅ Successfully updated parking record for slot {slot_id}")
                logging.info(f"   Exit time: {exit_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                logging.info(f"   Duration: {duration}")
                logging.info(f"   Vehicle: {record.get('license_plate', 'Unknown')}")
                logging.info(f"   Record ID: {record['_id']}")
                
                # Notify frontend about updated record
                socketio.emit('parking_record_updated', {
                    "slot_id": slot_id,
                    "license_plate": record.get('license_plate', 'Unknown'),
                    "exit_time": exit_time.isoformat(),
                    "duration": str(duration)
                })
            else:
                logging.warning(f"⚠️ No records modified for slot {slot_id}")
        else:
            # Try alternative query - maybe the record doesn't have exit_time field
            record = parking_records.find_one({
                "slot_id": slot_id
            })
            
            if record and not record.get("exit_time"):
                # Update the record with exit time and duration
                result = parking_records.update_one(
                    {"_id": record["_id"]},
                    {
                        "$set": {
                            "exit_time": exit_time,
                            "duration": str(duration),
                            "updated_at": exit_time
                        }
                    }
                )
                
                if result.modified_count > 0:
                    logging.info(f"✅ Successfully updated parking record for slot {slot_id} (alternative query)")
                    logging.info(f"   Exit time: {exit_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
                    logging.info(f"   Duration: {duration}")
                    logging.info(f"   Vehicle: {record.get('license_plate', 'Unknown')}")
                    
                    # Notify frontend about updated record
                    socketio.emit('parking_record_updated', {
                        "slot_id": slot_id,
                        "license_plate": record.get('license_plate', 'Unknown'),
                        "exit_time": exit_time.isoformat(),
                        "duration": str(duration)
                    })
                else:
                    logging.warning(f"⚠️ No records modified for slot {slot_id} (alternative query)")
            else:
                logging.warning(f"⚠️ No parking record found for slot {slot_id} to update")
                
    except Exception as e:
        logging.error(f"Error updating parking record for slot {slot_id}: {e}")
        # Log the full error details for debugging
        import traceback
        logging.error(f"Full error traceback: {traceback.format_exc()}")

# Enhanced OCR debugging for booking scenarios
def log_ocr_debug_info(slot_id: str, license_plate: str, booking_info=None):
    """Log detailed OCR debugging information for booking scenarios"""
    if booking_info:
        logging.info(f"🔍 OCR DEBUG - Slot {slot_id} (BOOKED SCENARIO)")
        logging.info(f"   Expected plate: {booking_info.license_plate}")
        logging.info(f"   Detected plate: {license_plate}")
        logging.info(f"   Booking ID: {booking_info.order_id}")
        logging.info(f"   Customer: {booking_info.customer_name}")
        if license_plate and not (str(license_plate).upper().startswith("UNKNOWN") or str(license_plate).upper() == "UNREADABLE"):
            logging.info(f"   ✅ OCR succeeded - will validate against booking")
        else:
            logging.info(f"   ❌ OCR failed - skipping booking validation")
    else:
        logging.info(f"🔍 OCR DEBUG - Slot {slot_id} (NON-BOOKED SCENARIO)")
        logging.info(f"   Detected plate: {license_plate}")
        if license_plate and not (str(license_plate).upper().startswith("UNKNOWN") or str(license_plate).upper() == "UNREADABLE"):
            logging.info(f"   ✅ OCR succeeded")
        else:
            logging.info(f"   ❌ OCR failed")

# API Routes
@app.route('/')
def index():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/api/start-detection', methods=['POST'])
def start_detection():
    global is_detection_running
    if not is_detection_running:
        is_detection_running = True
        thread = threading.Thread(target=process_vehicle_detection)
        thread.daemon = True
        thread.start()
        return jsonify({"status": "success", "message": "Detection started"})
    return jsonify({"status": "error", "message": "Detection already running"})

@app.route('/api/stop-detection', methods=['POST'])
def stop_detection():
    global is_detection_running
    is_detection_running = False
    return jsonify({"status": "success", "message": "Detection stopped"})

@app.route('/api/parking-status')
def get_parking_status():
    return jsonify(serialize_slot_status(slot_status))

@app.route('/api/parking-records')
def get_parking_records():
    try:
        # Get date filter from query parameters
        date_filter = request.args.get('date')
        
        if date_filter:
            # Parse the date and create date range using Sri Lanka timezone
            try:
                filter_date = datetime.fromisoformat(date_filter.replace('Z', '+00:00'))
                # Convert to Sri Lanka timezone
                filter_date = SRI_LANKA_TZ.localize(filter_date.replace(tzinfo=None))
                start_date = filter_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = start_date + timedelta(days=1)
                
                # Filter records by date
                records = list(parking_records.find({
                    "entry_time": {
                        "$gte": start_date,
                        "$lt": end_date
                    }
                }, {'_id': 0}).sort('entry_time', -1))
            except ValueError:
                # If date parsing fails, return all records
                records = list(parking_records.find({}, {'_id': 0}).sort('entry_time', -1).limit(100))
        else:
            # Return recent records if no date filter
            records = list(parking_records.find({}, {'_id': 0}).sort('entry_time', -1).limit(100))
        
        # Convert time fields to Sri Lanka timezone for display
        def convert_time_for_display(time_obj):
            if time_obj:
                if isinstance(time_obj, str):
                    # Parse ISO string
                    try:
                        dt = datetime.fromisoformat(time_obj.replace('Z', '+00:00'))
                        # Convert to Sri Lanka timezone
                        if dt.tzinfo is None:
                            dt = SRI_LANKA_TZ.localize(dt)
                        else:
                            dt = dt.astimezone(SRI_LANKA_TZ)
                        return dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                    except:
                        return time_obj
                elif isinstance(time_obj, datetime):
                    # Convert datetime to Sri Lanka timezone
                    if time_obj.tzinfo is None:
                        time_obj = SRI_LANKA_TZ.localize(time_obj)
                    else:
                        time_obj = time_obj.astimezone(SRI_LANKA_TZ)
                    return time_obj.strftime('%Y-%m-%d %H:%M:%S %Z')
            return time_obj
        
        # Convert time fields in records
        for record in records:
            if 'entry_time' in record:
                record['entry_time_display'] = convert_time_for_display(record['entry_time'])
            if 'exit_time' in record:
                record['exit_time_display'] = convert_time_for_display(record['exit_time'])
            if 'created_at' in record:
                record['created_at_display'] = convert_time_for_display(record['created_at'])
            if 'updated_at' in record:
                record['updated_at_display'] = convert_time_for_display(record['updated_at'])
        
        return jsonify(records)
    except Exception as e:
        logging.error(f"Error fetching parking records: {e}")
        return jsonify([])

@app.route('/api/unknown-vehicles')
def get_unknown_vehicles():
    try:
        records = list(unknown_vehicles.find({}, {'_id': 0}).sort('created_at', -1).limit(50))
        return jsonify(records)
    except Exception as e:
        logging.error(f"Error fetching unknown vehicles: {e}")
        return jsonify([])

@app.route('/api/switch-ocr', methods=['POST'])
def switch_ocr_method():
    global current_ocr_method
    data = request.get_json()
    method = data.get('method')
    
    if method in ['EasyOCR', 'OpenAI']:
        current_ocr_method = method
        # Update system status in database
        system_status.update_one(
            {"key": "ocr_method"},
            {"$set": {"value": method, "updated_at": datetime.now()}},
            upsert=True
        )
        return jsonify({"status": "success", "method": method})
    
    return jsonify({"status": "error", "message": "Invalid OCR method"})

@app.route('/api/current-ocr')
def get_current_ocr():
    return jsonify({"method": current_ocr_method})

@app.route('/api/statistics')
def get_statistics():
    try:
        # Get today's records using Sri Lanka timezone
        current_time = get_sri_lanka_time()
        today = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_records = parking_records.count_documents({
            "entry_time": {"$gte": today}
        })
        
        total_records = parking_records.count_documents({})
        unknown_count = unknown_vehicles.count_documents({})
        
        # Get current occupancy and detecting slots
        occupied_slots = 0
        detecting_slots = 0
        
        for status in slot_status.values():
            if status["occupied"]:
                occupied_slots += 1
                if status["license_plate"] in ["Unknown", "UNREADABLE"]:
                    detecting_slots += 1
        
        # Get recent activity (last 24 hours) using Sri Lanka timezone
        yesterday = current_time - timedelta(days=1)
        recent_records = parking_records.count_documents({
            "entry_time": {"$gte": yesterday}
        })
        
        return jsonify({
            "today_records": today_records,
            "total_records": total_records,
            "unknown_vehicles": unknown_count,
            "occupied_slots": occupied_slots,
            "detecting_slots": detecting_slots,
            "total_slots": len(PARKING_SLOTS),
            "recent_activity": recent_records,
            "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        })
    except Exception as e:
        logging.error(f"Error fetching statistics: {e}")
        return jsonify({})

# Additional API endpoints from app_video.py

@app.route('/api/p10-status')
def get_p10_status():
    """Get current P10 display status"""
    if P10_ENABLED and p10_display:
        try:
            status = p10_display.get_current_status()
            return jsonify({
                "status": "success",
                "p10_enabled": True,
                "display_status": status
            })
        except Exception as e:
            return jsonify({
                "status": "error", 
                "p10_enabled": True,
                "error": str(e)
            })
    else:
        return jsonify({
            "status": "success",
            "p10_enabled": False,
            "message": "P10 display not available"
        })

@app.route('/api/p10-test', methods=['POST'])
def test_p10_display():
    """Test P10 display with custom message"""
    if not P10_ENABLED or not p10_display:
        return jsonify({"status": "error", "message": "P10 display not available"})
    
    try:
        data = request.get_json()
        test_type = data.get('type', 'status')
        
        if test_type == 'status':
            success = p10_display.display_slot_status()
        elif test_type == 'entering':
            slot_id = data.get('slot_id', '1')
            success = p10_display.display_vehicle_entering(slot_id)
        elif test_type == 'exiting':
            slot_id = data.get('slot_id', '1')
            plate = data.get('plate', 'ABC1234')
            success = p10_display.display_vehicle_exiting(slot_id, plate)
        elif test_type == 'plate':
            slot_id = data.get('slot_id', '1')
            plate = data.get('plate', 'ABC1234')
            success = p10_display.display_plate_detected(slot_id, plate)
        elif test_type == 'custom':
            first_text = data.get('first_text', 'TEST')
            second_text = data.get('second_text', 'MESSAGE')
            success = p10_display.send_double_row_static(first_text, second_text)
        else:
            return jsonify({"status": "error", "message": "Invalid test type"})
        
        if success:
            return jsonify({"status": "success", "message": f"P10 test '{test_type}' completed"})
        else:
            return jsonify({"status": "error", "message": f"P10 test '{test_type}' failed"})
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route('/api/p10/test-both-busy-non-booked', methods=['POST'])
def test_both_busy_non_booked():
    """Test both slots busy in non-booked mode (no unauthorized vehicles)"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    
    try:
        success = p10_display.test_both_slots_busy_non_booked()
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Test both slots busy non-booked completed",
                "slot1_plate": "CBB4567",
                "slot2_plate": "AAB7793",
                "expected_cycle": [
                    {
                        "first_row": "SLOT 1 BUSY",
                        "second_row": "CBB4567"
                    },
                    {
                        "first_row": "SLOT 2 BUSY", 
                        "second_row": "AAB7793"
                    }
                ],
                "mode": "non-booked",
                "unauthorized_vehicles": "none"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Test both slots busy non-booked failed"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/p10/test-both-busy-unauthorized', methods=['POST'])
def test_both_busy_unauthorized():
    """Test both slots busy with unauthorized vehicles"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    
    try:
        success = p10_display.test_both_slots_busy_unauthorized()
        
        if success:
            return jsonify({
                "status": "success",
                "message": f"Test both slots busy unauthorized completed",
                "slot1_plate": "CBB4567",
                "slot2_plate": "AAB7793",
                "unauthorized_vehicles": "both",
                "expected_cycle": [
                    {
                        "first_row": "SLOT 1 BUSY",
                        "second_row": "CBB4567"
                    },
                    {
                        "first_row": "SLOT 2 BUSY", 
                        "second_row": "AAB7793"
                    },
                    {
                        "first_row": "UNAUTHORIZED",
                        "second_row": "VEHICLES"
                    }
                ]
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Test both slots busy unauthorized failed"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/booking/status')
def get_booking_status():
    """Get current booking status for all slots"""
    if not BOOKING_ENABLED or not booking_integration:
        return jsonify({
            "status": "error",
            "message": "Booking integration not available"
        })
    
    try:
        booking_status = {}
        for slot_id in PARKING_SLOTS:
            status = booking_integration.get_slot_booking_status(slot_id)
            booking_status[slot_id] = status
        
        return jsonify({
            "status": "success",
            "booking_status": booking_status
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/booking/validate', methods=['POST'])
def validate_booking():
    """Validate a vehicle against booking system"""
    if not BOOKING_ENABLED or not booking_integration:
        return jsonify({
            "status": "error",
            "message": "Booking integration not available"
        })
    
    try:
        data = request.get_json()
        slot_id = data.get('slot_id')
        license_plate = data.get('license_plate')
        
        if not slot_id or not license_plate:
            return jsonify({
                "status": "error",
                "message": "Slot ID and license plate are required"
            })
        
        validation_result = booking_integration.validate_vehicle_arrival(slot_id, license_plate)
        
        return jsonify({
            "status": "success",
            "validation_result": validation_result
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/booking/conflicts')
def get_booking_conflicts():
    """Get booking conflicts for current time"""
    if not BOOKING_ENABLED or not booking_integration:
        return jsonify({
            "status": "error",
            "message": "Booking integration not available"
        })
    
    try:
        conflicts = booking_integration.get_booking_conflicts()
        
        return jsonify({
            "status": "success",
            "conflicts": conflicts
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/p10/test-audio-alert', methods=['POST'])
def test_audio_alert():
    """Test audio alert for unauthorized vehicle"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    try:
        success = p10_display.trigger_unauthorized_audio_alert()
        if success:
            return jsonify({
                "status": "success",
                "message": "Audio alert test completed"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Audio alert test failed"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/p10/stop-audio-alert', methods=['POST'])
def stop_audio_alert():
    """Stop audio alert"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    try:
        success = p10_display.stop_unauthorized_audio_alert()
        return jsonify({
            "status": "success" if success else "error",
            "message": "Audio alert stopped" if success else "Failed to stop audio alert"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/p10/unauthorized-warning', methods=['POST'])
def test_unauthorized_warning():
    """Test unauthorized vehicle warning on P10 display"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    
    try:
        success = p10_display.test_unauthorized_warning()
        
        if success:
            return jsonify({
                "status": "success",
                "message": "Unauthorized warning test completed",
                "expected_message": "UNAUTHORIZED VEHICLES"
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Unauthorized warning test failed"
            })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

@app.route('/api/p10/unauthorized-status')
def get_unauthorized_status():
    """Get current unauthorized vehicle status"""
    if not P10_ENABLED or not p10_display:
        return jsonify({
            "status": "error",
            "message": "P10 display not available"
        })
    
    try:
        status = p10_display.get_unauthorized_status()
        
        return jsonify({
            "status": "success",
            "unauthorized_status": status
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        })

def shutdown_p10_display():
    """Shutdown P10 display gracefully"""
    if P10_ENABLED and p10_display:
        try:
            p10_display.shutdown()
            logging.info("P10 display shutdown completed")
        except Exception as e:
            logging.error(f"Error during P10 display shutdown: {e}")

# WebSocket events
@socketio.on('connect')
def handle_connect():
    logging.info("Client connected")
    # Send initial status with serialized data
    serialized_status = serialize_slot_status(slot_status)
    emit('parking_status_update', serialized_status)

@socketio.on('disconnect')
def handle_disconnect():
    logging.info("Client disconnected")

if __name__ == '__main__':
    # Clear slot status on startup to ensure fresh state
    clear_slot_status_on_startup()
    
    # Initialize system status
    system_status.update_one(
        {"key": "ocr_method"},
        {"$set": {"value": current_ocr_method, "updated_at": datetime.now()}},
        upsert=True
    )
    
    logging.info("Starting AI Parking System Backend...")
    # Run server without reloader/debug to avoid duplicate processes interfering with RTSP/GUI
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False)