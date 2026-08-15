"""
Configuration for the ANPR AI Parking System (RTSP / live-camera mode).

Secrets are loaded from environment variables (see .env.example). Copy
.env.example to .env, fill in your own values, and never commit .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Secrets (from environment) ---------------------------------------------
# MongoDB Atlas connection string, e.g.
# mongodb+srv://<user>:<password>@<cluster>/?retryWrites=true&w=majority
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "parking_system")

# RTSP camera stream, e.g. rtsp://<user>:<pass>@<host>:554/Streaming/Channels/101
RTSP_URL = os.getenv("RTSP_URL", "")
# VIDEO_SOURCE defaults to the RTSP stream; override with a file path for testing.
VIDEO_SOURCE = os.getenv("VIDEO_SOURCE", RTSP_URL)

# AI service API keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY", "")
LICENSE_PLATE_MODEL_ID = os.getenv("LICENSE_PLATE_MODEL_ID", "license-plate-recognition-rxg4e/11")

# --- RTSP tuning -------------------------------------------------------------
RTSP_BUFFER_SIZE = 1  # Minimize latency
RTSP_FPS = 15  # Reduced FPS for stability
RTSP_RECONNECT_DELAY = 5  # seconds between reconnection attempts
RTSP_MAX_CONSECUTIVE_FAILURES = 10

# --- AI models ---------------------------------------------------------------
VEHICLE_CLASSES = ['car', 'truck', 'bus', 'motorcycle']
CAR_DETECTION_CONFIDENCE = 0.5
LICENSE_PLATE_CONFIDENCE = 0.4

# --- Parking slots (polygon coordinates for the 1020x500 resized frame) ------
PARKING_SLOTS = {
    '1': [(328, 115), (28, 340), (430, 426), (546, 153)],
    '2': [(601, 145), (555, 450), (1000, 484), (834, 167)],
}

# --- OCR tuning --------------------------------------------------------------
OCR_TRIGGER_DELAY = 10   # seconds a vehicle must be parked before OCR fires
OCR_RETRY_INTERVAL = 8   # seconds between OCR retries
MAX_OCR_ATTEMPTS = 4

# --- Processing --------------------------------------------------------------
PROCESSING_FPS_LIMIT = 30
FRAME_SKIP_COUNT = 2
DEBUG_FRAME_INTERVAL = 60
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

# --- Debug directories -------------------------------------------------------
DEBUG_DIRECTORIES = [
    "debug_plates",
    "debug_cars",
    "ocr_tests",
    "error_vehicles",
]

# --- P10 LED display (ESP32 on the local network) ----------------------------
P10_ENABLED = os.getenv("P10_ENABLED", "true").lower() == "true"
ESP32_IP = os.getenv("ESP32_IP", "192.168.8.130")
ESP32_KEY = os.getenv("ESP32_KEY", "uom")  # must match the key set in the ESP32 firmware

# --- Error handling ----------------------------------------------------------
MAX_STREAM_RECONNECT_ATTEMPTS = 3
STREAM_HEALTH_CHECK_INTERVAL = 15  # seconds
PROCESSING_TIMEOUT = 30  # seconds for individual operations
