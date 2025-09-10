"""
Advanced Movement Controller

This module provides advanced movement control capabilities for the Niryo Ned2 robotic arm,
extending the basic robot controller with precise Cartesian and joint space control,
velocity profiling, and smooth motion generation.

Features:
- Precise Cartesian space control with orientation
- Advanced joint space control with interpolation
- Velocity profiling and acceleration control
- Position interpolation between waypoints
- Enhanced movement validation and safety
- Smooth motion generation with configurable curves
"""

import time
import math
import numpy as np
from typing import List, Tuple, Optional, Union, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from pyniryo import PoseObject, JointsPosition
except ImportError:
    # Mock classes for development without hardware
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw
    
    class JointsPosition:
        def __init__(self, joints: List[float]):
            self.joints = joints

from core.robot_controller import RobotController, RobotState
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError, SafetyError

logger = get_logger(__name__)


class MovementType(Enum):
    """Types of robot movements."""
    LINEAR = "linear"
    JOINT = "joint"
    CIRCULAR = "circular"
    SPLINE = "spline"


class VelocityProfile(Enum):
    """Velocity profile types for smooth motion."""
    TRAPEZOIDAL = "trapezoidal"
    S_CURVE = "s_curve"
    SINUSOIDAL = "sinusoidal"
    CUSTOM = "custom"


@dataclass
class MovementParameters:
    """Parameters for advanced movement control."""
    max_velocity: float = 50.0  # Percentage of maximum robot velocity
    acceleration: float = 30.0  # Acceleration percentage
    deceleration: float = 30.0  # Deceleration percentage
    jerk_limit: float = 100.0  # Jerk limit for smooth motion
    velocity_profile: VelocityProfile = VelocityProfile.TRAPEZOIDAL
    interpolation_steps: int = 50  # Steps for path interpolation
    pause_time: float = 0.1  # Pause between waypoints
    validate_path: bool = True  # Enable path validation


@dataclass
class Waypoint:
    """Waypoint definition for trajectory planning."""
    pose: Union[PoseObject, JointsPosition]
    movement_type: MovementType = MovementType.LINEAR
    velocity: Optional[float] = None  # Override default velocity
    pause_duration: Optional[float] = None  # Pause at waypoint
    tool_action: Optional[str] = None  # Tool action at waypoint ("grasp", "release")


@dataclass
class MovementResult:
    """Result of movement execution."""
    success: bool
    execution_time: float
    actual_path: List[Union[PoseObject, JointsPosition]]
    max_deviation: float
    average_velocity: float
    error_message: Optional[str] = None


