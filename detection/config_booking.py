# Booking System Integration Configuration
# Configuration file for connecting booking system with parking system

# Booking System API Settings
BOOKING_API_URL = "http://localhost:5001"  # Base URL for booking system API
BOOKING_API_TIMEOUT = 10  # seconds for API requests

# Integration Settings
ENABLE_BOOKING_VALIDATION = True  # Validate vehicles against bookings
SHOW_BOOKING_INFO_ON_DISPLAY = True  # Show booking info on P10 display
AUTO_UPDATE_BOOKING_STATUS = True  # Automatically update booking arrival/departure times

# Mode Settings
BOOKING_MODE = "real"  # Options: "auto", "mock", "real"
# auto: Try real booking system first, fallback to mock if not available
# mock: Always use mock booking system for testing
# real: Always use real booking system (will fail if not available)

# Port Configuration
VIDEO_SYSTEM_PORT = 5001  # Port for app_video.py (video testing)
RTSP_SYSTEM_PORT = 5000   # Port for app.py (RTSP testing)
BOOKING_SYSTEM_PORT = 5001  # Port for booking system server

# Cache Settings
BOOKING_CACHE_DURATION = 60  # seconds to cache booking data
FORCE_REFRESH_INTERVAL = 300  # seconds to force refresh booking data

# Display Settings
BOOKING_DISPLAY_DURATION = 15  # seconds to show booking info on P10 display
SHOW_CUSTOMER_INITIALS = True  # Show customer initials instead of full name

# Conflict Detection
ENABLE_CONFLICT_DETECTION = True  # Detect unauthorized vehicles in booked slots
LOG_CONFLICTS = True  # Log booking conflicts
NOTIFY_ON_CONFLICTS = True  # Send notifications for conflicts

# Debug Settings
DEBUG_BOOKING_REQUESTS = True  # Set to False to reduce logging
LOG_BOOKING_VALIDATIONS = True

# Mock Booking Data (for testing)
MOCK_BOOKINGS = {
    "1": {
        "order_id": "MOCK001",
        "license_plate": "ABC1234",
        "customer_name": "John Doe",
        "start_time": "09:00",
        "end_time": "17:00",
        "date": "2024-01-15",
        "status": "confirmed"
    }
    # Slot 2 is not booked (removed from mock data)
} 