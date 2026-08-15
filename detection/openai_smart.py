import cv2
import numpy as np
from inference_sdk import InferenceHTTPClient
from ultralytics import YOLO
import time
import re
import logging
import os
import json
from datetime import datetime
import base64
import requests
import threading
import psutil
import gc
from dotenv import load_dotenv

# Load secrets from a local .env file (see .env.example)
load_dotenv()
# Enhanced exit detection removed - using simpler buffer-based detection from livedetect.py

# =================================================================================
# --- CONFIGURATION ---
# =================================================================================

# Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# --- OpenAI Configuration ---
# Loaded from the OPENAI_API_KEY environment variable (see .env.example)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"

# --- Roboflow Configuration ---
ROBOFLOW_CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=os.getenv("ROBOFLOW_API_KEY", "")
)
LICENSE_PLATE_MODEL_ID = "license-plate-recognition-rxg4e/11"
PLATE_CONFIDENCE_THRESHOLD = 0.4

# --- Local YOLO Model for Vehicle Detection ---
CAR_DETECTION_MODEL = YOLO('yolov8n.pt')
VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle']

# --- Parking Slot Configuration (from livedetect.py config) ---
try:
    from config import PARKING_SLOTS
    logging.info("Using parking slots from config file")
except ImportError:
    # Fallback coordinates if config file not available
    PARKING_SLOTS = {
        '1': [(299, 110), (2, 359), (390, 439), (486, 156)],
        '2': [(538, 127), (512, 450), (987, 455), (836, 127)],
    }
    logging.warning("Using fallback parking slot coordinates")

# --- RTSP Configuration ---
# Default RTSP URL - can be overridden by config file
DEFAULT_RTSP_URL = os.getenv("RTSP_URL", "")  # Set in .env, e.g. rtsp://user:pass@host:554/Streaming/Channels/101

# --- Timing & Retry Configuration ---
try:
    from config import OCR_TRIGGER_DELAY, OCR_RETRY_INTERVAL, MAX_OCR_ATTEMPTS
except ImportError:
    OCR_TRIGGER_DELAY = 10  # Seconds before triggering OCR after car entry
    OCR_RETRY_INTERVAL = 8  # Seconds between OCR retries if failed
    MAX_OCR_ATTEMPTS = 4    # Maximum number of OCR attempts per vehicle

# --- Image Processing & Debugging Configuration ---
OCR_DEBUG_MODE = True
MIN_PLATE_WIDTH = 40
MIN_PLATE_HEIGHT = 15

# --- Directories ---
os.makedirs("debug_plates", exist_ok=True)
os.makedirs("debug_cars", exist_ok=True)
os.makedirs("error_vehicles", exist_ok=True)

# --- Global State Tracking ---
unknown_counter = 1
is_detection_running = True

# OCR Scheduling to prevent simultaneous API calls
ocr_lock = threading.Lock()
last_ocr_time = 0
OCR_MIN_INTERVAL = 2  # Minimum seconds between OCR calls to prevent API conflicts
ocr_queue = []  # Queue for OCR processing

def monitor_system_resources():
    """Monitor system resources and log warnings if resources are low."""
    try:
        # Memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 85:
            logging.warning(f"High memory usage: {memory.percent}%")
            gc.collect()  # Force garbage collection
        
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            logging.warning(f"High CPU usage: {cpu_percent}%")
        
        # Log resource status periodically
        if int(time.time()) % 60 == 0:  # Every minute
            logging.info(f"Resources - CPU: {cpu_percent}%, Memory: {memory.percent}%")
            
    except Exception as e:
        logging.error(f"Resource monitoring error: {e}")

def cleanup_old_debug_files():
    """Clean up old debug files to prevent disk space issues."""
    try:
        import os
        import glob
        from datetime import datetime, timedelta
        
        # Clean files older than 1 hour
        cutoff_time = datetime.now() - timedelta(hours=1)
        
        for folder in ['debug_frames', 'debug_plates', 'debug_cars']:
            if os.path.exists(folder):
                for file_path in glob.glob(os.path.join(folder, '*')):
                    try:
                        file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if file_time < cutoff_time:
                            os.remove(file_path)
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

def start_monitoring_thread():
    """Start background monitoring thread."""
    def monitoring_loop():
        while is_detection_running:
            monitor_system_resources()
            cleanup_old_debug_files()
            time.sleep(30)  # Check every 30 seconds
    
    monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitor_thread.start()
    logging.info("System monitoring thread started")

# Buffer for vehicle exit detection
exit_buffer = {
    slot_id: {
        "last_seen": None,
        "buffer_start": None,
        "buffer_duration": 3  # seconds
    } for slot_id in PARKING_SLOTS
}

# Main status dictionary for all slots
slot_status = {
    slot_id: {
        "occupied": False,
        "entry_time": None,
        "car_bbox": None,
        "vehicle_type": None,
        "ocr_triggered": False,
        "license_plate": None,
        "parked_time_start": None,
        "last_ocr_attempt": None,
        "ocr_attempts": 0
    } for slot_id in PARKING_SLOTS
}


# =================================================================================
# --- OPENAI OCR FUNCTIONS (REPLACED EASYOCR) ---
# =================================================================================

def encode_image_to_base64(image: np.ndarray) -> str:
    """Convert OpenCV image to base64 string for OpenAI API."""
    try:
        _, buffer = cv2.imencode('.jpg', image)
        return base64.b64encode(buffer.tobytes()).decode('utf-8')
    except Exception as e:
        logging.error(f"Error encoding image to base64: {e}")
        return ""


