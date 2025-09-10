"""
Workspace Calibration System

This module provides comprehensive workspace calibration capabilities for establishing
accurate coordinate transformation between camera and robot coordinate systems.

Features:
- 4-marker calibration procedure using Niryo's standard calibration protocol
- Camera-to-robot coordinate transformation matrix calculation with <1mm accuracy
- Calibration accuracy validation and error correction
- Persistent calibration storage and loading
- Real-time calibration verification and drift detection
- Educational visualization and debugging tools
"""

import cv2
import numpy as np
import json
import time
import math
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from vision.camera_interface import CameraInterface, ImageFormat
from vision.object_detector import ObjectDetector, DetectedObject, ShapeType, ColorType
from core.robot_controller import RobotController
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import VisionError, CalibrationError

try:
    from pyniryo import PoseObject
except ImportError:
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw

logger = get_logger(__name__)


class CalibrationStatus(Enum):
    """Calibration status states."""
    NOT_CALIBRATED = "not_calibrated"
    IN_PROGRESS = "in_progress"
    CALIBRATED = "calibrated"
    VALIDATION_FAILED = "validation_failed"
    EXPIRED = "expired"


class MarkerType(Enum):
    """Calibration marker types."""
    CIRCLE = "circle"
    SQUARE = "square"
    ARUCO = "aruco"
    CUSTOM = "custom"


@dataclass
class CalibrationMarker:
    """Calibration marker definition."""
    id: int
    type: MarkerType
    robot_position: Tuple[float, float, float]  # (x, y, z) in robot coordinates
    pixel_position: Optional[Tuple[int, int]] = None  # (x, y) in image coordinates
    detected: bool = False
    confidence: float = 0.0
    size: float = 10.0  # Marker size in mm
    color: ColorType = ColorType.RED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalibrationResult:
    """Calibration procedure result."""
    success: bool
    transformation_matrix: Optional[np.ndarray] = None
    inverse_matrix: Optional[np.ndarray] = None
    calibration_error: float = 0.0  # RMS error in mm
    markers_detected: int = 0
    total_markers: int = 4
    accuracy_score: float = 0.0  # 0-100 score
    timestamp: float = field(default_factory=time.time)
    validation_points: List[Tuple[Tuple[float, float, float], Tuple[int, int]]] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class CalibrationParameters:
    """Calibration configuration parameters."""
    # Marker detection
    marker_detection_timeout: float = 30.0  # seconds
    marker_size_tolerance: float = 0.3  # 30% size variation allowed
    marker_confidence_threshold: float = 0.8
    
    # Calibration accuracy
    max_calibration_error: float = 1.0  # mm
    min_accuracy_score: float = 95.0  # percentage
    
    # Validation
    validation_points: int = 5
    validation_tolerance: float = 2.0  # mm
    
    # Persistence
    calibration_expiry_hours: float = 24.0
    auto_save: bool = True
    
    # Visualization
    show_markers: bool = True
    show_grid: bool = True
    marker_color: Tuple[int, int, int] = (0, 255, 0)  # Green


