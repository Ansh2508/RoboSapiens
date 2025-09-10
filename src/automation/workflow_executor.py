"""
Workflow Executor

This module provides comprehensive workflow execution capabilities for complete
automation sequences, including end-to-end pick-and-place operations, multi-object
processing, error recovery, and performance monitoring.

Features:
- End-to-end pick-and-place automation sequences
- Multi-object processing with intelligent queue management
- Error recovery and retry mechanisms
- Performance monitoring and analytics
- Integration with Phase 2 movement patterns and Phase 3 vision control
- Educational workflow demonstrations
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty, PriorityQueue
import json
from pathlib import Path

from core.robot_controller import RobotController
from core.advanced_movement import AdvancedMovementController
from vision.camera_interface import CameraInterface
from vision.object_detector import ObjectDetector, DetectedObject
from vision.workspace_calibrator import WorkspaceCalibrator
from automation.conveyor_controller import ConveyorController, ConveyorDirection
from automation.sensor_interface import SensorInterface, SensorEvent
from automation.coordination_manager import CoordinationManager
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError

logger = get_logger(__name__)


class WorkflowState(Enum):
    """Workflow execution states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowType(Enum):
    """Workflow type options."""
    PICK_AND_PLACE = "pick_and_place"
    CONVEYOR_SORTING = "conveyor_sorting"
    MULTI_OBJECT_PROCESSING = "multi_object_processing"
    QUALITY_INSPECTION = "quality_inspection"
    EDUCATIONAL_DEMO = "educational_demo"
    CUSTOM = "custom"


