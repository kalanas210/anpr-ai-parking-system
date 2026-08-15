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
from dotenv import load_dotenv

# Load secrets from a local .env file (see .env.example)
load_dotenv()

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

# --- Parking Slot Configuration (from livedetect_video.py) ---
PARKING_SLOTS = {
    '1': [(276, 118), (2, 358), (396, 436), (489, 148)],
    '2': [(545, 121), (513, 459), (957, 466), (824, 122)],
}

# --- Timing & Retry Configuration ---
OCR_TRIGGER_DELAY = 15  # Seconds before triggering OCR after car entry
OCR_RETRY_INTERVAL = 10 # Seconds between OCR retries if failed
MAX_OCR_ATTEMPTS = 3    # Maximum number of OCR attempts per vehicle

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
    """Performs OCR on license plate image using OpenAI GPT-4o-mini."""
    base64_image = encode_image_to_base64(image)
    if not base64_image:
        return "UNREADABLE"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }

    # This prompt asks the AI to reconstruct the plate, making it more resilient
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analyze this image for a Sri Lankan license plate. The format is typically 2-3 letters and 4 numbers (e.g., 'CBB 4567'). The text may be fragmented. Please piece together the most likely license plate number from all visible characters. Return only the final, combined plate number in the format 'ABC1234'. If a valid plate cannot be constructed, return 'UNREADABLE'."
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                    }
                ]
            }
        ],
        "max_tokens": 50,
        "temperature": 0.1
    }

    try:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            result = response.json()
            plate_text = result['choices'][0]['message']['content'].strip().upper()
            # Clean up potential markdown or extra text from the AI
            plate_text = re.sub(r'[^A-Z0-9]', '', plate_text)
            
            # Final validation check
            if re.match(r'^[A-Z]{2,3}[0-9]{4}$', plate_text):
                # Format the plate with a space between letters and numbers
                letters = re.match(r'^[A-Z]{2,3}', plate_text).group()
                numbers = plate_text[len(letters):]
                formatted_plate = f"{letters} {numbers}"
                return formatted_plate
            else:
                logging.warning(f"OpenAI returned a non-standard format: '{plate_text}'")
                return "UNREADABLE"
        else:
            logging.error(f"OpenAI API error: {response.status_code} - {response.text}")
            return "UNREADABLE"
    except Exception as e:
        logging.error(f"Error during OpenAI OCR request: {e}")
        return "UNREADABLE"


# =================================================================================
# --- CORE WORKFLOW FUNCTIONS (FROM LIVEDETECT_VIDEO.PY) ---
# =================================================================================

def detect_vehicle_type(frame, bbox):
    """Detect vehicle type using YOLO model."""
    try:
        x1, y1, x2, y2 = bbox
        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            return "Unknown"
        
        results = CAR_DETECTION_MODEL.predict(vehicle_crop, verbose=False)[0]
        boxes = results.boxes.data.cpu().numpy()
        
        if len(boxes) > 0:
            best_detection = max(boxes, key=lambda x: x[4]) # Get highest confidence
            class_id = int(best_detection[5])
            confidence = best_detection[4]
            
            if confidence > 0.5:
                class_name = results.names[class_id]
                if class_name in VEHICLE_CLASSES:
                    return class_name.title()
        return "Unknown"
    except Exception as e:
        logging.error(f"Error detecting vehicle type: {e}")
        return "Unknown"


