import cv2
import numpy as np
from inference_sdk import InferenceHTTPClient
from ultralytics import YOLO
import time
import easyocr
import re
import logging
import os
import glob
import json
from collections import Counter
from datetime import datetime
from dotenv import load_dotenv

# Load secrets from a local .env file (see .env.example)
load_dotenv()

# =================================================================================
# --- PIL COMPATIBILITY PATCH ---
# =================================================================================

# Fix for deprecated PIL.Image.ANTIALIAS in newer Pillow versions
try:
    import PIL.Image
    logging.info("PIL compatibility patch checked (no monkey patch needed)")
except Exception as e:
    logging.warning(f"PIL modules loading failed: {e}")

# Additional compatibility for EasyOCR
try:
    import PIL.ImageDraw
    import PIL.ImageFont
    # Ensure these modules are available for EasyOCR
    logging.info("PIL modules loaded successfully")
except Exception as e:
    logging.warning(f"PIL modules loading failed: {e}")

# =================================================================================
# --- CONFIGURATION ---
# =================================================================================

# Logging
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

# EasyOCR setup with GPU fallback
try:
    reader = easyocr.Reader(['en'], gpu=True)  # Try GPU first
    logging.info("EasyOCR initialized successfully with GPU")
except Exception as e:
    logging.warning(f"GPU initialization failed: {e}, falling back to CPU")
    try:
        reader = easyocr.Reader(['en'], gpu=False)  # Fallback to CPU
        logging.info("EasyOCR initialized successfully with CPU fallback")
    except Exception as e:
        logging.error(f"Error initializing EasyOCR: {e}")
        exit()

# Roboflow config
ROBOFLOW_CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=os.getenv("ROBOFLOW_API_KEY", "")
)
LICENSE_PLATE_MODEL_ID = "license-plate-recognition-rxg4e/11"
PLATE_CONFIDENCE_THRESHOLD = 0.4

# Local YOLO model
CAR_DETECTION_MODEL = YOLO('yolov8n.pt')
VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle']

# Parking slots
from config import PARKING_SLOTS

# Timing configuration
OCR_TRIGGER_DELAY = 20  # seconds before triggering OCR after car entry
OCR_RETRY_INTERVAL = 10  # seconds between OCR retries if failed
MAX_OCR_ATTEMPTS = 3  # Maximum number of OCR attempts

# Enhanced OCR Configuration (from numberplate.py)
OCR_DEBUG_MODE = True
MIN_PLATE_WIDTH = 40
MIN_PLATE_HEIGHT = 15
MAX_TEXT_HEIGHT_RATIO = 0.85
MIN_CONFIDENCE = 0.3

# Directories
os.makedirs("debug_plates", exist_ok=True)
os.makedirs("debug_cars", exist_ok=True)
os.makedirs("ocr_tests", exist_ok=True)
os.makedirs("error_vehicles", exist_ok=True)  # New error folder

# Sri Lankan license plate configuration (enhanced from numberplate.py)
PROVINCIAL_CODES = ['WP', 'SP', 'CP', 'NP', 'EP', 'NC', 'NW', 'UP', 'SG']
PLATE_PATTERN = r'^[A-Z]{2,3}\s*[0-9]{4}$'

# Counter for unknown vehicles
unknown_counter = 1

# Global variable to control detection loop
is_detection_running = True

# Global slot status tracking
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

# Add buffer tracking for vehicle exit detection
exit_buffer = {
    slot_id: {
        "last_seen": None,
        "buffer_start": None,
        "buffer_duration": 3  # 3 seconds buffer before marking as free
    } for slot_id in PARKING_SLOTS
}

# =================================================================================
# --- UTILITY FUNCTIONS ---
# =================================================================================

def detect_vehicle_type(frame, bbox):
    """Detect vehicle type using YOLO model"""
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


def save_slot_status_to_file():
    """Save current slot status to JSON file for Flask app to read"""
    try:
        # Convert slot_status to serializable format
        serializable_status = {}
        for slot_id, status in slot_status.items():
            serializable_status[slot_id] = {
                "occupied": status["occupied"],
                "entry_time": status["entry_time"],
                "license_plate": status["license_plate"],
                "vehicle_type": status["vehicle_type"],
                "parked_time_start": status["parked_time_start"],
                "last_updated": time.time()
            }
        
        with open("slot_status.json", "w") as f:
            json.dump(serializable_status, f, indent=2)
        logging.debug("Slot status saved to file successfully")
    except Exception as e:
        logging.error(f"Error saving slot status to file: {e}")