class WorkflowPriority(Enum):
    """Workflow priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class WorkflowError(RoboticsError):
    """Workflow-specific error class."""
    pass


@dataclass
class WorkflowStep:
    """Individual workflow step definition."""
    step_id: str
    step_type: str
    description: str
    
    # Parameters
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Dependencies and conditions
    dependencies: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Timing
    estimated_duration: float = 0.0
    timeout: float = 30.0
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # Status
    status: str = "pending"
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    retry_count: int = 0
    error_message: Optional[str] = None


@dataclass
class WorkflowDefinition:
    """Complete workflow definition."""
    workflow_id: str
    workflow_type: WorkflowType
    name: str
    description: str
    
    # Steps
    steps: List[WorkflowStep] = field(default_factory=list)
    
    # Configuration
    priority: WorkflowPriority = WorkflowPriority.NORMAL
    timeout: float = 300.0  # 5 minutes default
    
    # Error handling
    error_recovery_enabled: bool = True
    continue_on_error: bool = False
    
    # Performance
    target_cycle_time: float = 60.0  # seconds
    
    # Metadata
    created_time: float = field(default_factory=time.time)
    version: str = "1.0"
    tags: List[str] = field(default_factory=list)


@dataclass
class WorkflowExecution:
    """Workflow execution instance."""
    execution_id: str
    workflow_definition: WorkflowDefinition
    
    # Status
    state: WorkflowState = WorkflowState.IDLE
    current_step: Optional[str] = None
    progress: float = 0.0
    
    # Timing
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    
    # Results
    completed_steps: List[str] = field(default_factory=list)
    failed_steps: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    actual_cycle_time: Optional[float] = None
    efficiency_score: Optional[float] = None
    
    # Error handling
    error_count: int = 0
    last_error: Optional[str] = None


class WorkflowExecutor:
    """
    Advanced workflow executor providing end-to-end automation sequences
    with multi-object processing, error recovery, and performance monitoring.
    """
    
    def __init__(self,
                 coordination_manager: CoordinationManager,
                 robot_controller: RobotController,
                 advanced_movement: AdvancedMovementController,
                 conveyor_controller: ConveyorController,
                 sensor_interface: SensorInterface,
                 camera_interface: CameraInterface,
                 object_detector: ObjectDetector,
                 workspace_calibrator: WorkspaceCalibrator,
                 config_manager=None):
        """
        Initialize workflow executor.
        
        Args:
            coordination_manager: Coordination manager instance
            robot_controller: Robot controller instance
            advanced_movement: Advanced movement controller
            conveyor_controller: Conveyor controller instance
            sensor_interface: Sensor interface instance
            camera_interface: Camera interface instance
            object_detector: Object detector instance
            workspace_calibrator: Workspace calibrator instance
            config_manager: Configuration manager instance
        """
        self.coordination_manager = coordination_manager
        self.robot_controller = robot_controller
        self.advanced_movement = advanced_movement
        self.conveyor_controller = conveyor_controller
        self.sensor_interface = sensor_interface
        self.camera_interface = camera_interface
        self.object_detector = object_detector
        self.workspace_calibrator = workspace_calibrator
        
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Workflow management
        self._workflow_definitions: Dict[str, WorkflowDefinition] = {}
        self._active_executions: Dict[str, WorkflowExecution] = {}
        self._execution_history: List[WorkflowExecution] = []
        
        # Execution queue
        self._execution_queue = PriorityQueue()
        self._object_queue = Queue()
        
        # Threading
        self._executor_thread: Optional[threading.Thread] = None
        self._stop_executor = threading.Event()
        
        # Performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._statistics = {
            'workflows_executed': 0,
            'workflows_completed': 0,
            'workflows_failed': 0,
            'objects_processed': 0,
            'average_cycle_time': 0.0,
            'efficiency_score': 0.0
        }
        
        # Event callbacks
        self._event_callbacks: Dict[str, List[Callable]] = {
            'workflow_started': [],
            'workflow_completed': [],
            'workflow_failed': [],
            'step_completed': [],
            'object_processed': []
        }
        
        # Load predefined workflows
        self._load_predefined_workflows()
        
        logger.info("Workflow executor initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if workflow executor is ready."""
        return (self.coordination_manager.is_ready and
                self.workspace_calibrator.is_calibrated)
    
    @property
    def active_executions_count(self) -> int:
        """Get number of active workflow executions."""
        return len(self._active_executions)
    
    @property
    def queued_objects_count(self) -> int:
        """Get number of objects in processing queue."""
        return self._object_queue.qsize()
    
    def start_executor(self) -> bool:
        """
        Start workflow executor thread.
        
        Returns:
            True if executor started successfully
        """
        if self._executor_thread and self._executor_thread.is_alive():
            logger.warning("Workflow executor already running")
            return True
        
        if not self.is_ready:
            logger.error("Workflow executor not ready")
            return False
        
        logger.info("Starting workflow executor...")
        
        try:
            self._stop_executor.clear()
            self._executor_thread = threading.Thread(
                target=self._executor_loop,
                daemon=True
            )
            self._executor_thread.start()
            
            logger.info("Workflow executor started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start workflow executor: {e}")
            return False
    
    def stop_executor(self) -> None:
        """Stop workflow executor thread."""
        logger.info("Stopping workflow executor...")
        
        try:
            # Stop executor thread
            if self._executor_thread and self._executor_thread.is_alive():
                self._stop_executor.set()
                self._executor_thread.join(timeout=5.0)
            
            # Cancel active executions
            for execution in self._active_executions.values():
                execution.state = WorkflowState.CANCELLED
                execution.completion_time = time.time()
            
            self._active_executions.clear()
            
            logger.info("Workflow executor stopped")
            
        except Exception as e:
            logger.error(f"Error stopping workflow executor: {e}")
    
    def _executor_loop(self) -> None:
        """Main workflow executor loop."""
        logger.debug("Starting workflow executor loop")
        
        while not self._stop_executor.is_set():
            try:
                # Process execution queue
                self._process_execution_queue()
                
                # Monitor active executions
                self._monitor_active_executions()
                
                # Process object queue
                self._process_object_queue()
                
                # Update performance metrics
                self._update_performance_metrics()
                
                # Sleep for executor interval
                self._stop_executor.wait(0.1)  # 10Hz execution loop
                
            except Exception as e:
                logger.warning(f"Error in workflow executor loop: {e}")
                time.sleep(1.0)
        
        logger.debug("Workflow executor loop stopped")
    
    def _process_execution_queue(self) -> None:
        """Process pending workflow executions."""
        try:
            while not self._execution_queue.empty():
                priority, execution_id = self._execution_queue.get_nowait()
                
                if execution_id in self._active_executions:
                    execution = self._active_executions[execution_id]
                    
                    if execution.state == WorkflowState.READY:
                        self._start_workflow_execution(execution)
                    
        except Empty:
            pass
    
    def _monitor_active_executions(self) -> None:
        """Monitor active workflow executions."""
        current_time = time.time()
        executions_to_timeout = []
        
        for execution_id, execution in self._active_executions.items():
            # Check for timeouts
            if (execution.start_time and 
                (current_time - execution.start_time) > execution.workflow_definition.timeout):
                executions_to_timeout.append(execution_id)
            
            # Update progress
            if execution.state == WorkflowState.RUNNING:
                self._update_execution_progress(execution)
        
        # Handle timeouts
        for execution_id in executions_to_timeout:
            execution = self._active_executions[execution_id]
            logger.warning(f"Workflow execution timeout: {execution_id}")
            self._fail_workflow_execution(execution, "Workflow timeout")
    
    def _process_object_queue(self) -> None:
        """Process objects in the processing queue."""
        try:
            while not self._object_queue.empty():
                object_data = self._object_queue.get_nowait()
                
                # Create workflow for object processing
                workflow_id = self._create_object_processing_workflow(object_data)
                
                if workflow_id:
                    self.execute_workflow(workflow_id)
                    
        except Empty:
            pass
    
    def _load_predefined_workflows(self) -> None:
        """Load predefined workflow definitions."""
        # Basic pick and place workflow
        pick_place_workflow = WorkflowDefinition(
            workflow_id="basic_pick_place",
            workflow_type=WorkflowType.PICK_AND_PLACE,
            name="Basic Pick and Place",
            description="Simple pick and place operation",
            steps=[
                WorkflowStep(
                    step_id="detect_object",
                    step_type="vision_detection",
                    description="Detect object using vision system"
                ),
                WorkflowStep(
                    step_id="move_to_pick",
                    step_type="robot_movement",
                    description="Move robot to pick position",
                    dependencies=["detect_object"]
                ),
                WorkflowStep(
                    step_id="grasp_object",
                    step_type="gripper_control",
                    description="Grasp the object",
                    dependencies=["move_to_pick"]
                ),
                WorkflowStep(
                    step_id="move_to_place",
                    step_type="robot_movement",
                    description="Move robot to place position",
                    dependencies=["grasp_object"]
                ),
                WorkflowStep(
                    step_id="release_object",
                    step_type="gripper_control",
                    description="Release the object",
                    dependencies=["move_to_place"]
                ),
                WorkflowStep(
                    step_id="return_home",
                    step_type="robot_movement",
                    description="Return robot to home position",
                    dependencies=["release_object"]
                )
            ]
        )
        
        self._workflow_definitions["basic_pick_place"] = pick_place_workflow
        
        # Conveyor sorting workflow
        conveyor_sorting_workflow = WorkflowDefinition(
            workflow_id="conveyor_sorting",
            workflow_type=WorkflowType.CONVEYOR_SORTING,
            name="Conveyor Belt Sorting",
            description="Sort objects on conveyor belt by color/shape",
            steps=[
                WorkflowStep(
                    step_id="start_conveyor",
                    step_type="conveyor_control",
                    description="Start conveyor belt"
                ),
                WorkflowStep(
                    step_id="wait_for_object",
                    step_type="sensor_monitoring",
                    description="Wait for object detection on conveyor",
                    dependencies=["start_conveyor"]
                ),
                WorkflowStep(
                    step_id="analyze_object",
                    step_type="vision_analysis",
                    description="Analyze object properties",
                    dependencies=["wait_for_object"]
                ),
                WorkflowStep(
                    step_id="sort_decision",
                    step_type="decision_logic",
                    description="Decide sorting action based on analysis",
                    dependencies=["analyze_object"]
                ),
                WorkflowStep(
                    step_id="execute_sort",
                    step_type="robot_sorting",
                    description="Execute sorting action",
                    dependencies=["sort_decision"]
                )
            ]
        )
        
        self._workflow_definitions["conveyor_sorting"] = conveyor_sorting_workflow
        
        logger.info(f"Loaded {len(self._workflow_definitions)} predefined workflows")
    def execute_workflow(self, workflow_id: str, parameters: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute workflow by ID.

        Args:
            workflow_id: ID of workflow to execute
            parameters: Optional workflow parameters

        Returns:
            Execution ID
        """
        if workflow_id not in self._workflow_definitions:
            raise WorkflowError(f"Workflow not found: {workflow_id}")

        if not self.is_ready:
            raise WorkflowError("Workflow executor not ready")

        workflow_def = self._workflow_definitions[workflow_id]
        execution_id = f"{workflow_id}_{int(time.time())}"

        logger.info(f"Starting workflow execution: {execution_id}")

        # Create execution instance
        execution = WorkflowExecution(
            execution_id=execution_id,
            workflow_definition=workflow_def,
            state=WorkflowState.READY
        )

        # Apply parameters if provided
        if parameters:
            for step in execution.workflow_definition.steps:
                step.parameters.update(parameters.get(step.step_id, {}))

        # Add to active executions
        self._active_executions[execution_id] = execution

        # Queue for execution
        priority = -workflow_def.priority.value  # Negative for priority queue (higher priority first)
        self._execution_queue.put((priority, execution_id))

        # Update statistics
        self._statistics['workflows_executed'] += 1

        # Trigger event
        self._trigger_event('workflow_started', execution)

        return execution_id

    def _start_workflow_execution(self, execution: WorkflowExecution) -> None:
        """Start executing workflow steps."""
        logger.info(f"Starting workflow execution: {execution.execution_id}")

        execution.state = WorkflowState.RUNNING
        execution.start_time = time.time()

        # Execute steps in order
        try:
            for step in execution.workflow_definition.steps:
                if execution.state != WorkflowState.RUNNING:
                    break  # Execution was cancelled or failed

                self._execute_workflow_step(execution, step)

            # Check if all steps completed successfully
            if execution.state == WorkflowState.RUNNING:
                self._complete_workflow_execution(execution)

        except Exception as e:
            error_msg = f"Error in workflow execution {execution.execution_id}: {e}"
            logger.error(error_msg)
            self._fail_workflow_execution(execution, error_msg)

    def _execute_workflow_step(self, execution: WorkflowExecution, step: WorkflowStep) -> None:
        """Execute individual workflow step."""
        logger.debug(f"Executing step: {step.step_id} in workflow {execution.execution_id}")

        # Check dependencies
        for dep_id in step.dependencies:
            if dep_id not in execution.completed_steps:
                raise WorkflowError(f"Step dependency not met: {dep_id}")

        # Update execution state
        execution.current_step = step.step_id
        step.status = "running"
        step.start_time = time.time()

        # Execute step with retry logic
        success = False
        for attempt in range(step.max_retries + 1):
            try:
                if step.step_type == "vision_detection":
                    result = self._execute_vision_detection_step(step)
                elif step.step_type == "robot_movement":
                    result = self._execute_robot_movement_step(step)
                elif step.step_type == "gripper_control":
                    result = self._execute_gripper_control_step(step)
                elif step.step_type == "conveyor_control":
                    result = self._execute_conveyor_control_step(step)
                elif step.step_type == "sensor_monitoring":
                    result = self._execute_sensor_monitoring_step(step)
                elif step.step_type == "vision_analysis":
                    result = self._execute_vision_analysis_step(step)
                elif step.step_type == "decision_logic":
                    result = self._execute_decision_logic_step(step)
                elif step.step_type == "robot_sorting":
                    result = self._execute_robot_sorting_step(step)
                else:
                    raise WorkflowError(f"Unknown step type: {step.step_type}")

                # Step completed successfully
                step.status = "completed"
                step.completion_time = time.time()
                execution.completed_steps.append(step.step_id)
                execution.step_results[step.step_id] = result

                success = True
                break

            except Exception as e:
                step.retry_count += 1
                step.error_message = str(e)

                if attempt < step.max_retries:
                    logger.warning(f"Step {step.step_id} failed (attempt {attempt + 1}), retrying: {e}")
                    time.sleep(step.retry_delay)
                else:
                    logger.error(f"Step {step.step_id} failed after {step.max_retries + 1} attempts: {e}")
                    step.status = "failed"
                    step.completion_time = time.time()
                    execution.failed_steps.append(step.step_id)
                    execution.error_count += 1
                    execution.last_error = str(e)

                    if not execution.workflow_definition.continue_on_error:
                        raise WorkflowError(f"Step failed: {step.step_id} - {e}")

        if not success and not execution.workflow_definition.continue_on_error:
            raise WorkflowError(f"Step failed after all retries: {step.step_id}")

        # Trigger step completed event
        self._trigger_event('step_completed', {'execution': execution, 'step': step})

    def _execute_vision_detection_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute vision detection step."""
        # Capture image
        frame, frame_info = self.camera_interface.capture_frame()
        if frame is None:
            raise WorkflowError("Failed to capture image")

        # Detect objects
        objects = self.object_detector.detect_objects(frame)

        # Filter objects based on step parameters
        target_shape = step.parameters.get('target_shape')
        target_color = step.parameters.get('target_color')

        filtered_objects = []
        for obj in objects:
            if target_shape and obj.shape != target_shape:
                continue
            if target_color and obj.color != target_color:
                continue
            filtered_objects.append(obj)

        if not filtered_objects:
            raise WorkflowError("No matching objects detected")

        # Select best object (highest confidence)
        best_object = max(filtered_objects, key=lambda x: x.confidence)

        return {
            'detected_object': best_object,
            'all_objects': filtered_objects,
            'frame_info': frame_info
        }

    def _execute_robot_movement_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute robot movement step."""
        movement_type = step.parameters.get('movement_type', 'position')

        if movement_type == 'position':
            # Move to specific position
            target_pos = step.parameters.get('target_position')
            if not target_pos:
                raise WorkflowError("No target position specified")

            success = self.robot_controller.move_to_position(*target_pos)

        elif movement_type == 'home':
            # Move to home position
            success = self.robot_controller.move_to_home()

        elif movement_type == 'object':
            # Move to detected object position
            detected_object = step.parameters.get('detected_object')
            if not detected_object:
                raise WorkflowError("No detected object for movement")

            # Convert pixel coordinates to robot coordinates
            pixel_coords = (detected_object.center_x, detected_object.center_y)
            grasp_height = step.parameters.get('grasp_height', 200.0)

            robot_coords = self.workspace_calibrator.pixel_to_robot(pixel_coords, grasp_height)
            success = self.robot_controller.move_to_position(*robot_coords)

        else:
            raise WorkflowError(f"Unknown movement type: {movement_type}")

        if not success:
            raise WorkflowError("Robot movement failed")

        current_pose = self.robot_controller.get_current_pose()
        return {
            'movement_type': movement_type,
            'success': success,
            'final_position': (current_pose.x, current_pose.y, current_pose.z) if current_pose else None
        }

    def _execute_gripper_control_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute gripper control step."""
        action = step.parameters.get('action', 'close')

        if action == 'close':
            success = self.robot_controller.close_gripper()
        elif action == 'open':
            success = self.robot_controller.open_gripper()
        else:
            raise WorkflowError(f"Unknown gripper action: {action}")

        if not success:
            raise WorkflowError(f"Gripper {action} failed")

        return {
            'action': action,
            'success': success
        }

    def _execute_conveyor_control_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute conveyor control step."""
        action = step.parameters.get('action', 'start')

        if action == 'start':
            speed = step.parameters.get('speed', 50.0)
            direction = step.parameters.get('direction', ConveyorDirection.FORWARD)
            success = self.conveyor_controller.start(speed, direction)

        elif action == 'stop':
            success = self.conveyor_controller.stop()

        elif action == 'change_speed':
            new_speed = step.parameters.get('new_speed', 50.0)
            success = self.conveyor_controller.change_speed(new_speed)

        else:
            raise WorkflowError(f"Unknown conveyor action: {action}")

        if not success:
            raise WorkflowError(f"Conveyor {action} failed")

        return {
            'action': action,
            'success': success,
            'conveyor_status': self.conveyor_controller.get_status()
        }

    def _execute_sensor_monitoring_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute sensor monitoring step."""
        timeout = step.parameters.get('timeout', 10.0)
        sensor_id = step.parameters.get('sensor_id')

        start_time = time.time()
        object_detected = False

        while (time.time() - start_time) < timeout:
            if sensor_id:
                # Monitor specific sensor
                sensor_status = self.sensor_interface.get_sensor_status(sensor_id)
                if sensor_status['last_reading'] and sensor_status['last_reading']['triggered']:
                    object_detected = True
                    break
            else:
                # Monitor any sensor
                if self.sensor_interface.tracked_objects_count > 0:
                    object_detected = True
                    break

            time.sleep(0.1)

        if not object_detected:
            raise WorkflowError("No object detected by sensors within timeout")

        return {
            'object_detected': object_detected,
            'detection_time': time.time() - start_time,
            'tracked_objects': self.sensor_interface.get_tracked_objects()
        }

    def _execute_vision_analysis_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute vision analysis step."""
        # Capture current frame
        frame, frame_info = self.camera_interface.capture_frame()
        if frame is None:
            raise WorkflowError("Failed to capture image for analysis")

        # Detect and analyze objects
        objects = self.object_detector.detect_objects(frame)

        if not objects:
            raise WorkflowError("No objects found for analysis")

        # Analyze object properties
        analysis_results = []
        for obj in objects:
            analysis = {
                'object_id': f"obj_{len(analysis_results)}",
                'shape': obj.shape.value if hasattr(obj.shape, 'value') else str(obj.shape),
                'color': obj.color.value if hasattr(obj.color, 'value') else str(obj.color),
                'confidence': obj.confidence,
                'position': (obj.center_x, obj.center_y),
                'size': obj.area,
                'bounding_box': obj.bounding_box
            }
            analysis_results.append(analysis)

        return {
            'analysis_results': analysis_results,
            'object_count': len(objects),
            'frame_info': frame_info
        }

    def _execute_decision_logic_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute decision logic step."""
        analysis_results = step.parameters.get('analysis_results', [])

        if not analysis_results:
            raise WorkflowError("No analysis results for decision logic")

        # Simple sorting logic based on color and shape
        decisions = []
        for obj_analysis in analysis_results:
            decision = {
                'object_id': obj_analysis['object_id'],
                'action': 'ignore',  # default
                'target_location': None,
                'priority': 1
            }

            # Color-based sorting
            color = obj_analysis.get('color', 'unknown')
            if color == 'red':
                decision['action'] = 'sort_red'
                decision['target_location'] = (400, 100, 200)
                decision['priority'] = 3
            elif color == 'green':
                decision['action'] = 'sort_green'
                decision['target_location'] = (400, -100, 200)
                decision['priority'] = 2
            elif color == 'blue':
                decision['action'] = 'sort_blue'
                decision['target_location'] = (400, 0, 200)
                decision['priority'] = 2

            # Shape-based modifications
            shape = obj_analysis.get('shape', 'unknown')
            if shape == 'circle' and decision['action'] != 'ignore':
                decision['priority'] += 1  # Higher priority for circles

            decisions.append(decision)

        # Sort decisions by priority
        decisions.sort(key=lambda x: x['priority'], reverse=True)

        return {
            'decisions': decisions,
            'primary_decision': decisions[0] if decisions else None
        }

    def _execute_robot_sorting_step(self, step: WorkflowStep) -> Dict[str, Any]:
        """Execute robot sorting step."""
        decisions = step.parameters.get('decisions', [])
        primary_decision = step.parameters.get('primary_decision')

        if not primary_decision or primary_decision['action'] == 'ignore':
            return {'action': 'no_action', 'success': True}

        # Execute sorting action
        target_location = primary_decision['target_location']
        if not target_location:
            raise WorkflowError("No target location for sorting")

        # Move to target location
        success = self.robot_controller.move_to_position(*target_location)
        if not success:
            raise WorkflowError("Failed to move to sorting location")

        return {
            'action': primary_decision['action'],
            'target_location': target_location,
            'success': success,
            'object_id': primary_decision['object_id']
        }

    def _complete_workflow_execution(self, execution: WorkflowExecution) -> None:
        """Complete workflow execution successfully."""
        execution.state = WorkflowState.COMPLETED
        execution.completion_time = time.time()
        execution.actual_cycle_time = execution.completion_time - execution.start_time

        # Calculate efficiency score
        target_time = execution.workflow_definition.target_cycle_time
        if target_time > 0:
            execution.efficiency_score = min(1.0, target_time / execution.actual_cycle_time)

        # Update statistics
        self._statistics['workflows_completed'] += 1

        # Move to history
        self._execution_history.append(execution)
        del self._active_executions[execution.execution_id]

        # Keep only last 100 executions in history
        if len(self._execution_history) > 100:
            self._execution_history.pop(0)

        logger.info(f"Workflow execution completed: {execution.execution_id}")
        self._trigger_event('workflow_completed', execution)

    def _fail_workflow_execution(self, execution: WorkflowExecution, error_message: str) -> None:
        """Fail workflow execution."""
        execution.state = WorkflowState.FAILED
        execution.completion_time = time.time()
        execution.last_error = error_message

        # Update statistics
        self._statistics['workflows_failed'] += 1

        # Move to history
        self._execution_history.append(execution)
        del self._active_executions[execution.execution_id]

        logger.error(f"Workflow execution failed: {execution.execution_id} - {error_message}")
        self._trigger_event('workflow_failed', execution)

    def _update_execution_progress(self, execution: WorkflowExecution) -> None:
        """Update workflow execution progress."""
        total_steps = len(execution.workflow_definition.steps)
        completed_steps = len(execution.completed_steps)

        if total_steps > 0:
            execution.progress = (completed_steps / total_steps) * 100.0

    def _update_performance_metrics(self) -> None:
        """Update performance metrics."""
        if self._execution_history:
            # Calculate average cycle time
            completed_executions = [e for e in self._execution_history if e.state == WorkflowState.COMPLETED]
            if completed_executions:
                cycle_times = [e.actual_cycle_time for e in completed_executions if e.actual_cycle_time]
                if cycle_times:
                    self._statistics['average_cycle_time'] = sum(cycle_times) / len(cycle_times)

                # Calculate average efficiency
                efficiency_scores = [e.efficiency_score for e in completed_executions if e.efficiency_score]
                if efficiency_scores:
                    self._statistics['efficiency_score'] = sum(efficiency_scores) / len(efficiency_scores)

    def _create_object_processing_workflow(self, object_data: Dict[str, Any]) -> Optional[str]:
        """Create workflow for processing detected object."""
        # Create dynamic workflow based on object properties
        workflow_id = f"object_processing_{int(time.time())}"

        workflow_def = WorkflowDefinition(
            workflow_id=workflow_id,
            workflow_type=WorkflowType.MULTI_OBJECT_PROCESSING,
            name=f"Process Object {object_data.get('object_id', 'unknown')}",
            description="Process detected object",
            steps=[
                WorkflowStep(
                    step_id="move_to_object",
                    step_type="robot_movement",
                    description="Move to object position",
                    parameters={
                        'movement_type': 'object',
                        'detected_object': object_data,
                        'grasp_height': 200.0
                    }
                ),
                WorkflowStep(
                    step_id="grasp_object",
                    step_type="gripper_control",
                    description="Grasp the object",
                    parameters={'action': 'close'},
                    dependencies=["move_to_object"]
                ),
                WorkflowStep(
                    step_id="process_object",
                    step_type="robot_movement",
                    description="Move to processing location",
                    parameters={
                        'movement_type': 'position',
                        'target_position': (300, 0, 200)
                    },
                    dependencies=["grasp_object"]
                ),
                WorkflowStep(
                    step_id="release_object",
                    step_type="gripper_control",
                    description="Release the object",
                    parameters={'action': 'open'},
                    dependencies=["process_object"]
                )
            ]
        )

        self._workflow_definitions[workflow_id] = workflow_def
        return workflow_id

    def _trigger_event(self, event_type: str, data: Any = None) -> None:
        """Trigger workflow event and notify callbacks."""
        callbacks = self._event_callbacks.get(event_type, [])
        for callback in callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                logger.error(f"Error in workflow event callback: {e}")

    def add_object_to_queue(self, object_data: Dict[str, Any]) -> None:
        """Add object to processing queue."""
        self._object_queue.put(object_data)
        logger.debug(f"Added object to processing queue: {object_data.get('object_id', 'unknown')}")

    def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get status of workflow execution."""
        if execution_id in self._active_executions:
            execution = self._active_executions[execution_id]
        else:
            # Check history
            execution = next((e for e in self._execution_history if e.execution_id == execution_id), None)

        if not execution:
            return None

        return {
            'execution_id': execution.execution_id,
            'workflow_id': execution.workflow_definition.workflow_id,
            'state': execution.state.value,
            'progress': execution.progress,
            'current_step': execution.current_step,
            'completed_steps': execution.completed_steps,
            'failed_steps': execution.failed_steps,
            'start_time': execution.start_time,
            'completion_time': execution.completion_time,
            'actual_cycle_time': execution.actual_cycle_time,
            'efficiency_score': execution.efficiency_score,
            'error_count': execution.error_count,
            'last_error': execution.last_error
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get workflow executor statistics."""
        return {
            'is_ready': self.is_ready,
            'active_executions': self.active_executions_count,
            'queued_objects': self.queued_objects_count,
            'available_workflows': len(self._workflow_definitions),
            'statistics': self._statistics.copy()
        }

    def add_event_callback(self, event_type: str, callback: Callable) -> None:
        """Add callback for workflow events."""
        if event_type in self._event_callbacks:
            self._event_callbacks[event_type].append(callback)
            logger.info(f"Added callback for {event_type} events")

    def __enter__(self):
        """Context manager entry."""
        self.start_executor()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_executor()
