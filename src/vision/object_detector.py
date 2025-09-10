"""
Object Detection Engine

This module provides comprehensive object detection capabilities including shape detection,
color-based identification, and custom detection algorithms for educational robotics.

Features:
- Built-in detection for standard geometric shapes (circles, squares, triangles)
- Color-based object identification with HSV color space analysis
- Custom detection algorithm framework for workshop-specific objects
- Confidence scoring and detection validation with >95% accuracy target
- Real-time performance optimization with <100ms processing time per frame
- Educational visualization and debugging tools
"""

import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from vision.camera_interface import CameraInterface, ImageFormat
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import VisionError

logger = get_logger(__name__)


class ShapeType(Enum):
    """Supported geometric shapes."""
    CIRCLE = "circle"
    SQUARE = "square"
    RECTANGLE = "rectangle"
    TRIANGLE = "triangle"
    PENTAGON = "pentagon"
    HEXAGON = "hexagon"
    UNKNOWN = "unknown"


class ColorType(Enum):
    """Supported color categories."""
    RED = "red"
    GREEN = "green"
    BLUE = "blue"
    YELLOW = "yellow"
    ORANGE = "orange"
    PURPLE = "purple"
    CYAN = "cyan"
    WHITE = "white"
    BLACK = "black"
    UNKNOWN = "unknown"


@dataclass
class ColorRange:
    """HSV color range definition."""
    name: str
    lower: Tuple[int, int, int]  # Lower HSV bounds
    upper: Tuple[int, int, int]  # Upper HSV bounds
    description: str = ""


@dataclass
class DetectedObject:
    """Information about a detected object."""
    shape: ShapeType
    color: ColorType
    center: Tuple[int, int]  # (x, y) pixel coordinates
    bounding_box: Tuple[int, int, int, int]  # (x, y, width, height)
    area: float
    perimeter: float
    confidence: float  # 0.0 to 1.0
    contour: Optional[np.ndarray] = None
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DetectionParameters:
    """Object detection configuration parameters."""
    # Preprocessing
    blur_kernel_size: int = 5
    gaussian_blur: bool = True
    morphology_operations: bool = True
    
    # Contour detection
    min_contour_area: float = 100.0
    max_contour_area: float = 50000.0
    contour_approximation_epsilon: float = 0.02
    
    # Shape detection
    circle_detection_threshold: float = 0.8
    polygon_approximation_epsilon: float = 0.02
    aspect_ratio_tolerance: float = 0.2
    
    # Color detection
    color_detection_enabled: bool = True
    color_area_threshold: float = 0.1  # Minimum percentage of object area
    
    # Confidence thresholds
    min_confidence: float = 0.7
    shape_confidence_weight: float = 0.6
    color_confidence_weight: float = 0.4
    
    # Performance
    max_objects_per_frame: int = 20
    processing_timeout: float = 0.1  # 100ms timeout


