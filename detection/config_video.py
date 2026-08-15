"""
Configuration for the ANPR AI Parking System (offline video-file / demo mode).

Secrets are loaded from environment variables (see .env.example). Copy
.env.example to .env, fill in your own values, and never commit .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Secrets (from environment) ---------------------------------------------
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "parking_system")

# Path to a local video file to process (place your own test clip alongside the
# detection scripts and point VIDEO_SOURCE at it).
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", "test.mp4")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "")
LICENSE_PLATE_MODEL_ID = os.getenv("LICENSE_PLATE_MODEL_ID", "license-plate-recognition-rxg4e/11")

# --- AI models ---------------------------------------------------------------
VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle']
CAR_DETECTION_CONFIDENCE = 0.5
LICENSE_PLATE_CONFIDENCE = 0.4

# --- Parking slots (polygon coordinates for the 1020x500 resized frame) ------
PARKING_SLOTS = {
    '1': [(525, 252), (557, 426), (7, 428), (141, 224)],
    '2': [(538, 243), (568, 430), (1010, 435), (840, 253)],
}

# --- OCR ---------------------------------------------------------------------
DEFAULT_OCR_METHOD = "EasyOCR"  # Options: "EasyOCR", "OpenAI"
OCR_RETRY_ATTEMPTS = 3
OCR_DELAY_BETWEEN_ATTEMPTS = 2  # seconds

# --- Processing --------------------------------------------------------------
PROCESSING_DELAY = 0.1
VIDEO_RESIZE_WIDTH = 1020
VIDEO_RESIZE_HEIGHT = 500

# --- Web server --------------------------------------------------------------
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# --- Logging -----------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = "[%(asctime)s] %(message)s"

# --- Database retention (days) -----------------------------------------------
PARKING_RECORDS_RETENTION = 30
UNKNOWN_VEHICLES_RETENTION = 7

# --- License plate validation ------------------------------------------------
LICENSE_PLATE_PATTERN = r'^[A-Z]{2,3}\s*[0-9]{4}$'
PROVINCIAL_CODES = ['WP', 'SP', 'CP', 'NP', 'EP', 'NC', 'NW', 'UP', 'SG']

# --- Image processing --------------------------------------------------------
MIN_PLATE_WIDTH = 40
MIN_PLATE_HEIGHT = 15
MAX_TEXT_HEIGHT_RATIO = 0.85
MIN_CONFIDENCE = 0.3

# --- P10 LED display (ESP32 on the local network) ----------------------------
P10_ENABLED = os.getenv("P10_ENABLED", "true").lower() == "true"
ESP32_IP = os.getenv("ESP32_IP", "192.168.8.130")
ESP32_KEY = os.getenv("ESP32_KEY", "uom")

# --- Debug directories -------------------------------------------------------
DEBUG_DIRECTORIES = [
    "debug_plates",
    "debug_cars",
    "ocr_tests",
    "error_vehicles",
]