# =================================================================================
# --- ENHANCED OCR FUNCTIONS FROM NUMBERPLATE.PY ---
# =================================================================================

def extract_plate_text_from_ocr_results(ocr_results, image_shape):
    """
    Enhanced text extraction from OCR results with multiple strategies
    (Ported from numberplate.py with optimizations for real-time use)
    """
    if not ocr_results:
        return ""

    # Filter results by confidence first
    valid_results = [(bbox, text, confidence) for bbox, text, confidence in ocr_results
                     if confidence >= MIN_CONFIDENCE]

    if not valid_results:
        logging.warning("No OCR results meet minimum confidence threshold")
        return ""

    # Sort by confidence (highest first)
    valid_results.sort(key=lambda x: x[2], reverse=True)

    # Strategy 1: Look for complete plate in single detection
    for bbox, text, confidence in valid_results:
        cleaned_text = re.sub(r'[^A-Z0-9\s]', '', text.upper().strip())
        no_space_text = cleaned_text.replace(' ', '')

        # Look for valid plate pattern (2-3 letters + 4 digits)
        plate_match = re.search(r'([A-Z]{2,3})([0-9]{4})', no_space_text)
        if plate_match:
            result = f"{plate_match.group(1)} {plate_match.group(2)}"
            logging.info(f"Found complete plate in single detection: '{result}' (conf: {confidence:.3f})")
            return result

    # Strategy 2: Smart reconstruction from multiple detections
    logging.debug("No complete plate found in single detection, trying reconstruction...")

    # Separate detections into categories
    letter_detections = []
    number_detections = []
    mixed_detections = []

    for bbox, text, confidence in valid_results:
        cleaned_text = re.sub(r'[^A-Z0-9\s]', '', text.upper().strip()).replace(' ', '')

        # Skip provincial codes (but only if they appear to be standalone)
        if cleaned_text in PROVINCIAL_CODES:
            logging.debug(f"Skipping provincial code: '{cleaned_text}'")
            continue

        # Categorize the detection
        if re.match(r'^[A-Z]+$', cleaned_text):  # Only letters
            letter_detections.append((cleaned_text, confidence))
        elif re.match(r'^[0-9]+$', cleaned_text):  # Only numbers
            number_detections.append((cleaned_text, confidence))
        else:  # Mixed letters and numbers
            mixed_detections.append((cleaned_text, confidence))

    # Try to reconstruct from mixed detections first
    for text, confidence in mixed_detections:
        # Remove any provincial codes from the beginning
        test_text = text
        for code in PROVINCIAL_CODES:
            if test_text.startswith(code):
                test_text = test_text[len(code):]
                break

        # Check if remaining text is a valid plate
        plate_match = re.search(r'([A-Z]{2,3})([0-9]{4})', test_text)
        if plate_match:
            result = f"{plate_match.group(1)} {plate_match.group(2)}"
            logging.info(f"Reconstructed from mixed detection: '{result}' (conf: {confidence:.3f})")
            return result

    # Try to combine best letter and number detections
    if letter_detections and number_detections:
        # Get the best letter detection (highest confidence)
        best_letters = max(letter_detections, key=lambda x: x[1])[0]
        # Get the best number detection (highest confidence)
        best_numbers = max(number_detections, key=lambda x: x[1])[0]

        # Remove provincial codes from letters
        clean_letters = best_letters
        for code in PROVINCIAL_CODES:
            if clean_letters.startswith(code):
                clean_letters = clean_letters[len(code):]
                break

        # Validate the combination
        combined = clean_letters + best_numbers
        plate_match = re.search(r'([A-Z]{2,3})([0-9]{4})', combined)
        if plate_match:
            result = f"{plate_match.group(1)} {plate_match.group(2)}"
            logging.info(f"Combined from separate detections: '{result}'")
            return result

    # Strategy 3: Process all text together
    logging.debug("Trying to process all detected text together...")

    # Combine all valid text (excluding provincial codes)
    all_text = ""
    for bbox, text, confidence in valid_results:
        cleaned_text = re.sub(r'[^A-Z0-9\s]', '', text.upper().strip()).replace(' ', '')
        # Skip if it's just a provincial code
        if cleaned_text not in PROVINCIAL_CODES:
            all_text += cleaned_text

    # Remove provincial codes from the combined text
    for code in PROVINCIAL_CODES:
        all_text = all_text.replace(code, '', 1)

    # Try to extract plate from combined text
    plate_match = re.search(r'([A-Z]{2,3})([0-9]{4})', all_text)
    if plate_match:
        result = f"{plate_match.group(1)} {plate_match.group(2)}"
        logging.info(f"Extracted from combined text: '{result}'")
        return result

    logging.warning("Could not extract valid plate text from any strategy")
    return ""