def save_slot_status_to_file():
    """Save current slot status to JSON file for the Flask backend to read."""
    try:
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
        logging.info("slot_status.json updated: " + json.dumps(serializable_status))
    except Exception as e:
        logging.error(f"Error saving slot status to file: {e}")


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
                plate_crop = crop_image[py1:py2, px1:px2]
        else:
            pred = max(predictions, key=lambda x: x['confidence'])
            logging.info(f"Roboflow detected plate for Slot {slot_id} with confidence {pred['confidence']:.3f}")
            px1, py1 = int(pred['x'] - pred['width'] / 2), int(pred['y'] - pred['height'] / 2)
            px2, py2 = int(pred['x'] + pred['width'] / 2), int(pred['y'] + pred['height'] / 2)
            plate_crop = crop_image[py1:py2, px1:px2]

        if plate_crop is None or plate_crop.size == 0:
            logging.error(f"All plate detection methods failed for Slot {slot_id}. Could not crop plate.")
            return ""

        debug_path = f"debug_plates/slot_{slot_id}_{timestamp}.png"
        cv2.imwrite(debug_path, plate_crop)
        logging.info(f"Saved plate crop to {debug_path} for OCR.")

        # 3. Call the OpenAI function on the successfully cropped plate
        plate_text = read_plate_with_openai(plate_crop)

        if plate_text and plate_text != "UNREADABLE":
             logging.info(f"✓ OpenAI successfully read plate for Slot {slot_id}: '{plate_text}'")
             return plate_text
        else:
            logging.warning(f"✗ OpenAI could not read the license plate for Slot {slot_id}.")
            return ""

    except Exception as e:
        logging.error(f"Critical error in OpenAI processing for Slot {slot_id}: {e}")
        return ""


# =================================================================================
# --- MAIN DETECTION LOOP ---
# =================================================================================

