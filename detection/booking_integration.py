"""
Booking Integration Module
Connects the live detection system with the booking system
"""

import requests
import json
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BookingInfo:
    """Class to hold booking information"""
    def __init__(self, order_id, slot_number, license_plate, customer_name, start_time, end_time, date, status, is_pre_booked=False):
        self.order_id = order_id
        self.slot_number = slot_number
        self.license_plate = license_plate
        self.customer_name = customer_name
        self.start_time = start_time
        self.end_time = end_time
        self.date = date
        self.status = status
        self.is_pre_booked = is_pre_booked
        self.actual_arrival_time = None
        self.actual_departure_time = None

class MockBookingSystem:
    """Simple mock booking system for testing when the main booking system is not available"""
    
    def __init__(self):
        self.active_bookings = {
            "1": BookingInfo(
                order_id="MOCK001",
                slot_number="1",
                license_plate="ABC1234",
                customer_name="John Doe",
                start_time="09:00",
                end_time="17:00",
                date="2024-01-15",
                status="confirmed",
                is_pre_booked=True
            )
            # Slot 2 is not booked (removed from mock data)
        }
        logger.info("Mock booking system initialized with test data - only slot 1 booked")
    
    def get_active_bookings(self):
        """Get currently active bookings"""
        return self.active_bookings
    
    def validate_vehicle_arrival(self, slot_id, license_plate):
        """Validate if a vehicle matches the booking for a slot"""
        booking = self.active_bookings.get(slot_id)
        
        if booking:
            if booking.license_plate.upper() == license_plate.upper():
                return {
                    "valid": True,
                    "booking": booking,
                    "reason": "Vehicle matches booking"
                }
            else:
                return {
                    "valid": False,
                    "booking": booking,
                    "reason": "License plate mismatch"
                }
        else:
            return {
                "valid": False,
                "booking": None,
                "reason": "No booking for this slot"
            }
    
    def check_booking_conflicts(self, slot_id, license_plate):
        """Check for booking conflicts"""
        booking = self.active_bookings.get(slot_id)
        
        if booking:
            if booking.license_plate.upper() != license_plate.upper():
                return {
                    "has_conflict": True,
                    "expected_plate": booking.license_plate,
                    "customer_name": booking.customer_name,
                    "order_id": booking.order_id
                }
        
        return {
            "has_conflict": False,
            "expected_plate": None,
            "customer_name": None,
            "order_id": None
        }
    
    def get_booking_statistics(self):
        """Get booking system statistics"""
        return {
            "total_bookings": len(self.active_bookings),
            "active_bookings": len(self.active_bookings),
            "revenue": 5000
        }
    
    def get_booking_display_message(self, slot_id):
        """Get booking display message for P10 display"""
        booking = self.active_bookings.get(slot_id)
        
        if booking:
            return f"BOOKED | {booking.customer_name[:10]}"
        else:
            return "AVAILABLE"

