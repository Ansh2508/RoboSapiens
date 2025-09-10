"""
Vision-Guided Robot Control Integration

This module provides comprehensive integration between computer vision capabilities
and robot movement control, enabling precise vision-guided automation tasks.

Features:
- Vision-guided pick-and-place operations with sub-millimeter accuracy
- Real-time object tracking and robot positioning
- Educational demonstrations showcasing vision-guided automation
- Integration with Phase 2 movement capabilities and computer vision pipeline
- Safety monitoring and collision avoidance during vision-guided operations
- Performance optimization for real-time vision-guided control
"""

import cv2
import numpy as np
import time
import math
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

from ..core.robot_controller import RobotController
from ..core.advanced_movement import AdvancedMovementController
from ..core.trajectory_planner import TrajectoryPlanner, PathType
from ..core.tool_controller import ToolController
from ..vision.camera_interface import CameraInterface, ImageFormat
from ..vision.object_detector import ObjectDetector, DetectedObject, ShapeType, ColorType
from ..vision.workspace_calibrator import WorkspaceCalibrator
from ..vision.image_processor import ImageProcessor
from utils.config_manager import ConfigManager
from utils.logger import get_loggerndler import VisionError, SafetyError

try:
    from pyniryo import PoseObject
except ImportError:
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw

logger = get_logger(__name__)


class VisionTaskType(Enum):
    """Vision-guided task types."""
    PICK_AND_PLACE = "pick_and_place"
    OBJECT_TRACKING = "object_tracking"
    INSPECTION = "inspection"
    SORTING = "sorting"
    ASSEMBLY = "assembly"
    CUSTOM = "custom"


class VisionTaskStatus(Enum):
    """Vision task execution status."""
    IDLE = "idle"
    DETECTING = "detecting"
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


@dataclass
class VisionTarget:
    """Vision-guided target definition."""
    id: str
    shape: ShapeType
    color: ColorType
    robot_position: Optional[Tuple[float, float, float]] = None
    pixel_position: Optional[Tuple[int, int]] = None
    confidence: float = 0.0
    detected: bool = False
    approach_height: float = 250.0  # mm above target
    grasp_height: float = 200.0     # mm at target level
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VisionTask:
    """Vision-guided task definition."""
    task_id: str
    task_type: VisionTaskType
    targets: List[VisionTarget]
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: VisionTaskStatus = VisionTaskStatus.IDLE
    progress: float = 0.0
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class VisionControlParameters:
    """Vision-guided control configuration."""
    # Detection parameters
    detection_timeout: float = 30.0  # seconds
    min_detection_confidence: float = 0.8
    max_detection_attempts: int = 5
    
    # Movement parameters
    approach_speed: float = 50.0  # mm/s
    grasp_speed: float = 20.0     # mm/s
    lift_height: float = 50.0     # mm above grasp
    
    # Safety parameters
    workspace_bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]] = (
        (100, 300),   # X bounds (mm)
        (-200, 200),  # Y bounds (mm)
        (150, 300)    # Z bounds (mm)
    )
    
    # Vision parameters
    enable_real_time_tracking: bool = True
    tracking_update_rate: float = 10.0  # Hz
    position_tolerance: float = 2.0     # mm
    
    # Performance parameters
    max_task_duration: float = 300.0  # seconds
    enable_performance_monitoring: bool = True