class ObjectDetector:
    """
    Advanced object detection engine providing shape and color detection
    with educational visualization and custom detection capabilities.
    """
    
    def __init__(self, camera_interface: Optional[CameraInterface] = None, config_manager=None):
        """
        Initialize object detector.
        
        Args:
            camera_interface: Camera interface for live detection
            config_manager: Configuration manager instance
        """
        self.camera_interface = camera_interface
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Detection parameters
        self.parameters = DetectionParameters()
        
        # Color definitions (HSV color space)
        self._color_ranges = self._initialize_color_ranges()
        
        # Custom detection algorithms
        self._custom_detectors: Dict[str, Callable] = {}
        
        # Performance monitoring
        self._detection_history: List[Dict[str, Any]] = []
        
        # Statistics
        self._total_detections = 0
        self._successful_detections = 0
        self._processing_times = []
        
        logger.info("Object detector initialized")
    
    @property
    def detection_accuracy(self) -> float:
        """Get detection accuracy percentage."""
        if self._total_detections == 0:
            return 0.0
        return (self._successful_detections / self._total_detections) * 100
    
    @property
    def average_processing_time(self) -> float:
        """Get average processing time in milliseconds."""
        if not self._processing_times:
            return 0.0
        return sum(self._processing_times) / len(self._processing_times) * 1000
    
    def _initialize_color_ranges(self) -> Dict[ColorType, ColorRange]:
        """Initialize HSV color ranges for detection."""
        return {
            ColorType.RED: ColorRange("red", (0, 50, 50), (10, 255, 255), "Red objects"),
            ColorType.GREEN: ColorRange("green", (40, 50, 50), (80, 255, 255), "Green objects"),
            ColorType.BLUE: ColorRange("blue", (100, 50, 50), (130, 255, 255), "Blue objects"),
            ColorType.YELLOW: ColorRange("yellow", (20, 50, 50), (40, 255, 255), "Yellow objects"),
            ColorType.ORANGE: ColorRange("orange", (10, 50, 50), (20, 255, 255), "Orange objects"),
            ColorType.PURPLE: ColorRange("purple", (130, 50, 50), (160, 255, 255), "Purple objects"),
            ColorType.CYAN: ColorRange("cyan", (80, 50, 50), (100, 255, 255), "Cyan objects"),
            ColorType.WHITE: ColorRange("white", (0, 0, 200), (180, 30, 255), "White objects"),
            ColorType.BLACK: ColorRange("black", (0, 0, 0), (180, 255, 50), "Black objects")
        }
    
    def set_parameters(self, parameters: DetectionParameters) -> None:
        """
        Set detection parameters.
        
        Args:
            parameters: Detection parameters to set
        """
        self.parameters = parameters
        logger.info("Detection parameters updated")
    
    def add_color_range(self, color_type: ColorType, color_range: ColorRange) -> None:
        """
        Add or update color range definition.
        
        Args:
            color_type: Color type to define
            color_range: HSV color range
        """
        self._color_ranges[color_type] = color_range
        logger.info(f"Added color range for {color_type.value}: {color_range.name}")
    
    def add_custom_detector(self, name: str, detector_func: Callable) -> None:
        """
        Add custom detection algorithm.
        
        Args:
            name: Name of the custom detector
            detector_func: Function that takes (image, parameters) and returns List[DetectedObject]
        """
        self._custom_detectors[name] = detector_func
        logger.info(f"Added custom detector: {name}")
    def detect_objects(self, image: np.ndarray, 
                      detect_shapes: bool = True,
                      detect_colors: bool = True,
                      custom_detectors: Optional[List[str]] = None) -> List[DetectedObject]:
        """
        Detect objects in image using specified detection methods.
        
        Args:
            image: Input image (BGR format)
            detect_shapes: Enable shape detection
            detect_colors: Enable color detection
            custom_detectors: List of custom detector names to use
            
        Returns:
            List of detected objects
        """
        start_time = time.time()
        
        try:
            # Validate input
            if image is None or image.size == 0:
                raise VisionError("Invalid input image")
            
            # Preprocess image
            processed_image = self._preprocess_image(image)
            
            # Find contours
            contours = self._find_contours(processed_image)
            
            # Detect objects from contours
            detected_objects = []
            
            for contour in contours[:self.parameters.max_objects_per_frame]:
                # Check contour area
                area = cv2.contourArea(contour)
                if area < self.parameters.min_contour_area or area > self.parameters.max_contour_area:
                    continue
                
                # Create base object
                obj = self._create_base_object(contour, image)
                
                # Detect shape
                if detect_shapes:
                    obj.shape, shape_confidence = self._detect_shape(contour)
                else:
                    shape_confidence = 0.0
                
                # Detect color
                if detect_colors and self.parameters.color_detection_enabled:
                    obj.color, color_confidence = self._detect_color(image, contour)
                else:
                    color_confidence = 0.0
                
                # Calculate overall confidence
                obj.confidence = (
                    shape_confidence * self.parameters.shape_confidence_weight +
                    color_confidence * self.parameters.color_confidence_weight
                )
                
                # Apply confidence threshold
                if obj.confidence >= self.parameters.min_confidence:
                    detected_objects.append(obj)
            
            # Apply custom detectors
            if custom_detectors:
                for detector_name in custom_detectors:
                    if detector_name in self._custom_detectors:
                        try:
                            custom_objects = self._custom_detectors[detector_name](image, self.parameters)
                            detected_objects.extend(custom_objects)
                        except Exception as e:
                            logger.warning(f"Custom detector {detector_name} failed: {e}")
            
            # Update statistics
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            if len(self._processing_times) > 100:  # Keep last 100 measurements
                self._processing_times.pop(0)
            
            self._total_detections += 1
            if detected_objects:
                self._successful_detections += 1
            
            # Record detection
            self._record_detection({
                'timestamp': start_time,
                'objects_detected': len(detected_objects),
                'processing_time': processing_time,
                'shapes_detected': [obj.shape.value for obj in detected_objects],
                'colors_detected': [obj.color.value for obj in detected_objects],
                'average_confidence': sum(obj.confidence for obj in detected_objects) / len(detected_objects) if detected_objects else 0.0
            })
            
            logger.debug(f"Detected {len(detected_objects)} objects in {processing_time*1000:.1f}ms")
            return detected_objects
            
        except Exception as e:
            processing_time = time.time() - start_time
            self._processing_times.append(processing_time)
            
            error_msg = f"Object detection failed: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)
    
    def detect_objects_live(self, duration: float = 10.0,
                           callback: Optional[Callable[[List[DetectedObject]], None]] = None) -> List[List[DetectedObject]]:
        """
        Perform live object detection using camera interface.
        
        Args:
            duration: Detection duration in seconds
            callback: Optional callback for each detection result
            
        Returns:
            List of detection results for each frame
        """
        if not self.camera_interface or not self.camera_interface.is_connected:
            raise VisionError("Camera interface not available or not connected")
        
        logger.info(f"Starting live object detection for {duration} seconds...")
        
        results = []
        start_time = time.time()
        
        # Start streaming if not already active
        was_streaming = self.camera_interface.is_streaming
        if not was_streaming:
            self.camera_interface.start_streaming(ImageFormat.BGR)
        
        try:
            while time.time() - start_time < duration:
                # Get latest frame
                frame, frame_info = self.camera_interface.get_latest_frame(timeout=0.1)
                
                if frame is not None:
                    # Detect objects
                    detected_objects = self.detect_objects(frame)
                    results.append(detected_objects)
                    
                    # Call callback if provided
                    if callback:
                        try:
                            callback(detected_objects)
                        except Exception as e:
                            logger.warning(f"Detection callback error: {e}")
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)
        
        finally:
            # Stop streaming if we started it
            if not was_streaming:
                self.camera_interface.stop_streaming()
        
        logger.info(f"Live detection completed: {len(results)} frames processed")
        return results

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for object detection.

        Args:
            image: Input image (BGR format)

        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur
        if self.parameters.gaussian_blur:
            gray = cv2.GaussianBlur(gray, (self.parameters.blur_kernel_size, self.parameters.blur_kernel_size), 0)

        # Apply adaptive threshold
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )

        # Apply morphological operations
        if self.parameters.morphology_operations:
            kernel = np.ones((3, 3), np.uint8)
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

        return binary

    def _find_contours(self, binary_image: np.ndarray) -> List[np.ndarray]:
        """
        Find contours in binary image.

        Args:
            binary_image: Binary image

        Returns:
            List of contours sorted by area (largest first)
        """
        contours, _ = cv2.findContours(binary_image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter and sort contours by area
        filtered_contours = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.parameters.min_contour_area <= area <= self.parameters.max_contour_area:
                filtered_contours.append(contour)

        # Sort by area (largest first)
        filtered_contours.sort(key=cv2.contourArea, reverse=True)

        return filtered_contours

    def _create_base_object(self, contour: np.ndarray, image: np.ndarray) -> DetectedObject:
        """
        Create base detected object from contour.

        Args:
            contour: Object contour
            image: Original image

        Returns:
            Base detected object
        """
        # Calculate basic properties
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)

        # Calculate center
        M = cv2.moments(contour)
        if M["m00"] != 0:
            center_x = int(M["m10"] / M["m00"])
            center_y = int(M["m01"] / M["m00"])
        else:
            center_x, center_y = x + w // 2, y + h // 2

        return DetectedObject(
            shape=ShapeType.UNKNOWN,
            color=ColorType.UNKNOWN,
            center=(center_x, center_y),
            bounding_box=(x, y, w, h),
            area=area,
            perimeter=perimeter,
            confidence=0.0,
            contour=contour
        )

    def _detect_shape(self, contour: np.ndarray) -> Tuple[ShapeType, float]:
        """
        Detect shape from contour.

        Args:
            contour: Object contour

        Returns:
            Tuple of (shape_type, confidence)
        """
        # Approximate contour to polygon
        epsilon = self.parameters.polygon_approximation_epsilon * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Get number of vertices
        vertices = len(approx)

        # Calculate area and perimeter for additional checks
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        # Circle detection using area-to-perimeter ratio
        if vertices > 8:  # Many vertices suggest a circle
            circularity = 4 * math.pi * area / (perimeter * perimeter)
            if circularity > self.parameters.circle_detection_threshold:
                return ShapeType.CIRCLE, circularity

        # Polygon detection based on vertices
        if vertices == 3:
            return ShapeType.TRIANGLE, 0.9
        elif vertices == 4:
            # Distinguish between square and rectangle
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = float(w) / h

            if 1 - self.parameters.aspect_ratio_tolerance <= aspect_ratio <= 1 + self.parameters.aspect_ratio_tolerance:
                return ShapeType.SQUARE, 0.9
            else:
                return ShapeType.RECTANGLE, 0.8
        elif vertices == 5:
            return ShapeType.PENTAGON, 0.8
        elif vertices == 6:
            return ShapeType.HEXAGON, 0.8

        return ShapeType.UNKNOWN, 0.1

    def _detect_color(self, image: np.ndarray, contour: np.ndarray) -> Tuple[ColorType, float]:
        """
        Detect dominant color in contour region.

        Args:
            image: Original image (BGR format)
            contour: Object contour

        Returns:
            Tuple of (color_type, confidence)
        """
        # Create mask for the contour
        mask = np.zeros(image.shape[:2], np.uint8)
        cv2.fillPoly(mask, [contour], 255)

        # Convert image to HSV
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Calculate total pixels in contour
        total_pixels = cv2.countNonZero(mask)
        if total_pixels == 0:
            return ColorType.UNKNOWN, 0.0

        best_color = ColorType.UNKNOWN
        best_confidence = 0.0

        # Test each color range
        for color_type, color_range in self._color_ranges.items():
            # Create color mask
            color_mask = cv2.inRange(hsv, color_range.lower, color_range.upper)

            # Apply contour mask
            combined_mask = cv2.bitwise_and(color_mask, mask)

            # Count matching pixels
            matching_pixels = cv2.countNonZero(combined_mask)

            # Calculate confidence as percentage of contour area
            confidence = matching_pixels / total_pixels

            # Check if this color is dominant enough
            if confidence > self.parameters.color_area_threshold and confidence > best_confidence:
                best_color = color_type
                best_confidence = confidence

        return best_color, best_confidence

    def _record_detection(self, detection_data: Dict[str, Any]) -> None:
        """
        Record detection result in history.

        Args:
            detection_data: Detection data to record
        """
        self._detection_history.append(detection_data)

        # Keep only last 1000 detections
        if len(self._detection_history) > 1000:
            self._detection_history.pop(0)

    def get_detection_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive detection statistics.

        Returns:
            Dictionary with detection statistics
        """
        return {
            'total_detections': self._total_detections,
            'successful_detections': self._successful_detections,
            'detection_accuracy': self.detection_accuracy,
            'average_processing_time_ms': self.average_processing_time,
            'color_ranges_defined': len(self._color_ranges),
            'custom_detectors': list(self._custom_detectors.keys()),
            'detection_history_size': len(self._detection_history),
            'parameters': {
                'min_contour_area': self.parameters.min_contour_area,
                'max_contour_area': self.parameters.max_contour_area,
                'min_confidence': self.parameters.min_confidence,
                'color_detection_enabled': self.parameters.color_detection_enabled
            }
        }

    def reset_statistics(self) -> None:
        """Reset detection statistics."""
        self._total_detections = 0
        self._successful_detections = 0
        self._processing_times.clear()
        self._detection_history.clear()
        logger.info("Detection statistics reset")

    def visualize_detections(self, image: np.ndarray,
                           detected_objects: List[DetectedObject],
                           show_confidence: bool = True,
                           show_labels: bool = True) -> np.ndarray:
        """
        Visualize detected objects on image.

        Args:
            image: Original image
            detected_objects: List of detected objects
            show_confidence: Show confidence scores
            show_labels: Show shape and color labels

        Returns:
            Image with visualizations
        """
        result_image = image.copy()

        for obj in detected_objects:
            # Draw contour
            if obj.contour is not None:
                cv2.drawContours(result_image, [obj.contour], -1, (0, 255, 0), 2)

            # Draw bounding box
            x, y, w, h = obj.bounding_box
            cv2.rectangle(result_image, (x, y), (x + w, y + h), (255, 0, 0), 2)

            # Draw center point
            cv2.circle(result_image, obj.center, 5, (0, 0, 255), -1)

            # Add labels
            if show_labels or show_confidence:
                label_parts = []

                if show_labels:
                    if obj.shape != ShapeType.UNKNOWN:
                        label_parts.append(obj.shape.value)
                    if obj.color != ColorType.UNKNOWN:
                        label_parts.append(obj.color.value)

                if show_confidence:
                    label_parts.append(f"{obj.confidence:.2f}")

                if label_parts:
                    label = " ".join(label_parts)
                    cv2.putText(result_image, label, (x, y - 10),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return result_image
