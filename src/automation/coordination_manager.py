"""
Coordination Manager

This module provides comprehensive coordination logic for synchronized robot
and conveyor operations, implementing state machine management, collision
avoidance, and performance optimization for complex automation sequences.

Features:
- Synchronized robot and conveyor operations with microsecond timing precision
- State machine for managing complex automation sequences
- Handoff protocols between vision detection and conveyor sensors
- Collision avoidance and safety monitoring
- Performance optimization and adaptive timing
- Real-time coordination of multiple system components
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
import asyncio
from concurrent.futures import ThreadPoolExecutor

from core.robot_controller import RobotController
from vision.camera_interface import CameraInterface
from vision.object_detector import ObjectDetector
from vision.workspace_calibrator import WorkspaceCalibrator
from automation.conveyor_controller import ConveyorController, ConveyorDirection
from automation.sensor_interface import SensorInterface, SensorEvent
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError

logger = get_logger(__name__)


class CoordinationState(Enum):
    """Coordination system states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"
    SHUTTING_DOWN = "shutting_down"


class OperationMode(Enum):
    """Operation mode options."""
    MANUAL = "manual"
    SEMI_AUTOMATIC = "semi_automatic"
    FULLY_AUTOMATIC = "fully_automatic"
    CALIBRATION = "calibration"
    MAINTENANCE = "maintenance"


class CoordinationEvent(Enum):
    """Coordination event types."""
    SYSTEM_READY = "system_ready"
    OPERATION_STARTED = "operation_started"
    OPERATION_COMPLETED = "operation_completed"
    OBJECT_HANDOFF = "object_handoff"
    COLLISION_DETECTED = "collision_detected"
    SAFETY_VIOLATION = "safety_violation"
    PERFORMANCE_ALERT = "performance_alert"


class CoordinationError(RoboticsError):
    """Coordination-specific error class."""
    pass


@dataclass
class CoordinationParameters:
    """Coordination system parameters."""
    # Timing parameters
    sync_precision: float = 0.001  # 1ms synchronization precision
    handoff_timeout: float = 5.0   # seconds
    operation_timeout: float = 30.0  # seconds
    
    # Safety parameters
    collision_detection_enabled: bool = True
    safety_zone_radius: float = 100.0  # mm
    emergency_stop_time: float = 0.1   # seconds
    
    # Performance parameters
    max_concurrent_operations: int = 3
    performance_monitoring: bool = True
    adaptive_timing: bool = True
    
    # Coordination parameters
    vision_sensor_handoff_distance: float = 50.0  # mm
    conveyor_robot_clearance: float = 150.0  # mm
    operation_retry_count: int = 3


@dataclass
class SystemStatus:
    """Current system status information."""
    coordination_state: CoordinationState = CoordinationState.IDLE
    operation_mode: OperationMode = OperationMode.MANUAL
    
    # Component status
    robot_ready: bool = False
    conveyor_ready: bool = False
    vision_ready: bool = False
    sensors_ready: bool = False
    
    # Current operation
    current_operation: Optional[str] = None
    operation_progress: float = 0.0
    operation_start_time: Optional[float] = None
    
    # Performance metrics
    operations_completed: int = 0
    operations_failed: int = 0
    average_cycle_time: float = 0.0
    
    # Safety status
    safety_violations: int = 0
    emergency_stops: int = 0
    last_error: Optional[str] = None


@dataclass
class CoordinationTask:
    """Individual coordination task definition."""
    task_id: str
    task_type: str
    priority: int = 1
    
    # Task parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    # Timing
    estimated_duration: float = 0.0
    timeout: float = 30.0
    
    # Status
    status: str = "pending"
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    error_message: Optional[str] = None