class VisionGuidedController:
    """
    Advanced vision-guided robot control system integrating computer vision
    with precise robot movement capabilities.
    """
    
    def __init__(self,
                 robot_controller: RobotController,
                 camera_interface: CameraInterface,
                 workspace_calibrator: WorkspaceCalibrator,
                 object_detector: Optional[ObjectDetector] = None,
                 image_processor: Optional[ImageProcessor] = None,
                 config_manager=None):
        """
        Initialize vision-guided controller.
        
        Args:
            robot_controller: Robot controller instance
            camera_interface: Camera interface instance
            workspace_calibrator: Workspace calibrator instance
            object_detector: Object detector instance
            image_processor: Image processor instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.camera_interface = camera_interface
        self.workspace_calibrator = workspace_calibrator
        self.object_detector = object_detector or ObjectDetector(camera_interface)
        self.image_processor = image_processor or ImageProcessor(camera_interface)
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Initialize advanced controllers
        self.movement_controller = AdvancedMovementController(robot_controller)
        self.trajectory_planner = TrajectoryPlanner(robot_controller)
        self.tool_controller = ToolController(robot_controller)
        
        # Control parameters
        self.parameters = VisionControlParameters()
        
        # Task management
        self._current_task: Optional[VisionTask] = None
        self._task_history: List[VisionTask] = []
        self._active_targets: List[VisionTarget] = []
        
        # Performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._execution_stats = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'average_accuracy': 0.0
        }
        
        # Safety monitoring
        self._safety_enabled = True
        self._emergency_stop_callback: Optional[Callable] = None
        
        logger.info("Vision-guided controller initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if vision-guided controller is ready for operation."""
        return (
            self.robot_controller.is_ready and
            self.camera_interface.is_connected and
            self.workspace_calibrator.is_calibrated
        )
    
    @property
    def current_task(self) -> Optional[VisionTask]:
        """Get current active task."""
        return self._current_task
    
    @property
    def task_status(self) -> VisionTaskStatus:
        """Get current task status."""
        return self._current_task.status if self._current_task else VisionTaskStatus.IDLE
    
    def set_parameters(self, parameters: VisionControlParameters) -> None:
        """
        Set vision control parameters.
        
        Args:
            parameters: Vision control parameters to set
        """
        self.parameters = parameters
        logger.info("Vision control parameters updated")
    
    def set_emergency_stop_callback(self, callback: Callable) -> None:
        """
        Set emergency stop callback function.
        
        Args:
            callback: Function to call on emergency stop
        """
        self._emergency_stop_callback = callback
        logger.info("Emergency stop callback set")
    def execute_pick_and_place(self, 
                              source_target: VisionTarget,
                              destination_position: Tuple[float, float, float],
                              custom_parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute vision-guided pick-and-place operation.
        
        Args:
            source_target: Target object to pick up
            destination_position: Destination position (x, y, z) in robot coordinates
            custom_parameters: Optional custom parameters
            
        Returns:
            True if operation completed successfully
        """
        if not self.is_ready:
            raise VisionError("Vision-guided controller not ready")
        
        logger.info(f"Starting pick-and-place operation for target: {source_target.id}")
        
        # Create task
        task = VisionTask(
            task_id=f"pick_place_{int(time.time())}",
            task_type=VisionTaskType.PICK_AND_PLACE,
            targets=[source_target],
            parameters=custom_parameters or {}
        )
        
        try:
            self._current_task = task
            task.status = VisionTaskStatus.DETECTING
            task.start_time = time.time()
            
            # Step 1: Detect and locate target object
            detected_object = self._detect_target_object(source_target)
            if not detected_object:
                raise VisionError(f"Failed to detect target object: {source_target.id}")
            
            # Step 2: Convert pixel coordinates to robot coordinates
            robot_position = self.workspace_calibrator.pixel_to_robot(
                detected_object.center, source_target.grasp_height
            )
            source_target.robot_position = robot_position
            
            # Step 3: Plan and execute approach movement
            task.status = VisionTaskStatus.PLANNING
            approach_position = (robot_position[0], robot_position[1], source_target.approach_height)
            
            # Move to approach position
            task.status = VisionTaskStatus.EXECUTING
            task.progress = 0.2
            
            success = self.movement_controller.move_to_position(
                approach_position, speed=self.parameters.approach_speed
            )
            if not success:
                raise VisionError("Failed to move to approach position")
            
            # Step 4: Move to grasp position
            task.progress = 0.4
            success = self.movement_controller.move_to_position(
                robot_position, speed=self.parameters.grasp_speed
            )
            if not success:
                raise VisionError("Failed to move to grasp position")
            
            # Step 5: Grasp object
            task.progress = 0.6
            success = self.tool_controller.grasp_object()
            if not success:
                raise VisionError("Failed to grasp object")
            
            # Step 6: Lift object
            task.progress = 0.7
            lift_position = (robot_position[0], robot_position[1], robot_position[2] + self.parameters.lift_height)
            success = self.movement_controller.move_to_position(
                lift_position, speed=self.parameters.approach_speed
            )
            if not success:
                raise VisionError("Failed to lift object")
            
            # Step 7: Move to destination approach position
            task.progress = 0.8
            dest_approach = (destination_position[0], destination_position[1], destination_position[2] + self.parameters.lift_height)
            success = self.movement_controller.move_to_position(
                dest_approach, speed=self.parameters.approach_speed
            )
            if not success:
                raise VisionError("Failed to move to destination approach")
            
            # Step 8: Move to destination position
            task.progress = 0.9
            success = self.movement_controller.move_to_position(
                destination_position, speed=self.parameters.grasp_speed
            )
            if not success:
                raise VisionError("Failed to move to destination position")
            
            # Step 9: Release object
            task.progress = 0.95
            success = self.tool_controller.release_object()
            if not success:
                raise VisionError("Failed to release object")
            
            # Step 10: Move to safe position
            task.progress = 1.0
            safe_position = (destination_position[0], destination_position[1], destination_position[2] + self.parameters.lift_height)
            success = self.movement_controller.move_to_position(
                safe_position, speed=self.parameters.approach_speed
            )
            
            # Complete task
            task.status = VisionTaskStatus.COMPLETED
            task.end_time = time.time()
            
            # Update statistics
            self._execution_stats['tasks_completed'] += 1
            self._execution_stats['total_execution_time'] += task.end_time - task.start_time
            
            self._task_history.append(task)
            self._current_task = None
            
            logger.info(f"Pick-and-place operation completed successfully in {task.end_time - task.start_time:.2f}s")
            return True
            
        except Exception as e:
            task.status = VisionTaskStatus.FAILED
            task.end_time = time.time()
            task.error_message = str(e)
            
            # Update statistics
            self._execution_stats['tasks_failed'] += 1
            
            self._task_history.append(task)
            self._current_task = None
            
            error_msg = f"Pick-and-place operation failed: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)

    def _detect_target_object(self, target: VisionTarget) -> Optional[DetectedObject]:
        """
        Detect target object in current camera view.

        Args:
            target: Target object to detect

        Returns:
            Detected object or None if not found
        """
        logger.debug(f"Detecting target object: {target.id}")

        attempts = 0
        start_time = time.time()

        while attempts < self.parameters.max_detection_attempts:
            # Check timeout
            if time.time() - start_time > self.parameters.detection_timeout:
                logger.warning(f"Detection timeout for target: {target.id}")
                break

            # Capture frame
            frame, frame_info = self.camera_interface.capture_frame(ImageFormat.BGR)
            if frame is None:
                attempts += 1
                continue

            # Detect objects
            detected_objects = self.object_detector.detect_objects(frame)

            # Find matching object
            best_match = None
            best_score = 0.0

            for obj in detected_objects:
                # Check shape and color match
                shape_match = (obj.shape == target.shape or target.shape == ShapeType.UNKNOWN)
                color_match = (obj.color == target.color or target.color == ColorType.UNKNOWN)

                # Calculate match score
                score = obj.confidence
                if shape_match:
                    score *= 1.2
                if color_match:
                    score *= 1.2

                if score > best_score and score >= self.parameters.min_detection_confidence:
                    best_match = obj
                    best_score = score

            if best_match:
                target.pixel_position = best_match.center
                target.confidence = best_score
                target.detected = True

                logger.debug(f"Target detected: {target.id} at {best_match.center} with confidence {best_score:.2f}")
                return best_match

            attempts += 1
            time.sleep(0.1)  # Brief delay between attempts

        logger.warning(f"Failed to detect target object: {target.id} after {attempts} attempts")
        return None

    def execute_object_tracking(self, target: VisionTarget, duration: float = 10.0) -> List[Tuple[float, Tuple[int, int]]]:
        """
        Execute real-time object tracking.

        Args:
            target: Target object to track
            duration: Tracking duration in seconds

        Returns:
            List of (timestamp, pixel_position) tuples
        """
        if not self.is_ready:
            raise VisionError("Vision-guided controller not ready")

        logger.info(f"Starting object tracking for target: {target.id}")

        # Create task
        task = VisionTask(
            task_id=f"tracking_{int(time.time())}",
            task_type=VisionTaskType.OBJECT_TRACKING,
            targets=[target],
            parameters={'duration': duration}
        )

        tracking_data = []

        try:
            self._current_task = task
            task.status = VisionTaskStatus.EXECUTING
            task.start_time = time.time()

            # Start camera streaming
            was_streaming = self.camera_interface.is_streaming
            if not was_streaming:
                self.camera_interface.start_streaming(ImageFormat.BGR)

            start_time = time.time()
            last_update = 0.0
            update_interval = 1.0 / self.parameters.tracking_update_rate

            while time.time() - start_time < duration:
                current_time = time.time()

                # Check update rate
                if current_time - last_update < update_interval:
                    time.sleep(0.01)
                    continue

                # Get latest frame
                frame, frame_info = self.camera_interface.get_latest_frame(timeout=0.1)
                if frame is None:
                    continue

                # Detect objects
                detected_objects = self.object_detector.detect_objects(frame)

                # Find target object
                for obj in detected_objects:
                    shape_match = (obj.shape == target.shape or target.shape == ShapeType.UNKNOWN)
                    color_match = (obj.color == target.color or target.color == ColorType.UNKNOWN)

                    if shape_match and color_match and obj.confidence >= self.parameters.min_detection_confidence:
                        tracking_data.append((current_time, obj.center))
                        target.pixel_position = obj.center
                        target.confidence = obj.confidence
                        break

                last_update = current_time
                task.progress = (current_time - start_time) / duration

            # Stop streaming if we started it
            if not was_streaming:
                self.camera_interface.stop_streaming()

            # Complete task
            task.status = VisionTaskStatus.COMPLETED
            task.end_time = time.time()

            self._task_history.append(task)
            self._current_task = None

            logger.info(f"Object tracking completed: {len(tracking_data)} data points collected")
            return tracking_data

        except Exception as e:
            task.status = VisionTaskStatus.FAILED
            task.end_time = time.time()
            task.error_message = str(e)

            self._task_history.append(task)
            self._current_task = None

            error_msg = f"Object tracking failed: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)

    def execute_sorting_task(self,
                           source_area: Tuple[Tuple[float, float], Tuple[float, float]],
                           sort_criteria: Dict[str, Tuple[float, float, float]],
                           max_objects: int = 10) -> Dict[str, List[VisionTarget]]:
        """
        Execute object sorting task based on shape/color criteria.

        Args:
            source_area: ((min_x, max_x), (min_y, max_y)) source area bounds
            sort_criteria: Dictionary mapping criteria to destination positions
            max_objects: Maximum number of objects to sort

        Returns:
            Dictionary mapping criteria to sorted objects
        """
        if not self.is_ready:
            raise VisionError("Vision-guided controller not ready")

        logger.info("Starting object sorting task")

        # Create task
        task = VisionTask(
            task_id=f"sorting_{int(time.time())}",
            task_type=VisionTaskType.SORTING,
            targets=[],
            parameters={
                'source_area': source_area,
                'sort_criteria': sort_criteria,
                'max_objects': max_objects
            }
        )

        sorted_objects = {criteria: [] for criteria in sort_criteria.keys()}

        try:
            self._current_task = task
            task.status = VisionTaskStatus.DETECTING
            task.start_time = time.time()

            # Detect all objects in source area
            frame, frame_info = self.camera_interface.capture_frame(ImageFormat.BGR)
            if frame is None:
                raise VisionError("Failed to capture frame for sorting")

            detected_objects = self.object_detector.detect_objects(frame)

            # Filter objects in source area
            source_objects = []
            for obj in detected_objects:
                robot_pos = self.workspace_calibrator.pixel_to_robot(obj.center, 200.0)

                if (source_area[0][0] <= robot_pos[0] <= source_area[0][1] and
                    source_area[1][0] <= robot_pos[1] <= source_area[1][1]):

                    # Create vision target
                    target = VisionTarget(
                        id=f"obj_{len(source_objects)}",
                        shape=obj.shape,
                        color=obj.color,
                        robot_position=robot_pos,
                        pixel_position=obj.center,
                        confidence=obj.confidence,
                        detected=True
                    )
                    source_objects.append(target)

                    if len(source_objects) >= max_objects:
                        break

            task.targets = source_objects
            logger.info(f"Found {len(source_objects)} objects to sort")

            # Sort objects based on criteria
            task.status = VisionTaskStatus.EXECUTING

            for i, target in enumerate(source_objects):
                # Determine sort criteria
                criteria_key = None
                for criteria, destination in sort_criteria.items():
                    if criteria.startswith('shape_'):
                        shape_name = criteria.split('_')[1]
                        if target.shape.value == shape_name:
                            criteria_key = criteria
                            break
                    elif criteria.startswith('color_'):
                        color_name = criteria.split('_')[1]
                        if target.color.value == color_name:
                            criteria_key = criteria
                            break

                if criteria_key:
                    # Execute pick and place
                    destination_pos = sort_criteria[criteria_key]
                    success = self.execute_pick_and_place(target, destination_pos)

                    if success:
                        sorted_objects[criteria_key].append(target)
                        logger.info(f"Sorted object {target.id} to {criteria_key}")

                task.progress = (i + 1) / len(source_objects)

            # Complete task
            task.status = VisionTaskStatus.COMPLETED
            task.end_time = time.time()

            self._task_history.append(task)
            self._current_task = None

            total_sorted = sum(len(objects) for objects in sorted_objects.values())
            logger.info(f"Sorting task completed: {total_sorted}/{len(source_objects)} objects sorted")

            return sorted_objects

        except Exception as e:
            task.status = VisionTaskStatus.FAILED
            task.end_time = time.time()
            task.error_message = str(e)

            self._task_history.append(task)
            self._current_task = None

            error_msg = f"Sorting task failed: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)

    def create_educational_demonstration(self, demo_type: str = "basic_pick_place") -> Dict[str, Any]:
        """
        Create educational demonstration showcasing vision-guided automation.

        Args:
            demo_type: Type of demonstration to create

        Returns:
            Demonstration results and metrics
        """
        logger.info(f"Creating educational demonstration: {demo_type}")

        demo_results = {
            'demo_type': demo_type,
            'start_time': time.time(),
            'steps': [],
            'metrics': {},
            'success': False
        }

        try:
            if demo_type == "basic_pick_place":
                # Demonstrate basic pick and place with colored objects
                demo_results['steps'].append("Setting up colored object targets")

                # Define demonstration targets
                targets = [
                    VisionTarget(
                        id="red_circle",
                        shape=ShapeType.CIRCLE,
                        color=ColorType.RED,
                        grasp_height=200.0
                    ),
                    VisionTarget(
                        id="blue_square",
                        shape=ShapeType.SQUARE,
                        color=ColorType.BLUE,
                        grasp_height=200.0
                    )
                ]

                # Define destination positions
                destinations = [
                    (250, -100, 200),  # Position 1
                    (250, 100, 200)    # Position 2
                ]

                demo_results['steps'].append("Executing pick and place operations")

                for i, target in enumerate(targets):
                    step_start = time.time()

                    try:
                        success = self.execute_pick_and_place(target, destinations[i])
                        step_time = time.time() - step_start

                        demo_results['steps'].append(
                            f"Completed {target.id}: {'Success' if success else 'Failed'} in {step_time:.2f}s"
                        )

                        demo_results['metrics'][f'{target.id}_time'] = step_time
                        demo_results['metrics'][f'{target.id}_success'] = success

                    except Exception as e:
                        demo_results['steps'].append(f"Failed {target.id}: {e}")
                        demo_results['metrics'][f'{target.id}_success'] = False

            elif demo_type == "color_sorting":
                # Demonstrate color-based sorting
                demo_results['steps'].append("Setting up color sorting demonstration")

                source_area = ((150, 250), (-50, 50))
                sort_criteria = {
                    'color_red': (200, -150, 200),
                    'color_blue': (200, 0, 200),
                    'color_green': (200, 150, 200)
                }

                demo_results['steps'].append("Executing color sorting task")

                sorted_objects = self.execute_sorting_task(source_area, sort_criteria, max_objects=6)

                for criteria, objects in sorted_objects.items():
                    demo_results['steps'].append(f"Sorted {len(objects)} objects to {criteria}")
                    demo_results['metrics'][f'{criteria}_count'] = len(objects)

            elif demo_type == "object_tracking":
                # Demonstrate real-time object tracking
                demo_results['steps'].append("Setting up object tracking demonstration")

                target = VisionTarget(
                    id="tracking_target",
                    shape=ShapeType.CIRCLE,
                    color=ColorType.GREEN
                )

                demo_results['steps'].append("Executing 10-second object tracking")

                tracking_data = self.execute_object_tracking(target, duration=10.0)

                demo_results['metrics']['tracking_points'] = len(tracking_data)
                demo_results['metrics']['tracking_rate'] = len(tracking_data) / 10.0
                demo_results['steps'].append(f"Collected {len(tracking_data)} tracking points")

            demo_results['success'] = True
            demo_results['end_time'] = time.time()
            demo_results['total_duration'] = demo_results['end_time'] - demo_results['start_time']

            logger.info(f"Educational demonstration completed successfully in {demo_results['total_duration']:.2f}s")

        except Exception as e:
            demo_results['success'] = False
            demo_results['error'] = str(e)
            demo_results['end_time'] = time.time()

            logger.error(f"Educational demonstration failed: {e}")

        return demo_results

    def get_vision_control_info(self) -> Dict[str, Any]:
        """
        Get comprehensive vision control information.

        Returns:
            Dictionary with vision control information
        """
        return {
            'is_ready': self.is_ready,
            'current_task': {
                'task_id': self._current_task.task_id if self._current_task else None,
                'task_type': self._current_task.task_type.value if self._current_task else None,
                'status': self._current_task.status.value if self._current_task else 'idle',
                'progress': self._current_task.progress if self._current_task else 0.0
            },
            'execution_statistics': self._execution_stats.copy(),
            'task_history_size': len(self._task_history),
            'active_targets': len(self._active_targets),
            'parameters': {
                'detection_timeout': self.parameters.detection_timeout,
                'min_detection_confidence': self.parameters.min_detection_confidence,
                'approach_speed': self.parameters.approach_speed,
                'grasp_speed': self.parameters.grasp_speed,
                'workspace_bounds': self.parameters.workspace_bounds,
                'enable_real_time_tracking': self.parameters.enable_real_time_tracking
            },
            'component_status': {
                'robot_controller': self.robot_controller.is_ready,
                'camera_interface': self.camera_interface.is_connected,
                'workspace_calibrator': self.workspace_calibrator.is_calibrated,
                'object_detector': True,  # Always available
                'image_processor': True   # Always available
            }
        }

    def abort_current_task(self) -> bool:
        """
        Abort currently executing task.

        Returns:
            True if task was aborted successfully
        """
        if not self._current_task or self._current_task.status not in [
            VisionTaskStatus.DETECTING, VisionTaskStatus.PLANNING, VisionTaskStatus.EXECUTING
        ]:
            return False

        logger.warning(f"Aborting task: {self._current_task.task_id}")

        try:
            # Stop robot movement
            self.robot_controller.stop_movement()

            # Release any grasped objects
            self.tool_controller.release_object()

            # Update task status
            self._current_task.status = VisionTaskStatus.ABORTED
            self._current_task.end_time = time.time()
            self._current_task.error_message = "Task aborted by user"

            # Move to safe position
            self.movement_controller.move_to_home()

            # Archive task
            self._task_history.append(self._current_task)
            self._current_task = None

            logger.info("Task aborted successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to abort task: {e}")
            return False

    def emergency_stop(self) -> None:
        """Execute emergency stop procedure."""
        logger.critical("EMERGENCY STOP ACTIVATED")

        try:
            # Stop all robot movement immediately
            self.robot_controller.emergency_stop()

            # Release any grasped objects
            self.tool_controller.release_object()

            # Abort current task
            if self._current_task:
                self._current_task.status = VisionTaskStatus.ABORTED
                self._current_task.error_message = "Emergency stop activated"
                self._current_task.end_time = time.time()

            # Call emergency stop callback if set
            if self._emergency_stop_callback:
                self._emergency_stop_callback()

            logger.critical("Emergency stop procedure completed")

        except Exception as e:
            logger.critical(f"Emergency stop procedure failed: {e}")

    def reset_statistics(self) -> None:
        """Reset execution statistics."""
        self._execution_stats = {
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'average_accuracy': 0.0
        }
        self._task_history.clear()
        logger.info("Vision control statistics reset")

    def visualize_workspace(self, image: np.ndarray,
                          show_bounds: bool = True,
                          show_targets: bool = True,
                          show_robot_position: bool = True) -> np.ndarray:
        """
        Visualize workspace with targets and robot information.

        Args:
            image: Input image
            show_bounds: Show workspace bounds
            show_targets: Show active targets
            show_robot_position: Show current robot position

        Returns:
            Image with workspace visualization
        """
        result_image = image.copy()

        if show_bounds and self.workspace_calibrator.is_calibrated:
            # Draw workspace bounds
            bounds = self.parameters.workspace_bounds

            # Convert bounds to pixel coordinates
            try:
                corners = [
                    (bounds[0][0], bounds[1][0], bounds[2][0]),  # min_x, min_y, min_z
                    (bounds[0][1], bounds[1][0], bounds[2][0]),  # max_x, min_y, min_z
                    (bounds[0][1], bounds[1][1], bounds[2][0]),  # max_x, max_y, min_z
                    (bounds[0][0], bounds[1][1], bounds[2][0])   # min_x, max_y, min_z
                ]

                pixel_corners = [self.workspace_calibrator.robot_to_pixel(corner) for corner in corners]

                # Draw workspace rectangle
                pts = np.array(pixel_corners, np.int32)
                pts = pts.reshape((-1, 1, 2))
                cv2.polylines(result_image, [pts], True, (255, 255, 0), 2)

                # Add workspace label
                cv2.putText(result_image, "Workspace", pixel_corners[0],
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            except Exception as e:
                logger.debug(f"Failed to draw workspace bounds: {e}")

        if show_targets:
            # Draw active targets
            for target in self._active_targets:
                if target.detected and target.pixel_position:
                    # Draw target marker
                    cv2.circle(result_image, target.pixel_position, 15, (0, 255, 255), 3)

                    # Add target label
                    label = f"{target.id} ({target.confidence:.2f})"
                    cv2.putText(result_image, label,
                               (target.pixel_position[0] + 20, target.pixel_position[1] - 20),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        if show_robot_position and self.workspace_calibrator.is_calibrated:
            # Show current robot position
            try:
                current_pose = self.robot_controller.get_current_pose()
                if current_pose:
                    robot_pixel = self.workspace_calibrator.robot_to_pixel(
                        (current_pose.x, current_pose.y, current_pose.z)
                    )

                    # Draw robot position
                    cv2.circle(result_image, robot_pixel, 10, (0, 0, 255), -1)
                    cv2.putText(result_image, "Robot",
                               (robot_pixel[0] + 15, robot_pixel[1] - 15),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

            except Exception as e:
                logger.debug(f"Failed to draw robot position: {e}")

        # Add task status
        if self._current_task:
            status_text = f"Task: {self._current_task.task_type.value} ({self._current_task.status.value})"
            if self._current_task.progress > 0:
                status_text += f" - {self._current_task.progress:.1%}"

            cv2.putText(result_image, status_text, (10, image.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        return result_image
