import cv2
import numpy as np
import time
import logging
from typing import Dict, Tuple
import json


class EnhancedVehicleExitDetector:
    """
    Advanced vehicle exit detection system with multiple validation methods
    to reduce false positives caused by temporary occlusions.
    """

    def __init__(self, parking_slots: Dict):
        self.parking_slots = parking_slots
        self.slot_tracking = {
            slot_id: {
                # Current state
                "occupied": False,
                "vehicle_bbox": None,
                "license_plate": None,
                "vehicle_type": None,
                "entry_time": None,

                # Exit detection enhancement
                "exit_buffer": {
                    "start_time": None,
                    "buffer_duration": 4,  # Reduced from 8 to 4 seconds for faster response
                    "confidence_threshold": 0.6,  # Reduced from 0.7 to 0.6 for easier exit confirmation
                    "last_seen_time": None,
                    "consecutive_misses": 0,
                    "max_consecutive_misses": 3  # Reduced from 5 to 3 for faster exit detection
                },

                # Motion and change detection
                "motion_tracker": {
                    "background_model": None,
                    "motion_threshold": 500,  # Minimum motion pixels to consider significant
                    "motion_history": [],  # Store recent motion levels
                    "history_size": 10
                },

                # Multi-frame validation
                "frame_validator": {
                    "validation_frames": [],  # Store recent detection results
                    "frame_count": 15,  # Number of frames to analyze
                    "positive_threshold": 0.6  # 60% of frames must show no vehicle
                },

                # Occlusion detection
                "occlusion_detector": {
                    "baseline_brightness": None,
                    "brightness_threshold": 30,  # Significant brightness change indicates occlusion
                    "edge_density_baseline": None,
                    "edge_threshold": 0.3,  # Edge density change threshold
                    "occlusion_probability": 0.0
                },

                # Exit direction analysis
                "direction_tracker": {
                    "vehicle_positions": [],  # Store recent vehicle center positions
                    "position_history_size": 20,
                    "exit_direction_detected": False,
                    "exit_zones": None  # Filled below
                }
            } for slot_id in parking_slots
        }

        # Fill exit zones after dict creation
        for slot_id in self.parking_slots:
            self.slot_tracking[slot_id]["direction_tracker"]["exit_zones"] = self._define_exit_zones(slot_id)

        # Global settings
        self.frame_count = 0
        self.detection_confidence_threshold = 0.5

        # Initialize background subtractors for each slot
        for slot_id in self.parking_slots:
            self.slot_tracking[slot_id]["motion_tracker"]["background_model"] = \
                cv2.createBackgroundSubtractorMOG2(history=500, varThreshold=16, detectShadows=True)

    def _define_exit_zones(self, slot_id: str) -> Dict:
        """Define exit zones around parking slots for direction analysis"""
        slot_coords = self.parking_slots[slot_id]

        # Calculate slot center and boundaries
        x_coords = [point[0] for point in slot_coords]
        y_coords = [point[1] for point in slot_coords]
        center_x = sum(x_coords) // len(x_coords)
        center_y = sum(y_coords) // len(y_coords)

        # Define exit zones (expanded areas around the slot)
        margin = 50
        exit_zones = {
            "left": min(x_coords) - margin,
            "right": max(x_coords) + margin,
            "top": min(y_coords) - margin,
            "bottom": max(y_coords) + margin,
            "center": (center_x, center_y)
        }

        return exit_zones

    def detect_motion_in_slot(self, frame: np.ndarray, slot_id: str) -> float:
        """Detect motion level in a specific parking slot"""
        try:
            slot_coords = self.parking_slots[slot_id]
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [np.array(slot_coords, np.int32)], 255)

            # Apply background subtraction
            bg_model = self.slot_tracking[slot_id]["motion_tracker"]["background_model"]
            fg_mask = bg_model.apply(frame)

            # Apply slot mask
            slot_motion = cv2.bitwise_and(fg_mask, mask)

            # Calculate motion level
            motion_pixels = np.sum(slot_motion > 0)
            total_slot_pixels = np.sum(mask > 0)
            motion_ratio = motion_pixels / total_slot_pixels if total_slot_pixels > 0 else 0

            # Update motion history
            motion_tracker = self.slot_tracking[slot_id]["motion_tracker"]
            motion_tracker["motion_history"].append(motion_ratio)

            if len(motion_tracker["motion_history"]) > motion_tracker["history_size"]:
                motion_tracker["motion_history"].pop(0)

            return motion_ratio

        except Exception as e:
            logging.error(f"Motion detection error for slot {slot_id}: {e}")
            return 0.0

    def detect_occlusion(self, frame: np.ndarray, slot_id: str) -> float:
        """Detect if the slot is occluded by analyzing brightness and edge density"""
        try:
            slot_coords = self.parking_slots[slot_id]
            mask = np.zeros(frame.shape[:2], dtype=np.uint8)
            cv2.fillPoly(mask, [np.array(slot_coords, np.int32)], 255)

            # Extract slot region
            slot_region = cv2.bitwise_and(frame, frame, mask=mask)
            gray_slot = cv2.cvtColor(slot_region, cv2.COLOR_BGR2GRAY)

            # Calculate current metrics
            valid_pixels = gray_slot[mask > 0]
            if valid_pixels.size == 0:
                return 0.0
            current_brightness = float(np.mean(valid_pixels))
            edges = cv2.Canny(gray_slot, 50, 150)
            current_edge_density = float(np.sum(edges[mask > 0] > 0)) / float(np.sum(mask > 0))

            occlusion_detector = self.slot_tracking[slot_id]["occlusion_detector"]

            # Initialize baseline if not set
            if occlusion_detector["baseline_brightness"] is None:
                occlusion_detector["baseline_brightness"] = current_brightness
                occlusion_detector["edge_density_baseline"] = current_edge_density
                return 0.0

            # Calculate changes from baseline
            brightness_change = abs(current_brightness - occlusion_detector["baseline_brightness"])
            edge_density_change = abs(current_edge_density - occlusion_detector["edge_density_baseline"])

            # Determine occlusion probability
            occlusion_prob = 0.0

            if brightness_change > occlusion_detector["brightness_threshold"]:
                occlusion_prob += 0.4

            if edge_density_change > occlusion_detector["edge_threshold"]:
                occlusion_prob += 0.4

            # Check for uniform regions (possible complete occlusion)
            std_dev = float(np.std(valid_pixels))
            if std_dev < 10:  # Very uniform region
                occlusion_prob += 0.3

            occlusion_detector["occlusion_probability"] = min(occlusion_prob, 1.0)
            return occlusion_detector["occlusion_probability"]

        except Exception as e:
            logging.error(f"Occlusion detection error for slot {slot_id}: {e}")
            return 0.0

    def track_vehicle_direction(self, vehicle_bbox: Tuple, slot_id: str) -> bool:
        """Track vehicle movement direction to detect actual exits"""
        try:
            if not vehicle_bbox:
                return False

            x1, y1, x2, y2 = vehicle_bbox
            vehicle_center = ((x1 + x2) // 2, (y1 + y2) // 2)

            direction_tracker = self.slot_tracking[slot_id]["direction_tracker"]
            direction_tracker["vehicle_positions"].append({
                "position": vehicle_center,
                "timestamp": time.time()
            })

            # Keep only recent positions
            if len(direction_tracker["vehicle_positions"]) > direction_tracker["position_history_size"]:
                direction_tracker["vehicle_positions"].pop(0)

            # Analyze movement pattern if we have enough data
            if len(direction_tracker["vehicle_positions"]) >= 5:
                positions = [p["position"] for p in direction_tracker["vehicle_positions"]]

                # Calculate movement vector
                start_pos = positions[0]
                end_pos = positions[-1]
                movement_vector = (end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
                movement_magnitude = np.sqrt(movement_vector[0] ** 2 + movement_vector[1] ** 2)

                # Check if vehicle is moving towards exit zones
                exit_zones = direction_tracker["exit_zones"]
                slot_center = exit_zones["center"]

                # Determine if movement is away from slot center
                distance_from_center_start = np.sqrt((start_pos[0] - slot_center[0]) ** 2 +
                                                     (start_pos[1] - slot_center[1]) ** 2)
                distance_from_center_end = np.sqrt((end_pos[0] - slot_center[0]) ** 2 +
                                                   (end_pos[1] - slot_center[1]) ** 2)

                # Vehicle is likely exiting if:
                # 1. It's moving significantly (not stationary)
                # 2. It's moving away from the slot center
                # 3. Movement magnitude is substantial
                is_moving_away = distance_from_center_end > distance_from_center_start
                is_significant_movement = movement_magnitude > 20

                direction_tracker["exit_direction_detected"] = (is_moving_away and is_significant_movement)

                return direction_tracker["exit_direction_detected"]

            return False

        except Exception as e:
            logging.error(f"Direction tracking error for slot {slot_id}: {e}")
            return False

    def update_frame_validation(self, slot_id: str, vehicle_detected: bool) -> float:
        """Update multi-frame validation for robust exit detection"""
        frame_validator = self.slot_tracking[slot_id]["frame_validator"]

        frame_validator["validation_frames"].append(bool(vehicle_detected))

        if len(frame_validator["validation_frames"]) > frame_validator["frame_count"]:
            frame_validator["validation_frames"].pop(0)

        # Calculate detection ratio
        if len(frame_validator["validation_frames"]) >= frame_validator["frame_count"]:
            positive_detections = sum(1 for v in frame_validator["validation_frames"] if v)
            detection_ratio = positive_detections / float(len(frame_validator["validation_frames"]))
            return detection_ratio

        return 1.0  # Default to vehicle present if not enough data

    def enhanced_exit_detection(self, frame: np.ndarray, current_detections: Dict) -> Dict:
        """
        Main function for enhanced vehicle exit detection
        Returns updated slot status with reduced false positives
        """
        self.frame_count += 1
        updated_status = {}

        for slot_id in self.parking_slots:
            slot_info = self.slot_tracking[slot_id]
            current_detection = current_detections.get(slot_id, {})
            vehicle_detected = current_detection.get("vehicle_present", False)
            vehicle_bbox = current_detection.get("bbox", None)

            # Multi-layered analysis
            motion_level = self.detect_motion_in_slot(frame, slot_id)
            occlusion_probability = self.detect_occlusion(frame, slot_id)
            direction_analysis = self.track_vehicle_direction(vehicle_bbox, slot_id) if vehicle_bbox else False
            detection_ratio = self.update_frame_validation(slot_id, vehicle_detected)

            # Current slot state
            currently_occupied = slot_info["occupied"]
            exit_buffer = slot_info["exit_buffer"]

            exit_confidence = 0.0

            if vehicle_detected:
                # Vehicle is clearly visible
                exit_buffer["last_seen_time"] = time.time()
                exit_buffer["consecutive_misses"] = 0
                exit_buffer["start_time"] = None  # Reset exit buffer

                if not currently_occupied:
                    # New vehicle entry
                    slot_info["occupied"] = True
                    slot_info["entry_time"] = time.time()
                    slot_info["vehicle_bbox"] = vehicle_bbox
                    slot_info["license_plate"] = current_detection.get("license_plate")
                    slot_info["vehicle_type"] = current_detection.get("vehicle_type", "Unknown")
                    logging.info(f"Vehicle entered slot {slot_id}")

            elif currently_occupied:
                # Vehicle not detected but slot was occupied
                exit_buffer["consecutive_misses"] += 1

                # Enhanced decision making
                confidence_factors = {
                    "detection_ratio": detection_ratio,
                    "motion_level": motion_level,
                    "occlusion_probability": occlusion_probability,
                    "direction_analysis": direction_analysis,
                    "consecutive_misses": exit_buffer["consecutive_misses"]
                }

                # Calculate exit confidence
                exit_confidence = self._calculate_exit_confidence(confidence_factors, exit_buffer)

                # Start exit buffer if conditions are met
                if (exit_buffer["consecutive_misses"] >= exit_buffer["max_consecutive_misses"] and
                        exit_buffer["start_time"] is None):
                    exit_buffer["start_time"] = time.time()
                    logging.info(f"Exit buffer started for slot {slot_id} (confidence: {exit_confidence:.2f})")

                # Check if exit should be confirmed
                if (exit_buffer["start_time"] and
                        time.time() - exit_buffer["start_time"] >= exit_buffer["buffer_duration"] and
                        exit_confidence >= exit_buffer["confidence_threshold"]):

                    # Confirm vehicle exit
                    logging.info(
                        f"Vehicle exit confirmed for slot {slot_id} (confidence: {exit_confidence:.2f})")

                    # Reset slot state completely
                    slot_info["occupied"] = False
                    slot_info["vehicle_bbox"] = None
                    slot_info["entry_time"] = None
                    slot_info["license_plate"] = None
                    slot_info["vehicle_type"] = None

                    # Reset tracking data
                    exit_buffer["start_time"] = None
                    exit_buffer["consecutive_misses"] = 0
                    slot_info["direction_tracker"]["vehicle_positions"] = []
                    slot_info["frame_validator"]["validation_frames"] = []
                    
                    # Force immediate status update
                    logging.info(f"Slot {slot_id} status reset to FREE - exit confirmed")

                # If occlusion is high, extend buffer time
                elif occlusion_probability > 0.6:
                    if exit_buffer["start_time"]:
                        # Extend buffer for potential occlusion
                        extended_duration = exit_buffer["buffer_duration"] + 3  # Reduced from 5 to 3 seconds
                        if time.time() - exit_buffer["start_time"] < extended_duration:
                            logging.info(f"Extending exit buffer for slot {slot_id} due to occlusion")
                
                # Force exit if vehicle has been missing for too long (emergency exit)
                elif (exit_buffer["consecutive_misses"] >= 10 and 
                      exit_buffer["start_time"] and 
                      time.time() - exit_buffer["start_time"] >= 6):  # Force exit after 6 seconds
                    
                    logging.warning(f"FORCING exit for slot {slot_id} after extended absence")
                    slot_info["occupied"] = False
                    slot_info["vehicle_bbox"] = None
                    slot_info["entry_time"] = None
                    slot_info["license_plate"] = None
                    slot_info["vehicle_type"] = None
                    
                    # Reset all tracking data
                    exit_buffer["start_time"] = None
                    exit_buffer["consecutive_misses"] = 0
                    slot_info["direction_tracker"]["vehicle_positions"] = []
                    slot_info["frame_validator"]["validation_frames"] = []
                    
                    logging.info(f"Slot {slot_id} FORCED to FREE after extended absence")

            # Update status for return
            updated_status[slot_id] = {
                "occupied": slot_info["occupied"],
                "vehicle_bbox": slot_info["vehicle_bbox"],
                "license_plate": slot_info["license_plate"],
                "vehicle_type": slot_info["vehicle_type"],
                "entry_time": slot_info["entry_time"],
                "exit_confidence": exit_confidence if currently_occupied else 0.0,
                "motion_level": motion_level,
                "occlusion_probability": occlusion_probability
            }

        return updated_status

    def _calculate_exit_confidence(self, factors: Dict, exit_buffer: Dict) -> float:
        """Calculate confidence score for vehicle exit based on multiple factors"""
        confidence = 0.0

        # Low detection ratio increases exit confidence
        if factors["detection_ratio"] < 0.3:
            confidence += 0.4
        elif factors["detection_ratio"] < 0.5:
            confidence += 0.2

        # High motion during "exit" period suggests real movement
        if factors["motion_level"] > 0.1:
            confidence += 0.2
        elif factors["motion_level"] > 0.05:
            confidence += 0.1

        # Low occlusion probability increases exit confidence
        if factors["occlusion_probability"] < 0.3:
            confidence += 0.2
        elif factors["occlusion_probability"] > 0.7:
            confidence -= 0.3  # High occlusion reduces confidence

        # Direction analysis
        if factors["direction_analysis"]:
            confidence += 0.3

        # Consecutive misses (more misses = higher confidence)
        miss_factor = min(factors["consecutive_misses"] / 10.0, 0.2)
        confidence += miss_factor

        return float(min(max(confidence, 0.0), 1.0))

    def save_status_to_file(self, filename: str = "enhanced_slot_status.json"):
        """Save current slot status to file"""
        try:
            serializable_status = {}
            for slot_id, slot_info in self.slot_tracking.items():
                serializable_status[slot_id] = {
                    "occupied": slot_info["occupied"],
                    "license_plate": slot_info["license_plate"],
                    "vehicle_type": slot_info["vehicle_type"],
                    "entry_time": slot_info["entry_time"],
                    "last_updated": time.time()
                }

            with open(filename, "w") as f:
                json.dump(serializable_status, f, indent=2)

        except Exception as e:
            logging.error(f"Error saving status to file: {e}")