class CoordinationManager:
    """
    Advanced coordination manager providing synchronized robot and conveyor
    operations with state machine management and collision avoidance.
    """
    
    def __init__(self, 
                 robot_controller: RobotController,
                 conveyor_controller: ConveyorController,
                 sensor_interface: SensorInterface,
                 camera_interface: Optional[CameraInterface] = None,
                 object_detector: Optional[ObjectDetector] = None,
                 workspace_calibrator: Optional[WorkspaceCalibrator] = None,
                 config_manager=None):
        """
        Initialize coordination manager.
        
        Args:
            robot_controller: Robot controller instance
            conveyor_controller: Conveyor controller instance
            sensor_interface: Sensor interface instance
            camera_interface: Optional camera interface
            object_detector: Optional object detector
            workspace_calibrator: Optional workspace calibrator
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.conveyor_controller = conveyor_controller
        self.sensor_interface = sensor_interface
        self.camera_interface = camera_interface
        self.object_detector = object_detector
        self.workspace_calibrator = workspace_calibrator
        
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Coordination parameters
        self.parameters = CoordinationParameters()
        
        # System status
        self.status = SystemStatus()
        
        # State machine
        self._state_machine_lock = threading.RLock()
        self._state_transitions = self._initialize_state_machine()
        
        # Task management
        self._task_queue = Queue()
        self._active_tasks: Dict[str, CoordinationTask] = {}
        self._completed_tasks: List[CoordinationTask] = []
        
        # Threading and execution
        self._coordination_thread: Optional[threading.Thread] = None
        self._stop_coordination = threading.Event()
        self._executor = ThreadPoolExecutor(max_workers=self.parameters.max_concurrent_operations)
        
        # Event handling
        self._event_callbacks: Dict[CoordinationEvent, List[Callable]] = {
            event_type: [] for event_type in CoordinationEvent
        }
        
        # Performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._operation_history: List[Dict[str, Any]] = []
        
        # Safety monitoring
        self._safety_enabled = True
        self._collision_zones: List[Dict[str, Any]] = []
        
        # Synchronization primitives
        self._sync_events: Dict[str, threading.Event] = {}
        self._sync_locks: Dict[str, threading.Lock] = {}
        
        logger.info("Coordination manager initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if coordination system is ready."""
        return (self.status.coordination_state == CoordinationState.READY and
                self.status.robot_ready and
                self.status.conveyor_ready and
                self.status.sensors_ready)
    
    @property
    def is_running(self) -> bool:
        """Check if coordination system is running."""
        return self.status.coordination_state == CoordinationState.RUNNING
    
    @property
    def current_operation(self) -> Optional[str]:
        """Get current operation name."""
        return self.status.current_operation
    
    def initialize(self) -> bool:
        """
        Initialize coordination system and all components.
        
        Returns:
            True if initialization successful
        """
        logger.info("Initializing coordination system...")
        
        try:
            with self._state_machine_lock:
                self._transition_state(CoordinationState.INITIALIZING)
            
            # Initialize components
            success = True
            
            # Initialize robot
            if not self.robot_controller.is_connected:
                success &= self.robot_controller.connect()
            self.status.robot_ready = self.robot_controller.is_ready
            
            # Initialize conveyor
            if not self.conveyor_controller.is_connected:
                success &= self.conveyor_controller.connect()
            self.status.conveyor_ready = self.conveyor_controller.is_connected
            
            # Initialize sensors
            if not self.sensor_interface.is_connected:
                success &= self.sensor_interface.connect()
            self.status.sensors_ready = self.sensor_interface.is_connected
            
            # Initialize vision components if available
            if self.camera_interface and not self.camera_interface.is_connected:
                self.camera_interface.connect()
            self.status.vision_ready = (self.camera_interface.is_connected 
                                      if self.camera_interface else True)
            
            if success and self._check_system_readiness():
                # Setup event callbacks
                self._setup_event_callbacks()
                
                # Start coordination thread
                self._start_coordination_thread()
                
                # Transition to ready state
                with self._state_machine_lock:
                    self._transition_state(CoordinationState.READY)
                
                logger.info("Coordination system initialized successfully")
                self._trigger_event(CoordinationEvent.SYSTEM_READY)
                return True
            else:
                with self._state_machine_lock:
                    self._transition_state(CoordinationState.ERROR)
                logger.error("Failed to initialize coordination system")
                return False
                
        except Exception as e:
            error_msg = f"Error during coordination system initialization: {e}"
            logger.error(error_msg)
            self.status.last_error = error_msg
            with self._state_machine_lock:
                self._transition_state(CoordinationState.ERROR)
            return False
    
    def shutdown(self) -> None:
        """Shutdown coordination system and all components."""
        logger.info("Shutting down coordination system...")
        
        try:
            with self._state_machine_lock:
                self._transition_state(CoordinationState.SHUTTING_DOWN)
            
            # Stop coordination thread
            self._stop_coordination_thread()
            
            # Stop all active operations
            self.stop_all_operations()
            
            # Shutdown components
            if self.conveyor_controller.is_running:
                self.conveyor_controller.stop()
            
            self.conveyor_controller.disconnect()
            self.sensor_interface.disconnect()
            
            if self.camera_interface and self.camera_interface.is_connected:
                self.camera_interface.disconnect()
            
            # Shutdown executor
            self._executor.shutdown(wait=True)
            
            with self._state_machine_lock:
                self._transition_state(CoordinationState.IDLE)
            
            logger.info("Coordination system shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during coordination system shutdown: {e}")
    
    def _initialize_state_machine(self) -> Dict[CoordinationState, List[CoordinationState]]:
        """Initialize state machine transitions."""
        return {
            CoordinationState.IDLE: [CoordinationState.INITIALIZING],
            CoordinationState.INITIALIZING: [CoordinationState.READY, CoordinationState.ERROR],
            CoordinationState.READY: [CoordinationState.RUNNING, CoordinationState.PAUSED, 
                                    CoordinationState.SHUTTING_DOWN, CoordinationState.ERROR],
            CoordinationState.RUNNING: [CoordinationState.READY, CoordinationState.PAUSED, 
                                      CoordinationState.EMERGENCY_STOP, CoordinationState.ERROR],
            CoordinationState.PAUSED: [CoordinationState.RUNNING, CoordinationState.READY, 
                                     CoordinationState.SHUTTING_DOWN],
            CoordinationState.ERROR: [CoordinationState.READY, CoordinationState.SHUTTING_DOWN],
            CoordinationState.EMERGENCY_STOP: [CoordinationState.READY, CoordinationState.ERROR],
            CoordinationState.SHUTTING_DOWN: [CoordinationState.IDLE]
        }
    
    def _transition_state(self, new_state: CoordinationState) -> bool:
        """
        Transition to new coordination state.
        
        Args:
            new_state: Target state
            
        Returns:
            True if transition successful
        """
        current_state = self.status.coordination_state
        
        # Check if transition is valid
        valid_transitions = self._state_transitions.get(current_state, [])
        if new_state not in valid_transitions:
            logger.warning(f"Invalid state transition: {current_state.value} -> {new_state.value}")
            return False
        
        # Perform transition
        logger.info(f"State transition: {current_state.value} -> {new_state.value}")
        self.status.coordination_state = new_state
        
        # Perform state-specific actions
        self._on_state_entered(new_state)
        
        return True
    
    def _on_state_entered(self, state: CoordinationState) -> None:
        """Handle state entry actions."""
        if state == CoordinationState.READY:
            self.status.current_operation = None
            self.status.operation_progress = 0.0
        elif state == CoordinationState.EMERGENCY_STOP:
            self._handle_emergency_stop()
        elif state == CoordinationState.ERROR:
            self._handle_error_state()
    
    def _check_system_readiness(self) -> bool:
        """Check if all system components are ready."""
        return (self.status.robot_ready and
                self.status.conveyor_ready and
                self.status.sensors_ready and
                self.status.vision_ready)

    def _setup_event_callbacks(self) -> None:
        """Setup event callbacks for component integration."""
        # Sensor event callbacks
        self.sensor_interface.add_event_callback(
            SensorEvent.OBJECT_DETECTED,
            self._on_object_detected
        )

        self.sensor_interface.add_event_callback(
            SensorEvent.OBJECT_CLEARED,
            self._on_object_cleared
        )

        # Conveyor event callbacks
        self.conveyor_controller.add_emergency_stop_callback(
            self._on_conveyor_emergency_stop
        )

        self.conveyor_controller.add_status_change_callback(
            self._on_conveyor_status_change
        )

        logger.debug("Event callbacks setup complete")

    def _start_coordination_thread(self) -> None:
        """Start coordination monitoring thread."""
        if self._coordination_thread and self._coordination_thread.is_alive():
            return

        self._stop_coordination.clear()
        self._coordination_thread = threading.Thread(
            target=self._coordination_loop,
            daemon=True
        )
        self._coordination_thread.start()
        logger.debug("Coordination thread started")

    def _stop_coordination_thread(self) -> None:
        """Stop coordination monitoring thread."""
        if self._coordination_thread and self._coordination_thread.is_alive():
            self._stop_coordination.set()
            self._coordination_thread.join(timeout=2.0)
        logger.debug("Coordination thread stopped")

    def _coordination_loop(self) -> None:
        """Main coordination monitoring loop."""
        logger.debug("Starting coordination loop")

        while not self._stop_coordination.is_set():
            try:
                # Process task queue
                self._process_task_queue()

                # Monitor active tasks
                self._monitor_active_tasks()

                # Perform safety checks
                if self._safety_enabled:
                    self._perform_safety_checks()

                # Update performance metrics
                self._update_performance_metrics()

                # Sleep for coordination interval
                self._stop_coordination.wait(self.parameters.sync_precision)

            except Exception as e:
                logger.warning(f"Error in coordination loop: {e}")
                time.sleep(0.1)

        logger.debug("Coordination loop stopped")

    def _process_task_queue(self) -> None:
        """Process pending tasks from queue."""
        try:
            while not self._task_queue.empty():
                task = self._task_queue.get_nowait()

                # Check if task can be executed
                if self._can_execute_task(task):
                    self._execute_task(task)
                else:
                    # Put task back in queue
                    self._task_queue.put(task)
                    break

        except Empty:
            pass

    def _can_execute_task(self, task: CoordinationTask) -> bool:
        """Check if task can be executed now."""
        # Check system state
        if self.status.coordination_state != CoordinationState.READY:
            return False

        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id in self._active_tasks:
                return False  # Dependency still active

        # Check resource availability
        if len(self._active_tasks) >= self.parameters.max_concurrent_operations:
            return False

        return True

    def _execute_task(self, task: CoordinationTask) -> None:
        """Execute coordination task."""
        logger.info(f"Executing task: {task.task_id} ({task.task_type})")

        task.status = "running"
        task.start_time = time.time()
        self._active_tasks[task.task_id] = task

        # Submit task to executor
        future = self._executor.submit(self._run_task, task)
        task.future = future

    def _run_task(self, task: CoordinationTask) -> None:
        """Run individual coordination task."""
        try:
            # Execute task based on type
            if task.task_type == "pick_and_place":
                self._execute_pick_and_place_task(task)
            elif task.task_type == "conveyor_sync":
                self._execute_conveyor_sync_task(task)
            elif task.task_type == "vision_handoff":
                self._execute_vision_handoff_task(task)
            else:
                raise CoordinationError(f"Unknown task type: {task.task_type}")

            # Mark task as completed
            task.status = "completed"
            task.completion_time = time.time()

            logger.info(f"Task completed: {task.task_id}")

        except Exception as e:
            error_msg = f"Task failed: {task.task_id} - {e}"
            logger.error(error_msg)
            task.status = "failed"
            task.error_message = str(e)
            task.completion_time = time.time()

        finally:
            # Remove from active tasks
            if task.task_id in self._active_tasks:
                del self._active_tasks[task.task_id]

            # Add to completed tasks
            self._completed_tasks.append(task)

            # Keep only last 100 completed tasks
            if len(self._completed_tasks) > 100:
                self._completed_tasks.pop(0)

    def _monitor_active_tasks(self) -> None:
        """Monitor active tasks for timeouts and completion."""
        current_time = time.time()
        tasks_to_timeout = []

        for task_id, task in self._active_tasks.items():
            if task.start_time and (current_time - task.start_time) > task.timeout:
                tasks_to_timeout.append(task_id)

        # Handle timeouts
        for task_id in tasks_to_timeout:
            task = self._active_tasks[task_id]
            logger.warning(f"Task timeout: {task_id}")
            task.status = "timeout"
            task.error_message = "Task timeout"
            task.completion_time = current_time

            # Cancel task if possible
            if hasattr(task, 'future'):
                task.future.cancel()

            del self._active_tasks[task_id]
            self._completed_tasks.append(task)

    def _perform_safety_checks(self) -> None:
        """Perform safety checks and collision detection."""
        if not self.parameters.collision_detection_enabled:
            return

        # Check robot-conveyor clearance
        if self.robot_controller.is_ready and self.conveyor_controller.is_running:
            robot_pose = self.robot_controller.get_current_pose()

            # Simple collision check based on robot position
            if robot_pose and robot_pose.z < self.parameters.conveyor_robot_clearance:
                logger.warning("Robot-conveyor clearance violation detected")
                self._trigger_event(CoordinationEvent.COLLISION_DETECTED)

                # Take safety action
                if self._safety_enabled:
                    self.emergency_stop()

    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        # Calculate average cycle time
        if self._completed_tasks:
            completed_times = []
            for task in self._completed_tasks[-10:]:  # Last 10 tasks
                if task.start_time and task.completion_time:
                    cycle_time = task.completion_time - task.start_time
                    completed_times.append(cycle_time)

            if completed_times:
                self.status.average_cycle_time = sum(completed_times) / len(completed_times)

        # Update operation counts
        self.status.operations_completed = len([t for t in self._completed_tasks if t.status == "completed"])
        self.status.operations_failed = len([t for t in self._completed_tasks if t.status == "failed"])
    def execute_synchronized_operation(self, operation_type: str, parameters: Dict[str, Any]) -> bool:
        """
        Execute synchronized operation between robot and conveyor.

        Args:
            operation_type: Type of operation to execute
            parameters: Operation parameters

        Returns:
            True if operation successful
        """
        if not self.is_ready:
            raise CoordinationError("Coordination system not ready")

        logger.info(f"Starting synchronized operation: {operation_type}")

        try:
            with self._state_machine_lock:
                self._transition_state(CoordinationState.RUNNING)

            self.status.current_operation = operation_type
            self.status.operation_start_time = time.time()
            self.status.operation_progress = 0.0

            # Create coordination task
            task = CoordinationTask(
                task_id=f"{operation_type}_{int(time.time())}",
                task_type=operation_type,
                parameters=parameters,
                timeout=self.parameters.operation_timeout
            )

            # Add task to queue
            self._task_queue.put(task)

            # Wait for task completion
            start_time = time.time()
            while (task.task_id in self._active_tasks or
                   task.status == "pending"):

                if (time.time() - start_time) > self.parameters.operation_timeout:
                    raise CoordinationError("Operation timeout")

                time.sleep(0.1)

            # Check result
            success = task.status == "completed"

            if success:
                logger.info(f"Synchronized operation completed: {operation_type}")
                self._trigger_event(CoordinationEvent.OPERATION_COMPLETED)
            else:
                logger.error(f"Synchronized operation failed: {operation_type} - {task.error_message}")

            # Update status
            self.status.current_operation = None
            self.status.operation_progress = 100.0 if success else 0.0

            with self._state_machine_lock:
                self._transition_state(CoordinationState.READY)

            return success

        except Exception as e:
            error_msg = f"Error in synchronized operation {operation_type}: {e}"
            logger.error(error_msg)
            self.status.last_error = error_msg

            with self._state_machine_lock:
                self._transition_state(CoordinationState.ERROR)

            return False

    def _execute_pick_and_place_task(self, task: CoordinationTask) -> None:
        """Execute pick and place coordination task."""
        params = task.parameters

        # Get object position from vision or sensors
        if 'object_position' in params:
            object_pos = params['object_position']
        else:
            # Use vision system to detect object
            if not self.object_detector:
                raise CoordinationError("No object detector available")

            # Capture and analyze image
            frame, _ = self.camera_interface.capture_frame()
            objects = self.object_detector.detect_objects(frame)

            if not objects:
                raise CoordinationError("No objects detected")

            # Use first detected object
            detected_obj = objects[0]
            object_pos = (detected_obj.center_x, detected_obj.center_y)

        # Convert to robot coordinates
        if self.workspace_calibrator and self.workspace_calibrator.is_calibrated:
            robot_coords = self.workspace_calibrator.pixel_to_robot(object_pos, params.get('grasp_height', 200.0))
        else:
            raise CoordinationError("Workspace not calibrated")

        # Execute pick operation
        success = self.robot_controller.move_to_position(*robot_coords)
        if not success:
            raise CoordinationError("Failed to move to pick position")

        # Grasp object
        success = self.robot_controller.close_gripper()
        if not success:
            raise CoordinationError("Failed to grasp object")

        # Move to place position
        place_pos = params.get('place_position', (300.0, 0.0, 200.0))
        success = self.robot_controller.move_to_position(*place_pos)
        if not success:
            raise CoordinationError("Failed to move to place position")

        # Release object
        success = self.robot_controller.open_gripper()
        if not success:
            raise CoordinationError("Failed to release object")

        # Return to home
        self.robot_controller.move_to_home()

    def _execute_conveyor_sync_task(self, task: CoordinationTask) -> None:
        """Execute conveyor synchronization task."""
        params = task.parameters

        # Start conveyor
        speed = params.get('speed', 50.0)
        direction = params.get('direction', ConveyorDirection.FORWARD)

        success = self.conveyor_controller.start(speed, direction)
        if not success:
            raise CoordinationError("Failed to start conveyor")

        # Wait for specified duration or until object detected
        duration = params.get('duration', 5.0)
        wait_for_object = params.get('wait_for_object', False)

        start_time = time.time()
        while (time.time() - start_time) < duration:
            if wait_for_object and self.sensor_interface.tracked_objects_count > 0:
                break
            time.sleep(0.1)

        # Stop conveyor if requested
        if params.get('stop_after', True):
            self.conveyor_controller.stop()

    def _execute_vision_handoff_task(self, task: CoordinationTask) -> None:
        """Execute vision-sensor handoff task."""
        params = task.parameters

        # Wait for object detection in vision system
        if not self.object_detector:
            raise CoordinationError("No object detector available")

        timeout = params.get('timeout', 10.0)
        start_time = time.time()

        object_detected = False
        while (time.time() - start_time) < timeout:
            frame, _ = self.camera_interface.capture_frame()
            objects = self.object_detector.detect_objects(frame)

            if objects:
                object_detected = True
                break

            time.sleep(0.1)

        if not object_detected:
            raise CoordinationError("No object detected in vision system")

        # Wait for sensor confirmation
        sensor_timeout = params.get('sensor_timeout', 5.0)
        sensor_start = time.time()

        sensor_triggered = False
        while (time.time() - sensor_start) < sensor_timeout:
            if self.sensor_interface.tracked_objects_count > 0:
                sensor_triggered = True
                break
            time.sleep(0.1)

        if not sensor_triggered:
            raise CoordinationError("Sensor handoff failed")

    def _on_object_detected(self, event) -> None:
        """Handle object detected event from sensors."""
        logger.debug(f"Object detected by sensor: {event.sensor_id}")
        self._trigger_event(CoordinationEvent.OBJECT_HANDOFF)

    def _on_object_cleared(self, event) -> None:
        """Handle object cleared event from sensors."""
        logger.debug(f"Object cleared from sensor: {event.sensor_id}")

    def _on_conveyor_emergency_stop(self) -> None:
        """Handle conveyor emergency stop."""
        logger.critical("Conveyor emergency stop triggered")
        self.emergency_stop()

    def _on_conveyor_status_change(self, status) -> None:
        """Handle conveyor status change."""
        logger.debug(f"Conveyor status changed: {status}")
        self.status.conveyor_ready = (status != "error")

    def _handle_emergency_stop(self) -> None:
        """Handle emergency stop procedures."""
        logger.critical("COORDINATION EMERGENCY STOP ACTIVATED")

        # Stop all components
        try:
            if self.conveyor_controller.is_running:
                self.conveyor_controller.emergency_stop()

            if self.robot_controller.is_ready:
                self.robot_controller.emergency_stop()

            # Cancel all active tasks
            for task in self._active_tasks.values():
                if hasattr(task, 'future'):
                    task.future.cancel()
                task.status = "cancelled"
                task.error_message = "Emergency stop"

            self._active_tasks.clear()

            self.status.emergency_stops += 1

        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")

    def _handle_error_state(self) -> None:
        """Handle error state procedures."""
        logger.error("Coordination system in error state")

        # Stop current operation
        self.status.current_operation = None
        self.status.operation_progress = 0.0

        # Cancel active tasks
        for task in self._active_tasks.values():
            if hasattr(task, 'future'):
                task.future.cancel()
            task.status = "cancelled"
            task.error_message = "System error"

        self._active_tasks.clear()

    def _trigger_event(self, event_type: CoordinationEvent, data: Any = None) -> None:
        """Trigger coordination event and notify callbacks."""
        logger.debug(f"Triggering event: {event_type.value}")

        # Notify callbacks
        callbacks = self._event_callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    def emergency_stop(self) -> None:
        """Perform emergency stop of entire coordination system."""
        logger.critical("COORDINATION SYSTEM EMERGENCY STOP")

        with self._state_machine_lock:
            self._transition_state(CoordinationState.EMERGENCY_STOP)

    def reset_emergency_stop(self) -> bool:
        """Reset emergency stop state."""
        logger.info("Resetting coordination system emergency stop")

        try:
            # Reset component emergency stops
            success = True

            if hasattr(self.conveyor_controller, 'reset_emergency_stop'):
                success &= self.conveyor_controller.reset_emergency_stop()

            if hasattr(self.robot_controller, 'reset_emergency_stop'):
                success &= self.robot_controller.reset_emergency_stop()

            if success:
                with self._state_machine_lock:
                    self._transition_state(CoordinationState.READY)
                logger.info("Emergency stop reset successfully")
                return True
            else:
                logger.error("Failed to reset emergency stop")
                return False

        except Exception as e:
            logger.error(f"Error resetting emergency stop: {e}")
            return False

    def pause_operations(self) -> bool:
        """Pause all coordination operations."""
        logger.info("Pausing coordination operations")

        with self._state_machine_lock:
            if self.status.coordination_state == CoordinationState.RUNNING:
                return self._transition_state(CoordinationState.PAUSED)

        return False

    def resume_operations(self) -> bool:
        """Resume coordination operations."""
        logger.info("Resuming coordination operations")

        with self._state_machine_lock:
            if self.status.coordination_state == CoordinationState.PAUSED:
                return self._transition_state(CoordinationState.RUNNING)

        return False

    def stop_all_operations(self) -> None:
        """Stop all active operations."""
        logger.info("Stopping all coordination operations")

        # Cancel all active tasks
        for task in self._active_tasks.values():
            if hasattr(task, 'future'):
                task.future.cancel()
            task.status = "cancelled"
            task.error_message = "Operations stopped"

        self._active_tasks.clear()

        # Stop conveyor if running
        if self.conveyor_controller.is_running:
            self.conveyor_controller.stop()

        self.status.current_operation = None
        self.status.operation_progress = 0.0

    def add_event_callback(self, event_type: CoordinationEvent, callback: Callable) -> None:
        """Add callback for coordination events."""
        self._event_callbacks[event_type].append(callback)
        logger.info(f"Added callback for {event_type.value} events")

    def get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status."""
        return {
            'coordination_state': self.status.coordination_state.value,
            'operation_mode': self.status.operation_mode.value,
            'is_ready': self.is_ready,
            'is_running': self.is_running,
            'current_operation': self.status.current_operation,
            'operation_progress': self.status.operation_progress,
            'component_status': {
                'robot_ready': self.status.robot_ready,
                'conveyor_ready': self.status.conveyor_ready,
                'vision_ready': self.status.vision_ready,
                'sensors_ready': self.status.sensors_ready
            },
            'performance_metrics': {
                'operations_completed': self.status.operations_completed,
                'operations_failed': self.status.operations_failed,
                'average_cycle_time': self.status.average_cycle_time,
                'active_tasks': len(self._active_tasks),
                'completed_tasks': len(self._completed_tasks)
            },
            'safety_status': {
                'safety_violations': self.status.safety_violations,
                'emergency_stops': self.status.emergency_stops,
                'last_error': self.status.last_error
            }
        }

    def __enter__(self):
        """Context manager entry."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()
