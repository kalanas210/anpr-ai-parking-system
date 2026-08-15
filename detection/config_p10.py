# P10 Display Configuration
# ESP32 settings for the P10 LED matrix display.
# IP / key are read from the environment (see .env.example) so they are not
# hard-coded in source. Defaults are safe placeholders for local hardware.

import os
from dotenv import load_dotenv

load_dotenv()

# ESP32 IP address on your local network
ESP32_IP = os.getenv("ESP32_IP", "192.168.8.130")

# ESP32 authentication key - must match the key flashed into the firmware
ESP32_KEY = os.getenv("ESP32_KEY", "uom")

# Display settings
DISPLAY_WIDTH = 32  # P10 display width in pixels
DISPLAY_HEIGHT = 16  # P10 display height in pixels

# Update intervals (in seconds)
STATUS_UPDATE_INTERVAL = 5
DISPLAY_CYCLE_INTERVAL = 10
UNAUTHORIZED_WARNING_INTERVAL = 3

# Message display settings
MAX_MESSAGE_LENGTH = 16
SCROLL_SPEED = 100  # milliseconds per character

# Color settings (if supported by your P10 display)
COLORS = {
    'normal': 'green',
    'warning': 'yellow',
    'error': 'red',
    'info': 'blue'
}

# Test mode settings
TEST_MODE = False
TEST_MESSAGES = [
    "SLOT 1 BUSY",
    "SLOT 2 FREE",
    "UNAUTHORIZED",
    "VEHICLES"
]