class BookingSystemIntegration:
    def __init__(self, base_url="http://localhost:5001", use_mock=False):
        """
        Initialize the booking system integration
        
        Args:
            base_url (str): Base URL of the booking system API
            use_mock (bool): Whether to use mock booking system for testing
        """
        self.base_url = base_url
        self.use_mock = use_mock
        
        if use_mock:
            self.mock_system = MockBookingSystem()
            logger.info("Using mock booking system for testing")
        else:
            self.session = requests.Session()
            self.session.headers.update({
                'Content-Type': 'application/json'
            })
            logger.info(f"Connecting to booking system at {base_url}")
    
    def get_active_bookings(self):
        """
        Get currently active bookings
        
        Returns:
            dict: Dictionary of slot_id -> BookingInfo objects
        """
        if self.use_mock:
            return self.mock_system.get_active_bookings()
        
        try:
            url = f"{self.base_url}/api/parking/slot-status"
            response = self.session.get(url, timeout=5)  # Add timeout
            response.raise_for_status()
            
            result = response.json()
            active_bookings = {}
            
            if result.get("success") and "data" in result:
                slot_status = result["data"].get("slotStatus", {})
                for slot_id, slot_data in slot_status.items():
                    if slot_data.get("isBooked"):
                        booking = BookingInfo(
                            order_id=slot_data.get("orderId", ""),
                            slot_number=slot_id,
                            license_plate=slot_data.get("expectedPlate", ""),
                            customer_name=slot_data.get("customerName", ""),
                            start_time=slot_data.get("startTime", ""),
                            end_time=slot_data.get("endTime", ""),
                            date=slot_data.get("date", ""),
                            status=slot_data.get("status", ""),
                            is_pre_booked=slot_data.get("isPreBooked", False)
                        )
                        active_bookings[slot_id] = booking
            
            return active_bookings
            
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Booking system not available at {self.base_url}: {e}")
            logger.info("Falling back to mock booking system")
            # Fallback to mock system - only log once
            if not hasattr(self, '_fallback_logged'):
                self._fallback_logged = True
                logger.info("Switching to mock booking system for this session")
            self.use_mock = True
            self.mock_system = MockBookingSystem()
            return self.mock_system.get_active_bookings()
        except requests.exceptions.Timeout as e:
            logger.warning(f"Booking system timeout at {self.base_url}: {e}")
            # Fallback to mock system on timeout too
            if not hasattr(self, '_fallback_logged'):
                self._fallback_logged = True
                logger.info("Switching to mock booking system due to timeout")
            self.use_mock = True
            self.mock_system = MockBookingSystem()
            return self.mock_system.get_active_bookings()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get active bookings: {e}")
            return {}
    
    def validate_vehicle_arrival(self, slot_id, license_plate):
        """
        Validate if a vehicle matches the booking for a slot
        
        Args:
            slot_id (str): Slot ID (1 or 2)
            license_plate (str): Detected license plate
            
        Returns:
            dict: Validation result with booking info if valid
        """
        if self.use_mock:
            return self.mock_system.validate_vehicle_arrival(slot_id, license_plate)
        
        try:
            # Map parking system slot ID to booking system format
            booking_slot_id = f"Slot {slot_id}"
            
            # Get current slot status from booking system
            slot_status_response = self.get_slot_status()
            if not slot_status_response.get("success"):
                return {
                    "valid": False,
                    "booking": None,
                    "reason": "Failed to get slot status from booking system"
                }
            
            slot_status = slot_status_response.get("data", {}).get("slotStatus", {})
            booking_data = slot_status.get(slot_id)
            
            if booking_data:
                # Create BookingInfo object from booking data
                booking = BookingInfo(
                    order_id=booking_data.get("orderId", ""),
                    slot_number=slot_id,
                    license_plate=booking_data.get("expectedPlate", ""),
                    customer_name=booking_data.get("customerName", ""),
                    start_time=booking_data.get("startTime", ""),
                    end_time=booking_data.get("endTime", ""),
                    date=booking_data.get("date", ""),
                    status=booking_data.get("status", "confirmed"),
                    is_pre_booked=True
                )
                
                if booking.license_plate.upper() == license_plate.upper():
                    return {
                        "valid": True,
                        "booking": booking,
                        "reason": "Vehicle matches booking"
                    }
                else:
                    return {
                        "valid": False,
                        "booking": booking,
                        "reason": "License plate mismatch"
                    }
            else:
                return {
                    "valid": False,
                    "booking": None,
                    "reason": "No booking for this slot"
                }
                
        except Exception as e:
            logger.error(f"Error validating vehicle arrival: {e}")
            return {
                "valid": False,
                "booking": None,
                "reason": f"Validation error: {str(e)}"
            }
    
    def check_booking_conflicts(self, slot_id, license_plate):
        """
        Check for booking conflicts
        
        Args:
            slot_id (str): Slot ID (1 or 2)
            license_plate (str): Detected license plate
            
        Returns:
            dict: Conflict check result
        """
        if self.use_mock:
            return self.mock_system.check_booking_conflicts(slot_id, license_plate)
        
        try:
            # Get current slot status from booking system
            slot_status_response = self.get_slot_status()
            if not slot_status_response.get("success"):
                return {
                    "has_conflict": False,
                    "expected_plate": None,
                    "customer_name": None,
                    "order_id": None
                }
            
            slot_status = slot_status_response.get("data", {}).get("slotStatus", {})
            booking_data = slot_status.get(slot_id)
            
            if booking_data:
                expected_plate = booking_data.get("expectedPlate", "")
                if expected_plate.upper() != license_plate.upper():
                    return {
                        "has_conflict": True,
                        "expected_plate": expected_plate,
                        "customer_name": booking_data.get("customerName", ""),
                        "order_id": booking_data.get("orderId", "")
                    }
            
            return {
                "has_conflict": False,
                "expected_plate": None,
                "customer_name": None,
                "order_id": None
            }
            
        except Exception as e:
            logger.error(f"Error checking booking conflicts: {e}")
            return {
                "has_conflict": False,
                "expected_plate": None,
                "customer_name": None,
                "order_id": None
            }
    
    def update_booking_arrival(self, slot_id, booking):
        """
        Update booking with arrival time
        
        Args:
            slot_id (str): Slot ID
            booking (BookingInfo): Booking object
            
        Returns:
            bool: Success status
        """
        if self.use_mock:
            logger.info(f"Mock: Updated booking {booking.order_id} arrival for slot {slot_id}")
            return True
        
        try:
            url = f"{self.base_url}/api/parking/update-arrival"
            data = {
                "orderId": booking.order_id,
                "slotId": slot_id,
                "arrivalTime": datetime.now().isoformat()
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            return result.get("success", False)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update booking arrival: {e}")
            return False
    
    def update_booking_departure(self, slot_id, booking):
        """
        Update booking with departure time
        
        Args:
            slot_id (str): Slot ID
            booking (BookingInfo): Booking object
            
        Returns:
            bool: Success status
        """
        if self.use_mock:
            logger.info(f"Mock: Updated booking {booking.order_id} departure for slot {slot_id}")
            return True
        
        try:
            url = f"{self.base_url}/api/parking/update-departure"
            data = {
                "orderId": booking.order_id,
                "slotId": slot_id,
                "departureTime": datetime.now().isoformat()
            }
            
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            return result.get("success", False)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update booking departure: {e}")
            return False
    
    def get_booking_statistics(self):
        """
        Get booking system statistics
        
        Returns:
            dict: Statistics
        """
        if self.use_mock:
            return self.mock_system.get_booking_statistics()
        
        try:
            url = f"{self.base_url}/api/parking/statistics"
            response = self.session.get(url)
            response.raise_for_status()
            
            result = response.json()
            return result.get("data", {})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get booking statistics: {e}")
            return {}
    
    def get_booking_display_message(self, slot_id):
        """
        Get booking display message for P10 display
        
        Args:
            slot_id (str): Slot ID
            
        Returns:
            str: Display message
        """
        if self.use_mock:
            return self.mock_system.get_booking_display_message(slot_id)
        
        try:
            active_bookings = self.get_active_bookings()
            booking = active_bookings.get(slot_id)
            
            if booking:
                return f"BOOKED | {booking.customer_name[:10]}"
            else:
                return "AVAILABLE"
                
        except Exception as e:
            logger.error(f"Error getting booking display message: {e}")
            return "ERROR"

    def send_unauthorized_vehicle_alert(self, slot_number, detected_plate, timestamp=None):
        """
        Send unauthorized vehicle alert to booking system
        
        Args:
            slot_number (str): Slot number (1 or 2)
            detected_plate (str): Detected license plate
            timestamp (str, optional): Timestamp of detection
            
        Returns:
            dict: API response
        """
        if self.use_mock:
            logger.info(f"Mock: Unauthorized vehicle alert - Slot {slot_number}, Plate {detected_plate}")
            return {"success": True, "message": "Mock alert sent"}
        
        try:
            # Map parking system slot number to booking system format
            booking_slot_number = f"Slot {slot_number}"
            
            url = f"{self.base_url}/api/parking/unauthorized-vehicle"
            data = {
                "slotNumber": booking_slot_number,
                "detectedPlate": detected_plate,
                "timestamp": timestamp or datetime.now().isoformat()
            }
            
            logger.info(f"Sending unauthorized vehicle alert: {data}")
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Unauthorized vehicle alert sent successfully: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send unauthorized vehicle alert: {e}")
            return {"success": False, "error": str(e)}
    
    def send_slot_conflict_alert(self, slot_number, detected_plates, timestamp=None):
        """
        Send slot conflict alert to booking system
        
        Args:
            slot_number (str): Slot number (1 or 2)
            detected_plates (list): List of detected license plates
            timestamp (str, optional): Timestamp of detection
            
        Returns:
            dict: API response
        """
        if self.use_mock:
            logger.info(f"Mock: Slot conflict alert - Slot {slot_number}, Plates {detected_plates}")
            return {"success": True, "message": "Mock conflict alert sent"}
        
        try:
            # Map parking system slot number to booking system format
            booking_slot_number = f"Slot {slot_number}"
            
            url = f"{self.base_url}/api/parking/slot-conflict"
            data = {
                "slotNumber": booking_slot_number,
                "detectedPlates": detected_plates,
                "timestamp": timestamp or datetime.now().isoformat()
            }
            
            logger.info(f"Sending slot conflict alert: {data}")
            response = self.session.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Slot conflict alert sent successfully: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send slot conflict alert: {e}")
            return {"success": False, "error": str(e)}
    
    def get_slot_status(self, date=None):
        """
        Get current slot status from booking system
        
        Args:
            date (str, optional): Date in YYYY-MM-DD format
            
        Returns:
            dict: Current slot status
        """
        if self.use_mock:
            # Return mock slot status based on actual mock data
            active_bookings = self.mock_system.get_active_bookings()
            slot_status = {}
            
            # Add booked slots
            for slot_id, booking in active_bookings.items():
                slot_status[slot_id] = {
                    "isBooked": True,
                    "orderId": booking.order_id,
                    "expectedPlate": booking.license_plate,
                    "customerName": booking.customer_name,
                    "startTime": booking.start_time,
                    "endTime": booking.end_time,
                    "date": booking.date,
                    "status": booking.status,
                    "isPreBooked": booking.is_pre_booked
                }
            
            return {
                "success": True,
                "data": {
                    "slotStatus": slot_status
                }
            }
        
        try:
            url = f"{self.base_url}/api/parking/slot-status"
            params = {}
            if date:
                params["date"] = date
            
            logger.info(f"Getting slot status for date: {date or 'today'}")
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Slot status retrieved successfully: {result}")
            
            # Map booking system slot format to parking system format
            if result.get("success") and "data" in result:
                booking_slot_status = result["data"].get("slotStatus", {})
                parking_slot_status = {}
                
                # Map "Slot 1" -> "1", "Slot 2" -> "2"
                for booking_slot, booking_data in booking_slot_status.items():
                    if booking_data is not None:  # Only process if slot is booked
                        # Clean up slot name (handle cases like "Slot Slot 2")
                        clean_slot = booking_slot.replace("Slot ", "").replace("Slot", "").strip()
                        if clean_slot == "1":
                            parking_slot_status["1"] = {
                                "isBooked": True,
                                "orderId": booking_data.get("orderId", booking_data.get("bookingId", "")),
                                "expectedPlate": booking_data.get("expectedPlate", ""),
                                "customerName": booking_data.get("customerName", ""),
                                "vehicleModel": booking_data.get("vehicleModel", ""),
                                "vehicleMake": booking_data.get("vehicleMake", ""),
                                "ownerName": booking_data.get("ownerName", booking_data.get("customerName", "")),
                                "startTime": booking_data.get("startTime", ""),
                                "endTime": booking_data.get("endTime", ""),
                                "date": result["data"].get("date", ""),
                                "status": "confirmed",
                                "isPreBooked": True
                            }
                        elif clean_slot == "2":
                            parking_slot_status["2"] = {
                                "isBooked": True,
                                "orderId": booking_data.get("orderId", booking_data.get("bookingId", "")),
                                "expectedPlate": booking_data.get("expectedPlate", ""),
                                "customerName": booking_data.get("customerName", ""),
                                "vehicleModel": booking_data.get("vehicleModel", ""),
                                "vehicleMake": booking_data.get("vehicleMake", ""),
                                "ownerName": booking_data.get("ownerName", booking_data.get("customerName", "")),
                                "startTime": booking_data.get("startTime", ""),
                                "endTime": booking_data.get("endTime", ""),
                                "date": result["data"].get("date", ""),
                                "status": "confirmed",
                                "isPreBooked": True
                            }
                    # If booking_data is None, the slot is free (no need to add to parking_slot_status)
                
                result["data"]["slotStatus"] = parking_slot_status
            
            return result
            
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Booking system not available at {self.base_url}: {e}")
            # Fallback to mock system - only log once
            if not hasattr(self, '_fallback_logged'):
                self._fallback_logged = True
                logger.info("Switching to mock booking system for this session")
            self.use_mock = True
            self.mock_system = MockBookingSystem()
            return self.get_slot_status(date)
        except requests.exceptions.Timeout as e:
            logger.warning(f"Booking system timeout at {self.base_url}: {e}")
            return {"success": False, "error": "Booking system timeout"}
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get slot status: {e}")
            return {"success": False, "error": str(e)}
    
    def send_booking_reminder(self, booking_id, admin_token=None):
        """
        Send booking reminder SMS (requires admin authentication)
        
        Args:
            booking_id (str): Booking ID
            admin_token (str, optional): Admin JWT token
            
        Returns:
            dict: API response
        """
        if self.use_mock:
            logger.info(f"Mock: Booking reminder sent for booking {booking_id}")
            return {"success": True, "message": "Mock reminder sent"}
        
        try:
            url = f"{self.base_url}/api/parking/send-reminder"
            data = {"bookingId": booking_id}
            
            headers = {}
            if admin_token:
                headers["Authorization"] = f"Bearer {admin_token}"
            
            logger.info(f"Sending booking reminder for booking: {booking_id}")
            response = self.session.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Booking reminder sent successfully: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send booking reminder: {e}")
            return {"success": False, "error": str(e)}
    
    def check_booking_system_health(self):
        """
        Check if booking system is running and healthy
        
        Returns:
            dict: Health check response
        """
        if self.use_mock:
            return {"status": "OK", "message": "Mock booking system is running"}
        
        try:
            url = f"{self.base_url}/api/health"
            response = self.session.get(url)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Booking system health check: {result}")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Booking system health check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

def get_booking_integration(base_url="http://localhost:5001", use_mock=False):
    """
    Factory function to get booking integration instance
    
    Args:
        base_url (str): Base URL of the booking system API
        use_mock (bool): Whether to use mock booking system for testing
    
    Returns:
        BookingSystemIntegration: Booking integration instance
    """
    return BookingSystemIntegration(base_url, use_mock)

# Example usage functions
def example_unauthorized_vehicle_detection():
    """Example of how to use unauthorized vehicle detection"""
    integration = BookingSystemIntegration()
    
    # Simulate unauthorized vehicle detection
    result = integration.send_unauthorized_vehicle_alert(
        slot_number="Slot 1",
        detected_plate="XYZ789",
        timestamp=datetime.now().isoformat()
    )
    
    print("Unauthorized vehicle detection result:", json.dumps(result, indent=2))

def example_slot_conflict_detection():
    """Example of how to use slot conflict detection"""
    integration = BookingSystemIntegration()
    
    # Simulate slot conflict detection
    result = integration.send_slot_conflict_alert(
        slot_number="Slot 1",
        detected_plates=["ABC123", "XYZ789"],
        timestamp=datetime.now().isoformat()
    )
    
    print("Slot conflict detection result:", json.dumps(result, indent=2))

def example_get_slot_status():
    """Example of how to get current slot status"""
    integration = BookingSystemIntegration()
    
    # Get current slot status
    result = integration.get_slot_status()
    
    print("Current slot status:", json.dumps(result, indent=2))

def example_health_check():
    """Example of how to check booking system health"""
    integration = BookingSystemIntegration()
    
    # Check system health
    result = integration.check_booking_system_health()
    
    print("System health:", json.dumps(result, indent=2))

# Integration with your existing parking system
def integrate_with_parking_system(detected_plate, slot_number, confidence=0.8):
    """
    Integrate with your existing parking system
    
    Args:
        detected_plate (str): Detected license plate
        slot_number (str): Slot number where vehicle was detected
        confidence (float): Detection confidence (0.0 to 1.0)
    """
    integration = BookingSystemIntegration()
    
    # Get current slot status to check if there's an active booking
    slot_status = integration.get_slot_status()
    
    if not slot_status.get("success"):
        logger.error("Failed to get slot status")
        return
    
    current_slot = slot_status["data"]["slotStatus"].get(slot_number)
    
    if current_slot:
        # There's an active booking for this slot
        expected_plate = current_slot["expectedPlate"]
        
        if detected_plate.upper() != expected_plate.upper():
            # Unauthorized vehicle detected
            logger.warning(f"Unauthorized vehicle detected in {slot_number}: {detected_plate} (expected: {expected_plate})")
            
            result = integration.send_unauthorized_vehicle_alert(
                slot_number=slot_number,
                detected_plate=detected_plate
            )
            
            if result.get("success"):
                logger.info("Unauthorized vehicle alert sent successfully")
            else:
                logger.error("Failed to send unauthorized vehicle alert")
        else:
            logger.info(f"Authorized vehicle detected in {slot_number}: {detected_plate}")
    else:
        logger.info(f"No active booking for {slot_number}, vehicle {detected_plate} detected")

if __name__ == "__main__":
    # Run examples
    print("=== Booking System Integration Examples ===\n")
    
    print("1. Health Check:")
    example_health_check()
    print()
    
    print("2. Get Slot Status:")
    example_get_slot_status()
    print()
    
    print("3. Unauthorized Vehicle Detection:")
    example_unauthorized_vehicle_detection()
    print()
    
    print("4. Slot Conflict Detection:")
    example_slot_conflict_detection()
    print()
    
    print("5. Integration with Parking System:")
    integrate_with_parking_system("XYZ789", "Slot 1", 0.9)
    print() 