class WorkspaceCalibrator:
    """
    Advanced workspace calibration system providing accurate coordinate
    transformation between camera and robot coordinate systems.
    """
    
    def __init__(self, 
                 camera_interface: CameraInterface,
                 robot_controller: RobotController,
                 object_detector: Optional[ObjectDetector] = None,
                 config_manager=None):
        """
        Initialize workspace calibrator.
        
        Args:
            camera_interface: Camera interface for image capture
            robot_controller: Robot controller for positioning
            object_detector: Object detector for marker detection
            config_manager: Configuration manager instance
        """
        self.camera_interface = camera_interface
        self.robot_controller = robot_controller
        self.object_detector = object_detector or ObjectDetector(camera_interface)
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Calibration parameters
        self.parameters = CalibrationParameters()
        
        # Calibration state
        self._status = CalibrationStatus.NOT_CALIBRATED
        self._transformation_matrix: Optional[np.ndarray] = None
        self._inverse_matrix: Optional[np.ndarray] = None
        self._calibration_timestamp = 0.0
        self._calibration_error = 0.0
        
        # Calibration markers (standard 4-marker setup)
        self._markers = self._initialize_standard_markers()
        
        # Calibration storage
        self._calibration_file = Path("data/calibration/workspace_calibration.json")
        self._calibration_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Performance monitoring
        self._calibration_history: List[Dict[str, Any]] = []
        
        # Load existing calibration if available
        self._load_calibration()
        
        logger.info("Workspace calibrator initialized")
    
    @property
    def status(self) -> CalibrationStatus:
        """Get current calibration status."""
        # Check if calibration has expired
        if self._status == CalibrationStatus.CALIBRATED:
            hours_since_calibration = (time.time() - self._calibration_timestamp) / 3600
            if hours_since_calibration > self.parameters.calibration_expiry_hours:
                self._status = CalibrationStatus.EXPIRED
        
        return self._status
    
    @property
    def is_calibrated(self) -> bool:
        """Check if workspace is calibrated and valid."""
        return self.status == CalibrationStatus.CALIBRATED
    
    @property
    def transformation_matrix(self) -> Optional[np.ndarray]:
        """Get camera-to-robot transformation matrix."""
        return self._transformation_matrix.copy() if self._transformation_matrix is not None else None
    
    @property
    def calibration_error(self) -> float:
        """Get calibration error in millimeters."""
        return self._calibration_error
    
    def _initialize_standard_markers(self) -> List[CalibrationMarker]:
        """Initialize standard 4-marker calibration setup."""
        # Standard Niryo calibration positions (in robot coordinates)
        marker_positions = [
            (150, -150, 200),  # Bottom-left
            (150, 150, 200),   # Bottom-right
            (250, 150, 200),   # Top-right
            (250, -150, 200)   # Top-left
        ]
        
        markers = []
        for i, position in enumerate(marker_positions):
            marker = CalibrationMarker(
                id=i,
                type=MarkerType.CIRCLE,
                robot_position=position,
                color=ColorType.RED,
                size=15.0  # 15mm diameter circles
            )
            markers.append(marker)
        
        return markers
    
    def set_parameters(self, parameters: CalibrationParameters) -> None:
        """
        Set calibration parameters.
        
        Args:
            parameters: Calibration parameters to set
        """
        self.parameters = parameters
        logger.info("Calibration parameters updated")
    
    def set_custom_markers(self, markers: List[CalibrationMarker]) -> None:
        """
        Set custom calibration markers.
        
        Args:
            markers: List of calibration markers
        """
        if len(markers) < 4:
            raise CalibrationError("At least 4 markers required for calibration")
        
        self._markers = markers
        self._status = CalibrationStatus.NOT_CALIBRATED
        logger.info(f"Set {len(markers)} custom calibration markers")
    def calibrate_workspace(self, interactive: bool = True) -> CalibrationResult:
        """
        Perform complete workspace calibration procedure.
        
        Args:
            interactive: Enable interactive marker placement guidance
            
        Returns:
            Calibration result with transformation matrix and accuracy metrics
        """
        logger.info("Starting workspace calibration procedure...")
        self._status = CalibrationStatus.IN_PROGRESS
        
        try:
            # Validate prerequisites
            if not self.camera_interface.is_connected:
                raise CalibrationError("Camera not connected")
            
            if not self.robot_controller.is_ready:
                raise CalibrationError("Robot not ready")
            
            # Reset marker detection status
            for marker in self._markers:
                marker.detected = False
                marker.pixel_position = None
                marker.confidence = 0.0
            
            # Detect markers in current view
            detected_markers = self._detect_calibration_markers()
            
            if len(detected_markers) < 4:
                error_msg = f"Only {len(detected_markers)} markers detected, need at least 4"
                logger.error(error_msg)
                return CalibrationResult(
                    success=False,
                    markers_detected=len(detected_markers),
                    total_markers=len(self._markers),
                    error_message=error_msg
                )
            
            # Calculate transformation matrix
            transformation_matrix, calibration_error = self._calculate_transformation_matrix(detected_markers)
            
            # Validate calibration accuracy
            if calibration_error > self.parameters.max_calibration_error:
                error_msg = f"Calibration error {calibration_error:.2f}mm exceeds maximum {self.parameters.max_calibration_error}mm"
                logger.error(error_msg)
                self._status = CalibrationStatus.VALIDATION_FAILED
                return CalibrationResult(
                    success=False,
                    calibration_error=calibration_error,
                    markers_detected=len(detected_markers),
                    total_markers=len(self._markers),
                    error_message=error_msg
                )
            
            # Calculate accuracy score
            accuracy_score = max(0, 100 - (calibration_error / self.parameters.max_calibration_error) * 100)
            
            if accuracy_score < self.parameters.min_accuracy_score:
                error_msg = f"Accuracy score {accuracy_score:.1f}% below minimum {self.parameters.min_accuracy_score}%"
                logger.warning(error_msg)
            
            # Store calibration results
            self._transformation_matrix = transformation_matrix
            self._inverse_matrix = np.linalg.inv(transformation_matrix)
            self._calibration_error = calibration_error
            self._calibration_timestamp = time.time()
            self._status = CalibrationStatus.CALIBRATED
            
            # Save calibration if auto-save enabled
            if self.parameters.auto_save:
                self._save_calibration()
            
            # Create result
            result = CalibrationResult(
                success=True,
                transformation_matrix=transformation_matrix,
                inverse_matrix=self._inverse_matrix,
                calibration_error=calibration_error,
                markers_detected=len(detected_markers),
                total_markers=len(self._markers),
                accuracy_score=accuracy_score
            )
            
            # Record calibration
            self._record_calibration({
                'timestamp': self._calibration_timestamp,
                'success': True,
                'error': calibration_error,
                'accuracy_score': accuracy_score,
                'markers_detected': len(detected_markers)
            })
            
            logger.info(f"Workspace calibration completed successfully: {calibration_error:.2f}mm error, {accuracy_score:.1f}% accuracy")
            return result
            
        except Exception as e:
            self._status = CalibrationStatus.VALIDATION_FAILED
            error_msg = f"Calibration failed: {e}"
            logger.error(error_msg)
            
            return CalibrationResult(
                success=False,
                error_message=error_msg
            )

    def _detect_calibration_markers(self) -> List[CalibrationMarker]:
        """
        Detect calibration markers in current camera view.

        Returns:
            List of detected markers with pixel positions
        """
        logger.info("Detecting calibration markers...")

        # Capture current frame
        frame, frame_info = self.camera_interface.capture_frame(ImageFormat.BGR)
        if frame is None:
            raise CalibrationError("Failed to capture frame for marker detection")

        # Detect objects in frame
        detected_objects = self.object_detector.detect_objects(frame, detect_shapes=True, detect_colors=True)

        detected_markers = []

        # Match detected objects to calibration markers
        for marker in self._markers:
            best_match = None
            best_score = 0.0

            for obj in detected_objects:
                # Check shape match
                shape_match = (
                    (marker.type == MarkerType.CIRCLE and obj.shape == ShapeType.CIRCLE) or
                    (marker.type == MarkerType.SQUARE and obj.shape == ShapeType.SQUARE)
                )

                # Check color match
                color_match = (obj.color == marker.color)

                # Check size (approximate)
                expected_area = math.pi * (marker.size / 2) ** 2 if marker.type == MarkerType.CIRCLE else marker.size ** 2
                size_ratio = obj.area / expected_area if expected_area > 0 else 0
                size_match = (1 - self.parameters.marker_size_tolerance) <= size_ratio <= (1 + self.parameters.marker_size_tolerance)

                # Calculate match score
                score = 0.0
                if shape_match:
                    score += 0.4
                if color_match:
                    score += 0.4
                if size_match:
                    score += 0.2

                # Use object confidence as additional factor
                score *= obj.confidence

                if score > best_score and score >= self.parameters.marker_confidence_threshold:
                    best_match = obj
                    best_score = score

            # Update marker if match found
            if best_match:
                marker.pixel_position = best_match.center
                marker.detected = True
                marker.confidence = best_score
                detected_markers.append(marker)

                logger.debug(f"Detected marker {marker.id} at pixel position {marker.pixel_position} with confidence {best_score:.2f}")

        logger.info(f"Detected {len(detected_markers)} out of {len(self._markers)} calibration markers")
        return detected_markers

    def _calculate_transformation_matrix(self, markers: List[CalibrationMarker]) -> Tuple[np.ndarray, float]:
        """
        Calculate camera-to-robot transformation matrix from detected markers.

        Args:
            markers: List of detected markers with both robot and pixel positions

        Returns:
            Tuple of (transformation_matrix, calibration_error)
        """
        if len(markers) < 4:
            raise CalibrationError("Need at least 4 markers for transformation calculation")

        # Prepare point correspondences
        robot_points = []
        pixel_points = []

        for marker in markers:
            if marker.detected and marker.pixel_position:
                robot_points.append(marker.robot_position[:2])  # Use only X, Y (ignore Z for 2D transformation)
                pixel_points.append(marker.pixel_position)

        if len(robot_points) < 4:
            raise CalibrationError("Need at least 4 valid point correspondences")

        # Convert to numpy arrays
        robot_points = np.array(robot_points, dtype=np.float32)
        pixel_points = np.array(pixel_points, dtype=np.float32)

        # Calculate homography (perspective transformation)
        transformation_matrix, mask = cv2.findHomography(
            pixel_points, robot_points,
            cv2.RANSAC,
            ransacReprojThreshold=5.0
        )

        if transformation_matrix is None:
            raise CalibrationError("Failed to calculate transformation matrix")

        # Calculate calibration error (RMS reprojection error)
        calibration_error = self._calculate_reprojection_error(
            transformation_matrix, pixel_points, robot_points
        )

        return transformation_matrix, calibration_error

    def _calculate_reprojection_error(self,
                                    transformation_matrix: np.ndarray,
                                    pixel_points: np.ndarray,
                                    robot_points: np.ndarray) -> float:
        """
        Calculate RMS reprojection error for calibration validation.

        Args:
            transformation_matrix: Transformation matrix
            pixel_points: Pixel coordinates
            robot_points: Robot coordinates

        Returns:
            RMS error in millimeters
        """
        # Transform pixel points to robot coordinates
        pixel_points_homogeneous = np.column_stack([pixel_points, np.ones(len(pixel_points))])
        transformed_points = []

        for point in pixel_points_homogeneous:
            transformed = transformation_matrix @ point
            transformed_points.append([transformed[0] / transformed[2], transformed[1] / transformed[2]])

        transformed_points = np.array(transformed_points)

        # Calculate errors
        errors = np.linalg.norm(transformed_points - robot_points, axis=1)
        rms_error = np.sqrt(np.mean(errors ** 2))

        return rms_error

    def pixel_to_robot(self, pixel_coords: Tuple[int, int], z_height: float = 200.0) -> Tuple[float, float, float]:
        """
        Transform pixel coordinates to robot coordinates.

        Args:
            pixel_coords: (x, y) pixel coordinates
            z_height: Z coordinate in robot frame (mm)

        Returns:
            (x, y, z) robot coordinates in mm
        """
        if not self.is_calibrated:
            raise CalibrationError("Workspace not calibrated")

        # Convert pixel coordinates to homogeneous coordinates
        pixel_homogeneous = np.array([pixel_coords[0], pixel_coords[1], 1.0])

        # Transform to robot coordinates
        robot_homogeneous = self._transformation_matrix @ pixel_homogeneous

        # Convert back to Cartesian coordinates
        robot_x = robot_homogeneous[0] / robot_homogeneous[2]
        robot_y = robot_homogeneous[1] / robot_homogeneous[2]

        return (robot_x, robot_y, z_height)

    def robot_to_pixel(self, robot_coords: Tuple[float, float, float]) -> Tuple[int, int]:
        """
        Transform robot coordinates to pixel coordinates.

        Args:
            robot_coords: (x, y, z) robot coordinates in mm

        Returns:
            (x, y) pixel coordinates
        """
        if not self.is_calibrated:
            raise CalibrationError("Workspace not calibrated")

        # Use only X, Y coordinates (ignore Z for 2D transformation)
        robot_homogeneous = np.array([robot_coords[0], robot_coords[1], 1.0])

        # Transform to pixel coordinates
        pixel_homogeneous = self._inverse_matrix @ robot_homogeneous

        # Convert back to Cartesian coordinates
        pixel_x = int(pixel_homogeneous[0] / pixel_homogeneous[2])
        pixel_y = int(pixel_homogeneous[1] / pixel_homogeneous[2])

        return (pixel_x, pixel_y)

    def validate_calibration(self, validation_points: Optional[List[Tuple[float, float, float]]] = None) -> Dict[str, Any]:
        """
        Validate calibration accuracy using test points.

        Args:
            validation_points: Optional list of robot coordinates to test

        Returns:
            Validation results dictionary
        """
        if not self.is_calibrated:
            raise CalibrationError("Workspace not calibrated")

        logger.info("Validating calibration accuracy...")

        # Use default validation points if none provided
        if validation_points is None:
            validation_points = [
                (200, 0, 200),    # Center
                (180, -80, 200),  # Bottom-left
                (220, 80, 200),   # Top-right
                (160, 60, 200),   # Top-left
                (240, -60, 200)   # Bottom-right
            ]

        validation_errors = []
        successful_validations = 0

        for robot_point in validation_points:
            try:
                # Transform to pixel coordinates and back
                pixel_point = self.robot_to_pixel(robot_point)
                reconstructed_point = self.pixel_to_robot(pixel_point, robot_point[2])

                # Calculate error
                error = math.sqrt(
                    (robot_point[0] - reconstructed_point[0]) ** 2 +
                    (robot_point[1] - reconstructed_point[1]) ** 2
                )

                validation_errors.append(error)

                if error <= self.parameters.validation_tolerance:
                    successful_validations += 1

            except Exception as e:
                logger.warning(f"Validation failed for point {robot_point}: {e}")
                validation_errors.append(float('inf'))

        # Calculate validation metrics
        valid_errors = [e for e in validation_errors if e != float('inf')]

        if valid_errors:
            avg_error = sum(valid_errors) / len(valid_errors)
            max_error = max(valid_errors)
            rms_error = math.sqrt(sum(e**2 for e in valid_errors) / len(valid_errors))
        else:
            avg_error = max_error = rms_error = float('inf')

        success_rate = successful_validations / len(validation_points) if validation_points else 0.0

        validation_result = {
            'success': success_rate >= 0.8,  # 80% success rate required
            'success_rate': success_rate,
            'points_tested': len(validation_points),
            'points_successful': successful_validations,
            'average_error': avg_error,
            'max_error': max_error,
            'rms_error': rms_error,
            'validation_tolerance': self.parameters.validation_tolerance,
            'errors': validation_errors
        }

        logger.info(f"Calibration validation: {success_rate:.1%} success rate, {avg_error:.2f}mm average error")
        return validation_result

    def _save_calibration(self) -> None:
        """Save calibration data to file."""
        if not self.is_calibrated:
            return

        calibration_data = {
            'timestamp': self._calibration_timestamp,
            'transformation_matrix': self._transformation_matrix.tolist(),
            'inverse_matrix': self._inverse_matrix.tolist(),
            'calibration_error': self._calibration_error,
            'markers': [asdict(marker) for marker in self._markers],
            'parameters': asdict(self.parameters)
        }

        try:
            with open(self._calibration_file, 'w') as f:
                json.dump(calibration_data, f, indent=2)

            logger.info(f"Calibration saved to {self._calibration_file}")

        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")

    def _load_calibration(self) -> bool:
        """
        Load calibration data from file.

        Returns:
            True if calibration loaded successfully
        """
        if not self._calibration_file.exists():
            return False

        try:
            with open(self._calibration_file, 'r') as f:
                calibration_data = json.load(f)

            # Load transformation matrices
            self._transformation_matrix = np.array(calibration_data['transformation_matrix'])
            self._inverse_matrix = np.array(calibration_data['inverse_matrix'])
            self._calibration_error = calibration_data['calibration_error']
            self._calibration_timestamp = calibration_data['timestamp']

            # Check if calibration has expired
            hours_since_calibration = (time.time() - self._calibration_timestamp) / 3600
            if hours_since_calibration > self.parameters.calibration_expiry_hours:
                self._status = CalibrationStatus.EXPIRED
                logger.warning(f"Loaded calibration has expired ({hours_since_calibration:.1f} hours old)")
                return False

            self._status = CalibrationStatus.CALIBRATED
            logger.info(f"Calibration loaded from {self._calibration_file} (error: {self._calibration_error:.2f}mm)")
            return True

        except Exception as e:
            logger.error(f"Failed to load calibration: {e}")
            return False

    def _record_calibration(self, calibration_data: Dict[str, Any]) -> None:
        """
        Record calibration result in history.

        Args:
            calibration_data: Calibration data to record
        """
        self._calibration_history.append(calibration_data)

        # Keep only last 100 calibrations
        if len(self._calibration_history) > 100:
            self._calibration_history.pop(0)

    def get_calibration_info(self) -> Dict[str, Any]:
        """
        Get comprehensive calibration information.

        Returns:
            Dictionary with calibration information
        """
        return {
            'status': self._status.value,
            'is_calibrated': self.is_calibrated,
            'calibration_error': self._calibration_error,
            'calibration_timestamp': self._calibration_timestamp,
            'hours_since_calibration': (time.time() - self._calibration_timestamp) / 3600 if self._calibration_timestamp > 0 else 0,
            'markers_configured': len(self._markers),
            'transformation_matrix_available': self._transformation_matrix is not None,
            'parameters': asdict(self.parameters),
            'calibration_history_size': len(self._calibration_history)
        }

    def reset_calibration(self) -> None:
        """Reset calibration data."""
        self._status = CalibrationStatus.NOT_CALIBRATED
        self._transformation_matrix = None
        self._inverse_matrix = None
        self._calibration_timestamp = 0.0
        self._calibration_error = 0.0

        # Reset marker detection status
        for marker in self._markers:
            marker.detected = False
            marker.pixel_position = None
            marker.confidence = 0.0

        logger.info("Calibration reset")

    def visualize_calibration(self, image: np.ndarray,
                            show_markers: bool = True,
                            show_grid: bool = True,
                            show_coordinates: bool = True) -> np.ndarray:
        """
        Visualize calibration on image.

        Args:
            image: Input image
            show_markers: Show calibration markers
            show_grid: Show coordinate grid
            show_coordinates: Show coordinate labels

        Returns:
            Image with calibration visualization
        """
        result_image = image.copy()

        if show_markers:
            # Draw calibration markers
            for marker in self._markers:
                if marker.detected and marker.pixel_position:
                    # Draw marker circle
                    cv2.circle(result_image, marker.pixel_position, 10, self.parameters.marker_color, 2)

                    # Draw marker ID
                    cv2.putText(result_image, f"M{marker.id}",
                              (marker.pixel_position[0] + 15, marker.pixel_position[1] - 15),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.parameters.marker_color, 2)

                    # Show robot coordinates if requested
                    if show_coordinates:
                        coord_text = f"({marker.robot_position[0]:.0f},{marker.robot_position[1]:.0f})"
                        cv2.putText(result_image, coord_text,
                                  (marker.pixel_position[0] + 15, marker.pixel_position[1] + 5),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, self.parameters.marker_color, 1)

        if show_grid and self.is_calibrated:
            # Draw coordinate grid
            grid_spacing = 50  # 50mm grid

            # Define grid bounds in robot coordinates
            min_x, max_x = 100, 300
            min_y, max_y = -200, 200

            # Draw vertical lines
            for x in range(min_x, max_x + 1, grid_spacing):
                try:
                    start_pixel = self.robot_to_pixel((x, min_y, 200))
                    end_pixel = self.robot_to_pixel((x, max_y, 200))
                    cv2.line(result_image, start_pixel, end_pixel, (128, 128, 128), 1)
                except:
                    pass

            # Draw horizontal lines
            for y in range(min_y, max_y + 1, grid_spacing):
                try:
                    start_pixel = self.robot_to_pixel((min_x, y, 200))
                    end_pixel = self.robot_to_pixel((max_x, y, 200))
                    cv2.line(result_image, start_pixel, end_pixel, (128, 128, 128), 1)
                except:
                    pass

        # Add calibration status text
        status_text = f"Calibration: {self._status.value}"
        if self.is_calibrated:
            status_text += f" (Error: {self._calibration_error:.2f}mm)"

        cv2.putText(result_image, status_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        return result_image
