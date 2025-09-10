"""
Enhanced Tool Interface

This module provides advanced tool control capabilities for the Niryo Ned2 robotic arm,
including force feedback, grasp detection, tool calibration, and manipulation sequences.

Features:
- Advanced gripper control with force feedback
- Grasp detection and confirmation
- Tool calibration and offset management
- Pre-programmed manipulation sequences
- Safety monitoring during tool operations
- Tool performance analytics and logging
"""

import time
import math
from typing import List, Tuple, Optional, Union, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    from pyniryo import PoseObject, JointsPosition
    from pyniryo.api.enums import ToolID
except ImportError:
    # Mock classes for development without hardware
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw
    
    class JointsPosition:
        def __init__(self, joints: List[float]):
            self.joints = joints
    
    class ToolID:
        GRIPPER_1 = "GRIPPER_1"
        GRIPPER_2 = "GRIPPER_2"
        GRIPPER_3 = "GRIPPER_3"

from core.robot_controller import RobotController
from utils.config_manager import ConfigManager
from utils.logger import get_loggerndler import RoboticsError, SafetyError

logger = get_logger(__name__)


class ToolState(Enum):
    """Tool operational states."""
    UNKNOWN = "unknown"
    OPEN = "open"
    CLOSED = "closed"
    GRASPING = "grasping"
    ERROR = "error"


