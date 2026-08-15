import requests
import time
import logging
from typing import Dict, Any, Optional
from threading import Thread, Lock, Event
import json

class P10DisplayManager:
    """
    P10 Display Manager for AI Parking System
    Handles visual feedback display with minimal ESP32 requests
    """
    
    def __init__(self, esp32_ip: str = "192.168.8.130", key: str = "uom"):
        """
        Initialize P10 Display Manager
        
        Args:
            esp32_ip: IP address of ESP32 with P10 display
            key: Authentication key for ESP32
        """
        self.esp32_ip = esp32_ip
        self.key = key
        self.base_url = f"http://{esp32_ip}/setText"
        
        # Display state management
        self.current_message = ""
        self.current_mode = ""
        self.last_sent_message = ""
        self.display_lock = Lock()
        
        # Slot tracking
        self.slot_status = {
            "1": {"occupied": False, "license_plate": None, "entering": False, "exiting": False},
            "2": {"occupied": False, "license_plate": None, "entering": False, "exiting": False}
        }
        
        # Display cycle control
        self.display_thread = None
        self.display_event = Event()
        self.cycle_running = False
        self.current_display_type = "status"  # status, entering, plate_detected, exiting, alternating, unauthorized_warning, attention_conflict
        self.display_start_time = 0
        self.plate_display_duration = 25  # seconds to show plate after detection
        self.event_display_duration = 15  # seconds to show entering/exiting messages
        self.status_display_duration = 30  # seconds to show slot status
        self.alternating_display_duration = 20  # seconds to show license plates in alternating mode
        self.is_showing_status = True  # Track if currently showing status or plates
        self.current_plate_index = 0  # Track which occupied slot plate to show next
        
        # Unauthorized vehicle tracking
        self.unauthorized_slots = set()  # Track slots with unauthorized vehicles
        self.conflict_warning_displayed = set()  # Track which conflict warnings have been shown
        self.current_unauthorized_slot_index = 0  # Track which unauthorized slot to show next
        # Audio alert tracking
        self.audio_alert_active = False
        self.last_audio_start_time = 0.0
        
        # Booking integration (lazy-loaded)
        self._booking_integration = None
        
        logging.info(f"P10 Display Manager initialized for ESP32 at {esp32_ip}")
    
    def _get_booking_integration(self):
        """Get booking integration with consistent configuration"""
        # Initialize if not exists (for backward compatibility)
        if not hasattr(self, '_booking_integration'):
            self._booking_integration = None
            
        if self._booking_integration is None:
            try:
                from booking_integration import get_booking_integration
                from config_booking import BOOKING_MODE, BOOKING_API_URL
                
                # Use the same booking integration configuration as the main app
                if BOOKING_MODE == "mock":
                    self._booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=True)
                    logging.info("🔧 P10 Display: Booking integration loaded in MOCK mode")
                elif BOOKING_MODE == "real":
                    self._booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=False)
                    logging.info("🔧 P10 Display: Booking integration loaded in REAL mode")
                else:  # auto mode
                    self._booking_integration = get_booking_integration(base_url=BOOKING_API_URL, use_mock=False)
                    logging.info("🔧 P10 Display: Booking integration loaded in AUTO mode")
            except Exception as e:
                logging.warning(f"🔧 P10 Display: Failed to load booking integration: {e}")
                self._booking_integration = None
        
        return self._booking_integration
    
    def send_to_display(self, mode: str, first_text: str, second_text: str = "", first_pos: int = 0) -> bool:
        """
        Send display command to ESP32 P10 display
        
        Args:
            mode: Display mode (DBS=static, DBA=both animated, DBM=mixed)
            first_text: Text for first row
            second_text: Text for second row
            first_pos: Position for first row text
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create message string based on mode
            if mode == "DBS":  # Double Row Bold Static
                message = f"{self.key},{mode},{first_text},{first_pos},{second_text}"
            elif mode == "DBM":  # Double Row Bold Mixed (first static, second animated)
                message = f"{self.key},{mode},{first_text},{first_pos},{second_text}"
            elif mode == "DBA":  # Double Row Bold Animated (both animated)
                message = f"{self.key},{mode},{first_text},{first_pos},{second_text}"
            else:
                logging.error(f"Unknown display mode: {mode}")
                return False
                
            # Check if this is the same message we just sent
            if message == self.last_sent_message:
                logging.debug("Skipping duplicate message to ESP32")
                return True
            
            # Send request to ESP32
            response = requests.get(f"{self.base_url}?Settings={message}", timeout=5)
            
            if response.status_code == 200 and response.text.strip() == "+OK":
                self.last_sent_message = message
                logging.info(f"✅ P10 Display updated: {first_text} | {second_text}")
                return True
            else:
                logging.error(f"ESP32 responded with: {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to send to P10 display: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error sending to P10: {e}")
            return False
    
    def _send_audio_alert(self, command: str) -> bool:
        """
        Send audio alert command to ESP32 (START/STOP)
        
        Args:
            command: "START" or "STOP"
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            settings = f"{self.key},AUDIO_ALERT,{command}"
            response = requests.get(f"{self.base_url}?Settings={settings}", timeout=5)
            if response.status_code == 200 and response.text.strip() == "+OK":
                logging.info(f"🔊 Audio alert command sent: {command}")
                return True
            else:
                logging.error(f"ESP32 responded to audio command with: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Failed to send audio alert command '{command}': {e}")
            return False

    def trigger_unauthorized_audio_alert(self) -> bool:
        """Start the unauthorized vehicle audio alert on ESP32"""
        if self.audio_alert_active:
            return True
        success = self._send_audio_alert("START")
        if success:
            self.audio_alert_active = True
            self.last_audio_start_time = time.time()
        return success

    def stop_unauthorized_audio_alert(self) -> bool:
        """Stop the unauthorized vehicle audio alert on ESP32"""
        if not self.audio_alert_active:
            return True
        success = self._send_audio_alert("STOP")
        if success:
            self.audio_alert_active = False
        return success

    def _sync_audio_alert_state(self) -> None:
        """
        Ensure audio alert state matches presence of unauthorized vehicles.
        Starts audio when there are unauthorized slots; stops when none remain.
        Only starts audio if it hasn't been playing for 60 seconds already.
        """
        try:
            should_be_on = len(self.unauthorized_slots) > 0
            if should_be_on and not self.audio_alert_active:
                # Only start audio if it hasn't been playing recently
                if time.time() - self.last_audio_start_time > 60.0:
                    self.trigger_unauthorized_audio_alert()
                    logging.info("🔊 Audio alert started for unauthorized vehicle - will run for 60 seconds")
            # Don't stop audio automatically - let it run for 60 seconds
            # elif not should_be_on and self.audio_alert_active:
            #     self.stop_unauthorized_audio_alert()
        except Exception as e:
            logging.error(f"Error syncing audio alert state: {e}")

    def _maintain_audio_alert(self) -> None:
        """
        Maintain audio alert for 60 seconds without repeat.
        ESP32 will play audio for 60 seconds and then stop automatically.
        """
        try:
            # Only check if audio has been playing for more than 60 seconds
            if self.audio_alert_active and (time.time() - self.last_audio_start_time > 60.0):
                # Audio has been playing for 60 seconds, stop it
                self.stop_unauthorized_audio_alert()
                logging.info("🔇 Audio alert stopped after 60 seconds as requested")
        except Exception as e:
            logging.error(f"Error maintaining audio alert: {e}")
    
    def get_slot_status_message(self) -> tuple:
        """
        Generate slot status message based on current slot states
            
        Returns:
            tuple: (first_row, second_row)
        """
        # Check for booking information
        try:
            booking_integration = self._get_booking_integration()
            if booking_integration:
                slot_status_response = booking_integration.get_slot_status()
                active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                logging.debug(f"🔍 P10 Display: Retrieved booking data: {active_bookings}")
            else:
                active_bookings = {}
                logging.debug("🔍 P10 Display: No booking integration available")
        except Exception as e:
            active_bookings = {}
            logging.warning(f"🔍 P10 Display: Error getting booking data: {e}")
        
        slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
        slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
        
        # Check if slots are booked
        slot1_booked = "1" in active_bookings
        slot2_booked = "2" in active_bookings
        
        # Update status to show BOOKED for pre-booked slots
        if slot1_booked and not self.slot_status["1"]["occupied"]:
            slot1_status = "BOOK"
        if slot2_booked and not self.slot_status["2"]["occupied"]:
            slot2_status = "BOOK"
        
        # Default status display
        first_row = f"SLOT 1 {slot1_status}"
        second_row = f"SLOT 2 {slot2_status}"
        
        logging.debug(f"🔍 P10 Display: Status message - Slot 1: {slot1_status} (booked: {slot1_booked}), Slot 2: {slot2_status} (booked: {slot2_booked})")
        
        return first_row, second_row
    
    def display_system_ready(self) -> bool:
        """Display system ready message"""
        return self.send_to_display("DBS", "SYSTEM READY", "PARKING AI ACTIVE", 0)
    
    def display_slot_status(self) -> bool:
        """Display current slot status (both rows static)"""
        # Double-check that we're showing the correct status
        slot1_occupied = self.slot_status["1"]["occupied"]
        slot2_occupied = self.slot_status["2"]["occupied"]
        
        # Ensure we show BUSY for occupied slots regardless of booking status
        slot1_status = "BUSY" if slot1_occupied else "FREE"
        slot2_status = "BUSY" if slot2_occupied else "FREE"
        
        # Check for booking information
        try:
            booking_integration = self._get_booking_integration()
            if booking_integration:
                slot_status_response = booking_integration.get_slot_status()
                active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                logging.debug(f"🔍 P10 Display: Retrieved booking data for display: {active_bookings}")
            else:
                active_bookings = {}
                logging.debug("🔍 P10 Display: No booking integration available for display")
        except Exception as e:
            active_bookings = {}
            logging.warning(f"🔍 P10 Display: Error getting booking data for display: {e}")
        
        # Update status to show BOOKED for pre-booked slots that are not occupied
        slot1_booked = "1" in active_bookings
        slot2_booked = "2" in active_bookings
        
        if slot1_booked and not slot1_occupied:
            slot1_status = "BOOK"
        if slot2_booked and not slot2_occupied:
            slot2_status = "BOOK"
        
        first_row = f"SLOT 1 {slot1_status}"
        second_row = f"SLOT 2 {slot2_status}"
        
        logging.info(f"🔍 Display status: Slot 1 {slot1_status} (occupied: {slot1_occupied}), Slot 2 {slot2_status} (occupied: {slot2_occupied})")
        
        return self.send_to_display("DBS", first_row, second_row, 0)
    
    def display_vehicle_entering(self, slot_id: str) -> bool:
        """Display vehicle entering message (first static, second animated)"""
        first_row = f"SLOT {slot_id}"
        second_row = "VEHICLE ENTERING"
        return self.send_to_display("DBM", first_row, second_row, 0)
    
    def display_vehicle_exiting(self, slot_id: str, license_plate: str = None) -> bool:
        """Display vehicle exiting message (first static, second animated)"""
        first_row = f"SLOT {slot_id}"
        if license_plate and license_plate not in ["Unknown", "UNREADABLE"]:
            second_row = f"{license_plate} LEAVING"
        else:
            second_row = "VEHICLE LEAVING"
        return self.send_to_display("DBM", first_row, second_row, 0)
    
    def display_plate_detected(self, slot_id: str, license_plate: str) -> bool:
        """Display detected license plate (both rows static)"""
        first_row = f"SLOT {slot_id} BUSY"
        second_row = license_plate
        return self.send_to_display("DBS", first_row, second_row, 0)
    
    def display_occupied_slots_plates(self) -> bool:
        """Display license plates for all occupied slots"""
        # Check if both slots are busy
        both_busy = (self.slot_status["1"]["occupied"] and self.slot_status["2"]["occupied"])
        
        if both_busy:
            # Both slots are busy - cycle between slot 1 and slot 2 plates
            if not hasattr(self, 'current_both_busy_index'):
                self.current_both_busy_index = 0
            
            # Get both slots' plates
            slot1_plate = self.slot_status["1"].get("license_plate")
            slot2_plate = self.slot_status["2"].get("license_plate")
            
            # Determine which slot to show based on index
            if self.current_both_busy_index == 0:
                # Show slot 1's plate
                if slot1_plate and slot1_plate not in ["Unknown", "UNREADABLE"]:
                    first_row = "SLOT 1 BUSY"
                    second_row = slot1_plate
                else:
                    first_row = "SLOT 1 BUSY"
                    second_row = "SLOT 2 BUSY"
            else:
                # Show slot 2's plate
                if slot2_plate and slot2_plate not in ["Unknown", "UNREADABLE"]:
                    first_row = "SLOT 2 BUSY"
                    second_row = slot2_plate
                else:
                    first_row = "SLOT 1 BUSY"
                    second_row = "SLOT 2 BUSY"
            
            # Move to next slot for next call
            self.current_both_busy_index = (self.current_both_busy_index + 1) % 2
            
            return self.send_to_display("DBS", first_row, second_row, 0)
        
        # Check for unauthorized vehicles (when not both busy)
        if self.unauthorized_slots:
            # Show unauthorized vehicle warnings in cycle
            if not hasattr(self, 'unauthorized_index'):
                self.unauthorized_index = 0
            
            unauthorized_list = list(self.unauthorized_slots)
            slot_id = unauthorized_list[self.unauthorized_index % len(unauthorized_list)]
            
            # Check if this slot has a booking conflict
            try:
                booking_integration = self._get_booking_integration()
                if booking_integration:
                    slot_status_response = booking_integration.get_slot_status()
                    active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                    booking = active_bookings.get(slot_id)
                    
                    if booking and slot_id in self.conflict_warning_displayed:
                        # Show attention message
                        return self.display_attention_booking_conflict(slot_id, booking)
                    else:
                        # Show unauthorized warning
                        return self.display_unauthorized_vehicle_warning(slot_id)
                else:
                    # Booking integration not available, show unauthorized warning
                    return self.display_unauthorized_vehicle_warning(slot_id)
            except Exception:
                # Booking integration not available, show unauthorized warning
                return self.display_unauthorized_vehicle_warning(slot_id)
            
            # Move to next unauthorized slot
            self.unauthorized_index = (self.unauthorized_index + 1) % len(unauthorized_list)
        
        # Normal plate display logic (for single occupied slot)
        occupied_slots = []
        for slot_id, status in self.slot_status.items():
            if status["occupied"] and status["license_plate"] and status["license_plate"] not in ["Unknown", "UNREADABLE"]:
                occupied_slots.append((slot_id, status["license_plate"]))
        
        if not occupied_slots:
            # No occupied slots with valid plates, but check if slots are actually occupied
            occupied_slots_no_plates = []
            for slot_id, status in self.slot_status.items():
                if status["occupied"]:
                    occupied_slots_no_plates.append(slot_id)
            
            if occupied_slots_no_plates:
                # Slots are occupied but no plates yet, show status with BUSY
                slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
                slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
                first_row = f"SLOT 1 {slot1_status}"
                second_row = f"SLOT 2 {slot2_status}"
                return self.send_to_display("DBS", first_row, second_row, 0)
            else:
                # No slots occupied, show status
                return self.display_slot_status()
        
        if len(occupied_slots) == 1:
            # Single occupied slot
            slot_id, plate = occupied_slots[0]
            first_row = f"SLOT {slot_id} BUSY"
            second_row = plate
        else:
            # Multiple occupied slots - this should not happen as both_busy is handled above
            # But just in case, cycle through them
            if not hasattr(self, 'current_plate_index'):
                self.current_plate_index = 0
            
            # Get the slot to display
            slot_id, plate = occupied_slots[self.current_plate_index % len(occupied_slots)]
            first_row = f"SLOT {slot_id} BUSY"
            second_row = plate
            
            # Move to next slot for next call
            self.current_plate_index = (self.current_plate_index + 1) % len(occupied_slots)
        
        # Check for booking information
        try:
            booking_integration = self._get_booking_integration()
            if booking_integration:
                slot_status_response = booking_integration.get_slot_status()
                active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                booking = active_bookings.get(slot_id)
                
                if booking:
                    # Check if the detected plate matches the booking
                    expected_plate = booking.get("expectedPlate", "").upper().replace(' ', '').replace('-', '')
                    detected_plate_normalized = plate.upper().replace(' ', '').replace('-', '')
                    
                    if expected_plate == detected_plate_normalized:
                        # Vehicle matches booking - show the license plate
                        first_row = f"SLOT {slot_id} BUSY"
                        second_row = plate
                    else:
                        # Vehicle doesn't match booking - show booking info
                        first_row = f"SLOT {slot_id} BUSY"
                        second_row = f"BOOKED: {booking.get('expectedPlate', 'UNKNOWN')}"
        except Exception:
            # Booking integration not available, show plate as usual
            pass
        
        return self.send_to_display("DBS", first_row, second_row, 0)
    
    def display_processing(self) -> bool:
        """Display processing message"""
        return self.send_to_display("DBS", "PROCESSING", "PLEASE WAIT", 0)
    
    def display_unauthorized_vehicle_warning(self, slot_id: str) -> bool:
        """Display unauthorized vehicle warning (first static, second animated)"""
        first_row = f"SLOT {slot_id} BOOK"
        second_row = "PLEASE REMOVE YOUR VEHICLE"
        return self.send_to_display("DBM", first_row, second_row, 0)
    
    def display_attention_booking_conflict(self, slot_id: str, booking_data: dict = None) -> bool:
        """Display attention message for booking conflict (first static, second animated)"""
        first_row = "ATTENTION"
        
        if booking_data and isinstance(booking_data, dict):
            # Use complete booking information
            expected_plate = booking_data.get("expectedPlate", "")
            customer_name = booking_data.get("customerName", "")
            vehicle_model = booking_data.get("vehicleModel", "")
            vehicle_make = booking_data.get("vehicleMake", "")
            order_id = booking_data.get("orderId", "")
            owner_name = booking_data.get("ownerName", "")
            
            # Format the message with comprehensive information
            if expected_plate and vehicle_make and vehicle_model:
                # Show vehicle model and plate number
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {vehicle_make} {vehicle_model} No - {expected_plate}"
            elif expected_plate and vehicle_model:
                # Show vehicle model and plate number (without make)
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {vehicle_model} No - {expected_plate}"
            elif expected_plate and vehicle_make:
                # Show vehicle make and plate number (without model)
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {vehicle_make} No - {expected_plate}"
            elif expected_plate and owner_name:
                # Show owner name and plate number
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {owner_name} No - {expected_plate}"
            elif expected_plate:
                # Show just the plate number
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY CAR No - {expected_plate}"
            elif customer_name:
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {customer_name}"
            elif vehicle_model and vehicle_make:
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY {vehicle_make} {vehicle_model}"
            elif order_id:
                second_row = f"SLOT {slot_id} HAS BEEN BOOKED BY ORDER {order_id}"
            else:
                second_row = f"SLOT {slot_id} IS BOOKED"
        else:
            # Fallback to simple message
            second_row = f"SLOT {slot_id} IS BOOKED"
        
        return self.send_to_display("DBM", first_row, second_row, 0)
    
    def send_single_row_message(self, message: str) -> bool:
        """Send single row message (for special cases)"""
        try:
            settings = f"{self.key},SR,{message}"
            response = requests.get(f"{self.base_url}?Settings={settings}", timeout=5)
            
            if response.status_code == 200 and response.text.strip() == "+OK":
                logging.info(f"✅ P10 Single row message: {message}")
                return True
            else:
                logging.error(f"ESP32 responded with: {response.text}")
                return False
        except Exception as e:
            logging.error(f"Failed to send single row message: {e}")
            return False
    
    def send_double_row_static(self, first_text: str, second_text: str) -> bool:
        """Send double row static message"""
        return self.send_to_display("DBS", first_text, second_text, 0)
    
    def update_slot_status(self, slot_status_dict: Dict[str, Any]) -> None:
        """
        Update slot status and trigger appropriate display
        
        Args:
            slot_status_dict: Dictionary containing slot status information
        """
        with self.display_lock:
            # Track changes
            changes_detected = False
            
            for slot_id in ["1", "2"]:
                if slot_id in slot_status_dict:
                    new_status = slot_status_dict[slot_id]
                    old_status = self.slot_status[slot_id]
                    
                    # Check for status changes
                    if new_status.get("occupied", False) != old_status["occupied"]:
                        changes_detected = True
                        
                        if new_status.get("occupied", False):
                            # Vehicle entering
                            logging.info(f"🚗 Vehicle entering slot {slot_id}")
                            self.slot_status[slot_id]["entering"] = True
                            self.slot_status[slot_id]["exiting"] = False
                            self.current_display_type = "entering"
                            self.display_start_time = time.time()
                            self.display_vehicle_entering(slot_id)
                        else:
                            # Vehicle exiting
                            logging.info(f"🚗💨 Vehicle exiting slot {slot_id}")
                            plate = old_status.get("license_plate")
                            self.slot_status[slot_id]["exiting"] = True
                            self.slot_status[slot_id]["entering"] = False
                            self.current_display_type = "exiting"
                            self.display_start_time = time.time()
                            self.display_vehicle_exiting(slot_id, plate)
                            
                            # Remove from unauthorized slots when vehicle leaves
                            if slot_id in self.unauthorized_slots:
                                self.unauthorized_slots.remove(slot_id)
                                self.conflict_warning_displayed.discard(slot_id)
                                # Reset index if no more unauthorized slots
                                if len(self.unauthorized_slots) == 0:
                                    self.current_unauthorized_slot_index = 0
                                logging.info(f"✅ Unauthorized vehicle removed from slot {slot_id}")
                                # Note: Audio alert will continue for remaining time (max 60 seconds)
                                # No need to sync audio state when removing slots
                    
                    # Check for license plate changes
                    new_plate = new_status.get("license_plate")
                    old_plate = old_status.get("license_plate")
                    
                    if (new_plate and new_plate != old_plate and 
                        new_plate not in ["Unknown", "UNREADABLE"] and
                        new_status.get("occupied", False)):
                        # License plate detected
                        logging.info(f"🔢 License plate detected for slot {slot_id}: {new_plate}")
                        changes_detected = True
                        
                        # Check for booking conflicts
                        self.check_booking_conflict(slot_id, new_plate)
                        
                        self.current_display_type = "plate_detected"
                        self.display_start_time = time.time()
                        self.display_plate_detected(slot_id, new_plate)
                    
                    # Update our internal status
                    self.slot_status[slot_id].update({
                        "occupied": new_status.get("occupied", False),
                        "license_plate": new_plate
                    })
            
            # Handle display transitions based on current state
            current_time = time.time()
            
            # Check if both slots are busy
            both_busy = (self.slot_status["1"]["occupied"] and self.slot_status["2"]["occupied"])
            
            # Check if there are unauthorized vehicles (regardless of how many slots are busy)
            has_unauthorized = len(self.unauthorized_slots) > 0
            
            if both_busy:
                # Handle both slots busy scenario with improved unauthorized vehicle handling
                if self.unauthorized_slots:
                    # With unauthorized vehicles - use the improved cycle
                    if self.current_display_type in ["entering", "exiting", "plate_detected"]:
                        # After showing entering/exiting/plate for event duration, start unauthorized cycle
                        if current_time - self.display_start_time > self.event_display_duration:
                            self.current_display_type = "unauthorized_cycle"
                            self.unauthorized_cycle_state = "remove_message"
                            self.unauthorized_cycle_start_time = current_time
                            # Start with remove message for current unauthorized slot
                            unauthorized_slots_list = list(self.unauthorized_slots)
                            if unauthorized_slots_list:
                                unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                logging.info(f"🔄 Both slots busy (with unauthorized): Starting improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                            else:
                                # No unauthorized slots, switch to normal both busy cycling
                                self.current_display_type = "both_busy_alternating"
                                self.is_showing_status = True
                                self.display_start_time = current_time
                                self.display_slot_status()
                                logging.info("🔄 Both slots busy: No unauthorized slots, switching to normal alternating cycle")
                    elif self.current_display_type not in ["unauthorized_cycle", "entering", "exiting", "plate_detected"]:
                        # Initialize unauthorized cycle
                        self.current_display_type = "unauthorized_cycle"
                        self.unauthorized_cycle_state = "remove_message"
                        self.unauthorized_cycle_start_time = current_time
                        # Start with remove message for current unauthorized slot
                        unauthorized_slots_list = list(self.unauthorized_slots)
                        if unauthorized_slots_list:
                            unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                            self.display_unauthorized_vehicle_warning(unauthorized_slot)
                            logging.info(f"🔄 Both slots busy (with unauthorized): Initializing improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                        else:
                            # No unauthorized slots, switch to normal both busy cycling
                            self.current_display_type = "both_busy_alternating"
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                            logging.info("🔄 Both slots busy: No unauthorized slots, switching to normal alternating cycle")
                else:
                    # No unauthorized vehicles - normal both busy cycling
                    if self.current_display_type == "plate_detected":
                        # After showing plate for 25 seconds, start alternating cycle
                        if current_time - self.display_start_time > self.plate_display_duration:
                            self.current_display_type = "both_busy_alternating"
                            self.is_showing_status = True  # Start with status
                            self.display_start_time = current_time
                            self.display_slot_status()
                            logging.info("🔄 Both slots busy: Starting alternating cycle with status")
                    elif self.current_display_type in ["entering", "exiting"]:
                        # After showing entering/exiting for 15 seconds, start alternating cycle
                        if current_time - self.display_start_time > self.event_display_duration:
                            self.current_display_type = "both_busy_alternating"
                            self.is_showing_status = True  # Start with status
                            self.display_start_time = current_time
                            self.display_slot_status()
                            # Reset entering/exiting flags
                            for slot_id in ["1", "2"]:
                                self.slot_status[slot_id]["entering"] = False
                                self.slot_status[slot_id]["exiting"] = False
                            logging.info("🔄 Both slots busy: Starting alternating cycle after event")
                    elif self.current_display_type == "both_busy_alternating":
                        # Check if unauthorized vehicles have been detected while in alternating mode
                        if self.unauthorized_slots:
                            # Switch to unauthorized cycle immediately
                            self.current_display_type = "unauthorized_cycle"
                            self.unauthorized_cycle_state = "remove_message"
                            self.unauthorized_cycle_start_time = current_time
                            # Start with remove message for current unauthorized slot
                            unauthorized_slots_list = list(self.unauthorized_slots)
                            if unauthorized_slots_list:
                                unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                logging.info(f"🔄 Both slots busy: Switching from alternating to unauthorized cycle for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                            return  # Exit early to let the worker handle the cycle
                        
                        # Handle the alternating cycle: status -> slot1 -> slot2 -> status -> repeat
                        if self.is_showing_status:
                            # Currently showing status, switch to slot 1 plate after duration
                            if current_time - self.display_start_time > self.status_display_duration:
                                self.is_showing_status = False
                                self.current_plate_index = 0  # Start with slot 1
                                self.display_start_time = current_time
                                # Show slot 1 plate
                                slot1_plate = self.slot_status["1"].get("license_plate")
                                if slot1_plate and slot1_plate not in ["Unknown", "UNREADABLE"]:
                                    self.send_to_display("DBS", "SLOT 1 BUSY", slot1_plate, 0)
                                    logging.info(f"🔄 Both slots busy: Showing slot 1 plate: {slot1_plate}")
                                else:
                                    self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                    logging.info("🔄 Both slots busy: Showing both busy (no slot 1 plate)")
                        else:
                            # Currently showing plates, alternate between slot 1 and slot 2
                            if current_time - self.display_start_time > self.alternating_display_duration:
                                if self.current_plate_index == 0:
                                    # Switch to slot 2 plate
                                    self.current_plate_index = 1
                                    self.display_start_time = current_time
                                    slot2_plate = self.slot_status["2"].get("license_plate")
                                    if slot2_plate and slot2_plate not in ["Unknown", "UNREADABLE"]:
                                        self.send_to_display("DBS", "SLOT 2 BUSY", slot2_plate, 0)
                                        logging.info(f"🔔 Both slots busy: Showing slot 2 plate: {slot2_plate}")
                                    else:
                                        self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                        logging.info("🔔 Both slots busy: Showing both busy (no slot 2 plate)")
                                else:
                                    # Switch back to status
                                    self.is_showing_status = True
                                    self.display_start_time = current_time
                                    self.display_slot_status()
                                    logging.info("🔔 Both slots busy: Returning to status display")
                    elif self.current_display_type not in ["both_busy_alternating"]:
                        # Initialize both busy alternating cycle
                        self.current_display_type = "both_busy_alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                        logging.info("🔄 Both slots busy: Initializing alternating cycle")
                        
                        # Check if unauthorized vehicles have been detected while initializing
                        if self.unauthorized_slots:
                            # Switch to unauthorized cycle immediately
                            self.current_display_type = "unauthorized_cycle"
                            self.unauthorized_cycle_state = "remove_message"
                            self.unauthorized_cycle_start_time = current_time
                            # Start with remove message for current unauthorized slot
                            unauthorized_slots_list = list(self.unauthorized_slots)
                            if unauthorized_slots_list:
                                unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                logging.info(f"🔄 Both slots busy: Switching from initialization to unauthorized cycle for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                            return  # Exit early to let the worker handle the cycle
            
            elif has_unauthorized and not both_busy:
                # Handle unauthorized vehicles when only one slot is busy
                if self.current_display_type in ["entering", "exiting", "plate_detected"]:
                    # After showing entering/exiting/plate for event duration, start unauthorized cycle
                    if current_time - self.display_start_time > self.event_display_duration:
                        self.current_display_type = "unauthorized_cycle"
                        self.unauthorized_cycle_state = "remove_message"
                        self.unauthorized_cycle_start_time = current_time
                        # Start with remove message for current unauthorized slot
                        unauthorized_slots_list = list(self.unauthorized_slots)
                        if unauthorized_slots_list:
                            unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                            self.display_unauthorized_vehicle_warning(unauthorized_slot)
                            logging.info(f"🔄 Single slot unauthorized: Starting improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                        else:
                            # No unauthorized slots, switch to normal alternating
                            self.current_display_type = "alternating"
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                            logging.info("🔄 Single slot: No unauthorized slots, switching to normal alternating cycle")
                elif self.current_display_type not in ["unauthorized_cycle", "entering", "exiting", "plate_detected"]:
                    # Initialize unauthorized cycle
                    self.current_display_type = "unauthorized_cycle"
                    self.unauthorized_cycle_state = "remove_message"
                    self.unauthorized_cycle_start_time = current_time
                    # Start with remove message for current unauthorized slot
                    unauthorized_slots_list = list(self.unauthorized_slots)
                    if unauthorized_slots_list:
                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                        self.display_unauthorized_vehicle_warning(unauthorized_slot)
                        logging.info(f"🔄 Single slot unauthorized: Initializing improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                    else:
                        # No unauthorized slots, switch to normal alternating
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                        logging.info("🔄 Single slot: No unauthorized slots, switching to normal alternating cycle")
                    
            else:
                # Single slot busy or no slots busy - existing logic
                if self.current_display_type == "plate_detected":
                    if current_time - self.display_start_time > self.plate_display_duration:
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                elif self.current_display_type in ["entering", "exiting"]:
                    if current_time - self.display_start_time > self.event_display_duration:
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                        # Reset entering/exiting flags
                        for slot_id in ["1", "2"]:
                            self.slot_status[slot_id]["entering"] = False
                            self.slot_status[slot_id]["exiting"] = False
                elif self.current_display_type in ["unauthorized_warning", "attention_conflict"]:
                    if current_time - self.display_start_time > self.event_display_duration:
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                elif self.current_display_type in ["both_busy_alternating", "unauthorized_cycle"]:
                    # Check if we should continue with unauthorized cycle or switch to normal
                    if has_unauthorized:
                        # Continue with unauthorized cycle
                        self.current_display_type = "unauthorized_cycle"
                        self.unauthorized_cycle_state = "remove_message"
                        self.unauthorized_cycle_start_time = current_time
                        # Start with remove message for current unauthorized slot
                        unauthorized_slots_list = list(self.unauthorized_slots)
                        if unauthorized_slots_list:
                            unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                            self.display_unauthorized_vehicle_warning(unauthorized_slot)
                            logging.info(f"🔄 Switching from both busy to single slot unauthorized cycle for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                        else:
                            # No unauthorized slots, switch to normal alternating
                            self.current_display_type = "alternating"
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                            logging.info("🔄 Switching: No unauthorized slots, switching to normal alternating cycle")
                    else:
                        # No unauthorized vehicles, switch to normal alternating
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                        logging.info("🔄 Switching from both busy/unauthorized cycle to normal alternating")
                elif self.current_display_type == "alternating":
                    # Handle alternating between status and license plates (single slot busy)
                    if self.is_showing_status:
                        if current_time - self.display_start_time > self.status_display_duration:
                            self.is_showing_status = False
                            self.display_start_time = current_time
                            self.display_occupied_slots_plates()
                    else:
                        if current_time - self.display_start_time > self.alternating_display_duration:
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                elif changes_detected and self.current_display_type == "status":
                    # Update status display if there were changes and start alternating
                    self.current_display_type = "alternating"
                    self.is_showing_status = True
                    self.display_start_time = current_time
                    self.display_slot_status()
            
            # Handle dynamic booking changes
            self.handle_booking_status_change()
    
    def handle_booking_status_change(self) -> None:
        """
        Handle booking status changes during runtime
        This should be called when bookings are added/removed while the system is running
        """
        try:
            booking_integration = self._get_booking_integration()
            slot_status_response = booking_integration.get_slot_status()
            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
            
            # Check for booking conflicts with currently occupied slots
            for slot_id in ["1", "2"]:
                if self.slot_status[slot_id]["occupied"]:
                    current_plate = self.slot_status[slot_id].get("license_plate")
                    if current_plate and current_plate not in ["Unknown", "UNREADABLE"]:
                        # Check if this slot should be authorized now
                        if slot_id in active_bookings:
                            expected_plate = active_bookings[slot_id].get("expectedPlate", "")
                            if current_plate != expected_plate:
                                # Still unauthorized
                                if slot_id not in self.unauthorized_slots:
                                    self.unauthorized_slots.add(slot_id)
                                    logging.info(f"🔔 Slot {slot_id} marked as unauthorized due to new booking")
                            else:
                                # Now authorized
                                if slot_id in self.unauthorized_slots:
                                    self.unauthorized_slots.remove(slot_id)
                                    self.conflict_warning_displayed.discard(slot_id)
                                    logging.info(f"✅ Slot {slot_id} is now authorized")
                        else:
                            # No booking for this slot anymore - remove from unauthorized
                            if slot_id in self.unauthorized_slots:
                                self.unauthorized_slots.remove(slot_id)
                                self.conflict_warning_displayed.discard(slot_id)
                                logging.info(f"✅ Slot {slot_id} booking removed - no longer unauthorized")
                else:
                    # Slot is not occupied - remove from unauthorized
                    if slot_id in self.unauthorized_slots:
                        self.unauthorized_slots.remove(slot_id)
                        self.conflict_warning_displayed.discard(slot_id)
                        logging.info(f"✅ Slot {slot_id} is now free - removed from unauthorized")
            
            # Force display update if no unauthorized vehicles remain
            if not self.unauthorized_slots and self.current_display_type == "unauthorized_cycle":
                with self.display_lock:
                    self.current_display_type = "alternating"
                    self.is_showing_status = True
                    self.display_start_time = time.time()
                    self.display_slot_status()
                    logging.info("🔄 No more unauthorized vehicles - switching to normal alternating display")
            # Note: Audio alert will continue for remaining time (max 60 seconds)
            # No need to sync audio state when handling booking changes
        
        except Exception:
            # Booking integration not available
            pass
        except Exception as e:
            logging.error(f"Error handling booking status change: {e}")

    def check_booking_conflict(self, slot_id: str, detected_plate: str) -> None:
        """
        Check for booking conflicts and trigger appropriate warnings
        
        Args:
            slot_id: Slot ID
            detected_plate: Detected license plate
        """
        try:
            booking_integration = self._get_booking_integration()
            slot_status_response = booking_integration.get_slot_status()
            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
            
            if slot_id in active_bookings:
                expected_plate = active_bookings[slot_id].get("expectedPlate", "")
                if detected_plate != expected_plate:
                    # Add to unauthorized slots
                    was_empty = len(self.unauthorized_slots) == 0
                    self.unauthorized_slots.add(slot_id)
                    # Reset index if this is the first unauthorized slot added
                    if was_empty:
                        self.current_unauthorized_slot_index = 0
                    logging.info(f"🔔 Booking conflict detected for slot {slot_id}: {detected_plate} vs {expected_plate}")
                    # Start audio alert when first unauthorized appears
                    self._sync_audio_alert_state()
                
        except Exception as e:
            logging.error(f"Error checking booking conflict: {e}")
    
    def start_display_cycle(self, initial_slot_status: Dict[str, Any] = None) -> None:
        """
        Start the display management cycle
        
        Args:
            initial_slot_status: Initial slot status dictionary
        """
        if self.cycle_running:
            logging.warning("Display cycle already running")
            return
        
        self.cycle_running = True
        self.display_event.set()
        
        # Initialize with provided status
        if initial_slot_status:
            with self.display_lock:
                for slot_id in ["1", "2"]:
                    if slot_id in initial_slot_status:
                        status = initial_slot_status[slot_id]
                        self.slot_status[slot_id].update({
                            "occupied": status.get("occupied", False),
                            "license_plate": status.get("license_plate")
                        })
        
        # Start display thread
        self.display_thread = Thread(target=self._display_cycle_worker, daemon=True)
        self.display_thread.start()
        
        # Show initial status and start alternating display
        self.current_display_type = "alternating"
        self.is_showing_status = True
        self.display_start_time = time.time()
        self.display_slot_status()
        
        # Reset unauthorized slot index
        self.current_unauthorized_slot_index = 0
        
        logging.info("P10 Display cycle started")
    
    def _display_cycle_worker(self) -> None:
        """Background worker for display cycle management"""
        while self.cycle_running:
            try:
                current_time = time.time()
                
                with self.display_lock:
                    # Keep audio alert active while unauthorized vehicles persist
                    self._maintain_audio_alert()
                    # Check if both slots are busy
                    both_busy = (self.slot_status["1"]["occupied"] and self.slot_status["2"]["occupied"])
                    
                    # Check if there are unauthorized vehicles (regardless of how many slots are busy)
                    has_unauthorized = len(self.unauthorized_slots) > 0
                    
                    if both_busy:
                        # Handle unauthorized vehicle warnings with improved cycle
                        if self.unauthorized_slots:
                            # Initialize unauthorized cycle variables if not present
                            if not hasattr(self, 'unauthorized_cycle_state'):
                                self.unauthorized_cycle_state = "remove_message"
                                self.unauthorized_cycle_start_time = current_time
                                self.unauthorized_cycle_duration = 15  # 15 seconds per state
                                self.remove_message_duration = 5  # 5 seconds for remove message (2 animations)
                                self.attention_message_duration = 30  # 30 seconds for attention message (2 animations)
                            
                            # Handle the improved unauthorized cycle
                            if self.current_display_type == "unauthorized_cycle":
                                # Check if it's time to move to next state based on current state
                                current_duration = self.unauthorized_cycle_duration
                                if self.unauthorized_cycle_state == "remove_message":
                                    current_duration = self.remove_message_duration
                                elif self.unauthorized_cycle_state == "attention":
                                    current_duration = self.attention_message_duration
                                
                                if current_time - self.unauthorized_cycle_start_time > current_duration:
                                    self.unauthorized_cycle_start_time = current_time
                                    
                                    # Cycle through states: remove -> status -> attention -> slot1_plate -> slot2_plate -> remove
                                    if self.unauthorized_cycle_state == "remove_message":
                                        # Show remove message for current unauthorized slot
                                        unauthorized_slots_list = list(self.unauthorized_slots)
                                        if unauthorized_slots_list:
                                            unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                            self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                            logging.info(f"🔔 Unauthorized cycle: Showing remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                        self.unauthorized_cycle_state = "status"
                                        
                                    elif self.unauthorized_cycle_state == "status":
                                        # Skip status display when there are unauthorized vehicles to prioritize warnings
                                        # Go directly to attention message
                                        self.unauthorized_cycle_state = "attention"
                                        logging.info("🔔 Unauthorized cycle: Skipping status display to prioritize unauthorized warnings")
                                        
                                    elif self.unauthorized_cycle_state == "attention":
                                        # Show attention message for current unauthorized slot
                                        unauthorized_slots_list = list(self.unauthorized_slots)
                                        if unauthorized_slots_list:
                                            unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                            try:
                                                booking_integration = self._get_booking_integration()
                                                slot_status_response = booking_integration.get_slot_status()
                                                active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                                                booking = active_bookings.get(unauthorized_slot)
                                                
                                                if booking:
                                                    self.display_attention_booking_conflict(unauthorized_slot, booking)
                                                    self.conflict_warning_displayed.add(unauthorized_slot)
                                                    logging.info(f"🔔 Unauthorized cycle: Showing attention message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                            except Exception:
                                                # Fallback to unauthorized warning if booking integration not available
                                                self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                                logging.info(f"🔔 Unauthorized cycle: Showing unauthorized warning for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                        self.unauthorized_cycle_state = "slot1_plate"
                                        
                                    elif self.unauthorized_cycle_state == "slot1_plate":
                                        # Show slot 1 plate
                                        slot1_plate = self.slot_status["1"].get("license_plate")
                                        if slot1_plate and slot1_plate not in ["Unknown", "UNREADABLE"]:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", slot1_plate, 0)
                                            logging.info(f"🔔 Unauthorized cycle: Showing slot 1 plate: {slot1_plate}")
                                        else:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                            logging.info("🔔 Unauthorized cycle: Showing both busy (no slot 1 plate)")
                                        
                                        self.unauthorized_cycle_state = "slot2_plate"
                                        
                                    elif self.unauthorized_cycle_state == "slot2_plate":
                                        # Show slot 2 plate
                                        slot2_plate = self.slot_status["2"].get("license_plate")
                                        if slot2_plate and slot2_plate not in ["Unknown", "UNREADABLE"]:
                                            self.send_to_display("DBS", "SLOT 2 BUSY", slot2_plate, 0)
                                            logging.info(f"🔔 Unauthorized cycle: Showing slot 2 plate: {slot2_plate}")
                                        else:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                            logging.info("🔔 Unauthorized cycle: Showing both busy (no slot 2 plate)")
                                        
                                        # Move to next unauthorized slot and cycle back to remove message
                                        unauthorized_slots_list = list(self.unauthorized_slots)
                                        if unauthorized_slots_list:
                                            self.current_unauthorized_slot_index = (self.current_unauthorized_slot_index + 1) % len(unauthorized_slots_list)
                                            logging.info(f"🔔 Unauthorized cycle: Moving to next unauthorized slot {self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)}")
                                        else:
                                            # No more unauthorized slots, reset index
                                            self.current_unauthorized_slot_index = 0
                                            logging.info("🔔 Unauthorized cycle: No more unauthorized slots, resetting index")
                                        self.unauthorized_cycle_state = "remove_message"
                            
                            elif self.current_display_type in ["entering", "exiting", "plate_detected"]:
                                # After showing entering/exiting/plate for event duration, start unauthorized cycle
                                if current_time - self.display_start_time > self.event_display_duration:
                                    self.current_display_type = "unauthorized_cycle"
                                    self.unauthorized_cycle_state = "remove_message"
                                    self.unauthorized_cycle_start_time = current_time
                                    # Start with remove message for current unauthorized slot
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                        self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                        logging.info(f"🔄 Both slots busy (with unauthorized): Starting improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                    else:
                                        # No unauthorized slots, switch to normal both busy cycling
                                        self.current_display_type = "both_busy_alternating"
                                        self.is_showing_status = True
                                        self.display_start_time = current_time
                                        self.display_slot_status()
                                        logging.info("🔄 Both slots busy: No unauthorized slots, switching to normal alternating cycle")
                            
                            elif self.current_display_type not in ["unauthorized_cycle", "entering", "exiting", "plate_detected"]:
                                # Initialize unauthorized cycle
                                self.current_display_type = "unauthorized_cycle"
                                self.unauthorized_cycle_state = "remove_message"
                                self.unauthorized_cycle_start_time = current_time
                                # Start with remove message for current unauthorized slot
                                unauthorized_slots_list = list(self.unauthorized_slots)
                                if unauthorized_slots_list:
                                    unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                    self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                    logging.info(f"🔄 Both slots busy (with unauthorized): Initializing improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                else:
                                    # No unauthorized slots, switch to normal both busy cycling
                                    self.current_display_type = "both_busy_alternating"
                                    self.is_showing_status = True
                                    self.display_start_time = current_time
                                    self.display_slot_status()
                                    logging.info("🔄 Both slots busy: No unauthorized slots, switching to normal alternating cycle")
                        
                        else:
                            # No unauthorized vehicles - normal both busy cycling
                            if self.current_display_type == "both_busy_alternating":
                                # Check if unauthorized vehicles have been detected while in alternating mode
                                if self.unauthorized_slots:
                                    # Switch to unauthorized cycle immediately
                                    self.current_display_type = "unauthorized_cycle"
                                    self.unauthorized_cycle_state = "remove_message"
                                    self.unauthorized_cycle_start_time = current_time
                                    # Start with remove message for current unauthorized slot
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                        self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                        logging.info(f"🔄 Worker: Switching from both busy alternating to unauthorized cycle for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                    continue  # Skip to next iteration to handle unauthorized cycle
                                
                                if self.is_showing_status:
                                    # Currently showing status, switch to slot 1 plate after duration
                                    if current_time - self.display_start_time > self.status_display_duration:
                                        self.is_showing_status = False
                                        self.current_plate_index = 0  # Start with slot 1
                                        self.display_start_time = current_time
                                        # Show slot 1 plate
                                        slot1_plate = self.slot_status["1"].get("license_plate")
                                        if slot1_plate and slot1_plate not in ["Unknown", "UNREADABLE"]:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", slot1_plate, 0)
                                            logging.info(f"🔄 Worker: Both slots busy - Showing slot 1 plate: {slot1_plate}")
                                        else:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                            logging.info("🔄 Worker: Both slots busy - Showing both busy (no slot 1 plate)")
                                else:
                                    # Currently showing plates, alternate between slot 1 and slot 2
                                    if current_time - self.display_start_time > self.alternating_display_duration:
                                        if self.current_plate_index == 0:
                                            # Switch to slot 2 plate
                                            self.current_plate_index = 1
                                            self.display_start_time = current_time
                                            slot2_plate = self.slot_status["2"].get("license_plate")
                                            if slot2_plate and slot2_plate not in ["Unknown", "UNREADABLE"]:
                                                self.send_to_display("DBS", "SLOT 2 BUSY", slot2_plate, 0)
                                                logging.info(f"🔄 Worker: Both slots busy - Showing slot 2 plate: {slot2_plate}")
                                            else:
                                                self.send_to_display("DBS", "SLOT 1 BUSY", "SLOT 2 BUSY", 0)
                                                logging.info("🔄 Worker: Both slots busy - Showing both busy (no slot 2 plate)")
                                        else:
                                            # Switch back to status
                                            self.is_showing_status = True
                                            self.display_start_time = current_time
                                            self.display_slot_status()
                                            logging.info("🔄 Worker: Both slots busy - Returning to status display")
                            
                            elif self.current_display_type not in ["both_busy_alternating", "entering", "exiting", "plate_detected"]:
                                # Initialize both busy alternating cycle
                                self.current_display_type = "both_busy_alternating"
                                self.is_showing_status = True
                                self.display_start_time = current_time
                                self.display_slot_status()
                                logging.info("🔄 Worker: Both slots busy - Initializing alternating cycle")
                                
                                # Check if unauthorized vehicles have been detected while initializing
                                if self.unauthorized_slots:
                                    # Switch to unauthorized cycle immediately
                                    self.current_display_type = "unauthorized_cycle"
                                    self.unauthorized_cycle_state = "remove_message"
                                    self.unauthorized_cycle_start_time = current_time
                                    # Start with remove message for current unauthorized slot
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                        self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                        logging.info(f"🔄 Worker: Switching from both busy initialization to unauthorized cycle for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                    continue  # Skip to next iteration to handle unauthorized cycle
                    
                    # Handle unauthorized vehicles when only one slot is busy
                    elif has_unauthorized and not both_busy:
                        # Initialize unauthorized cycle variables if not present
                        if not hasattr(self, 'unauthorized_cycle_state'):
                            self.unauthorized_cycle_state = "remove_message"
                            self.unauthorized_cycle_start_time = current_time
                            self.unauthorized_cycle_duration = 15  # 15 seconds per state
                            self.remove_message_duration = 10  # 5 seconds for remove message (2 animations)
                            self.attention_message_duration = 10  # 30 seconds for attention message (2 animations)
                        
                        # Handle the improved unauthorized cycle for single slot
                        if self.current_display_type == "unauthorized_cycle":
                            # Check if it's time to move to next state based on current state
                            current_duration = self.unauthorized_cycle_duration
                            if self.unauthorized_cycle_state == "remove_message":
                                current_duration = self.remove_message_duration
                            elif self.unauthorized_cycle_state == "attention":
                                current_duration = self.attention_message_duration
                            
                            if current_time - self.unauthorized_cycle_start_time > current_duration:
                                self.unauthorized_cycle_start_time = current_time
                                
                                # Cycle through states: remove -> status -> attention -> slot1_plate -> slot2_plate -> remove
                                if self.unauthorized_cycle_state == "remove_message":
                                    # Show remove message for current unauthorized slot
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                        self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                        logging.info(f"🔔 Single slot unauthorized cycle: Showing remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                    self.unauthorized_cycle_state = "status"
                                    
                                elif self.unauthorized_cycle_state == "status":
                                    # Skip status display when there are unauthorized vehicles to prioritize warnings
                                    # Go directly to attention message
                                    self.unauthorized_cycle_state = "attention"
                                    logging.info("🔔 Single slot unauthorized cycle: Skipping status display to prioritize unauthorized warnings")
                                    
                                elif self.unauthorized_cycle_state == "attention":
                                    # Show attention message for current unauthorized slot
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                        try:
                                            booking_integration = self._get_booking_integration()
                                            slot_status_response = booking_integration.get_slot_status()
                                            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                                            booking = active_bookings.get(unauthorized_slot)
                                            
                                            if booking:
                                                self.display_attention_booking_conflict(unauthorized_slot, booking)
                                                self.conflict_warning_displayed.add(unauthorized_slot)
                                                logging.info(f"🔔 Single slot unauthorized cycle: Showing attention message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                        except Exception:
                                            # Fallback to unauthorized warning if booking integration not available
                                            self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                            logging.info(f"🔔 Single slot unauthorized cycle: Showing unauthorized warning for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                    self.unauthorized_cycle_state = "slot1_plate"
                                    
                                elif self.unauthorized_cycle_state == "slot1_plate":
                                    # Show slot 1 plate if occupied, otherwise show actual status
                                    if self.slot_status["1"]["occupied"]:
                                        slot1_plate = self.slot_status["1"].get("license_plate")
                                        if slot1_plate and slot1_plate not in ["Unknown", "UNREADABLE"]:
                                            self.send_to_display("DBS", "SLOT 1 BUSY", slot1_plate, 0)
                                            logging.info(f"🔔 Single slot unauthorized cycle: Showing slot 1 plate: {slot1_plate}")
                                        else:
                                            # Show actual slot status instead of wrong message
                                            slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
                                            slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
                                            self.send_to_display("DBS", f"SLOT 1 {slot1_status}", f"SLOT 2 {slot2_status}", 0)
                                            logging.info(f"🔔 Single slot unauthorized cycle: Showing actual status - slot 1 {slot1_status}, slot 2 {slot2_status}")
                                    else:
                                        # Show actual slot status
                                        slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
                                        slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
                                        
                                        # Check for bookings
                                        try:
                                            booking_integration = self._get_booking_integration()
                                            slot_status_response = booking_integration.get_slot_status()
                                            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                                            
                                            # Update status to show BOOK for pre-booked slots that are not occupied
                                            if "1" in active_bookings and not self.slot_status["1"]["occupied"]:
                                                slot1_status = "BOOK"
                                            if "2" in active_bookings and not self.slot_status["2"]["occupied"]:
                                                slot2_status = "BOOK"
                                        except Exception:
                                            pass
                                        
                                        self.send_to_display("DBS", f"SLOT 1 {slot1_status}", f"SLOT 2 {slot2_status}", 0)
                                        logging.info(f"🔔 Single slot unauthorized cycle: Showing actual status - slot 1 {slot1_status}, slot 2 {slot2_status}")
                                    
                                    self.unauthorized_cycle_state = "slot2_plate"
                                    
                                elif self.unauthorized_cycle_state == "slot2_plate":
                                    # Show slot 2 plate if occupied, otherwise show actual status
                                    if self.slot_status["2"]["occupied"]:
                                        slot2_plate = self.slot_status["2"].get("license_plate")
                                        if slot2_plate and slot2_plate not in ["Unknown", "UNREADABLE"]:
                                            self.send_to_display("DBS", "SLOT 2 BUSY", slot2_plate, 0)
                                            logging.info(f"🔔 Single slot unauthorized cycle: Showing slot 2 plate: {slot2_plate}")
                                        else:
                                            # Show actual slot status instead of wrong message
                                            slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
                                            slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
                                            self.send_to_display("DBS", f"SLOT 1 {slot1_status}", f"SLOT 2 {slot2_status}", 0)
                                            logging.info(f"🔔 Single slot unauthorized cycle: Showing actual status - slot 1 {slot1_status}, slot 2 {slot2_status}")
                                    else:
                                        # Show actual slot status
                                        slot1_status = "BUSY" if self.slot_status["1"]["occupied"] else "FREE"
                                        slot2_status = "BUSY" if self.slot_status["2"]["occupied"] else "FREE"
                                        
                                        # Check for bookings
                                        try:
                                            booking_integration = self._get_booking_integration()
                                            slot_status_response = booking_integration.get_slot_status()
                                            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                                            
                                            # Update status to show BOOK for pre-booked slots that are not occupied
                                            if "1" in active_bookings and not self.slot_status["1"]["occupied"]:
                                                slot1_status = "BOOK"
                                            if "2" in active_bookings and not self.slot_status["2"]["occupied"]:
                                                slot2_status = "BOOK"
                                        except Exception:
                                            pass
                                        
                                        self.send_to_display("DBS", f"SLOT 1 {slot1_status}", f"SLOT 2 {slot2_status}", 0)
                                        logging.info(f"🔔 Single slot unauthorized cycle: Showing actual status - slot 1 {slot1_status}, slot 2 {slot2_status}")
                                    
                                    # Move to next unauthorized slot and cycle back to remove message
                                    unauthorized_slots_list = list(self.unauthorized_slots)
                                    if unauthorized_slots_list:
                                        self.current_unauthorized_slot_index = (self.current_unauthorized_slot_index + 1) % len(unauthorized_slots_list)
                                        logging.info(f"🔔 Single slot unauthorized cycle: Moving to next unauthorized slot {self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)}")
                                    else:
                                        # No more unauthorized slots, reset index
                                        self.current_unauthorized_slot_index = 0
                                        logging.info("🔔 Single slot unauthorized cycle: No more unauthorized slots, resetting index")
                                    self.unauthorized_cycle_state = "remove_message"
                        
                        elif self.current_display_type in ["entering", "exiting", "plate_detected"]:
                            # After showing entering/exiting/plate for event duration, start unauthorized cycle
                            if current_time - self.display_start_time > self.event_display_duration:
                                self.current_display_type = "unauthorized_cycle"
                                self.unauthorized_cycle_state = "remove_message"
                                self.unauthorized_cycle_start_time = current_time
                                # Start with remove message for current unauthorized slot
                                unauthorized_slots_list = list(self.unauthorized_slots)
                                if unauthorized_slots_list:
                                    unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                    self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                    logging.info(f"🔄 Single slot unauthorized: Starting improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                                else:
                                    # No unauthorized slots, switch to normal alternating
                                    self.current_display_type = "alternating"
                                    self.is_showing_status = True
                                    self.display_start_time = current_time
                                    self.display_slot_status()
                                    logging.info("🔄 Single slot: No unauthorized slots, switching to normal alternating cycle")
                        
                        elif self.current_display_type not in ["unauthorized_cycle", "entering", "exiting", "plate_detected"]:
                            # Initialize unauthorized cycle
                            self.current_display_type = "unauthorized_cycle"
                            self.unauthorized_cycle_state = "remove_message"
                            self.unauthorized_cycle_start_time = current_time
                            # Start with remove message for current unauthorized slot
                            unauthorized_slots_list = list(self.unauthorized_slots)
                            if unauthorized_slots_list:
                                unauthorized_slot = unauthorized_slots_list[self.current_unauthorized_slot_index % len(unauthorized_slots_list)]
                                self.display_unauthorized_vehicle_warning(unauthorized_slot)
                                logging.info(f"🔄 Single slot unauthorized: Initializing improved cycle with remove message for slot {unauthorized_slot} ({self.current_unauthorized_slot_index + 1}/{len(unauthorized_slots_list)})")
                            else:
                                # No unauthorized slots, switch to normal alternating
                                self.current_display_type = "alternating"
                                self.is_showing_status = True
                                self.display_start_time = current_time
                                self.display_slot_status()
                                logging.info("🔄 Single slot: No unauthorized slots, switching to normal alternating cycle")
                    
                    # Single slot or no slots busy logic (existing code)
                    elif self.current_display_type == "plate_detected":
                        if current_time - self.display_start_time > self.plate_display_duration:
                            self.current_display_type = "alternating"
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                    elif self.current_display_type in ["entering", "exiting", "unauthorized_warning", "attention_conflict"]:
                        if current_time - self.display_start_time > self.event_display_duration:
                            self.current_display_type = "alternating"
                            self.is_showing_status = True
                            self.display_start_time = current_time
                            self.display_slot_status()
                            # Reset flags
                            for slot_id in ["1", "2"]:
                                self.slot_status[slot_id]["entering"] = False
                                self.slot_status[slot_id]["exiting"] = False
                    elif self.current_display_type == "both_busy_alternating":
                        # Both slots are no longer busy, switch to normal alternating
                        self.current_display_type = "alternating"
                        self.is_showing_status = True
                        self.display_start_time = current_time
                        self.display_slot_status()
                        logging.info("🔄 Worker: Switching from both busy to normal alternating")
                    elif self.current_display_type == "alternating":
                        # Handle alternating between status and license plates
                        if self.is_showing_status:
                            if current_time - self.display_start_time > self.status_display_duration:
                                self.is_showing_status = False
                                self.display_start_time = current_time
                                self.display_occupied_slots_plates()
                        else:
                            if current_time - self.display_start_time > self.alternating_display_duration:
                                self.is_showing_status = True
                                self.display_start_time = current_time
                                self.display_slot_status()
                
                # Periodic booking status check (every 30 seconds)
                if not hasattr(self, 'last_booking_check'):
                    self.last_booking_check = current_time
                
                if current_time - self.last_booking_check > 30:  # Check every 30 seconds
                    self.handle_booking_status_change()
                    self.last_booking_check = current_time
                
                # Sleep for a short interval
                time.sleep(0.5)
                
            except Exception as e:
                logging.error(f"Error in display cycle worker: {e}")
                time.sleep(1)
    
    def stop_display_cycle(self) -> None:
        """Stop the display management cycle"""
        self.cycle_running = False
        self.display_event.clear()
        
        if self.display_thread and self.display_thread.is_alive():
            self.display_thread.join(timeout=2)
        
        logging.info("P10 Display cycle stopped")
    
    def get_current_status(self) -> Dict[str, Any]:
        """Get current display and slot status"""
        with self.display_lock:
            return {
                "slot_status": self.slot_status.copy(),
                "current_display_type": self.current_display_type,
                "cycle_running": self.cycle_running,
                "last_message": self.last_sent_message,
                "unauthorized_slots": list(self.unauthorized_slots),
                "conflict_warnings": list(self.conflict_warning_displayed)
            }
    
    def trigger_unauthorized_warning(self, slot_id: str, expected_plate: str = "ABC1234") -> bool:
        """
        Manually trigger unauthorized vehicle warning for testing
        
        Args:
            slot_id: Slot ID
            expected_plate: Expected license plate
            
        Returns:
            bool: True if successful
        """
        try:
            # Add to unauthorized slots
            self.unauthorized_slots.add(slot_id)
            
            # Show unauthorized warning
            self.current_display_type = "unauthorized_warning"
            self.display_start_time = time.time()
            success = self.display_unauthorized_vehicle_warning(slot_id)
            
            # Schedule attention message after 15 seconds
            def show_attention_message():
                time.sleep(15)
                if slot_id in self.unauthorized_slots:
                    self.current_display_type = "attention_conflict"
                    self.display_start_time = time.time()
                    # Get complete booking data for the slot
                    try:
                        booking_integration = self._get_booking_integration()
                        if booking_integration:
                            slot_status_response = booking_integration.get_slot_status()
                            active_bookings = slot_status_response.get("data", {}).get("slotStatus", {})
                            booking = active_bookings.get(slot_id)
                            self.display_attention_booking_conflict(slot_id, booking)
                        else:
                            self.display_attention_booking_conflict(slot_id, {"expectedPlate": expected_plate})
                    except Exception:
                        self.display_attention_booking_conflict(slot_id, {"expectedPlate": expected_plate})
                    self.conflict_warning_displayed.add(slot_id)
            
            # Start attention message thread
            import threading
            attention_thread = threading.Thread(target=show_attention_message, daemon=True)
            attention_thread.start()
            
            logging.info(f"🔔 Triggered unauthorized warning for slot {slot_id}")
            return success
            
        except Exception as e:
            logging.error(f"Error triggering unauthorized warning: {e}")
            return False

    def test_both_slots_busy_non_booked(self) -> bool:
        """
        Test both slots busy scenario in non-booked mode (no unauthorized vehicles)
        
        Returns:
            bool: True if successful
        """
        try:
            # Simulate both slots busy in non-booked mode
            self.slot_status["1"]["occupied"] = True
            self.slot_status["1"]["license_plate"] = "CBB4567"  # Slot 1's plate
            self.slot_status["2"]["occupied"] = True
            self.slot_status["2"]["license_plate"] = "AAB7793"  # Slot 2's plate
            
            # Clear unauthorized slots (non-booked mode)
            self.unauthorized_slots.clear()
            
            # Test the display - should cycle between slot 1 and slot 2
            success = self.display_occupied_slots_plates()
            
            if success:
                logging.info(f"✅ Test both slots busy non-booked successful")
                logging.info(f"   Slot 1 plate: CBB4567")
                logging.info(f"   Slot 2 plate: AAB7793")
                logging.info(f"   Display should cycle between:")
                logging.info(f"   - SLOT 1 BUSY")
                logging.info(f"     CBB4567")
                logging.info(f"   - SLOT 2 BUSY")
                logging.info(f"     AAB7793")
                logging.info(f"   No unauthorized vehicles - pure cycling only")
            else:
                logging.error(f"❌ Test both slots busy non-booked failed")
            
            return success
            
        except Exception as e:
            logging.error(f"Error testing both slots busy non-booked: {e}")
            return False

    def test_both_slots_busy_unauthorized(self, slot_id: str = "2", unauthorized_plate: str = "BGG5654") -> bool:
        """
        Test both slots busy scenario with cycling between slot 1 and slot 2 plates
        
        Args:
            slot_id: Slot ID with unauthorized vehicle (default: "2")
            unauthorized_plate: License plate of unauthorized vehicle
            
        Returns:
            bool: True if successful
        """
        try:
            # Simulate both slots busy
            self.slot_status["1"]["occupied"] = True
            self.slot_status["1"]["license_plate"] = "CBB4567"  # Slot 1's actual plate
            self.slot_status["2"]["occupied"] = True
            self.slot_status["2"]["license_plate"] = unauthorized_plate  # Slot 2's plate (unauthorized)
            
            # Add to unauthorized slots
            self.unauthorized_slots.add(slot_id)
            
            # Test the display - should show slot 1's plate first
            success = self.display_occupied_slots_plates()
            
            if success:
                logging.info(f"✅ Test both slots busy successful")
                logging.info(f"   Slot 1 plate: CBB4567")
                logging.info(f"   Slot 2 plate: {unauthorized_plate}")
                logging.info(f"   Display should cycle between:")
                logging.info(f"   - SLOT 1 BUSY")
                logging.info(f"     CBB4567")
                logging.info(f"   - SLOT 2 BUSY")
                logging.info(f"     {unauthorized_plate}")
                logging.info(f"   With periodic attention and remove messages")
            else:
                logging.error(f"❌ Test both slots busy failed")
            
            return success
            
        except Exception as e:
            logging.error(f"Error testing both slots busy: {e}")
            return False

# Factory function to create and configure P10 display manager
def get_p10_display(esp32_ip: str = "192.168.8.130", key: str = "uom") -> P10DisplayManager:
    """
    Factory function to create P10 Display Manager instance
    
    Args:
        esp32_ip: IP address of ESP32
        key: Authentication key
        
    Returns:
        P10DisplayManager: Configured display manager instance
    """
    return P10DisplayManager(esp32_ip, key)

# Example usage and testing
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s: %(message)s')
    
    # Create display manager
    display = get_p10_display("192.168.8.130", "uom")
    
    # Test system ready
    print("Testing system ready message...")
    display.display_system_ready()
    time.sleep(3)
    
    # Test slot status
    print("Testing slot status...")
    display.display_slot_status()
    time.sleep(3)
    
    # Test vehicle entering
    print("Testing vehicle entering...")
    display.display_vehicle_entering("1")
    time.sleep(3)
    
    # Test plate detection
    print("Testing plate detection...")
    display.display_plate_detected("1", "ABC1234")
    time.sleep(3)
    
    # Test vehicle exiting
    print("Testing vehicle exiting...")
    display.display_vehicle_exiting("1", "ABC1234")
    time.sleep(3)
    
    # Return to status
    print("Returning to status...")
    display.display_slot_status()
    
    print("P10 Display Manager test completed!")