def main():
    """
    Main function for the parking detection system, using the robust workflow
    from livedetect_video.py and the OpenAI OCR engine.
    """
    global unknown_counter, slot_status, is_detection_running
    logging.info("=== STARTING HYBRID PARKING DETECTION SYSTEM (ROBOFLOW + OPENAI) ===")
    
    # --- Video Source Configuration ---
    try:
        from config_video import VIDEO_SOURCE
        video_source = VIDEO_SOURCE
    except ImportError:
        video_source = 'new2.mp4'  # Fallback video file
    
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        logging.error(f"Error opening video source: '{video_source}'")
        return

    logging.info(f"Video capture initialized for '{video_source}'")

    try:
        while cap.isOpened() and is_detection_running:
            start_time = time.time()
            ret, frame = cap.read()
            if not ret:
                logging.info("End of video file. Restarting...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            frame = cv2.resize(frame, (1020, 500))
            h, w = frame.shape[:2]
            left_half = frame[:, :w // 2]
            right_half = frame[:, w // 2:]

            results = CAR_DETECTION_MODEL.predict(frame, verbose=False)[0]
            boxes = results.boxes.data.cpu().numpy()

            current_occupancy = {slot_id: False for slot_id in PARKING_SLOTS}
            cars_in_slots = {slot_id: None for slot_id in PARKING_SLOTS}

            for box in boxes:
                x1, y1, x2, y2, score, cls_id = box
                if results.names[int(cls_id)] in VEHICLE_CLASSES:
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    for slot_id, area in PARKING_SLOTS.items():
                        if cv2.pointPolygonTest(np.array(area, np.int32), (cx, cy), False) >= 0:
                            current_occupancy[slot_id] = True
                            cars_in_slots[slot_id] = (int(x1), int(y1), int(x2), int(y2))
                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                            break

            current_time = time.time()
            for slot_id in PARKING_SLOTS:
                status = slot_status[slot_id]
                buffer = exit_buffer[slot_id]

                # --- Vehicle Exit Logic (with buffer) ---
                if current_occupancy[slot_id]:
                    buffer["last_seen"] = current_time
                    buffer["buffer_start"] = None
                elif status["occupied"] and buffer["last_seen"]:
                    if buffer["buffer_start"] is None:
                        buffer["buffer_start"] = current_time
                    elif current_time - buffer["buffer_start"] >= buffer["buffer_duration"]:
                        logging.info(f"🚗💨 Car left Slot {slot_id}. Plate was: {status.get('license_plate', 'N/A')}")
                        slot_status[slot_id] = {k: None for k in status}
                        slot_status[slot_id]['occupied'] = False
                        slot_status[slot_id]['ocr_attempts'] = 0
                        buffer["last_seen"] = None
                        buffer["buffer_start"] = None
                        save_slot_status_to_file()

                # --- Vehicle Entry Logic ---
                if current_occupancy[slot_id] and not status["occupied"]:
                    logging.info(f"🚗 Car entered Slot {slot_id}")
                    status.update({
                        "occupied": True, "entry_time": current_time,
                        "car_bbox": cars_in_slots[slot_id],
                        "vehicle_type": detect_vehicle_type(frame, cars_in_slots[slot_id]),
                        "ocr_triggered": False, "license_plate": None,
                        "parked_time_start": None, "last_ocr_attempt": None,
                        "ocr_attempts": 0
                    })
                    buffer["last_seen"] = current_time
                    save_slot_status_to_file()

                # --- OCR Trigger and Retry Logic ---
                elif current_occupancy[slot_id] and status["occupied"] and not status["license_plate"]:
                    time_since_entry = current_time - status["entry_time"]
                    
                    # Check if it's time to try OCR
                    is_first_attempt = (status['ocr_attempts'] == 0 and time_since_entry > OCR_TRIGGER_DELAY)
                    is_retry_time = (status['ocr_attempts'] > 0 and 
                                     current_time - status['last_ocr_attempt'] > OCR_RETRY_INTERVAL)

                    if (is_first_attempt or is_retry_time) and status['ocr_attempts'] < MAX_OCR_ATTEMPTS:
                        status["ocr_attempts"] += 1
                        status["last_ocr_attempt"] = current_time
                        logging.info(f"🔍 Triggering OpenAI OCR for Slot {slot_id} (Attempt {status['ocr_attempts']})...")

                        crop_image = left_half if slot_id == '1' else right_half
                        if crop_image.size > 0:
                            plate_text = process_plate_with_openai(slot_id, crop_image)
                            if plate_text:
                                status["license_plate"] = plate_text
                                status["parked_time_start"] = current_time
                                logging.info(f"✅ OCR Success for Slot {slot_id}: '{plate_text}'")
                            else:
                                logging.warning(f"❌ OCR Attempt {status['ocr_attempts']} failed for Slot {slot_id}.")
                            save_slot_status_to_file()
                    
                    # Handle max attempts reached
                    elif status['ocr_attempts'] >= MAX_OCR_ATTEMPTS and not status['license_plate']:
                        status["license_plate"] = f"Unknown_{unknown_counter}"
                        logging.error(f"❌ Max OCR attempts reached for Slot {slot_id}. Marked as '{status['license_plate']}'.")
                        
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        error_path = f"error_vehicles/slot_{slot_id}_unknown_{unknown_counter}_{timestamp}.jpg"
                        crop_image = left_half if slot_id == '1' else right_half
                        cv2.imwrite(error_path, crop_image)
                        unknown_counter += 1
                        save_slot_status_to_file()


            # --- Drawing Overlays ---
            for slot_id, area in PARKING_SLOTS.items():
                status = slot_status.get(slot_id, {})
                color = (0, 255, 0) if not status.get("occupied") else (0, 0, 255)
                cv2.polylines(frame, [np.array(area, np.int32)], True, color, 2)
                
                text = f"S{slot_id}: "
                if status.get("occupied"):
                    text += f"{status.get('vehicle_type', '')} - "
                    if status.get("license_plate"):
                        text += status['license_plate']
                    else:
                        text += f"Proc... (A:{status.get('ocr_attempts', 0)})"
                else:
                    text += "Free"
                
                text_pos = (area[0][0], area[0][1] - 10)
                cv2.putText(frame, text, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            
            cv2.putText(frame, f"FPS: {int(1 / (time.time() - start_time))}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.imshow("Hybrid AI Parking System (OpenAI)", frame)

            if cv2.waitKey(1) & 0xFF == 27:
                logging.info("ESC key pressed. Exiting.")
                break

    except KeyboardInterrupt:
        logging.info("Process interrupted by user (Ctrl+C).")
    finally:
        is_detection_running = False
        cap.release()
        cv2.destroyAllWindows()
        logging.info("System shut down gracefully.")


if __name__ == "__main__":
    main() 