class GraspResult(Enum):
    """Grasp operation results."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    FORCE_EXCEEDED = "force_exceeded"


@dataclass
class ToolParameters:
    """Parameters for tool control operations."""
    max_force: float = 30.0  # Maximum grip force in Newtons
    min_force: float = 5.0   # Minimum grip force in Newtons
    grip_speed: float = 50.0  # Grip speed percentage
    force_threshold: float = 2.0  # Force change threshold for grasp detection
    timeout: float = 5.0  # Operation timeout in seconds
    retry_attempts: int = 3  # Number of retry attempts
    safety_margin: float = 10.0  # Safety margin for force limits


@dataclass
class GraspAttempt:
    """Single grasp attempt record."""
    timestamp: float
    target_force: float
    actual_force: float
    duration: float
    result: GraspResult
    object_detected: bool = False
    force_readings: List[float] = field(default_factory=list)


@dataclass
class ToolStatus:
    """Current tool status information."""
    state: ToolState
    current_force: float = 0.0
    target_force: float = 0.0
    position: float = 0.0  # Tool position (0=open, 1=closed)
    temperature: float = 0.0
    last_calibration: Optional[float] = None
    error_count: int = 0
    total_operations: int = 0


@dataclass
class ManipulationSequence:
    """Pre-programmed manipulation sequence."""
    name: str
    description: str
    steps: List[Dict[str, Any]]
    estimated_duration: float = 0.0
    success_rate: float = 0.0
    usage_count: int = 0


class ToolController:
    """
    Enhanced tool controller providing advanced gripper control with
    force feedback, grasp detection, and manipulation sequences.
    """
    
    def __init__(self, robot_controller: RobotController, config_manager=None):
        """
        Initialize tool controller.
        
        Args:
            robot_controller: Base robot controller instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Tool parameters and status
        self.default_params = ToolParameters()
        self._tool_status = ToolStatus(state=ToolState.UNKNOWN)
        self._grasp_history: List[GraspAttempt] = []
        self._manipulation_sequences: Dict[str, ManipulationSequence] = {}
        
        # Tool calibration data
        self._tool_offset = PoseObject(0, 0, 0, 0, 0, 0)
        self._force_calibration = {'zero_point': 0.0, 'scale_factor': 1.0}
        
        # Initialize built-in manipulation sequences
        self._initialize_manipulation_sequences()
        
        logger.info("Enhanced tool controller initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if tool controller is ready."""
        return self.robot_controller.is_ready
    
    @property
    def tool_status(self) -> ToolStatus:
        """Get current tool status."""
        return self._tool_status
    
    def set_tool_parameters(self, params: ToolParameters) -> None:
        """
        Set default tool parameters.
        
        Args:
            params: Tool parameters to set as default
        """
        self.default_params = params
        logger.info(f"Tool parameters updated: max_force={params.max_force}N, "
                   f"grip_speed={params.grip_speed}%")
    def calibrate_tool(self, force_samples: int = 10) -> bool:
        """
        Calibrate tool force sensors and position offsets.
        
        Args:
            force_samples: Number of force samples for calibration
            
        Returns:
            True if calibration successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for tool calibration")
        
        logger.info("Starting tool calibration...")
        
        try:
                # Calibrate force sensor (zero point)
                force_readings = []
                for _ in range(force_samples):
                    force = self._read_tool_force()
                    force_readings.append(force)
                    time.sleep(0.1)
                
                zero_point = sum(force_readings) / len(force_readings)
                self._force_calibration['zero_point'] = zero_point
                
                # Test tool movement for position calibration
                self._calibrate_tool_position()
                
                # Update tool in robot controller
                self.robot_controller._robot.update_tool()
                
                self._tool_status.last_calibration = time.time()
                self._tool_status.state = ToolState.OPEN
                
                logger.info(f"Tool calibration completed: zero_point={zero_point:.2f}N")
                return True
        
        except Exception as e:
            error_msg = f"Tool calibration failed: {e}"
            logger.error(error_msg)
            self._tool_status.state = ToolState.ERROR
            return False
    def grasp_with_feedback(self, 
                           target_force: Optional[float] = None,
                           params: Optional[ToolParameters] = None) -> GraspAttempt:
        """
        Perform grasp operation with force feedback and detection.
        
        Args:
            target_force: Target grip force (uses default if None)
            params: Tool parameters (uses default if None)
            
        Returns:
            GraspAttempt with operation details
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for grasp operation")
        
        params = params or self.default_params
        target_force = target_force or params.max_force
        
        # Validate force limits
        if not (params.min_force <= target_force <= params.max_force):
            raise SafetyError(f"Target force {target_force}N outside safe limits "
                            f"({params.min_force}-{params.max_force}N)")
        
        start_time = time.time()
        force_readings = []
        
        logger.info(f"Starting grasp operation with target force {target_force}N")
        
        try:
            # Initialize grasp attempt
            attempt = GraspAttempt(
                timestamp=start_time,
                target_force=target_force,
                actual_force=0.0,
                duration=0.0,
                result=GraspResult.FAILED
            )
            
            # Monitor initial force
            initial_force = self._read_tool_force()
            force_readings.append(initial_force)
            
            # Start grasp operation
            self._tool_status.state = ToolState.GRASPING
            self._tool_status.target_force = target_force
            
            # Perform gradual grasp with force monitoring
            for step in range(10):  # 10 steps for gradual grasp
                step_force = target_force * (step + 1) / 10
                
                # Execute grasp step
                self._execute_grasp_step(step_force, params)
                
                # Monitor force feedback
                current_force = self._read_tool_force()
                force_readings.append(current_force)
                
                # Check for object detection
                force_change = current_force - initial_force
                if force_change > params.force_threshold:
                    attempt.object_detected = True
                    logger.debug(f"Object detected: force change {force_change:.2f}N")
                
                # Check for force limit exceeded
                if current_force > target_force + params.safety_margin:
                    attempt.result = GraspResult.FORCE_EXCEEDED
                    logger.warning(f"Force limit exceeded: {current_force:.2f}N")
                    break
                
                # Check timeout
                if time.time() - start_time > params.timeout:
                    attempt.result = GraspResult.TIMEOUT
                    logger.warning("Grasp operation timeout")
                    break
                
                time.sleep(0.1)  # Small delay between steps
            
            # Finalize grasp attempt
            final_force = self._read_tool_force()
            attempt.actual_force = final_force
            attempt.duration = time.time() - start_time
            attempt.force_readings = force_readings
            
            # Determine grasp result
            if attempt.result == GraspResult.FAILED:  # No error occurred
                if attempt.object_detected and abs(final_force - target_force) < params.safety_margin:
                    attempt.result = GraspResult.SUCCESS
                    self._tool_status.state = ToolState.CLOSED
                elif attempt.object_detected:
                    attempt.result = GraspResult.PARTIAL
                    self._tool_status.state = ToolState.GRASPING
                else:
                    attempt.result = GraspResult.FAILED
                    self._tool_status.state = ToolState.OPEN
            
            # Update tool status
            self._tool_status.current_force = final_force
            self._tool_status.total_operations += 1
            
            # Record attempt
            self._grasp_history.append(attempt)
            
            logger.info(f"Grasp operation completed: {attempt.result.value}, "
                       f"force={final_force:.2f}N, duration={attempt.duration:.2f}s")
            
            return attempt
        
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Grasp operation failed: {e}"
            logger.error(error_msg)
            
            self._tool_status.state = ToolState.ERROR
            self._tool_status.error_count += 1
            
            # Create error attempt record
            error_attempt = GraspAttempt(
                timestamp=start_time,
                target_force=target_force,
                actual_force=0.0,
                duration=duration,
                result=GraspResult.FAILED,
                force_readings=force_readings
            )
            
            self._grasp_history.append(error_attempt)
            return error_attempt
    def release_with_feedback(self, params: Optional[ToolParameters] = None) -> bool:
        """
        Release grasp with feedback monitoring.
        
        Args:
            params: Tool parameters (uses default if None)
            
        Returns:
            True if release successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for release operation")
        
        params = params or self.default_params
        
        logger.info("Starting release operation")
        
        try:
            # Monitor initial force
            initial_force = self._read_tool_force()
            
            # Execute release
            self.robot_controller.release()
            
            # Wait for force to stabilize
            time.sleep(0.5)
            
            # Check final force
            final_force = self._read_tool_force()
            force_drop = initial_force - final_force
            
            # Determine success based on force drop
            success = force_drop > self.default_params.force_threshold
            
            if success:
                self._tool_status.state = ToolState.OPEN
                self._tool_status.current_force = final_force
                self._tool_status.target_force = 0.0
                logger.info(f"Release successful: force dropped {force_drop:.2f}N")
            else:
                logger.warning(f"Release may have failed: force drop only {force_drop:.2f}N")
            
            self._tool_status.total_operations += 1
            return success
        
        except Exception as e:
            error_msg = f"Release operation failed: {e}"
            logger.error(error_msg)
            self._tool_status.state = ToolState.ERROR
            self._tool_status.error_count += 1
            return False

    def execute_manipulation_sequence(self, sequence_name: str,
                                    parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Execute pre-programmed manipulation sequence.

        Args:
            sequence_name: Name of sequence to execute
            parameters: Optional parameters for sequence customization

        Returns:
            True if sequence executed successfully, False otherwise
        """
        if sequence_name not in self._manipulation_sequences:
            raise RoboticsError(f"Unknown manipulation sequence: {sequence_name}")

        sequence = self._manipulation_sequences[sequence_name]
        parameters = parameters or {}

        logger.info(f"Executing manipulation sequence: {sequence_name}")

        try:
            start_time = time.time()

            for i, step in enumerate(sequence.steps):
                logger.debug(f"Executing sequence step {i+1}/{len(sequence.steps)}: {step['action']}")

                # Execute step based on action type
                if step['action'] == 'grasp':
                    force = parameters.get('grasp_force', step.get('force', self.default_params.max_force))
                    attempt = self.grasp_with_feedback(force)
                    if attempt.result not in [GraspResult.SUCCESS, GraspResult.PARTIAL]:
                        logger.error(f"Grasp failed in sequence step {i+1}")
                        return False

                elif step['action'] == 'release':
                    if not self.release_with_feedback():
                        logger.error(f"Release failed in sequence step {i+1}")
                        return False

                elif step['action'] == 'move':
                    pose = step.get('pose')
                    if pose:
                        if not self.robot_controller.move_to_pose(pose):
                            logger.error(f"Movement failed in sequence step {i+1}")
                            return False

                elif step['action'] == 'wait':
                    duration = step.get('duration', 1.0)
                    time.sleep(duration)

                elif step['action'] == 'custom':
                    # Execute custom function if provided
                    custom_func = step.get('function')
                    if custom_func and callable(custom_func):
                        if not custom_func(parameters):
                            logger.error(f"Custom action failed in sequence step {i+1}")
                            return False

                else:
                    logger.warning(f"Unknown action in sequence step {i+1}: {step['action']}")

            # Update sequence statistics
            execution_time = time.time() - start_time
            sequence.usage_count += 1

            # Update success rate (simple moving average)
            if sequence.usage_count == 1:
                sequence.success_rate = 1.0
            else:
                sequence.success_rate = (sequence.success_rate * (sequence.usage_count - 1) + 1.0) / sequence.usage_count

            logger.info(f"Manipulation sequence '{sequence_name}' completed successfully in {execution_time:.2f}s")
            return True

        except Exception as e:
            error_msg = f"Manipulation sequence '{sequence_name}' failed: {e}"
            logger.error(error_msg)

            # Update failure statistics
            if sequence.usage_count > 0:
                sequence.success_rate = (sequence.success_rate * sequence.usage_count) / (sequence.usage_count + 1)
            sequence.usage_count += 1

            return False

    def add_manipulation_sequence(self, sequence: ManipulationSequence) -> None:
        """
        Add custom manipulation sequence.

        Args:
            sequence: Manipulation sequence to add
        """
        self._manipulation_sequences[sequence.name] = sequence
        logger.info(f"Added manipulation sequence: {sequence.name}")

    def get_manipulation_sequences(self) -> Dict[str, ManipulationSequence]:
        """
        Get all available manipulation sequences.

        Returns:
            Dictionary of manipulation sequences
        """
        return self._manipulation_sequences.copy()

    def _initialize_manipulation_sequences(self) -> None:
        """Initialize built-in manipulation sequences."""

        # Pick and place sequence
        pick_and_place = ManipulationSequence(
            name="pick_and_place",
            description="Basic pick and place operation",
            steps=[
                {'action': 'move', 'description': 'Move to approach position'},
                {'action': 'move', 'description': 'Move to grasp position'},
                {'action': 'grasp', 'force': 20.0, 'description': 'Grasp object'},
                {'action': 'move', 'description': 'Lift object'},
                {'action': 'move', 'description': 'Move to place position'},
                {'action': 'release', 'description': 'Release object'},
                {'action': 'move', 'description': 'Move to safe position'}
            ],
            estimated_duration=15.0
        )

        # Gentle grasp sequence for delicate objects
        gentle_grasp = ManipulationSequence(
            name="gentle_grasp",
            description="Gentle grasp for delicate objects",
            steps=[
                {'action': 'move', 'description': 'Move to approach position'},
                {'action': 'grasp', 'force': 8.0, 'description': 'Gentle grasp'},
                {'action': 'wait', 'duration': 1.0, 'description': 'Stabilize grasp'}
            ],
            estimated_duration=5.0
        )

        # Firm grasp sequence for heavy objects
        firm_grasp = ManipulationSequence(
            name="firm_grasp",
            description="Firm grasp for heavy objects",
            steps=[
                {'action': 'move', 'description': 'Move to approach position'},
                {'action': 'grasp', 'force': 35.0, 'description': 'Firm grasp'},
                {'action': 'wait', 'duration': 0.5, 'description': 'Confirm grasp'}
            ],
            estimated_duration=4.0
        )

        # Test sequence for calibration
        test_sequence = ManipulationSequence(
            name="test_grasp_release",
            description="Test grasp and release cycle",
            steps=[
                {'action': 'grasp', 'force': 15.0, 'description': 'Test grasp'},
                {'action': 'wait', 'duration': 2.0, 'description': 'Hold position'},
                {'action': 'release', 'description': 'Test release'},
                {'action': 'wait', 'duration': 1.0, 'description': 'Stabilize'}
            ],
            estimated_duration=6.0
        )

        # Add sequences to collection
        for sequence in [pick_and_place, gentle_grasp, firm_grasp, test_sequence]:
            self._manipulation_sequences[sequence.name] = sequence

        logger.info(f"Initialized {len(self._manipulation_sequences)} built-in manipulation sequences")

    def _read_tool_force(self) -> float:
        """
        Read current tool force (simulated for now).

        Returns:
            Current force reading in Newtons
        """
        # In a real implementation, this would read from force sensors
        # For now, return simulated force based on tool state
        if self._tool_status.state == ToolState.CLOSED:
            return self._tool_status.target_force + (time.time() % 1.0 - 0.5) * 2.0  # Add noise
        elif self._tool_status.state == ToolState.GRASPING:
            return self._tool_status.target_force * 0.8 + (time.time() % 1.0 - 0.5) * 1.0
        else:
            return self._force_calibration['zero_point'] + (time.time() % 1.0 - 0.5) * 0.5

    def _calibrate_tool_position(self) -> None:
        """Calibrate tool position offsets."""
        # In a real implementation, this would perform tool position calibration
        # For now, just set default offsets
        self._tool_offset = PoseObject(0, 0, 100, 0, 0, 0)  # 100mm Z offset for gripper
        logger.debug("Tool position calibration completed")

    def _execute_grasp_step(self, force: float, params: ToolParameters) -> None:
        """
        Execute single grasp step with specified force.

        Args:
            force: Target force for this step
            params: Tool parameters
        """
        # In a real implementation, this would control gripper with specific force
        # For now, use basic grasp command
        self.robot_controller.grasp()
        self._tool_status.current_force = force

    def get_grasp_history(self) -> List[GraspAttempt]:
        """
        Get grasp operation history.

        Returns:
            List of grasp attempts
        """
        return self._grasp_history.copy()

    def clear_grasp_history(self) -> None:
        """Clear grasp operation history."""
        self._grasp_history.clear()
        logger.info("Grasp history cleared")

    def get_tool_analytics(self) -> Dict[str, Any]:
        """
        Get tool performance analytics.

        Returns:
            Dictionary with tool analytics data
        """
        if not self._grasp_history:
            return {'total_operations': 0, 'success_rate': 0.0}

        successful_grasps = sum(1 for attempt in self._grasp_history
                               if attempt.result == GraspResult.SUCCESS)

        total_attempts = len(self._grasp_history)
        success_rate = successful_grasps / total_attempts if total_attempts > 0 else 0.0

        avg_force = sum(attempt.actual_force for attempt in self._grasp_history) / total_attempts
        avg_duration = sum(attempt.duration for attempt in self._grasp_history) / total_attempts

        return {
            'total_operations': self._tool_status.total_operations,
            'total_grasp_attempts': total_attempts,
            'successful_grasps': successful_grasps,
            'success_rate': success_rate,
            'average_force': avg_force,
            'average_duration': avg_duration,
            'error_count': self._tool_status.error_count,
            'last_calibration': self._tool_status.last_calibration,
            'current_state': self._tool_status.state.value
        }

    def set_tool_offset(self, offset: PoseObject) -> None:
        """
        Set tool coordinate offset.

        Args:
            offset: Tool offset pose
        """
        self._tool_offset = offset
        logger.info(f"Tool offset updated: {offset.x}, {offset.y}, {offset.z}")

    def get_tool_offset(self) -> PoseObject:
        """
        Get current tool offset.

        Returns:
            Tool offset pose
        """
        return self._tool_offset