def read_plate_with_openai(image: np.ndarray) -> str:
    """Performs OCR on license plate image using OpenAI GPT-4o-mini with improved error handling."""
    base64_image = encode_image_to_base64(image)
    if not base64_image:
        return "UNREADABLE"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # Improved prompt for better Sri Lankan plate recognition
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Read the license plate in this image. Sri Lankan plates may have provincial codes like 'WP CBB 6788' or 'WP KO 8646'. IGNORE the provincial code (WP, CP, SP, etc.) and return ONLY the main plate number. Format: 2-3 letters + 4 numbers like 'CBB6788' or 'KO8646'. If unreadable, return 'UNREADABLE'."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 20,
        "temperature": 0.0
    }

    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            plate_text = result['choices'][0]['message']['content'].strip().upper()
            
            # Handle exact "UNREADABLE" response
            if plate_text == "UNREADABLE":
                return "UNREADABLE"
            
            # Extract potential plate from longer text (handles malformed responses)
            # Look for patterns like "CBB6788", "WP CBB 6788", etc.
            # First try to find patterns without provincial codes
            plate_patterns = re.findall(r'(?:^|[^A-Z]|(?:WP|CP|SP|NP|EP|NC|NW|UP|SG)\s+)([A-Z]{2,3}\s*[0-9]{4})(?:[^0-9]|$)', plate_text)
            
            if not plate_patterns:
                # Fallback: find any 2-3 letters + 4 numbers pattern
                plate_patterns = re.findall(r'[A-Z]{2,3}\s*[0-9]{4}', plate_text)
            
            if plate_patterns:
                # Take the first valid pattern found (skip provincial codes)
                found_text = plate_patterns[0] if isinstance(plate_patterns[0], str) else plate_patterns[0]
                found_plate = re.sub(r'[^A-Z0-9]', '', found_text)
                
                # Remove common provincial codes if they appear at the start
                provincial_codes = ['WP', 'CP', 'SP', 'NP', 'EP', 'NC', 'NW', 'UP', 'SG']
                for code in provincial_codes:
                    if found_plate.startswith(code) and len(found_plate) > len(code):
                        found_plate = found_plate[len(code):]
                        break
                
                if re.match(r'^[A-Z]{2,3}[0-9]{4}$', found_plate):
                    # Format the plate with a space between letters and numbers
                    letters = re.match(r'^[A-Z]{2,3}', found_plate).group()
                    numbers = found_plate[len(letters):]
                    formatted_plate = f"{letters} {numbers}"
                    logging.info(f"✓ Extracted plate from OpenAI response: '{formatted_plate}' (from: '{plate_text[:50]}...')")
                    return formatted_plate
            
            # If no valid pattern found, try cleaning the entire response
            cleaned_text = re.sub(r'[^A-Z0-9]', '', plate_text)
            
            # Remove provincial codes from cleaned text if present
            provincial_codes = ['WP', 'CP', 'SP', 'NP', 'EP', 'NC', 'NW', 'UP', 'SG']
            for code in provincial_codes:
                if cleaned_text.startswith(code) and len(cleaned_text) > len(code):
                    cleaned_text = cleaned_text[len(code):]
                    break
            
            if re.match(r'^[A-Z]{2,3}[0-9]{4}$', cleaned_text):
                # Format the plate with a space between letters and numbers
                letters = re.match(r'^[A-Z]{2,3}', cleaned_text).group()
                numbers = cleaned_text[len(letters):]
                formatted_plate = f"{letters} {numbers}"
                logging.info(f"✓ Cleaned plate from OpenAI response: '{formatted_plate}' (removed provincial code)")
                return formatted_plate
            else:
                logging.warning(f"OpenAI returned a non-standard format: '{plate_text[:100]}...'")
                return "UNREADABLE"
        elif response.status_code == 429:
            logging.warning(f"OpenAI API rate limit hit - this may cause conflicts with simultaneous requests")
            return "UNREADABLE"
        else:
            logging.error(f"OpenAI API error: {response.status_code} - {response.text}")
            return "UNREADABLE"
    except requests.exceptions.Timeout:
        logging.error(f"OpenAI API timeout - this may indicate API congestion from multiple requests")
        return "UNREADABLE"
    except Exception as e:
        logging.error(f"Error during OpenAI OCR request: {e}")
        return "UNREADABLE"


# =================================================================================
# --- CORE WORKFLOW FUNCTIONS (FROM LIVEDETECT_VIDEO.PY) ---
# =================================================================================

def detect_vehicle_type(frame, bbox):
    """Detect vehicle type using YOLO model (improved from livedetect.py)"""
    try:
        x1, y1, x2, y2 = bbox
        # Crop the vehicle region
        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            return "Unknown"
        
        # Run YOLO detection on the cropped vehicle
        results = CAR_DETECTION_MODEL.predict(vehicle_crop, verbose=False)[0]
        boxes = results.boxes.data.cpu().numpy()
        
        if len(boxes) > 0:
            # Get the highest confidence detection
            best_detection = boxes[0]
            class_id = int(best_detection[5])
            confidence = best_detection[4]
            
            if confidence > 0.5:  # Only use high confidence detections
                class_name = results.names[class_id]
                if class_name in VEHICLE_CLASSES:
                    return class_name.title()  # Capitalize first letter
        
        return "Unknown"
    except Exception as e:
        logging.error(f"Error detecting vehicle type: {e}")
        return "Unknown"


def has_valid_license_plate(license_plate):
    """Check if a license plate is valid and not empty/unknown"""
    if not license_plate:
        return False
    
    license_plate_str = str(license_plate).strip().upper()
    
    # Check for empty, None, or unknown values
    if not license_plate_str or license_plate_str in ["NONE", "NULL", "UNREADABLE"]:
        return False
    
    # Check for "Unknown X" pattern
    if license_plate_str.startswith("UNKNOWN"):
        return False
    
    # Check for valid Sri Lankan plate format (basic check)
    if re.match(r'^[A-Z]{2,3}\s*[0-9]{4}$', license_plate_str):
        return True
    
    return False


def save_slot_status_to_file():
    """Save current slot status to JSON file for the Flask backend to read."""
    try:
        serializable_status = {}
        for slot_id, status in slot_status.items():
            serializable_status[slot_id] = {
                "occupied": status["occupied"],
                "entry_time": status["entry_time"],
                "license_plate": status["license_plate"],
                "vehicle_type": status.get("vehicle_type", "Unknown"),  # Ensure we always have a vehicle type
                "parked_time_start": status["parked_time_start"],
                "last_updated": datetime.now().isoformat(),
                "vehicle_image": None  # Clear vehicle image when saving status
            }
        
        with open("slot_status.json", "w") as f:
            json.dump(serializable_status, f, indent=2)
        
        # Log status for debugging vehicle type issues
        for slot_id, status in serializable_status.items():
            if status["occupied"]:
                logging.info(f"📝 Slot {slot_id}: {status['vehicle_type']} - Plate: {status.get('license_plate', 'None')}")
    except Exception as e:
        logging.error(f"Error saving slot status to file: {e}")


def enhanced_preprocess_plate_image(image: np.ndarray) -> list:
    """
    Enhanced preprocessing with multiple methods for better OCR
    (From proven livedetect.py techniques)
    """
    h, w = image.shape[:2]

    # Ensure minimum size for processing
    if h < 50 or w < 150:
        scale_factor = max(2.5, 150 / w, 50 / h)
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    processed_images = []

    # Method 1: Enhanced adaptive thresholding
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    filtered = cv2.bilateralFilter(enhanced, 9, 75, 75)
    thresh1 = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 21, 5)
    processed_images.append(thresh1)

    # Method 2: Otsu's thresholding
    _, thresh2 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_images.append(thresh2)

    # Method 3: Morphological operations for better character separation
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    morph = cv2.morphologyEx(thresh1, cv2.MORPH_CLOSE, kernel)
    processed_images.append(morph)

    return processed_images


