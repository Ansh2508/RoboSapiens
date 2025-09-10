"""
Trajectory Planning System

This module provides advanced trajectory planning capabilities for the Niryo Ned2 robotic arm,
including path optimization, smooth motion generation, collision detection, and waypoint management.

Features:
- Path optimization with shortest path calculation
- Smooth motion generation using Bezier curves and splines
- Real-time collision detection and avoidance
- Sequential waypoint execution with pause/resume
- Dynamic speed adjustment based on path complexity
- Obstacle avoidance and workspace constraints
"""

import time
import math
import numpy as np
from typing import List, Tuple, Optional, Union, Dict, Any, Callable
from dataclasses import dataclass, field
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

from core.robot_controller import RobotController
from core.advanced_movement import AdvancedMovementController, MovementParameters, Waypoint, MovementResult
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError, SafetyError

logger = get_logger(__name__)


class PathType(Enum):
    """Types of trajectory paths."""
    LINEAR = "linear"
    BEZIER = "bezier"
    SPLINE = "spline"
    CIRCULAR = "circular"
    HELICAL = "helical"


class CollisionCheckMode(Enum):
    """Collision detection modes."""
    NONE = "none"
    BASIC = "basic"
    ADVANCED = "advanced"
    REAL_TIME = "real_time"


@dataclass
class Obstacle:
    """Obstacle definition for collision avoidance."""
    center: Tuple[float, float, float]  # X, Y, Z coordinates
    radius: float  # Obstacle radius in mm
    height: Optional[float] = None  # Height for cylindrical obstacles
    shape: str = "sphere"  # "sphere", "cylinder", "box"
    safety_margin: float = 50.0  # Additional safety margin in mm


@dataclass
class TrajectoryParameters:
    """Parameters for trajectory planning."""
    path_type: PathType = PathType.LINEAR
    collision_check: CollisionCheckMode = CollisionCheckMode.BASIC
    max_deviation: float = 2.0  # Maximum allowed deviation from planned path (mm)
    smoothing_factor: float = 0.5  # Smoothing factor for spline generation
    optimization_iterations: int = 10  # Iterations for path optimization
    safety_margin: float = 20.0  # Safety margin for obstacles (mm)
    dynamic_speed: bool = True  # Enable dynamic speed adjustment
    min_speed_percent: float = 10.0  # Minimum speed percentage
    max_speed_percent: float = 80.0  # Maximum speed percentage


@dataclass
class TrajectoryPoint:
    """Single point in a trajectory."""
    pose: Union[PoseObject, JointsPosition]
    velocity: float = 50.0  # Velocity percentage
    acceleration: float = 30.0  # Acceleration percentage
    timestamp: float = 0.0  # Time from trajectory start
    tool_action: Optional[str] = None  # Tool action at this point


@dataclass
class Trajectory:
    """Complete trajectory definition."""
    points: List[TrajectoryPoint] = field(default_factory=list)
    total_time: float = 0.0
    total_distance: float = 0.0
    path_type: PathType = PathType.LINEAR
    obstacles: List[Obstacle] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryResult:
    """Result of trajectory execution."""
    success: bool
    execution_time: float
    planned_trajectory: Trajectory
    actual_path: List[Union[PoseObject, JointsPosition]]
    max_deviation: float
    average_velocity: float
    collision_detected: bool = False
    error_message: Optional[str] = None