class AdvancedMovementController:
    """
    Advanced movement controller providing precise robot control with
    velocity profiling, path interpolation, and smooth motion generation.
    """
    
    def __init__(self, robot_controller: RobotController, config_manager=None):
        """
        Initialize advanced movement controller.
        
        Args:
            robot_controller: Base robot controller instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('robot', {})
        
        # Movement parameters
        self.default_params = MovementParameters()
        self._current_position: Optional[Union[PoseObject, JointsPosition]] = None
        self._movement_history: List[Dict[str, Any]] = []
        
        # Workspace boundaries (inherited from robot controller)
        self._workspace_boundaries = robot_controller._workspace_boundaries
        
        logger.info("Advanced movement controller initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if robot is ready for advanced movements."""
        return self.robot_controller.is_ready
    
    @property
    def current_position(self) -> Optional[Union[PoseObject, JointsPosition]]:
        """Get current robot position."""
        return self.robot_controller.get_position()
    
    @property
    def current_joints(self) -> Optional[List[float]]:
        """Get current joint positions."""
        return self.robot_controller.get_joints()
    
    def set_movement_parameters(self, params: MovementParameters) -> None:
        """
        Set default movement parameters.
        
        Args:
            params: Movement parameters to set as default
        """
        self.default_params = params
        logger.info(f"Movement parameters updated: velocity={params.max_velocity}%, "
                   f"profile={params.velocity_profile.value}")
    def move_cartesian(self, 
                      target: PoseObject, 
                      params: Optional[MovementParameters] = None) -> MovementResult:
        """
        Move robot to target Cartesian position with advanced control.
        
        Args:
            target: Target Cartesian pose
            params: Movement parameters (uses default if None)
            
        Returns:
            MovementResult with execution details
            
        Raises:
            RoboticsError: If movement fails
            SafetyError: If target position is unsafe
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for movement")
        
        params = params or self.default_params
        start_time = time.time()
        
        try:
            # Validate target position
            if params.validate_path and not self._validate_cartesian_position(target):
                raise SafetyError("Target Cartesian position is outside workspace boundaries")
            
            # Get current position for path planning
            current_pose = self.current_position
            if not current_pose:
                raise RoboticsError("Cannot get current robot position")
            
            # Generate interpolated path
            path = self._generate_cartesian_path(current_pose, target, params)
            
            # Execute movement with velocity profiling
            actual_path = self._execute_cartesian_path(path, params)
            
            execution_time = time.time() - start_time
            max_deviation = self._calculate_path_deviation(path, actual_path)
            avg_velocity = self._calculate_average_velocity(actual_path, execution_time)
            
            # Record movement in history
            self._record_movement({
                'type': 'cartesian',
                'target': target,
                'execution_time': execution_time,
                'max_deviation': max_deviation,
                'success': True
            })
            
            return MovementResult(
                success=True,
                execution_time=execution_time,
                actual_path=actual_path,
                max_deviation=max_deviation,
                average_velocity=avg_velocity
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Cartesian movement failed: {e}"
            logger.error(error_msg)
            
            self._record_movement({
                'type': 'cartesian',
                'target': target,
                'execution_time': execution_time,
                'error': str(e),
                'success': False
            })
            
            return MovementResult(
                success=False,
                execution_time=execution_time,
                actual_path=[],
                max_deviation=0.0,
                average_velocity=0.0,
                error_message=error_msg
            )
    def move_joints(self, 
                   target: Union[List[float], JointsPosition], 
                   params: Optional[MovementParameters] = None) -> MovementResult:
        """
        Move robot to target joint positions with advanced control.
        
        Args:
            target: Target joint positions
            params: Movement parameters (uses default if None)
            
        Returns:
            MovementResult with execution details
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for movement")
        
        params = params or self.default_params
        start_time = time.time()
        
        try:
            # Convert to JointsPosition if needed
            if isinstance(target, list):
                target_joints = JointsPosition(target)
            else:
                target_joints = target
            
            # Validate joint positions
            if params.validate_path and not self._validate_joint_positions(target_joints.joints):
                raise SafetyError("Target joint positions are outside safe limits")
            
            # Get current joint positions
            current_joints = self.current_joints
            if not current_joints:
                raise RoboticsError("Cannot get current joint positions")
            
            # Generate interpolated joint path
            path = self._generate_joint_path(current_joints, target_joints.joints, params)
            
            # Execute movement with velocity profiling
            actual_path = self._execute_joint_path(path, params)
            
            execution_time = time.time() - start_time
            max_deviation = self._calculate_joint_deviation(path, actual_path)
            avg_velocity = self._calculate_average_velocity(actual_path, execution_time)
            
            # Record movement in history
            self._record_movement({
                'type': 'joint',
                'target': target_joints.joints,
                'execution_time': execution_time,
                'max_deviation': max_deviation,
                'success': True
            })
            
            return MovementResult(
                success=True,
                execution_time=execution_time,
                actual_path=actual_path,
                max_deviation=max_deviation,
                average_velocity=avg_velocity
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Joint movement failed: {e}"
            logger.error(error_msg)
            
            return MovementResult(
                success=False,
                execution_time=execution_time,
                actual_path=[],
                max_deviation=0.0,
                average_velocity=0.0,
                error_message=error_msg
            )
    
    def _validate_cartesian_position(self, pose: PoseObject) -> bool:
        """
        Validate Cartesian position against workspace boundaries.
        
        Args:
            pose: Pose to validate
            
        Returns:
            True if position is valid, False otherwise
        """
        boundaries = self._workspace_boundaries
        
        # Check position boundaries
        if not (boundaries['x'][0] <= pose.x <= boundaries['x'][1]):
            return False
        if not (boundaries['y'][0] <= pose.y <= boundaries['y'][1]):
            return False
        if not (boundaries['z'][0] <= pose.z <= boundaries['z'][1]):
            return False
        
        # Check orientation boundaries
        if not (boundaries['roll'][0] <= pose.roll <= boundaries['roll'][1]):
            return False
        if not (boundaries['pitch'][0] <= pose.pitch <= boundaries['pitch'][1]):
            return False
        if not (boundaries['yaw'][0] <= pose.yaw <= boundaries['yaw'][1]):
            return False
        
        return True
    
    def _validate_joint_positions(self, joints: List[float]) -> bool:
        """
        Validate joint positions against safe limits.
        
        Args:
            joints: Joint positions to validate
            
        Returns:
            True if positions are valid, False otherwise
        """
        # Niryo Ned2 joint limits (approximate)
        joint_limits = [
            (-3.14, 3.14),  # Joint 1
            (-1.57, 1.57),  # Joint 2
            (-1.57, 1.57),  # Joint 3
            (-3.14, 3.14),  # Joint 4
            (-1.57, 1.57),  # Joint 5
            (-3.14, 3.14),  # Joint 6
        ]
        
        if len(joints) != len(joint_limits):
            return False
        
        for joint_val, (min_val, max_val) in zip(joints, joint_limits):
            if not (min_val <= joint_val <= max_val):
                return False
        
        return True

    def _generate_cartesian_path(self,
                                start: PoseObject,
                                end: PoseObject,
                                params: MovementParameters) -> List[PoseObject]:
        """
        Generate interpolated Cartesian path between start and end poses.

        Args:
            start: Starting pose
            end: Target pose
            params: Movement parameters

        Returns:
            List of interpolated poses
        """
        path = []
        steps = params.interpolation_steps

        for i in range(steps + 1):
            t = i / steps

            # Apply velocity profile
            t_profile = self._apply_velocity_profile(t, params.velocity_profile)

            # Linear interpolation for position
            x = start.x + (end.x - start.x) * t_profile
            y = start.y + (end.y - start.y) * t_profile
            z = start.z + (end.z - start.z) * t_profile

            # Spherical interpolation for orientation
            roll = self._interpolate_angle(start.roll, end.roll, t_profile)
            pitch = self._interpolate_angle(start.pitch, end.pitch, t_profile)
            yaw = self._interpolate_angle(start.yaw, end.yaw, t_profile)

            path.append(PoseObject(x, y, z, roll, pitch, yaw))

        return path

    def _generate_joint_path(self,
                           start: List[float],
                           end: List[float],
                           params: MovementParameters) -> List[List[float]]:
        """
        Generate interpolated joint path between start and end positions.

        Args:
            start: Starting joint positions
            end: Target joint positions
            params: Movement parameters

        Returns:
            List of interpolated joint positions
        """
        path = []
        steps = params.interpolation_steps

        for i in range(steps + 1):
            t = i / steps

            # Apply velocity profile
            t_profile = self._apply_velocity_profile(t, params.velocity_profile)

            # Linear interpolation for each joint
            joints = []
            for start_joint, end_joint in zip(start, end):
                joint_val = start_joint + (end_joint - start_joint) * t_profile
                joints.append(joint_val)

            path.append(joints)

        return path

    def _apply_velocity_profile(self, t: float, profile: VelocityProfile) -> float:
        """
        Apply velocity profile to interpolation parameter.

        Args:
            t: Interpolation parameter (0 to 1)
            profile: Velocity profile type

        Returns:
            Modified interpolation parameter
        """
        if profile == VelocityProfile.TRAPEZOIDAL:
            # Simple trapezoidal profile
            accel_time = 0.3
            decel_time = 0.3

            if t < accel_time:
                return 0.5 * (t / accel_time) ** 2
            elif t > (1 - decel_time):
                t_decel = (t - (1 - decel_time)) / decel_time
                return 1 - 0.5 * (1 - t_decel) ** 2
            else:
                return t

        elif profile == VelocityProfile.S_CURVE:
            # S-curve profile using sigmoid function
            return 1 / (1 + math.exp(-10 * (t - 0.5)))

        elif profile == VelocityProfile.SINUSOIDAL:
            # Sinusoidal profile
            return 0.5 * (1 - math.cos(math.pi * t))

        else:  # LINEAR or CUSTOM
            return t

    def _interpolate_angle(self, start_angle: float, end_angle: float, t: float) -> float:
        """
        Interpolate between two angles taking into account wrap-around.

        Args:
            start_angle: Starting angle in radians
            end_angle: Ending angle in radians
            t: Interpolation parameter (0 to 1)

        Returns:
            Interpolated angle
        """
        # Normalize angles to [-pi, pi]
        start_norm = math.atan2(math.sin(start_angle), math.cos(start_angle))
        end_norm = math.atan2(math.sin(end_angle), math.cos(end_angle))

        # Calculate shortest angular distance
        diff = end_norm - start_norm
        if diff > math.pi:
            diff -= 2 * math.pi
        elif diff < -math.pi:
            diff += 2 * math.pi

        return start_norm + diff * t

    def _execute_cartesian_path(self,
                               path: List[PoseObject],
                               params: MovementParameters) -> List[PoseObject]:
        """
        Execute Cartesian path with velocity control.

        Args:
            path: Path to execute
            params: Movement parameters

        Returns:
            Actual executed path
        """
        actual_path = []

        # Set robot velocity
        original_velocity = self.config.max_velocity_percent
        self.robot_controller._robot.set_arm_max_velocity(params.max_velocity)

        try:
            for i, pose in enumerate(path):
                # Execute movement to waypoint
                success = self.robot_controller.move_to_pose(pose, validate=False)

                if not success:
                    logger.warning(f"Failed to reach waypoint {i}")
                    break

                # Record actual position
                actual_pose = self.robot_controller.get_position()
                if actual_pose:
                    actual_path.append(actual_pose)

                # Pause between waypoints
                if params.pause_time > 0 and i < len(path) - 1:
                    time.sleep(params.pause_time)

        finally:
            # Restore original velocity
            self.robot_controller._robot.set_arm_max_velocity(original_velocity)

        return actual_path

    def _execute_joint_path(self,
                           path: List[List[float]],
                           params: MovementParameters) -> List[List[float]]:
        """
        Execute joint path with velocity control.

        Args:
            path: Joint path to execute
            params: Movement parameters

        Returns:
            Actual executed joint positions
        """
        actual_path = []

        # Set robot velocity
        original_velocity = self.config.max_velocity_percent
        self.robot_controller._robot.set_arm_max_velocity(params.max_velocity)

        try:
            for i, joints in enumerate(path):
                # Execute movement to joint position
                success = self.robot_controller.move_to_joints(joints, validate=False)

                if not success:
                    logger.warning(f"Failed to reach joint waypoint {i}")
                    break

                # Record actual joint positions
                actual_joints = self.robot_controller.get_joints()
                if actual_joints:
                    actual_path.append(actual_joints)

                # Pause between waypoints
                if params.pause_time > 0 and i < len(path) - 1:
                    time.sleep(params.pause_time)

        finally:
            # Restore original velocity
            self.robot_controller._robot.set_arm_max_velocity(original_velocity)

        return actual_path

    def _calculate_path_deviation(self,
                                 planned_path: List[Union[PoseObject, List[float]]],
                                 actual_path: List[Union[PoseObject, List[float]]]) -> float:
        """
        Calculate maximum deviation between planned and actual path.

        Args:
            planned_path: Planned path
            actual_path: Actual executed path

        Returns:
            Maximum deviation in mm or radians
        """
        if not planned_path or not actual_path:
            return 0.0

        max_deviation = 0.0
        min_length = min(len(planned_path), len(actual_path))

        for i in range(min_length):
            planned = planned_path[i]
            actual = actual_path[i]

            if isinstance(planned, PoseObject) and isinstance(actual, PoseObject):
                # Cartesian deviation
                pos_dev = math.sqrt(
                    (planned.x - actual.x) ** 2 +
                    (planned.y - actual.y) ** 2 +
                    (planned.z - actual.z) ** 2
                )
                max_deviation = max(max_deviation, pos_dev)

            elif isinstance(planned, list) and isinstance(actual, list):
                # Joint deviation
                joint_dev = max(abs(p - a) for p, a in zip(planned, actual))
                max_deviation = max(max_deviation, joint_dev)

        return max_deviation

    def _calculate_average_velocity(self,
                                   path: List[Union[PoseObject, List[float]]],
                                   execution_time: float) -> float:
        """
        Calculate average velocity during path execution.

        Args:
            path: Executed path
            execution_time: Total execution time

        Returns:
            Average velocity in mm/s or rad/s
        """
        if len(path) < 2 or execution_time <= 0:
            return 0.0

        total_distance = 0.0

        for i in range(1, len(path)):
            prev = path[i-1]
            curr = path[i]

            if isinstance(prev, PoseObject) and isinstance(curr, PoseObject):
                # Cartesian distance
                distance = math.sqrt(
                    (curr.x - prev.x) ** 2 +
                    (curr.y - prev.y) ** 2 +
                    (curr.z - prev.z) ** 2
                )
            elif isinstance(prev, list) and isinstance(curr, list):
                # Joint distance (sum of absolute joint movements)
                distance = sum(abs(c - p) for p, c in zip(prev, curr))
            else:
                continue

            total_distance += distance

        return total_distance / execution_time

    def _record_movement(self, movement_data: Dict[str, Any]) -> None:
        """
        Record movement in history for analysis.

        Args:
            movement_data: Movement execution data
        """
        movement_data['timestamp'] = time.time()
        self._movement_history.append(movement_data)

        # Keep only last 100 movements
        if len(self._movement_history) > 100:
            self._movement_history.pop(0)

    def get_movement_history(self) -> List[Dict[str, Any]]:
        """
        Get movement execution history.

        Returns:
            List of movement execution records
        """
        return self._movement_history.copy()

    def clear_movement_history(self) -> None:
        """Clear movement execution history."""
        self._movement_history.clear()
        logger.info("Movement history cleared")