def create_enhanced_debug_montage(slot_id: str, original_image: np.ndarray, plate_crop: np.ndarray, result: str):
    """
    Create enhanced debug montage with detailed OCR analysis (from livedetect.py)
    """
    try:
        # Create montage
        montage_height = 300
        montage_width = 800
        montage = np.zeros((montage_height, montage_width, 3), dtype=np.uint8)

        # Add original image
        h, w = plate_crop.shape[:2]
        display_height = 120
        display_width = int(w * display_height / h)
        if display_width > 300:
            display_width = 300
            display_height = int(h * display_width / w)

        orig_resized = cv2.resize(plate_crop, (display_width, display_height))
        if len(orig_resized.shape) == 2:
            orig_resized = cv2.cvtColor(orig_resized, cv2.COLOR_GRAY2BGR)

        # Place original in montage
        montage[20:20 + display_height, 20:20 + display_width] = orig_resized

        # Add processed image
        processed_imgs = enhanced_preprocess_plate_image(plate_crop)
        if processed_imgs:
            proc_resized = cv2.resize(processed_imgs[0], (display_width, display_height))
            if len(proc_resized.shape) == 2:
                proc_resized = cv2.cvtColor(proc_resized, cv2.COLOR_GRAY2BGR)
            montage[20:20 + display_height, 400:400 + display_width] = proc_resized

        # Add labels and results
        cv2.putText(montage, f"Slot {slot_id} - Original", (20, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(montage, "Processed", (400, 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Highlight final result
        result_color = (0, 255, 0) if re.match(r'^[A-Z]{2,3}\s*[0-9]{4}$', result) else (0, 0, 255)
        cv2.putText(montage, f"RESULT: {result}", (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, result_color, 2)

        # Save montage
        timestamp = int(time.time())
        montage_path = f"debug_plates/montage_slot_{slot_id}_{timestamp}.png"
        cv2.imwrite(montage_path, montage)
        logging.info(f"Enhanced debug montage saved to {montage_path}")

    except Exception as e:
        logging.error(f"Error creating enhanced debug montage: {e}")


def enhance_plate_image(plate_image: np.ndarray) -> np.ndarray:
    """
    Enhance license plate image using proven techniques from livedetect.py
    """
    try:
        if plate_image.size == 0:
            return plate_image
        
        # Use the proven preprocessing method
        processed_images = enhanced_preprocess_plate_image(plate_image)
        
        # Return the best processed image (adaptive threshold usually works best)
        if processed_images:
            best_image = processed_images[0]  # Adaptive threshold method
            # Convert back to BGR for consistency with OpenAI API
            if len(best_image.shape) == 2:
                result = cv2.cvtColor(best_image, cv2.COLOR_GRAY2BGR)
            else:
                result = best_image
            return result
        else:
            return plate_image
            
    except Exception as e:
        logging.error(f"Error enhancing plate image: {e}")
        return plate_image

def enhanced_fallback_plate_detection(image: np.ndarray) -> tuple:
    """
    CRITICAL FALLBACK: Use contour analysis to find a plate if Roboflow fails.
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            area = w * h

            if (MIN_PLATE_WIDTH <= w <= image.shape[1] * 0.8 and
                MIN_PLATE_HEIGHT <= h <= image.shape[0] * 0.6 and
                1.5 <= aspect_ratio <= 7 and
                area > 500):
                candidates.append((x, y, x + w, y + h, area))

        if candidates:
            best_candidate = max(candidates, key=lambda x: x[4])
            logging.info(f"Fallback detector found a potential plate via contours.")
            return best_candidate[:4]

        logging.warning("Contour fallback could not find a valid plate candidate.")
        return None
    except Exception as e:
        logging.error(f"Fallback plate detection failed: {e}")
        return None


def schedule_ocr_processing(slot_id: str, crop_image: np.ndarray, current_time: float) -> bool:
    """
    Schedule OCR processing to prevent simultaneous API calls that cause conflicts.
    Returns True if OCR was scheduled/processed, False if it should wait.
    """
    global last_ocr_time
    
    with ocr_lock:
        # Check if enough time has passed since last OCR call
        time_since_last_ocr = current_time - last_ocr_time
        
        if time_since_last_ocr < OCR_MIN_INTERVAL:
            # Not enough time has passed, add to queue for later processing
            if slot_id not in [item['slot_id'] for item in ocr_queue]:
                ocr_queue.append({
                    'slot_id': slot_id,
                    'crop_image': crop_image.copy(),
                    'scheduled_time': current_time + OCR_MIN_INTERVAL
                })
                logging.info(f"📅 OCR for Slot {slot_id} queued for {OCR_MIN_INTERVAL}s to avoid conflicts")
            return False
        else:
            # Enough time has passed, process immediately
            last_ocr_time = current_time
            result = process_plate_with_openai(slot_id, crop_image)
            
            # Update slot status
            if result:
                slot_status[slot_id]["license_plate"] = result
                slot_status[slot_id]["parked_time_start"] = current_time
                logging.info(f"✅ Successfully detected license plate for Slot {slot_id}: '{result}'")
            else:
                logging.warning(f"❌ Failed to detect valid license plate for Slot {slot_id}")
            
            save_slot_status_to_file()
            return True

def process_queued_ocr(current_time: float):
    """Process queued OCR requests when their time comes."""
    global last_ocr_time
    
    if not ocr_queue:
        return
    
    with ocr_lock:
        # Check if any queued items are ready to process
        ready_items = [item for item in ocr_queue if current_time >= item['scheduled_time']]
        
        if ready_items and (current_time - last_ocr_time) >= OCR_MIN_INTERVAL:
            # Process the first ready item
            item = ready_items[0]
            slot_id = item['slot_id']
            crop_image = item['crop_image']
            
            logging.info(f"🔄 Processing queued OCR for Slot {slot_id}")
            
            last_ocr_time = current_time
            result = process_plate_with_openai(slot_id, crop_image)
            
            # Update slot status
            if result:
                slot_status[slot_id]["license_plate"] = result
                slot_status[slot_id]["parked_time_start"] = current_time
                logging.info(f"✅ Successfully detected license plate for Slot {slot_id}: '{result}' (from queue)")
            else:
                logging.warning(f"❌ Failed to detect valid license plate for Slot {slot_id} (from queue)")
            
            save_slot_status_to_file()
            
            # Remove processed item from queue
            ocr_queue.remove(item)

def process_plate_with_openai(slot_id: str, crop_image: np.ndarray) -> str:
    """
    This is the new main processing function that combines the robust plate
    detection workflow with the powerful OpenAI OCR engine.
    """
    timestamp = int(time.time())
    car_debug_path = f"debug_cars/slot_{slot_id}_{timestamp}.jpg"
    cv2.imwrite(car_debug_path, crop_image)

    try:
        # 1. Use Roboflow for primary plate detection
        plate_results = ROBOFLOW_CLIENT.infer(car_debug_path, model_id=LICENSE_PLATE_MODEL_ID)
        predictions = [p for p in plate_results.get('predictions', []) if p.get('confidence', 0) >= PLATE_CONFIDENCE_THRESHOLD]

        plate_crop = None
        if not predictions:
            logging.warning(f"Roboflow failed for Slot {slot_id}. Triggering contour fallback...")
            # 2. Use the fallback detector if Roboflow fails
            plate_coords = enhanced_fallback_plate_detection(crop_image)
            if plate_coords:
                px1, py1, px2, py2 = plate_coords
                # Add padding around detected plate
                padding = 5
                px1 = max(0, px1 - padding)
                py1 = max(0, py1 - padding)
                px2 = min(crop_image.shape[1], px2 + padding)
                py2 = min(crop_image.shape[0], py2 + padding)
                plate_crop = crop_image[py1:py2, px1:px2]
        else:
            pred = max(predictions, key=lambda x: x['confidence'])
            logging.info(f"Roboflow detected plate for Slot {slot_id} with confidence {pred['confidence']:.3f}")
            
            # Calculate coordinates with improved accuracy
            h, w = crop_image.shape[:2]
            cx, cy = pred['x'], pred['y']
            plate_w, plate_h = pred['width'], pred['height']
            
            # Add padding to improve OCR
            padding_factor = 0.1  # 10% padding
            padded_w = plate_w * (1 + padding_factor)
            padded_h = plate_h * (1 + padding_factor)
            
            px1 = max(0, int(cx - padded_w / 2))
            py1 = max(0, int(cy - padded_h / 2))
            px2 = min(w, int(cx + padded_w / 2))
            py2 = min(h, int(cy + padded_h / 2))
            
            plate_crop = crop_image[py1:py2, px1:px2]
            logging.info(f"Extracted plate region: ({px1},{py1}) to ({px2},{py2}) with padding")

        if plate_crop is None or plate_crop.size == 0:
            logging.error(f"All plate detection methods failed for Slot {slot_id}. Could not crop plate.")
            return ""

        # Enhance the plate image before OCR using proven techniques
        enhanced_plate = enhance_plate_image(plate_crop)
        
        debug_path = f"debug_plates/slot_{slot_id}_{timestamp}.png"
        cv2.imwrite(debug_path, enhanced_plate)
        logging.info(f"Saved enhanced plate crop to {debug_path} for OCR.")

        # 3. Try multiple processing methods like livedetect.py
        processed_images = enhanced_preprocess_plate_image(plate_crop)
        plate_text = ""
        
        # Try each processed image with OpenAI
        for i, processed_img in enumerate(processed_images):
            # Convert grayscale to BGR for OpenAI API
            if len(processed_img.shape) == 2:
                processed_bgr = cv2.cvtColor(processed_img, cv2.COLOR_GRAY2BGR)
            else:
                processed_bgr = processed_img
                
            # Save debug image for this method
            method_debug_path = f"debug_plates/slot_{slot_id}_method_{i}_{timestamp}.png"
            cv2.imwrite(method_debug_path, processed_bgr)
            
            plate_text = read_plate_with_openai(processed_bgr)
            
            if plate_text and plate_text != "UNREADABLE":
                logging.info(f"✓ OpenAI successfully read plate for Slot {slot_id} using method {i}: '{plate_text}'")
                break
            else:
                logging.warning(f"✗ OpenAI method {i} failed for Slot {slot_id}")
        
        # Create debug montage for analysis (like livedetect.py)
        if OCR_DEBUG_MODE:
            create_enhanced_debug_montage(slot_id, crop_image, plate_crop, plate_text if plate_text else "UNREADABLE")

        if plate_text and plate_text != "UNREADABLE":
             return plate_text
        else:
            logging.warning(f"✗ All OpenAI processing methods failed for Slot {slot_id}.")
            return ""

    except Exception as e:
        logging.error(f"Critical error in OpenAI processing for Slot {slot_id}: {e}")
        return ""


def initialize_rtsp_stream(rtsp_url: str):
    """
    Initialize RTSP stream with proper configuration for live streaming.
    """
    cap = cv2.VideoCapture(rtsp_url)
    
    # Critical: Set these properties before opening
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
    cap.set(cv2.CAP_PROP_FPS, 15)  # Reduce FPS for stability
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))
    except Exception:
        pass
    
    # Force flush buffer to get latest frame
    if cap.isOpened():
        for _ in range(5):  # Skip first few frames
            cap.grab()
    
    return cap


def get_latest_frame(cap, max_retries=3):
    """
    Get the latest frame with proper error handling and buffer flushing.
    """
    for attempt in range(max_retries):
        try:
            # Flush buffer by grabbing multiple frames
            for _ in range(2):
                if not cap.grab():
                    return False, None
            
            # Get the actual frame
            ret, frame = cap.retrieve()
            if ret and frame is not None:
                return True, frame
                
        except Exception as e:
            logging.warning(f"Frame grab attempt {attempt + 1} failed: {e}")
            time.sleep(0.1)
    
    return False, None


def monitor_rtsp_health(cap, last_successful_frame_time):
    """
    Monitor RTSP stream health and detect disconnections.
    """
    current_time = time.time()
    time_since_last_frame = current_time - last_successful_frame_time
    
    # Check if stream is healthy
    if time_since_last_frame > 15:  # 15 seconds without frame
        logging.warning(f"Stream unhealthy: {time_since_last_frame:.1f}s since last frame")
        return False
    
    return True


def reconnect_rtsp_stream(rtsp_url: str, max_retries: int = 3):
    """
    Attempt to reconnect to RTSP stream with improved retry logic.
    """
    for attempt in range(max_retries):
        logging.info(f"Reconnecting to RTSP stream (attempt {attempt + 1}/{max_retries})...")
        
        try:
            cap = initialize_rtsp_stream(rtsp_url)
            
            if cap.isOpened():
                # Test with actual frame grab
                ret, test_frame = get_latest_frame(cap, max_retries=2)
                if ret and test_frame is not None:
                    logging.info("Successfully reconnected to RTSP stream")
                    return cap
                else:
                    logging.warning(f"Stream opened but no frames available (attempt {attempt + 1})")
                    cap.release()
            else:
                logging.warning(f"Failed to open stream (attempt {attempt + 1})")
                
        except Exception as e:
            logging.error(f"Reconnection attempt {attempt + 1} failed: {e}")
        
        time.sleep(5)  # Wait longer between retries
    
    logging.error("Failed to reconnect to RTSP stream after all attempts")
    return None


# =================================================================================
# --- MAIN DETECTION LOOP ---
# =================================================================================

def main_video_file(cap):
    """
    Main function for video file processing (same logic as livedetect.py)
    """
    global unknown_counter, slot_status, is_detection_running
    logging.info("=== STARTING ENHANCED PARKING DETECTION SYSTEM (OPENAI) - VIDEO FILE ===")
    
    logging.info("Video capture initialized successfully")
    logging.info(f"Parking slots configured: {list(PARKING_SLOTS.keys())}")
    
    try:
        frame_count = 0
        while cap.isOpened() and is_detection_running:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                logging.info("End of video reached, restarting...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame_count += 1

            # Resize frame for processing
            frame = cv2.resize(frame, (1020, 500))
            h, w = frame.shape[:2]
            left_half = frame[:, :w // 2]
            right_half = frame[:, w // 2:]

            # Car detection using YOLO
            results = CAR_DETECTION_MODEL.predict(frame, verbose=False)[0]
            boxes = results.boxes.data.cpu().numpy()

            # Track current occupancy
            current_occupancy = {slot_id: False for slot_id in PARKING_SLOTS}
            cars_in_slots = {slot_id: None for slot_id in PARKING_SLOTS}

            # Process detected vehicles
            detected_vehicle_types = {}  # Store vehicle types for each slot
            
            for box in boxes:
                x1, y1, x2, y2, score, cls_id = box
                class_name = results.names[int(cls_id)]

                if class_name in VEHICLE_CLASSES:
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    # Check if vehicle is in any parking slot
                    for slot_id, area in PARKING_SLOTS.items():
                        area_np = np.array(area, np.int32)
                        if cv2.pointPolygonTest(area_np, (cx, cy), False) >= 0:
                            current_occupancy[slot_id] = True
                            cars_in_slots[slot_id] = (int(x1), int(y1), int(x2), int(y2))
                            detected_vehicle_types[slot_id] = class_name.title()  # Store the detected vehicle type
                            # Draw detection rectangle
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                            cv2.putText(frame, f"{class_name.title()} ({score:.2f})",
                                        (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            break

            # Update parking slot status and trigger OCR (improved from livedetect.py)
            current_time = time.time()
            
            # Process any queued OCR requests first
            process_queued_ocr(current_time)

            for slot_id in PARKING_SLOTS:
                status = slot_status[slot_id]
                buffer = exit_buffer[slot_id]

                # Car entered slot - IMPROVED VEHICLE ENTRY DETECTION
                if current_occupancy[slot_id] and not status["occupied"]:
                    logging.info(f"🚗 NEW VEHICLE ENTRY - Slot {slot_id}")
                    
                    # Use the detected vehicle type from main detection loop
                    vehicle_type = detected_vehicle_types.get(slot_id, "Unknown")
                    logging.info(f"Detected vehicle type for Slot {slot_id}: {vehicle_type}")
                    
                    # Force clear exit buffer immediately when new vehicle enters
                    buffer["last_seen"] = current_time
                    buffer["buffer_start"] = None
                    
                    # Clean up any old debug images for this slot first
                    try:
                        cleanup_old_vehicle_images(slot_id)
                    except Exception as e:
                        logging.warning(f"Error cleaning up old images for slot {slot_id}: {e}")
                    
                    # Completely reset slot status for new vehicle (avoid stale data)
                    status.clear()  # Clear any remaining state
                    status.update({
                        "occupied": True,
                        "entry_time": current_time,
                        "car_bbox": cars_in_slots[slot_id],
                        "vehicle_type": vehicle_type,
                        "ocr_triggered": False,
                        "license_plate": None,
                        "parked_time_start": None,
                        "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    })
                    
                    logging.info(f"🔄 Slot {slot_id} completely reset for new vehicle entry")
                    save_slot_status_to_file()

                # Car is still in slot
                elif current_occupancy[slot_id] and status["occupied"]:
                    time_since_entry = current_time - status["entry_time"]
                    
                    # Log periodic status for long-parked vehicles (every 60 seconds)
                    if time_since_entry > 60 and int(time_since_entry) % 60 == 0:
                        plate_status = "Valid" if has_valid_license_plate(status["license_plate"]) else "Invalid/Missing"
                        logging.info(f"📊 Slot {slot_id} - Parked for {int(time_since_entry/60)}min - Plate: {status.get('license_plate', 'None')} ({plate_status}) - OCR attempts: {status.get('ocr_attempts', 0)}")
                    
                    # Update vehicle type if it's Unknown or missing and we have a detection
                    if (not status.get("vehicle_type") or status.get("vehicle_type") == "Unknown") and slot_id in detected_vehicle_types:
                        vehicle_type = detected_vehicle_types[slot_id]
                        status["vehicle_type"] = vehicle_type
                        logging.info(f"Updated vehicle type for Slot {slot_id}: {vehicle_type}")
                        save_slot_status_to_file()

                    # Trigger OCR after delay (improved logic for new vehicles)
                    should_trigger_ocr = (
                        time_since_entry > OCR_TRIGGER_DELAY and not status["ocr_triggered"]
                    ) or (
                        # Force immediate retry if no license plate detected after reasonable time
                        time_since_entry > (OCR_TRIGGER_DELAY + 5) and 
                        not status.get("license_plate") and 
                        status.get("ocr_attempts", 0) < MAX_OCR_ATTEMPTS
                    )
                    
                    if should_trigger_ocr:
                        if not status["ocr_triggered"]:
                            status["ocr_triggered"] = True
                            status["ocr_attempts"] = 1
                        else:
                            status["ocr_attempts"] = status.get("ocr_attempts", 0) + 1
                            
                        status["last_ocr_attempt"] = current_time
                        logging.info(
                            f"🔍 Triggering OpenAI OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        # Select appropriate image half
                        crop_image = left_half if slot_id == '1' else right_half

                        if crop_image.size > 0:
                            # Use scheduled OCR to prevent conflicts with other slots
                            ocr_processed = schedule_ocr_processing(slot_id, crop_image, current_time)
                            if not ocr_processed:
                                logging.info(f"⏳ OCR for Slot {slot_id} scheduled due to API timing constraints")
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Retry OCR if failed and enough time has passed (but not if we already have a valid plate)
                    # Also don't retry if the vehicle has been parked for more than 5 minutes (300 seconds)
                    elif (not has_valid_license_plate(status["license_plate"]) and
                          status["last_ocr_attempt"] and
                          current_time - status["last_ocr_attempt"] > OCR_RETRY_INTERVAL and
                          status["ocr_attempts"] < MAX_OCR_ATTEMPTS and
                          time_since_entry < 300):

                        status["last_ocr_attempt"] = current_time
                        status["ocr_attempts"] += 1
                        logging.info(
                            f"🔄 Retrying OpenAI OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            # Use scheduled OCR to prevent conflicts with other slots
                            ocr_processed = schedule_ocr_processing(slot_id, crop_image, current_time)
                            if ocr_processed:
                                logging.info(f"🔄 OCR retry processed for Slot {slot_id}")
                            else:
                                logging.info(f"⏳ OCR retry for Slot {slot_id} scheduled due to API timing constraints")
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Handle max attempts reached or vehicle parked too long without valid plate
                    elif (not has_valid_license_plate(status["license_plate"]) and
                          (status["ocr_attempts"] >= MAX_OCR_ATTEMPTS or time_since_entry >= 300)):
                        status["license_plate"] = f"Unknown {unknown_counter}"
                        status["parked_time_start"] = current_time
                        logging.info(
                            f"❌ Max OCR attempts ({MAX_OCR_ATTEMPTS}) reached for Slot {slot_id}. Marking as '{status['license_plate']}'")

                        # Save vehicle image to error folder
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        error_path = f"error_vehicles/slot_{slot_id}_unknown_{unknown_counter}_{timestamp}.jpg"
                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            cv2.imwrite(error_path, crop_image)
                            logging.info(f"📸 Saved unknown vehicle image to {error_path}")
                        unknown_counter += 1

                # Car left slot
                elif not current_occupancy[slot_id] and status["occupied"]:
                    plate_info = f" (Plate: {status['license_plate']})" if status[
                        'license_plate'] else " (No plate detected)"
                    logging.info(f"🚗💨 Car left Slot {slot_id}{plate_info}")

                    # Reset slot status
                    slot_status[slot_id] = {
                        "occupied": False,
                        "entry_time": None,
                        "car_bbox": None,
                        "vehicle_type": None,
                        "ocr_triggered": False,
                        "license_plate": None,
                        "parked_time_start": None,
                        "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    }
                    save_slot_status_to_file()

                # --- BUFFER LOGIC (from livedetect.py) ---
                if current_occupancy[slot_id]:
                    buffer["last_seen"] = current_time
                    buffer["buffer_start"] = None
                elif status["occupied"] and buffer["last_seen"]:
                    if buffer["buffer_start"] is None:
                        buffer["buffer_start"] = current_time
                        logging.info(f"Vehicle no longer detected in Slot {slot_id}, starting {buffer['buffer_duration']}s buffer...")
                    elif current_time - buffer["buffer_start"] >= buffer["buffer_duration"]:
                        logging.info(f"Car left Slot {slot_id}. Plate: {status['license_plate']}")
                        slot_status[slot_id] = {
                            "occupied": False,
                            "entry_time": None,
                            "car_bbox": None,
                            "vehicle_type": None,
                            "ocr_triggered": False,
                            "license_plate": None,
                            "parked_time_start": None,
                            "last_ocr_attempt": None,
                            "ocr_attempts": 0
                        }
                        # Reset buffer
                        buffer["last_seen"] = None
                        buffer["buffer_start"] = None
                        logging.info(f"Slot {slot_id} set to FREE. Writing to slot_status.json.")
                        save_slot_status_to_file()
                # --- END BUFFER LOGIC ---

            # Draw parking slot overlays and status (improved from livedetect.py)
            for slot_id, area in PARKING_SLOTS.items():
                status = slot_status[slot_id]

                # Choose color based on occupancy
                color = (0, 255, 0) if not status["occupied"] else (0, 0, 255)

                # Draw parking slot boundary
                cv2.polylines(frame, [np.array(area, np.int32)], True, color, 3)

                # Prepare status text
                text = f"Slot {slot_id}: "
                if status["occupied"]:
                    vehicle_type = status.get("vehicle_type", "Unknown")
                    if status["license_plate"]:
                        parked_duration = int(current_time - status["parked_time_start"])
                        text += f"{vehicle_type} - {status['license_plate']} ({parked_duration}s)"
                    else:
                        entry_duration = int(current_time - status["entry_time"])
                        if status["ocr_triggered"]:
                            text += f"{vehicle_type} - Processing... ({entry_duration}s)"
                        else:
                            wait_time = OCR_TRIGGER_DELAY - entry_duration
                            text += f"{vehicle_type} - Waiting {max(0, wait_time)}s for OCR"
                else:
                    text += "Free"

                # Draw status text with background
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                text_x, text_y = area[0][0], area[0][1] - 15
                cv2.rectangle(frame, (text_x - 5, text_y - text_size[1] - 5),
                              (text_x + text_size[0] + 5, text_y + 5), (0, 0, 0), -1)
                cv2.putText(frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
            # Add system information (from livedetect.py)
            fps = 1 / (time.time() - start_time)
            info_text = [
                f"FPS: {int(fps)}",
                f"Frame: {frame_count}",
                f"OpenAI OCR System",
                f"Slots: {sum(1 for s in slot_status.values() if s['occupied'])}/{len(PARKING_SLOTS)} occupied"
            ]

            for i, text in enumerate(info_text):
                cv2.putText(frame, text, (10, 30 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Display frame
            cv2.imshow("Enhanced AI Parking Detection System (OpenAI)", frame)

            # Exit on ESC key
            if cv2.waitKey(1) & 0xFF == 27:
                logging.info("ESC key pressed, exiting...")
                break

    except KeyboardInterrupt:
        logging.info("Interrupted by user (Ctrl+C)")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        cv2.destroyAllWindows()
        logging.info("Enhanced parking detection system closed successfully")

def main():
    """
    Main function with improved RTSP handling and GUI support.
    """
    global unknown_counter, slot_status, is_detection_running
    logging.info("=== STARTING HYBRID PARKING DETECTION SYSTEM (ROBOFLOW + OPENAI) - RTSP LIVE STREAM ===")
    
    # --- Video Source Configuration (same as livedetect.py) ---
    try:
        from config import VIDEO_SOURCE
        video_source = VIDEO_SOURCE
    except ImportError:
        video_source = 'new2.mp4'  # Fallback default
    
    # Check if it's RTSP or video file
    if video_source.startswith('rtsp://'):
        rtsp_url = video_source
    else:
        # It's a video file, convert to file path
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            logging.error(f"Error opening video file '{video_source}'")
            return
        
        # For video files, we use different processing
        logging.info("Using video file instead of RTSP stream")
        return main_video_file(cap)
    
    logging.info(f"Using RTSP URL: {rtsp_url}")
    
    # Initialize RTSP stream
    cap = initialize_rtsp_stream(rtsp_url)
    if not cap.isOpened():
        logging.error(f"Error opening RTSP stream: '{rtsp_url}'")
        return

    logging.info("RTSP stream initialized successfully")

    # Variables for connection monitoring
    last_successful_frame_time = time.time()
    frame_count = 0
    fps_start_time = time.time()
    consecutive_failures = 0
    max_consecutive_failures = 10
    
    # GUI availability check
    gui_available = True
    try:
        # Test if GUI is available
        test_window = "test_gui"
        cv2.namedWindow(test_window)
        cv2.destroyWindow(test_window)
        logging.info("GUI display available")
    except:
        gui_available = False
        logging.info("GUI display not available - running in headless mode")

    try:
        while is_detection_running:
            start_time = time.time()
            
            # Get frame with improved error handling
            ret, frame = get_latest_frame(cap)
            
            if not ret or frame is None:
                consecutive_failures += 1
                logging.warning(f"Failed to get frame (failure {consecutive_failures})")
                
                if consecutive_failures >= max_consecutive_failures:
                    logging.error("Too many consecutive failures. Attempting reconnection...")
                    cap.release()
                    cap = reconnect_rtsp_stream(rtsp_url)
                    if cap is None:
                        logging.error("Failed to reconnect. Exiting...")
                        break
                    consecutive_failures = 0
                    last_successful_frame_time = time.time()
                    continue
                
                time.sleep(0.5)
                continue
            
            # Reset failure counter on successful frame
            consecutive_failures = 0
            last_successful_frame_time = time.time()
            frame_count += 1
            
            # Monitor stream health
            if not monitor_rtsp_health(cap, last_successful_frame_time):
                logging.warning("Stream health check failed. Reconnecting...")
                cap.release()
                cap = reconnect_rtsp_stream(rtsp_url)
                if cap is None:
                    break
                continue
            
            # Calculate FPS every 30 frames
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_start_time)
                fps_start_time = time.time()
                logging.info(f"Processing FPS: {fps:.1f}, Frame count: {frame_count}")

            # Resize frame for processing (ensure dimensions are correct)
            try:
                frame = cv2.resize(frame, (1020, 500))
                h, w = frame.shape[:2]
                left_half = frame[:, :w // 2]
                right_half = frame[:, w // 2:]
            except Exception as e:
                logging.error(f"Frame processing error: {e}")
                continue

            # Vehicle detection
            try:
                results = CAR_DETECTION_MODEL.predict(frame, verbose=False)[0]
                boxes = results.boxes.data.cpu().numpy()
            except Exception as e:
                logging.error(f"YOLO detection error: {e}")
                continue

            current_occupancy = {slot_id: False for slot_id in PARKING_SLOTS}
            cars_in_slots = {slot_id: None for slot_id in PARKING_SLOTS}

            # Process detections (improved from livedetect.py)
            detected_vehicle_types = {}  # Store vehicle types for each slot
            
            for box in boxes:
                try:
                    x1, y1, x2, y2, score, cls_id = box
                    class_name = results.names[int(cls_id)]
                    
                    if class_name in VEHICLE_CLASSES:
                        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                        
                        # Check if vehicle is in any parking slot
                        for slot_id, area in PARKING_SLOTS.items():
                            area_np = np.array(area, np.int32)
                            if cv2.pointPolygonTest(area_np, (cx, cy), False) >= 0:
                                current_occupancy[slot_id] = True
                                cars_in_slots[slot_id] = (int(x1), int(y1), int(x2), int(y2))
                                detected_vehicle_types[slot_id] = class_name.title()  # Store the detected vehicle type
                                # Draw detection rectangle
                                cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                                cv2.putText(frame, f"{class_name.title()} ({score:.2f})",
                                           (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                                break
                except Exception as e:
                    logging.error(f"Detection processing error: {e}")
                    continue

            # Update parking slot status and trigger OCR (improved from livedetect.py)
            current_time = time.time()
            
            # Process any queued OCR requests first
            process_queued_ocr(current_time)

            for slot_id in PARKING_SLOTS:
                status = slot_status[slot_id]
                buffer = exit_buffer[slot_id]

                # Car entered slot - IMPROVED VEHICLE ENTRY DETECTION (RTSP)
                if current_occupancy[slot_id] and not status["occupied"]:
                    logging.info(f"🚗 NEW VEHICLE ENTRY - Slot {slot_id}")
                    
                    # Use the detected vehicle type from main detection loop
                    vehicle_type = detected_vehicle_types.get(slot_id, "Unknown")
                    logging.info(f"Detected vehicle type for Slot {slot_id}: {vehicle_type}")
                    
                    # Force clear exit buffer immediately when new vehicle enters
                    buffer["last_seen"] = current_time
                    buffer["buffer_start"] = None
                    
                    # Clean up any old debug images for this slot first
                    try:
                        cleanup_old_vehicle_images(slot_id)
                    except Exception as e:
                        logging.warning(f"Error cleaning up old images for slot {slot_id}: {e}")
                    
                    # Completely reset slot status for new vehicle (avoid stale data)
                    status.clear()  # Clear any remaining state
                    status.update({
                        "occupied": True,
                        "entry_time": current_time,
                        "car_bbox": cars_in_slots[slot_id],
                        "vehicle_type": vehicle_type,
                        "ocr_triggered": False,
                        "license_plate": None,
                        "parked_time_start": None,
                        "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    })
                    
                    logging.info(f"🔄 Slot {slot_id} completely reset for new vehicle entry")
                    save_slot_status_to_file()

                # Car is still in slot
                elif current_occupancy[slot_id] and status["occupied"]:
                    time_since_entry = current_time - status["entry_time"]
                    
                    # Log periodic status for long-parked vehicles (every 60 seconds)
                    if time_since_entry > 60 and int(time_since_entry) % 60 == 0:
                        plate_status = "Valid" if has_valid_license_plate(status["license_plate"]) else "Invalid/Missing"
                        logging.info(f"📊 Slot {slot_id} - Parked for {int(time_since_entry/60)}min - Plate: {status.get('license_plate', 'None')} ({plate_status}) - OCR attempts: {status.get('ocr_attempts', 0)}")
                    
                    # Update vehicle type if it's Unknown or missing and we have a detection
                    if (not status.get("vehicle_type") or status.get("vehicle_type") == "Unknown") and slot_id in detected_vehicle_types:
                        vehicle_type = detected_vehicle_types[slot_id]
                        status["vehicle_type"] = vehicle_type
                        logging.info(f"Updated vehicle type for Slot {slot_id}: {vehicle_type}")
                        save_slot_status_to_file()

                    # Trigger OCR after delay (improved logic for new vehicles)
                    should_trigger_ocr = (
                        time_since_entry > OCR_TRIGGER_DELAY and not status["ocr_triggered"]
                    ) or (
                        # Force immediate retry if no license plate detected after reasonable time
                        time_since_entry > (OCR_TRIGGER_DELAY + 5) and 
                        not status.get("license_plate") and 
                        status.get("ocr_attempts", 0) < MAX_OCR_ATTEMPTS
                    )
                    
                    if should_trigger_ocr:
                        if not status["ocr_triggered"]:
                            status["ocr_triggered"] = True
                            status["ocr_attempts"] = 1
                        else:
                            status["ocr_attempts"] = status.get("ocr_attempts", 0) + 1
                            
                        status["last_ocr_attempt"] = current_time
                        logging.info(
                            f"🔍 Triggering OpenAI OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        # Select appropriate image half
                        crop_image = left_half if slot_id == '1' else right_half

                        if crop_image.size > 0:
                            # Use scheduled OCR to prevent conflicts with other slots
                            ocr_processed = schedule_ocr_processing(slot_id, crop_image, current_time)
                            if not ocr_processed:
                                logging.info(f"⏳ OCR for Slot {slot_id} scheduled due to API timing constraints")
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Retry OCR if failed and enough time has passed (but not if we already have a valid plate)
                    # Also don't retry if the vehicle has been parked for more than 5 minutes (300 seconds)
                    elif (not has_valid_license_plate(status["license_plate"]) and
                          status["last_ocr_attempt"] and
                          current_time - status["last_ocr_attempt"] > OCR_RETRY_INTERVAL and
                          status["ocr_attempts"] < MAX_OCR_ATTEMPTS and
                          time_since_entry < 300):

                        status["last_ocr_attempt"] = current_time
                        status["ocr_attempts"] += 1
                        logging.info(
                            f"🔄 Retrying OpenAI OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            # Use scheduled OCR to prevent conflicts with other slots
                            ocr_processed = schedule_ocr_processing(slot_id, crop_image, current_time)
                            if ocr_processed:
                                logging.info(f"🔄 OCR retry processed for Slot {slot_id}")
                            else:
                                logging.info(f"⏳ OCR retry for Slot {slot_id} scheduled due to API timing constraints")
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Handle max attempts reached or vehicle parked too long without valid plate
                    elif (not has_valid_license_plate(status["license_plate"]) and
                          (status["ocr_attempts"] >= MAX_OCR_ATTEMPTS or time_since_entry >= 300)):
                        status["license_plate"] = f"Unknown {unknown_counter}"
                        status["parked_time_start"] = current_time
                        logging.info(
                            f"❌ Max OCR attempts ({MAX_OCR_ATTEMPTS}) reached for Slot {slot_id}. Marking as '{status['license_plate']}'")

                        # Save vehicle image to error folder
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        error_path = f"error_vehicles/slot_{slot_id}_unknown_{unknown_counter}_{timestamp}.jpg"
                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            cv2.imwrite(error_path, crop_image)
                            logging.info(f"📸 Saved unknown vehicle image to {error_path}")
                        unknown_counter += 1

                # Car left slot
                elif not current_occupancy[slot_id] and status["occupied"]:
                    plate_info = f" (Plate: {status['license_plate']})" if status[
                        'license_plate'] else " (No plate detected)"
                    logging.info(f"🚗💨 Car left Slot {slot_id}{plate_info}")

                    # Reset slot status
                    slot_status[slot_id] = {
                        "occupied": False,
                        "entry_time": None,
                        "car_bbox": None,
                        "vehicle_type": None,
                        "ocr_triggered": False,
                        "license_plate": None,
                        "parked_time_start": None,
                        "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    }
                    save_slot_status_to_file()

                # --- BUFFER LOGIC (from livedetect.py) ---
                if current_occupancy[slot_id]:
                    buffer["last_seen"] = current_time
                    buffer["buffer_start"] = None
                elif status["occupied"] and buffer["last_seen"]:
                    if buffer["buffer_start"] is None:
                        buffer["buffer_start"] = current_time
                        logging.info(f"Vehicle no longer detected in Slot {slot_id}, starting {buffer['buffer_duration']}s buffer...")
                    elif current_time - buffer["buffer_start"] >= buffer["buffer_duration"]:
                        logging.info(f"Car left Slot {slot_id}. Plate: {status['license_plate']}")
                        slot_status[slot_id] = {
                            "occupied": False,
                            "entry_time": None,
                            "car_bbox": None,
                            "vehicle_type": None,
                            "ocr_triggered": False,
                            "license_plate": None,
                            "parked_time_start": None,
                            "last_ocr_attempt": None,
                            "ocr_attempts": 0
                        }
                        # Reset buffer
                        buffer["last_seen"] = None
                        buffer["buffer_start"] = None
                        logging.info(f"Slot {slot_id} set to FREE. Writing to slot_status.json.")
                        save_slot_status_to_file()
                # --- END BUFFER LOGIC ---

            # Draw parking slot overlays and status (improved from livedetect.py)
            for slot_id, area in PARKING_SLOTS.items():
                status = slot_status[slot_id]

                # Choose color based on occupancy
                color = (0, 255, 0) if not status["occupied"] else (0, 0, 255)

                # Draw parking slot boundary
                cv2.polylines(frame, [np.array(area, np.int32)], True, color, 3)

                # Prepare status text
                text = f"Slot {slot_id}: "
                if status["occupied"]:
                    vehicle_type = status.get("vehicle_type", "Unknown")
                    if status["license_plate"]:
                        parked_duration = int(current_time - status["parked_time_start"])
                        text += f"{vehicle_type} - {status['license_plate']} ({parked_duration}s)"
                    else:
                        entry_duration = int(current_time - status["entry_time"])
                        if status["ocr_triggered"]:
                            text += f"{vehicle_type} - Processing... ({entry_duration}s)"
                        else:
                            wait_time = OCR_TRIGGER_DELAY - entry_duration
                            text += f"{vehicle_type} - Waiting {max(0, wait_time)}s for OCR"
                else:
                    text += "Free"

                # Draw status text with background
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                text_x, text_y = area[0][0], area[0][1] - 15
                cv2.rectangle(frame, (text_x - 5, text_y - text_size[1] - 5),
                              (text_x + text_size[0] + 5, text_y + 5), (0, 0, 0), -1)
                cv2.putText(frame, text, (text_x, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
            # Add system information (from livedetect.py)
            fps = 1 / (time.time() - start_time)
            info_text = [
                f"FPS: {int(fps)}",
                f"Frame: {frame_count}",
                f"OpenAI OCR System",
                f"Slots: {sum(1 for s in slot_status.values() if s['occupied'])}/{len(PARKING_SLOTS)} occupied"
            ]

            for i, text in enumerate(info_text):
                cv2.putText(frame, text, (10, 30 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Display frame if GUI is available
            if gui_available:
                try:
                    cv2.imshow("Enhanced AI Parking Detection System (OpenAI)", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == 27:  # ESC key
                        logging.info("ESC key pressed. Exiting.")
                        break
                except Exception as e:
                    logging.warning(f"GUI display error: {e}")
                    gui_available = False  # Disable GUI if error occurs

            # Save debug frame periodically
            if frame_count % 60 == 0:  # Save every 60 frames
                try:
                    debug_frame_path = f"debug_frames/rtsp_frame_{frame_count}.jpg"
                    os.makedirs("debug_frames", exist_ok=True)
                    cv2.imwrite(debug_frame_path, frame)
                    logging.info(f"Saved debug frame: {debug_frame_path}")
                except Exception as e:
                    logging.warning(f"Debug frame save error: {e}")

            # Small delay to prevent overwhelming the system
            time.sleep(0.033)  # ~30 FPS processing

    except KeyboardInterrupt:
        logging.info("Process interrupted by user (Ctrl+C).")
    except Exception as e:
        logging.error(f"Unexpected error in main loop: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
    finally:
        is_detection_running = False
        if cap:
            cap.release()
        if gui_available:
            cv2.destroyAllWindows()
        logging.info("System shut down gracefully.")


if __name__ == "__main__":
    start_monitoring_thread()  # Start system monitoring
    main() 