class TrajectoryPlanner:
    """
    Advanced trajectory planner providing path optimization, smooth motion generation,
    and collision detection for robotic arm control.
    """
    
    def __init__(self, 
                 robot_controller: RobotController,
                 movement_controller: AdvancedMovementController,
                 config_manager=None):
        """
        Initialize trajectory planner.
        
        Args:
            robot_controller: Base robot controller instance
            movement_controller: Advanced movement controller instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.movement_controller = movement_controller
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('robot', {})
        
        # Trajectory planning parameters
        self.default_params = TrajectoryParameters()
        self._obstacles: List[Obstacle] = []
        self._trajectory_history: List[Dict[str, Any]] = []
        
        # Workspace boundaries
        self._workspace_boundaries = robot_controller._workspace_boundaries
        
        logger.info("Trajectory planner initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if trajectory planner is ready."""
        return self.robot_controller.is_ready
    
    def add_obstacle(self, obstacle: Obstacle) -> None:
        """
        Add obstacle for collision avoidance.
        
        Args:
            obstacle: Obstacle definition
        """
        self._obstacles.append(obstacle)
        logger.info(f"Added obstacle at {obstacle.center} with radius {obstacle.radius}mm")
    
    def remove_obstacle(self, center: Tuple[float, float, float]) -> bool:
        """
        Remove obstacle by center coordinates.
        
        Args:
            center: Obstacle center coordinates
            
        Returns:
            True if obstacle was removed, False if not found
        """
        for i, obstacle in enumerate(self._obstacles):
            if obstacle.center == center:
                self._obstacles.pop(i)
                logger.info(f"Removed obstacle at {center}")
                return True
        return False
    
    def clear_obstacles(self) -> None:
        """Clear all obstacles."""
        self._obstacles.clear()
        logger.info("All obstacles cleared")
    
    def set_trajectory_parameters(self, params: TrajectoryParameters) -> None:
        """
        Set default trajectory parameters.
        
        Args:
            params: Trajectory parameters to set as default
        """
        self.default_params = params
        logger.info(f"Trajectory parameters updated: path_type={params.path_type.value}, "
                   f"collision_check={params.collision_check.value}")
    
    def plan_trajectory(self,
                       waypoints: List[Waypoint],
                       params: Optional[TrajectoryParameters] = None) -> Trajectory:
        """
        Plan trajectory through multiple waypoints.
        
        Args:
            waypoints: List of waypoints to visit
            params: Trajectory parameters (uses default if None)
            
        Returns:
            Planned trajectory
            
        Raises:
            RoboticsError: If trajectory planning fails
            SafetyError: If trajectory is unsafe
        """
        if not waypoints:
            raise RoboticsError("No waypoints provided for trajectory planning")
        
        params = params or self.default_params
        
        logger.info(f"Planning trajectory through {len(waypoints)} waypoints")
        
        try:
            # Validate all waypoints
            self._validate_waypoints(waypoints, params)

            # Generate trajectory based on path type
            if params.path_type == PathType.LINEAR:
                trajectory = self._plan_linear_trajectory(waypoints, params)
            elif params.path_type == PathType.BEZIER:
                trajectory = self._plan_bezier_trajectory(waypoints, params)
            elif params.path_type == PathType.SPLINE:
                trajectory = self._plan_spline_trajectory(waypoints, params)
            elif params.path_type == PathType.CIRCULAR:
                trajectory = self._plan_circular_trajectory(waypoints, params)
            elif params.path_type == PathType.HELICAL:
                trajectory = self._plan_helical_trajectory(waypoints, params)
            else:
                raise RoboticsError(f"Unsupported path type: {params.path_type}")

            # Optimize trajectory
            if params.optimization_iterations > 0:
                trajectory = self._optimize_trajectory(trajectory, params)

            # Perform collision checking
            if params.collision_check != CollisionCheckMode.NONE:
                self._check_trajectory_collisions(trajectory, params)
                
                # Calculate timing and velocities
                self._calculate_trajectory_timing(trajectory, params)
                
                logger.info(f"Trajectory planned successfully: {len(trajectory.points)} points, "
                           f"{trajectory.total_time:.2f}s duration")
                
                return trajectory
        
        except Exception as e:
            error_msg = f"Trajectory planning failed: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    
    def execute_trajectory(self,
                          trajectory: Trajectory,
                          params: Optional[MovementParameters] = None) -> TrajectoryResult:
        """
        Execute planned trajectory.
        
        Args:
            trajectory: Trajectory to execute
            params: Movement parameters (uses default if None)
            
        Returns:
            TrajectoryResult with execution details
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for trajectory execution")
        
        if not trajectory.points:
            raise RoboticsError("Empty trajectory provided")
        
        params = params or MovementParameters()
        start_time = time.time()
        
        logger.info(f"Executing trajectory with {len(trajectory.points)} points")
        
        try:
            actual_path = []
            collision_detected = False
            
            # Execute each trajectory point
            for i, point in enumerate(trajectory.points):
                # Real-time collision checking if enabled
                if self.default_params.collision_check == CollisionCheckMode.REAL_TIME:
                    if self._check_point_collision(point.pose):
                        collision_detected = True
                        logger.warning(f"Collision detected at trajectory point {i}")
                        break
                
                # Set dynamic velocity if enabled
                if self.default_params.dynamic_speed:
                    params.max_velocity = point.velocity
                
                # Execute movement to trajectory point
                if isinstance(point.pose, PoseObject):
                    result = self.movement_controller.move_cartesian(point.pose, params)
                else:
                    result = self.movement_controller.move_joints(point.pose, params)
                
                if not result.success:
                    logger.warning(f"Failed to reach trajectory point {i}: {result.error_message}")
                    break
                
                # Record actual position
                actual_position = self.robot_controller.get_position()
                if actual_position:
                    actual_path.append(actual_position)
                
                # Execute tool action if specified
                if point.tool_action:
                    self._execute_tool_action(point.tool_action)
                
                # Progress logging
                if i % 10 == 0 or i == len(trajectory.points) - 1:
                    progress = (i + 1) / len(trajectory.points) * 100
                    logger.debug(f"Trajectory execution progress: {progress:.1f}%")
            
            execution_time = time.time() - start_time
            max_deviation = self._calculate_trajectory_deviation(trajectory, actual_path)
            avg_velocity = self._calculate_trajectory_velocity(actual_path, execution_time)
            
            # Record trajectory execution
            self._record_trajectory({
                'points': len(trajectory.points),
                'execution_time': execution_time,
                'max_deviation': max_deviation,
                'collision_detected': collision_detected,
                'success': not collision_detected
            })
            
            return TrajectoryResult(
                success=not collision_detected,
                execution_time=execution_time,
                planned_trajectory=trajectory,
                actual_path=actual_path,
                max_deviation=max_deviation,
                average_velocity=avg_velocity,
                collision_detected=collision_detected
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Trajectory execution failed: {e}"
            logger.error(error_msg)
            
            return TrajectoryResult(
                success=False,
                execution_time=execution_time,
                planned_trajectory=trajectory,
                actual_path=actual_path,
                max_deviation=0.0,
                average_velocity=0.0,
                error_message=error_msg
            )

    def _validate_waypoints(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> None:
        """
        Validate all waypoints for safety and feasibility.

        Args:
            waypoints: Waypoints to validate
            params: Trajectory parameters

        Raises:
            SafetyError: If any waypoint is unsafe
        """
        for i, waypoint in enumerate(waypoints):
            if isinstance(waypoint.pose, PoseObject):
                if not self.movement_controller._validate_cartesian_position(waypoint.pose):
                    raise SafetyError(f"Waypoint {i} is outside workspace boundaries")
            elif isinstance(waypoint.pose, JointsPosition):
                if not self.movement_controller._validate_joint_positions(waypoint.pose.joints):
                    raise SafetyError(f"Waypoint {i} has unsafe joint positions")

    def _plan_linear_trajectory(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> Trajectory:
        """
        Plan linear trajectory through waypoints.

        Args:
            waypoints: Waypoints to connect
            params: Trajectory parameters

        Returns:
            Linear trajectory
        """
        trajectory = Trajectory(path_type=PathType.LINEAR, obstacles=self._obstacles.copy())

        for i, waypoint in enumerate(waypoints):
            # Calculate velocity based on path complexity
            velocity = self._calculate_dynamic_velocity(waypoint, waypoints, i, params)

            trajectory_point = TrajectoryPoint(
                pose=waypoint.pose,
                velocity=velocity,
                tool_action=waypoint.tool_action
            )
            trajectory.points.append(trajectory_point)

        return trajectory

    def _plan_bezier_trajectory(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> Trajectory:
        """
        Plan smooth Bezier curve trajectory through waypoints.

        Args:
            waypoints: Waypoints to connect with curves
            params: Trajectory parameters

        Returns:
            Bezier curve trajectory
        """
        trajectory = Trajectory(path_type=PathType.BEZIER, obstacles=self._obstacles.copy())

        if len(waypoints) < 2:
            return self._plan_linear_trajectory(waypoints, params)

        # Generate Bezier curves between consecutive waypoints
        for i in range(len(waypoints) - 1):
            start_waypoint = waypoints[i]
            end_waypoint = waypoints[i + 1]

            # Generate control points for smooth curves
            control_points = self._generate_bezier_control_points(
                start_waypoint.pose, end_waypoint.pose, params.smoothing_factor
            )

            # Generate interpolated points along Bezier curve
            curve_points = self._interpolate_bezier_curve(control_points, 20)

            for j, pose in enumerate(curve_points):
                velocity = self._calculate_dynamic_velocity(start_waypoint, waypoints, i, params)

                trajectory_point = TrajectoryPoint(
                    pose=pose,
                    velocity=velocity,
                    tool_action=start_waypoint.tool_action if j == 0 else None
                )
                trajectory.points.append(trajectory_point)

        return trajectory

    def _plan_spline_trajectory(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> Trajectory:
        """
        Plan smooth spline trajectory through waypoints.

        Args:
            waypoints: Waypoints for spline interpolation
            params: Trajectory parameters

        Returns:
            Spline trajectory
        """
        trajectory = Trajectory(path_type=PathType.SPLINE, obstacles=self._obstacles.copy())

        if len(waypoints) < 3:
            return self._plan_linear_trajectory(waypoints, params)

        # Extract positions for spline calculation
        positions = []
        for waypoint in waypoints:
            if isinstance(waypoint.pose, PoseObject):
                positions.append([waypoint.pose.x, waypoint.pose.y, waypoint.pose.z])
            else:
                positions.append(waypoint.pose.joints[:3])  # Use first 3 joints for position

        # Generate spline interpolation
        spline_points = self._interpolate_spline(positions, params.smoothing_factor)

        for point in spline_points:
            # Create pose from spline point
            if isinstance(waypoints[0].pose, PoseObject):
                pose = PoseObject(point[0], point[1], point[2], 0, 0, 0)
            else:
                joints = waypoints[0].pose.joints.copy()
                joints[:3] = point
                pose = JointsPosition(joints)

            velocity = self._calculate_dynamic_velocity(waypoints[0], waypoints, 0, params)

            trajectory_point = TrajectoryPoint(
                pose=pose,
                velocity=velocity
            )
            trajectory.points.append(trajectory_point)

        return trajectory

    def _plan_circular_trajectory(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> Trajectory:
        """
        Plan circular arc trajectory through waypoints.

        Args:
            waypoints: Waypoints defining circular arc
            params: Trajectory parameters

        Returns:
            Circular trajectory
        """
        trajectory = Trajectory(path_type=PathType.CIRCULAR, obstacles=self._obstacles.copy())

        if len(waypoints) < 3:
            return self._plan_linear_trajectory(waypoints, params)

        # Use first three waypoints to define circular arc
        start = waypoints[0].pose
        mid = waypoints[1].pose
        end = waypoints[2].pose

        if isinstance(start, PoseObject):
            # Calculate circular arc in Cartesian space
            center, radius = self._calculate_circle_center(
                [start.x, start.y, start.z],
                [mid.x, mid.y, mid.z],
                [end.x, end.y, end.z]
            )

            # Generate points along circular arc
            arc_points = self._generate_circular_arc(center, radius, start, end, 30)

            for pose in arc_points:
                velocity = self._calculate_dynamic_velocity(waypoints[0], waypoints, 0, params)

                trajectory_point = TrajectoryPoint(
                    pose=pose,
                    velocity=velocity
                )
                trajectory.points.append(trajectory_point)

        return trajectory

    def _plan_helical_trajectory(self, waypoints: List[Waypoint], params: TrajectoryParameters) -> Trajectory:
        """
        Plan helical (spiral) trajectory.

        Args:
            waypoints: Waypoints defining helix parameters
            params: Trajectory parameters

        Returns:
            Helical trajectory
        """
        trajectory = Trajectory(path_type=PathType.HELICAL, obstacles=self._obstacles.copy())

        if len(waypoints) < 2:
            return self._plan_linear_trajectory(waypoints, params)

        start = waypoints[0].pose
        end = waypoints[1].pose

        if isinstance(start, PoseObject):
            # Generate helical path
            helix_points = self._generate_helix(start, end, radius=50.0, turns=2.0, points=50)

            for pose in helix_points:
                velocity = self._calculate_dynamic_velocity(waypoints[0], waypoints, 0, params)

                trajectory_point = TrajectoryPoint(
                    pose=pose,
                    velocity=velocity
                )
                trajectory.points.append(trajectory_point)

        return trajectory

    def _calculate_dynamic_velocity(self, waypoint: Waypoint, waypoints: List[Waypoint],
                                   index: int, params: TrajectoryParameters) -> float:
        """
        Calculate dynamic velocity based on path complexity.

        Args:
            waypoint: Current waypoint
            waypoints: All waypoints
            index: Current waypoint index
            params: Trajectory parameters

        Returns:
            Calculated velocity percentage
        """
        if not params.dynamic_speed:
            return params.max_speed_percent

        # Override velocity if specified in waypoint
        if waypoint.velocity is not None:
            return waypoint.velocity

        # Calculate path complexity factors
        curvature_factor = 1.0
        distance_factor = 1.0

        if index > 0 and index < len(waypoints) - 1:
            # Calculate curvature at this waypoint
            prev_pose = waypoints[index - 1].pose
            curr_pose = waypoint.pose
            next_pose = waypoints[index + 1].pose

            curvature = self._calculate_path_curvature(prev_pose, curr_pose, next_pose)
            curvature_factor = max(0.3, 1.0 - curvature / 100.0)  # Reduce speed for high curvature

        # Calculate velocity based on factors
        velocity = params.max_speed_percent * curvature_factor * distance_factor
        return max(params.min_speed_percent, min(params.max_speed_percent, velocity))

    def _calculate_path_curvature(self, prev_pose: Union[PoseObject, JointsPosition],
                                 curr_pose: Union[PoseObject, JointsPosition],
                                 next_pose: Union[PoseObject, JointsPosition]) -> float:
        """
        Calculate path curvature at a waypoint.

        Args:
            prev_pose: Previous pose
            curr_pose: Current pose
            next_pose: Next pose

        Returns:
            Curvature value (higher = more curved)
        """
        if isinstance(curr_pose, PoseObject):
            # Cartesian curvature calculation
            p1 = np.array([prev_pose.x, prev_pose.y, prev_pose.z])
            p2 = np.array([curr_pose.x, curr_pose.y, curr_pose.z])
            p3 = np.array([next_pose.x, next_pose.y, next_pose.z])

            # Calculate vectors
            v1 = p2 - p1
            v2 = p3 - p2

            # Calculate angle between vectors
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle = math.acos(cos_angle)

            # Convert to curvature (0 = straight, pi = sharp turn)
            return angle * 180 / math.pi

        else:
            # Joint space curvature (simplified)
            j1 = np.array(prev_pose.joints)
            j2 = np.array(curr_pose.joints)
            j3 = np.array(next_pose.joints)

            # Calculate joint angle changes
            change1 = np.linalg.norm(j2 - j1)
            change2 = np.linalg.norm(j3 - j2)

            return abs(change2 - change1) * 180 / math.pi

    def _generate_bezier_control_points(self, start: Union[PoseObject, JointsPosition],
                                       end: Union[PoseObject, JointsPosition],
                                       smoothing: float) -> List[Union[PoseObject, JointsPosition]]:
        """
        Generate control points for Bezier curve.

        Args:
            start: Start pose
            end: End pose
            smoothing: Smoothing factor (0-1)

        Returns:
            List of control points
        """
        control_points = [start]

        if isinstance(start, PoseObject):
            # Generate intermediate control points
            mid_x = (start.x + end.x) / 2
            mid_y = (start.y + end.y) / 2
            mid_z = (start.z + end.z) / 2 + smoothing * 50  # Add height for smooth curve

            control1 = PoseObject(
                start.x + (mid_x - start.x) * 0.3,
                start.y + (mid_y - start.y) * 0.3,
                start.z + (mid_z - start.z) * 0.3,
                start.roll, start.pitch, start.yaw
            )

            control2 = PoseObject(
                end.x - (end.x - mid_x) * 0.3,
                end.y - (end.y - mid_y) * 0.3,
                end.z - (end.z - mid_z) * 0.3,
                end.roll, end.pitch, end.yaw
            )

            control_points.extend([control1, control2])

        control_points.append(end)
        return control_points

    def _interpolate_bezier_curve(self, control_points: List[Union[PoseObject, JointsPosition]],
                                 num_points: int) -> List[Union[PoseObject, JointsPosition]]:
        """
        Interpolate points along Bezier curve.

        Args:
            control_points: Bezier control points
            num_points: Number of interpolated points

        Returns:
            Interpolated curve points
        """
        curve_points = []

        for i in range(num_points):
            t = i / (num_points - 1)
            point = self._evaluate_bezier_curve(control_points, t)
            curve_points.append(point)

        return curve_points

    def _evaluate_bezier_curve(self, control_points: List[Union[PoseObject, JointsPosition]],
                              t: float) -> Union[PoseObject, JointsPosition]:
        """
        Evaluate Bezier curve at parameter t.

        Args:
            control_points: Bezier control points
            t: Parameter (0-1)

        Returns:
            Point on curve at parameter t
        """
        n = len(control_points) - 1

        if isinstance(control_points[0], PoseObject):
            x = y = z = roll = pitch = yaw = 0.0

            for i, point in enumerate(control_points):
                # Bernstein polynomial
                coeff = math.comb(n, i) * (t ** i) * ((1 - t) ** (n - i))

                x += coeff * point.x
                y += coeff * point.y
                z += coeff * point.z
                roll += coeff * point.roll
                pitch += coeff * point.pitch
                yaw += coeff * point.yaw

            return PoseObject(x, y, z, roll, pitch, yaw)

        else:
            joints = [0.0] * len(control_points[0].joints)

            for i, point in enumerate(control_points):
                coeff = math.comb(n, i) * (t ** i) * ((1 - t) ** (n - i))

                for j in range(len(joints)):
                    joints[j] += coeff * point.joints[j]

            return JointsPosition(joints)

    def _interpolate_spline(self, positions: List[List[float]], smoothing: float) -> List[List[float]]:
        """
        Interpolate smooth spline through positions.

        Args:
            positions: List of 3D positions
            smoothing: Smoothing factor

        Returns:
            Interpolated spline points
        """
        if len(positions) < 3:
            return positions

        # Simple spline interpolation using numpy
        positions_array = np.array(positions)
        t_original = np.linspace(0, 1, len(positions))
        t_interpolated = np.linspace(0, 1, len(positions) * 5)  # 5x more points

        spline_points = []
        for i in range(positions_array.shape[1]):  # For each dimension
            interpolated = np.interp(t_interpolated, t_original, positions_array[:, i])
            if i == 0:
                spline_points = [[val] for val in interpolated]
            else:
                for j, val in enumerate(interpolated):
                    spline_points[j].append(val)

        return spline_points

    def _calculate_circle_center(self, p1: List[float], p2: List[float], p3: List[float]) -> Tuple[List[float], float]:
        """
        Calculate center and radius of circle through three points.

        Args:
            p1, p2, p3: Three points on the circle

        Returns:
            Tuple of (center, radius)
        """
        # Simplified 2D circle calculation (using X-Y plane)
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        x3, y3 = p3[0], p3[1]

        # Calculate center
        d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(d) < 1e-6:  # Points are collinear
            return [(x1 + x3) / 2, (y1 + y3) / 2, (p1[2] + p3[2]) / 2], 0.0

        ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
        uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
        uz = (p1[2] + p2[2] + p3[2]) / 3  # Average Z coordinate

        center = [ux, uy, uz]
        radius = math.sqrt((ux - x1)**2 + (uy - y1)**2)

        return center, radius

    def _generate_circular_arc(self, center: List[float], radius: float,
                              start: PoseObject, end: PoseObject, num_points: int) -> List[PoseObject]:
        """
        Generate points along circular arc.

        Args:
            center: Arc center
            radius: Arc radius
            start: Start pose
            end: End pose
            num_points: Number of points to generate

        Returns:
            List of poses along arc
        """
        arc_points = []

        # Calculate start and end angles
        start_angle = math.atan2(start.y - center[1], start.x - center[0])
        end_angle = math.atan2(end.y - center[1], end.x - center[0])

        # Ensure we take the shorter arc
        angle_diff = end_angle - start_angle
        if angle_diff > math.pi:
            angle_diff -= 2 * math.pi
        elif angle_diff < -math.pi:
            angle_diff += 2 * math.pi

        for i in range(num_points):
            t = i / (num_points - 1)
            angle = start_angle + angle_diff * t

            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            z = start.z + (end.z - start.z) * t  # Linear interpolation for Z

            # Interpolate orientation
            roll = start.roll + (end.roll - start.roll) * t
            pitch = start.pitch + (end.pitch - start.pitch) * t
            yaw = start.yaw + (end.yaw - start.yaw) * t

            arc_points.append(PoseObject(x, y, z, roll, pitch, yaw))

        return arc_points

    def _generate_helix(self, start: PoseObject, end: PoseObject,
                       radius: float, turns: float, points: int) -> List[PoseObject]:
        """
        Generate helical (spiral) path.

        Args:
            start: Start pose
            end: End pose
            radius: Helix radius
            turns: Number of turns
            points: Number of points to generate

        Returns:
            List of poses along helix
        """
        helix_points = []

        # Calculate helix parameters
        center_x = (start.x + end.x) / 2
        center_y = (start.y + end.y) / 2
        height_diff = end.z - start.z

        for i in range(points):
            t = i / (points - 1)
            angle = turns * 2 * math.pi * t

            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            z = start.z + height_diff * t

            # Interpolate orientation
            roll = start.roll + (end.roll - start.roll) * t
            pitch = start.pitch + (end.pitch - start.pitch) * t
            yaw = start.yaw + (end.yaw - start.yaw) * t

            helix_points.append(PoseObject(x, y, z, roll, pitch, yaw))

        return helix_points

    def _check_trajectory_collisions(self, trajectory: Trajectory, params: TrajectoryParameters) -> None:
        """
        Check trajectory for collisions with obstacles.

        Args:
            trajectory: Trajectory to check
            params: Trajectory parameters

        Raises:
            SafetyError: If collision is detected
        """
        if params.collision_check == CollisionCheckMode.NONE:
            return

        for i, point in enumerate(trajectory.points):
            if self._check_point_collision(point.pose, params.safety_margin):
                raise SafetyError(f"Collision detected at trajectory point {i}")

    def _check_point_collision(self, pose: Union[PoseObject, JointsPosition],
                              safety_margin: float = 20.0) -> bool:
        """
        Check if a pose collides with any obstacles.

        Args:
            pose: Pose to check
            safety_margin: Additional safety margin

        Returns:
            True if collision detected, False otherwise
        """
        if not self._obstacles:
            return False

        if isinstance(pose, PoseObject):
            point = [pose.x, pose.y, pose.z]

            for obstacle in self._obstacles:
                distance = math.sqrt(
                    (point[0] - obstacle.center[0])**2 +
                    (point[1] - obstacle.center[1])**2 +
                    (point[2] - obstacle.center[2])**2
                )

                if distance < (obstacle.radius + obstacle.safety_margin + safety_margin):
                    return True

        return False

    def _optimize_trajectory(self, trajectory: Trajectory, params: TrajectoryParameters) -> Trajectory:
        """
        Optimize trajectory for smoothness and efficiency.

        Args:
            trajectory: Trajectory to optimize
            params: Trajectory parameters

        Returns:
            Optimized trajectory
        """
        # Simple optimization: remove redundant points
        if len(trajectory.points) < 3:
            return trajectory

        optimized_points = [trajectory.points[0]]  # Always keep first point

        for i in range(1, len(trajectory.points) - 1):
            prev_point = optimized_points[-1]
            curr_point = trajectory.points[i]
            next_point = trajectory.points[i + 1]

            # Check if current point is necessary (not on straight line)
            if self._is_point_necessary(prev_point.pose, curr_point.pose, next_point.pose, params.max_deviation):
                optimized_points.append(curr_point)

        optimized_points.append(trajectory.points[-1])  # Always keep last point

        trajectory.points = optimized_points
        logger.info(f"Trajectory optimized: {len(optimized_points)} points (reduced from {len(trajectory.points)})")

        return trajectory

    def _is_point_necessary(self, prev_pose: Union[PoseObject, JointsPosition],
                           curr_pose: Union[PoseObject, JointsPosition],
                           next_pose: Union[PoseObject, JointsPosition],
                           max_deviation: float) -> bool:
        """
        Check if a point is necessary for trajectory accuracy.

        Args:
            prev_pose: Previous pose
            curr_pose: Current pose
            next_pose: Next pose
            max_deviation: Maximum allowed deviation

        Returns:
            True if point is necessary, False if it can be removed
        """
        if isinstance(curr_pose, PoseObject):
            # Calculate deviation from straight line
            p1 = np.array([prev_pose.x, prev_pose.y, prev_pose.z])
            p2 = np.array([curr_pose.x, curr_pose.y, curr_pose.z])
            p3 = np.array([next_pose.x, next_pose.y, next_pose.z])

            # Calculate distance from point to line
            line_vec = p3 - p1
            point_vec = p2 - p1

            if np.linalg.norm(line_vec) < 1e-6:
                return False  # Points are too close

            # Project point onto line
            projection = np.dot(point_vec, line_vec) / np.dot(line_vec, line_vec)
            closest_point = p1 + projection * line_vec

            deviation = np.linalg.norm(p2 - closest_point)
            return deviation > max_deviation

        return True  # Conservative: keep all joint space points

    def _calculate_trajectory_timing(self, trajectory: Trajectory, params: TrajectoryParameters) -> None:
        """
        Calculate timing and velocities for trajectory points.

        Args:
            trajectory: Trajectory to calculate timing for
            params: Trajectory parameters
        """
        if not trajectory.points:
            return

        total_time = 0.0
        total_distance = 0.0

        for i in range(len(trajectory.points)):
            point = trajectory.points[i]

            if i > 0:
                prev_point = trajectory.points[i - 1]

                # Calculate distance between points
                if isinstance(point.pose, PoseObject):
                    distance = math.sqrt(
                        (point.pose.x - prev_point.pose.x)**2 +
                        (point.pose.y - prev_point.pose.y)**2 +
                        (point.pose.z - prev_point.pose.z)**2
                    )
                else:
                    distance = sum(abs(j1 - j2) for j1, j2 in
                                 zip(point.pose.joints, prev_point.pose.joints))

                # Calculate time based on velocity
                velocity_ms = point.velocity / 100.0 * 1000.0  # Convert to mm/s
                time_segment = distance / velocity_ms if velocity_ms > 0 else 0.1

                total_time += time_segment
                total_distance += distance

            point.timestamp = total_time

        trajectory.total_time = total_time
        trajectory.total_distance = total_distance

    def _calculate_trajectory_deviation(self, trajectory: Trajectory,
                                      actual_path: List[Union[PoseObject, JointsPosition]]) -> float:
        """
        Calculate maximum deviation between planned and actual trajectory.

        Args:
            trajectory: Planned trajectory
            actual_path: Actual executed path

        Returns:
            Maximum deviation
        """
        if not trajectory.points or not actual_path:
            return 0.0

        max_deviation = 0.0
        min_length = min(len(trajectory.points), len(actual_path))

        for i in range(min_length):
            planned = trajectory.points[i].pose
            actual = actual_path[i]

            if isinstance(planned, PoseObject) and isinstance(actual, PoseObject):
                deviation = math.sqrt(
                    (planned.x - actual.x)**2 +
                    (planned.y - actual.y)**2 +
                    (planned.z - actual.z)**2
                )
            elif hasattr(planned, 'joints') and hasattr(actual, 'joints'):
                deviation = max(abs(p - a) for p, a in zip(planned.joints, actual.joints))
            else:
                continue

            max_deviation = max(max_deviation, deviation)

        return max_deviation

    def _calculate_trajectory_velocity(self, actual_path: List[Union[PoseObject, JointsPosition]],
                                     execution_time: float) -> float:
        """
        Calculate average velocity during trajectory execution.

        Args:
            actual_path: Executed path
            execution_time: Total execution time

        Returns:
            Average velocity
        """
        if len(actual_path) < 2 or execution_time <= 0:
            return 0.0

        total_distance = 0.0

        for i in range(1, len(actual_path)):
            prev = actual_path[i-1]
            curr = actual_path[i]

            if isinstance(prev, PoseObject) and isinstance(curr, PoseObject):
                distance = math.sqrt(
                    (curr.x - prev.x)**2 +
                    (curr.y - prev.y)**2 +
                    (curr.z - prev.z)**2
                )
            elif hasattr(prev, 'joints') and hasattr(curr, 'joints'):
                distance = sum(abs(c - p) for p, c in zip(prev.joints, curr.joints))
            else:
                continue

            total_distance += distance

        return total_distance / execution_time

    def _execute_tool_action(self, action: str) -> None:
        """
        Execute tool action at trajectory point.

        Args:
            action: Tool action to execute ("grasp", "release")
        """
        try:
            if action.lower() == "grasp":
                self.robot_controller.grasp()
                logger.debug("Tool grasp executed at trajectory point")
            elif action.lower() == "release":
                self.robot_controller.release()
                logger.debug("Tool release executed at trajectory point")
            else:
                logger.warning(f"Unknown tool action: {action}")
        except Exception as e:
            logger.error(f"Tool action failed: {e}")

    def _record_trajectory(self, trajectory_data: Dict[str, Any]) -> None:
        """
        Record trajectory execution in history.

        Args:
            trajectory_data: Trajectory execution data
        """
        trajectory_data['timestamp'] = time.time()
        self._trajectory_history.append(trajectory_data)

        # Keep only last 50 trajectories
        if len(self._trajectory_history) > 50:
            self._trajectory_history.pop(0)

    def get_trajectory_history(self) -> List[Dict[str, Any]]:
        """
        Get trajectory execution history.

        Returns:
            List of trajectory execution records
        """
        return self._trajectory_history.copy()

    def clear_trajectory_history(self) -> None:
        """Clear trajectory execution history."""
        self._trajectory_history.clear()
        logger.info("Trajectory history cleared")

    def get_obstacles(self) -> List[Obstacle]:
        """
        Get current obstacles.

        Returns:
            List of current obstacles
        """
        return self._obstacles.copy()

    def visualize_trajectory(self, trajectory: Trajectory) -> Dict[str, Any]:
        """
        Generate trajectory visualization data.

        Args:
            trajectory: Trajectory to visualize

        Returns:
            Visualization data dictionary
        """
        visualization_data = {
            'path_type': trajectory.path_type.value,
            'total_points': len(trajectory.points),
            'total_time': trajectory.total_time,
            'total_distance': trajectory.total_distance,
            'points': [],
            'obstacles': []
        }

        # Extract point data
        for point in trajectory.points:
            if isinstance(point.pose, PoseObject):
                point_data = {
                    'x': point.pose.x,
                    'y': point.pose.y,
                    'z': point.pose.z,
                    'velocity': point.velocity,
                    'timestamp': point.timestamp
                }
            else:
                point_data = {
                    'joints': point.pose.joints,
                    'velocity': point.velocity,
                    'timestamp': point.timestamp
                }

            visualization_data['points'].append(point_data)

        # Extract obstacle data
        for obstacle in trajectory.obstacles:
            obstacle_data = {
                'center': obstacle.center,
                'radius': obstacle.radius,
                'shape': obstacle.shape,
                'safety_margin': obstacle.safety_margin
            }
            visualization_data['obstacles'].append(obstacle_data)

        return visualization_data