def enhanced_preprocess_plate_image(image: np.ndarray) -> list:
    """
    Enhanced preprocessing with multiple methods for better OCR
    (Optimized version from numberplate.py for real-time use)
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


def advanced_ocr_with_multiple_configs(image: np.ndarray, slot_id: str) -> str:
    """
    Enhanced OCR with better result processing and detailed debugging
    (Optimized version from numberplate.py for real-time use)
    """
    if image.size == 0:
        return ""

    processed_images = enhanced_preprocess_plate_image(image)
    all_results = []

    for i, processed_img in enumerate(processed_images):
        # Save debug image (limit to reduce I/O in real-time)
        if OCR_DEBUG_MODE and i < 2:  # Only save first 2 methods for performance
            debug_path = f"debug_plates/slot_{slot_id}_method_{i}_{int(time.time())}.png"
            cv2.imwrite(debug_path, processed_img)

        try:
            # Multiple OCR configurations (optimized for speed)
            ocr_configs = [
                {'allowlist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ', 'paragraph': False},
                {'allowlist': 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', 'paragraph': False},
            ]

            for j, config in enumerate(ocr_configs):
                ocr_results = reader.readtext(processed_img, **config)

                if ocr_results:
                    # Extract text using improved method
                    extracted_text = extract_plate_text_from_ocr_results(ocr_results, processed_img.shape)

                    if extracted_text:
                        # Calculate average confidence
                        avg_confidence = sum(float(res[2]) if isinstance(res, (list, tuple)) and len(res) > 2 else 0 for res in ocr_results) / len(ocr_results)

                        # Store result
                        result_entry = {
                            'text': extracted_text,
                            'confidence': avg_confidence,
                            'method': i,
                            'config': j,
                            'raw_results': ocr_results
                        }
                        all_results.append(result_entry)

                        logging.info(
                            f"Slot {slot_id} - Method {i}, Config {j}: '{extracted_text}' (conf: {avg_confidence:.3f})")

        except Exception as e:
            logging.error(f"OCR failed for Slot {slot_id}, method {i}: {e}")

    # Choose the best result
    if all_results:
        # Filter valid results
        valid_results = [r for r in all_results if validate_license_plate(r['text'])]

        if valid_results:
            # Sort by confidence and choose the best
            best_result = max(valid_results, key=lambda x: x['confidence'])
            logging.info(
                f"Best valid result for Slot {slot_id}: '{best_result['text']}' (conf: {best_result['confidence']:.3f})")
            return best_result['text']
        else:
            # Return the highest confidence result even if validation fails
            if all_results:
                fallback_result = max(all_results, key=lambda x: x['confidence'])
                logging.info(f"Using fallback result for Slot {slot_id}: '{fallback_result['text']}'")
                return fallback_result['text']

    logging.warning(f"No OCR results obtained for Slot {slot_id}")
    return ""


def enhanced_fallback_plate_detection(image: np.ndarray) -> tuple:
    """
    Enhanced fallback plate detection using contour analysis
    """
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / float(h)
            area = w * h

            # Enhanced criteria for plate detection
            if (MIN_PLATE_WIDTH <= w <= image.shape[1] * 0.8 and
                    MIN_PLATE_HEIGHT <= h <= image.shape[0] * 0.6 and
                    1.5 <= aspect_ratio <= 7 and
                    area > 500):  # Minimum area threshold

                candidates.append((x, y, x + w, y + h, area))

        if candidates:
            # Return the largest candidate (most likely to be a plate)
            best_candidate = max(candidates, key=lambda x: x[4])
            logging.debug(
                f"Detected plate contour: x={best_candidate[0]}, y={best_candidate[1]}, area={best_candidate[4]}")
            return best_candidate[:4]

        logging.warning("No valid plate contour detected")
        return (0, 0, 0, 0)
    except Exception as e:
        logging.debug(f"Enhanced fallback plate detection failed: {e}")
        return (0, 0, 0, 0)


def validate_license_plate(plate_text: str) -> bool:
    """
    Enhanced validation for Sri Lankan license plates
    """
    if not plate_text:
        return False

    # Remove spaces and convert to uppercase
    cleaned = plate_text.replace(' ', '').upper()

    # Check if it matches the pattern: 2-3 letters followed by 4 digits
    match = re.match(r'^[A-Z]{2,3}[0-9]{4}$', cleaned)

    if match:
        logging.debug(f"Valid plate format: '{plate_text}' -> '{cleaned}'")
        return True
    else:
        logging.debug(f"Invalid plate format: '{plate_text}' -> '{cleaned}'")
        return False


def create_enhanced_debug_montage(slot_id: str, original_image: np.ndarray, plate_crop: np.ndarray, result: str):
    """
    Create enhanced debug montage with detailed OCR analysis
    """
    try:
        # Get OCR results for visualization
        ocr_results = reader.readtext(plate_crop, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')

        # Create montage
        montage_height = 300
        montage_width = 800
        montage = np.zeros((montage_height, montage_width, 3), dtype=np.uint8)

        # Add original image with bounding boxes
        h, w = plate_crop.shape[:2]
        display_height = 120
        display_width = int(w * display_height / h)
        if display_width > 300:
            display_width = 300
            display_height = int(h * display_width / w)

        orig_resized = cv2.resize(plate_crop, (display_width, display_height))
        if len(orig_resized.shape) == 2:
            orig_resized = cv2.cvtColor(orig_resized, cv2.COLOR_GRAY2BGR)

        # Draw bounding boxes on original
        for i, (bbox, text, conf) in enumerate(ocr_results):
            if float(conf) >= MIN_CONFIDENCE:
                # Scale bounding box coordinates
                scaled_bbox = []
                for point in bbox:
                    scaled_x = int(float(point[0]) * display_width / w)
                    scaled_y = int(float(point[1]) * display_height / h)
                    scaled_bbox.append([scaled_x, scaled_y])

                # Draw rectangle
                color = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255)][i % 5]
                pts = np.array(scaled_bbox, np.int32)
                cv2.polylines(orig_resized, [pts], True, color, 2)

                # Add text label
                cv2.putText(orig_resized, f"{text}({conf:.2f})",
                            (scaled_bbox[0][0], scaled_bbox[0][1] - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)

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
        result_color = (0, 255, 0) if validate_license_plate(result) else (0, 0, 255)
        cv2.putText(montage, f"RESULT: {result}", (20, 180),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, result_color, 2)

        # Add detection details
        y_offset = 200
        for i, (bbox, text, conf) in enumerate(ocr_results[:4]):  # Show up to 4 detections
            y_pos = y_offset + i * 20
            if y_pos < montage_height - 10:
                color = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0)][i % 4]
                cv2.putText(montage, f"{i + 1}. '{text}' ({conf:.3f})",
                            (20, y_pos),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Save montage
        timestamp = int(time.time())
        montage_path = f"debug_plates/montage_slot_{slot_id}_{timestamp}.png"
        cv2.imwrite(montage_path, montage)
        logging.info(f"Enhanced debug montage saved to {montage_path}")

    except Exception as e:
        logging.error(f"Error creating enhanced debug montage: {e}")


# =================================================================================
# --- ENHANCED PLATE PROCESSING FOR PARKING SLOTS ---
# =================================================================================

def process_enhanced_ocr_for_slot(slot_id: str, crop_image: np.ndarray) -> str:
    """
    Enhanced OCR processing for parking slots using improved methods
    """
    timestamp = int(time.time())
    car_debug_path = f"debug_cars/slot_{slot_id}_{timestamp}.jpg"
    cv2.imwrite(car_debug_path, crop_image)
    logging.info(f"Saved cropped car image to {car_debug_path}")

    try:
        # Use Roboflow for initial plate detection
        plate_results = ROBOFLOW_CLIENT.infer(car_debug_path, model_id=LICENSE_PLATE_MODEL_ID)
        predictions = []
        if isinstance(plate_results, dict) and 'predictions' in plate_results:
            predictions = [p for p in plate_results['predictions']
                           if p['confidence'] >= PLATE_CONFIDENCE_THRESHOLD]

        if not predictions:
            logging.info(f"No plate detected by Roboflow for Slot {slot_id}, trying enhanced fallback...")
            plate_coords = enhanced_fallback_plate_detection(crop_image)
            if plate_coords:
                px1, py1, px2, py2 = plate_coords
            else:
                logging.warning(f"No plate detected for Slot {slot_id}")
                return ""
        else:
            # Use best Roboflow detection
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            pred = predictions[0]
            px1 = int(pred['x'] - pred['width'] / 2)
            py1 = int(pred['y'] - pred['height'] / 2)
            px2 = int(pred['x'] + pred['width'] / 2)
            py2 = int(pred['y'] + pred['height'] / 2)
            logging.info(f"Roboflow detected plate for Slot {slot_id} with confidence {pred['confidence']:.3f}")

        # Crop plate with padding
        h, w = crop_image.shape[:2]
        padding = 15
        px1, py1 = max(0, px1 - padding), max(0, py1 - padding)
        px2, py2 = min(w, px2 + padding), min(h, py2 + padding)

        plate_crop = crop_image[py1:py2, px1:px2]
        if plate_crop.size == 0:
            logging.warning(f"Plate crop for Slot {slot_id} is empty")
            return ""

        # Save plate crop for debugging
        debug_path = f"debug_plates/slot_{slot_id}_{timestamp}.png"
        cv2.imwrite(debug_path, plate_crop)
        logging.info(f"Saved plate crop to {debug_path}")

        # Enhanced OCR processing
        plate_text = advanced_ocr_with_multiple_configs(plate_crop, slot_id)

        # Fallback to simple OCR if enhanced method fails
        if not plate_text:
            logging.info(f"Enhanced OCR failed for Slot {slot_id}, trying simple fallback...")
            try:
                simple_results = reader.readtext(plate_crop, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')
                if simple_results:
                    plate_text = extract_plate_text_from_ocr_results(simple_results, plate_crop.shape)
            except Exception as e:
                logging.error(f"Simple OCR fallback failed for Slot {slot_id}: {e}")

        # Create debug montage if enabled
        if OCR_DEBUG_MODE and plate_text:
            create_enhanced_debug_montage(slot_id, crop_image, plate_crop, plate_text)

        # Validate and return result
        if plate_text and validate_license_plate(plate_text):
            logging.info(f"✓ Valid Sri Lankan license plate detected for Slot {slot_id}: '{plate_text}'")
            return plate_text
        else:
            logging.warning(f"✗ Invalid or no OCR result for Slot {slot_id}: '{plate_text}'")
            return ""

    except Exception as e:
        logging.error(f"Enhanced OCR processing error for Slot {slot_id}: {e}")
        return ""


# =================================================================================
# --- BASIC TESTING FUNCTIONS ---
# =================================================================================

def test_easyocr_basic():
    """Test if EasyOCR is working with a simple test image"""
    logging.info("Testing EasyOCR with simple image...")
    test_image = np.ones((100, 400, 3), dtype=np.uint8) * 255
    cv2.putText(test_image, "ABC 1234", (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    test_path = "ocr_tests/test_simple.png"
    cv2.imwrite(test_path, test_image)

    try:
        results = reader.readtext(test_image, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ')
        text = extract_plate_text_from_ocr_results(results, test_image.shape)
        logging.info(f"Basic OCR test result: '{text.strip()}'")
        if "ABC" in text and "1234" in text:
            logging.info("✓ EasyOCR is working correctly")
            return True
        else:
            logging.error(f"✗ EasyOCR test failed, expected 'ABC 1234', got '{text.strip()}'")
            return False
    except Exception as e:
        logging.error(f"✗ EasyOCR test failed: {e}")
        return False


# =================================================================================
# --- MAIN LIVE DETECTION SYSTEM ---
# =================================================================================

def main():
    """
    Main function for live parking detection with enhanced OCR
    """
    global unknown_counter
    logging.info("=== STARTING ENHANCED LIVE PARKING DETECTION SYSTEM ===")

    # Test EasyOCR functionality
    if not test_easyocr_basic():
        logging.error("EasyOCR is not working correctly. Please check installation.")
        # Do not return or exit; continue to run the main detection loop

    # Use global slot_status (already initialized)
    global slot_status

    # Open video capture - use config file
    try:
        from config import VIDEO_SOURCE
        video_source = VIDEO_SOURCE
    except ImportError:
        video_source = 'new2.mp4'  # Fallback default
    
    cap = cv2.VideoCapture(video_source)

    if not cap.isOpened():
        logging.error(f"Error opening video file '{video_source}'")
        return

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
            cars_in_slots = {slot_id: None for slot_id in PARKING_SLOTS}  # type: ignore

            # Process detected vehicles
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
                            cars_in_slots[slot_id] = (int(x1), int(y1), int(x2), int(y2))  # type: ignore[assignment]
                            # Draw detection rectangle
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                            cv2.putText(frame, f"{class_name} ({score:.2f})",
                                        (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                            break

            # Update parking slot status and trigger OCR
            current_time = time.time()

            for slot_id in PARKING_SLOTS:
                status = slot_status[slot_id]
                buffer = exit_buffer[slot_id]

                # Car entered slot
                if current_occupancy[slot_id] and not status["occupied"]:
                    logging.info(f"🚗 Car entered Slot {slot_id}")
                    
                    # Detect vehicle type
                    vehicle_type = "Unknown"
                    if cars_in_slots[slot_id]:
                        vehicle_type = detect_vehicle_type(frame, cars_in_slots[slot_id])
                        logging.info(f"Detected vehicle type for Slot {slot_id}: {vehicle_type}")
                    
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
                    save_slot_status_to_file()

                # Car is still in slot
                elif current_occupancy[slot_id] and status["occupied"]:
                    time_since_entry = current_time - status["entry_time"]

                    # Trigger OCR after delay
                    if (time_since_entry > OCR_TRIGGER_DELAY and not status["ocr_triggered"]):
                        status["ocr_triggered"] = True
                        status["last_ocr_attempt"] = current_time
                        status["ocr_attempts"] = 1
                        logging.info(
                            f"🔍 Triggering enhanced OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        # Select appropriate image half
                        crop_image = left_half if slot_id == '1' else right_half

                        if crop_image.size > 0:
                            plate_text = process_enhanced_ocr_for_slot(slot_id, crop_image)
                            if plate_text:
                                status["license_plate"] = plate_text
                                status["parked_time_start"] = current_time
                                logging.info(
                                    f"✅ Successfully detected license plate for Slot {slot_id}: '{plate_text}'")
                                save_slot_status_to_file()
                            else:
                                logging.warning(f"❌ Failed to detect valid license plate for Slot {slot_id}")
                                save_slot_status_to_file()
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Retry OCR if failed and enough time has passed
                    elif (not status["license_plate"] and
                          status["last_ocr_attempt"] and
                          current_time - status["last_ocr_attempt"] > OCR_RETRY_INTERVAL and
                          status["ocr_attempts"] < MAX_OCR_ATTEMPTS):

                        status["last_ocr_attempt"] = current_time
                        status["ocr_attempts"] += 1
                        logging.info(
                            f"🔄 Retrying enhanced OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            plate_text = process_enhanced_ocr_for_slot(slot_id, crop_image)
                            if plate_text:
                                status["license_plate"] = plate_text
                                status["parked_time_start"] = current_time
                                logging.info(
                                    f"✅ Successfully detected license plate on retry for Slot {slot_id}: '{plate_text}'")
                            else:
                                logging.warning(f"❌ Failed to detect valid license plate for Slot {slot_id}")
                        else:
                            logging.warning(f"⚠️ Cropped image for Slot {slot_id} is empty")

                    # Handle max attempts reached
                    elif (not status["license_plate"] and
                          status["ocr_attempts"] >= MAX_OCR_ATTEMPTS):
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
                        "ocr_triggered": False,
                        "license_plate": None,
                        "parked_time_start": None,
                        "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    }
                    save_slot_status_to_file()

                # --- BUFFER LOGIC ---
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

            # Draw parking slot overlays and status
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

            # Add system information
            fps = 1 / (time.time() - start_time)
            info_text = [
                f"FPS: {int(fps)}",
                f"Frame: {frame_count}",
                f"Enhanced OCR System",
                f"Slots: {sum(1 for s in slot_status.values() if s['occupied'])}/{len(PARKING_SLOTS)} occupied"
            ]

            for i, text in enumerate(info_text):
                cv2.putText(frame, text, (10, 30 + i * 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Display frame
            cv2.imshow("Enhanced AI Parking Detection System", frame)

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


if __name__ == "__main__":
    main()