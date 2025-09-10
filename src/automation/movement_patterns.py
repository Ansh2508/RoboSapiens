"""
Movement Pattern Library

This module provides a comprehensive library of movement patterns for the Niryo Ned2 robotic arm,
including geometric patterns, calibration routines, test sequences, and educational demonstrations.

Features:
- Geometric patterns (square, circle, triangle, helix, spiral, zigzag)
- Calibration routines for workspace mapping
- Test patterns for accuracy and repeatability validation
- Demo sequences for educational workshops
- Pattern validation and execution monitoring
- Customizable pattern parameters and scaling
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

from ..core.robot_controller import RobotController
from ..core.advanced_movement import AdvancedMovementController, MovementParameters
from core.trajectory_planner import TrajectoryPlanner, TrajectoryParameters, Waypoint
from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError, SafetyError

logger = get_logger(__name__)


class PatternType(Enum):
    """Types of movement patterns."""
    SQUARE = "square"
    CIRCLE = "circle"
    TRIANGLE = "triangle"
    HELIX = "helix"
    SPIRAL = "spiral"
    ZIGZAG = "zigzag"
    FIGURE_EIGHT = "figure_eight"
    STAR = "star"
    CUSTOM = "custom"


class PatternPlane(Enum):
    """Planes for pattern execution."""
    XY = "xy"  # Horizontal plane
    XZ = "xz"  # Vertical plane (front)
    YZ = "yz"  # Vertical plane (side)
    CUSTOM = "custom"


@dataclass
class PatternParameters:
    """Parameters for pattern generation and execution."""
    size: float = 100.0  # Pattern size in mm
    center: Tuple[float, float, float] = (200.0, 0.0, 200.0)  # Pattern center (X, Y, Z)
    plane: PatternPlane = PatternPlane.XY
    points: int = 20  # Number of points in pattern
    speed: float = 50.0  # Movement speed percentage
    height_variation: float = 0.0  # Z-axis variation for 3D patterns
    rotation: float = 0.0  # Pattern rotation in radians
    repetitions: int = 1  # Number of pattern repetitions
    pause_between_points: float = 0.1  # Pause between points in seconds
    return_to_start: bool = True  # Return to start position after pattern


@dataclass
class PatternResult:
    """Result of pattern execution."""
    success: bool
    pattern_type: PatternType
    execution_time: float
    points_executed: int
    max_deviation: float
    average_velocity: float
    accuracy_score: float  # 0-100 score based on deviation
    error_message: Optional[str] = None


@dataclass
class MovementPattern:
    """Complete movement pattern definition."""
    name: str
    pattern_type: PatternType
    description: str
    waypoints: List[Waypoint] = field(default_factory=list)
    parameters: PatternParameters = field(default_factory=PatternParameters)
    estimated_duration: float = 0.0
    difficulty_level: int = 1  # 1-5 difficulty scale
    educational_notes: str = ""


class MovementPatternLibrary:
    """
    Comprehensive library of movement patterns for robotic arm control,
    education, and testing purposes.
    """
    
    def __init__(self, 
                 robot_controller: RobotController,
                 movement_controller: AdvancedMovementController,
                 trajectory_planner: TrajectoryPlanner,
                 config_manager=None):
        """
        Initialize movement pattern library.
        
        Args:
            robot_controller: Base robot controller instance
            movement_controller: Advanced movement controller instance
            trajectory_planner: Trajectory planner instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.movement_controller = movement_controller
        self.trajectory_planner = trajectory_planner
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Pattern library and execution history
        self._patterns: Dict[str, MovementPattern] = {}
        self._execution_history: List[Dict[str, Any]] = []
        
        # Default parameters
        self.default_params = PatternParameters()
        
        # Workspace boundaries for pattern validation
        self._workspace_boundaries = robot_controller._workspace_boundaries
        
        # Initialize built-in patterns
        self._initialize_pattern_library()
        
        logger.info("Movement pattern library initialized")
    
    @property
    def is_ready(self) -> bool:
        """Check if pattern library is ready."""
        return self.robot_controller.is_ready
    
    def set_default_parameters(self, params: PatternParameters) -> None:
        """
        Set default pattern parameters.
        
        Args:
            params: Pattern parameters to set as default
        """
        self.default_params = params
        logger.info(f"Default pattern parameters updated: size={params.size}mm, "
                   f"center={params.center}, plane={params.plane.value}")
    def execute_pattern(self, 
                       pattern_name: str, 
                       params: Optional[PatternParameters] = None) -> PatternResult:
        """
        Execute a movement pattern by name.
        
        Args:
            pattern_name: Name of pattern to execute
            params: Pattern parameters (uses default if None)
            
        Returns:
            PatternResult with execution details
        """
        if pattern_name not in self._patterns:
            raise RoboticsError(f"Unknown pattern: {pattern_name}")
        
        pattern = self._patterns[pattern_name]
        params = params or self.default_params
        
        logger.info(f"Executing pattern: {pattern_name}")
        
        try:
            start_time = time.time()
            
            # Generate pattern waypoints
            waypoints = self._generate_pattern_waypoints(pattern.pattern_type, params)
            
            # Validate pattern within workspace
            self._validate_pattern_waypoints(waypoints)
            
            # Execute pattern using trajectory planner
            trajectory_params = TrajectoryParameters(
                max_speed_percent=params.speed,
                dynamic_speed=True
            )
            
            trajectory = self.trajectory_planner.plan_trajectory(waypoints, trajectory_params)
            result = self.trajectory_planner.execute_trajectory(trajectory)
            
            execution_time = time.time() - start_time
            
            # Calculate accuracy score
            accuracy_score = self._calculate_accuracy_score(result.max_deviation, params.size)
            
            # Create pattern result
            pattern_result = PatternResult(
                success=result.success,
                pattern_type=pattern.pattern_type,
                execution_time=execution_time,
                points_executed=len(waypoints),
                max_deviation=result.max_deviation,
                average_velocity=result.average_velocity,
                accuracy_score=accuracy_score,
                error_message=result.error_message
            )
            
            # Record execution
            self._record_pattern_execution({
                'pattern_name': pattern_name,
                'pattern_type': pattern.pattern_type.value,
                'success': result.success,
                'execution_time': execution_time,
                'accuracy_score': accuracy_score,
                'parameters': params
            })
            
            logger.info(f"Pattern '{pattern_name}' executed: success={result.success}, "
                       f"accuracy={accuracy_score:.1f}%, time={execution_time:.2f}s")
            
            return pattern_result
        
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Pattern execution failed: {e}"
            logger.error(error_msg)
            
            return PatternResult(
                success=False,
                pattern_type=pattern.pattern_type,
                execution_time=execution_time,
                points_executed=0,
                max_deviation=0.0,
                average_velocity=0.0,
                accuracy_score=0.0,
                error_message=error_msg
            )
    def execute_calibration_routine(self, routine_name: str = "workspace_mapping") -> PatternResult:
        """
        Execute calibration routine for workspace mapping and accuracy testing.
        
        Args:
            routine_name: Name of calibration routine
            
        Returns:
            PatternResult with calibration details
        """
        logger.info(f"Executing calibration routine: {routine_name}")
        
        if routine_name == "workspace_mapping":
            return self._execute_workspace_mapping()
        elif routine_name == "accuracy_test":
            return self._execute_accuracy_test()
        elif routine_name == "repeatability_test":
            return self._execute_repeatability_test()
        else:
            raise RoboticsError(f"Unknown calibration routine: {routine_name}")
    
    def add_custom_pattern(self, pattern: MovementPattern) -> None:
        """
        Add custom movement pattern to library.
        
        Args:
            pattern: Movement pattern to add
        """
        self._patterns[pattern.name] = pattern
        logger.info(f"Added custom pattern: {pattern.name}")
    
    def get_available_patterns(self) -> Dict[str, MovementPattern]:
        """
        Get all available movement patterns.
        
        Returns:
            Dictionary of available patterns
        """
        return self._patterns.copy()
    
    def get_pattern_info(self, pattern_name: str) -> Optional[MovementPattern]:
        """
        Get information about a specific pattern.
        
        Args:
            pattern_name: Name of pattern
            
        Returns:
            Pattern information or None if not found
        """
        return self._patterns.get(pattern_name)
    
    def _initialize_pattern_library(self) -> None:
        """Initialize built-in movement patterns."""
        
        # Square pattern
        square_pattern = MovementPattern(
            name="square",
            pattern_type=PatternType.SQUARE,
            description="Square pattern in specified plane",
            difficulty_level=1,
            educational_notes="Basic geometric pattern for learning coordinate systems"
        )
        
        # Circle pattern
        circle_pattern = MovementPattern(
            name="circle",
            pattern_type=PatternType.CIRCLE,
            description="Circular pattern with smooth curves",
            difficulty_level=2,
            educational_notes="Demonstrates smooth curved motion and trajectory planning"
        )
        
        # Triangle pattern
        triangle_pattern = MovementPattern(
            name="triangle",
            pattern_type=PatternType.TRIANGLE,
            description="Triangular pattern with sharp corners",
            difficulty_level=1,
            educational_notes="Shows angular movements and corner handling"
        )
        
        # Helix pattern
        helix_pattern = MovementPattern(
            name="helix",
            pattern_type=PatternType.HELIX,
            description="3D helical spiral pattern",
            difficulty_level=4,
            educational_notes="Advanced 3D pattern combining rotation and translation"
        )
        
        # Spiral pattern
        spiral_pattern = MovementPattern(
            name="spiral",
            pattern_type=PatternType.SPIRAL,
            description="2D spiral pattern with increasing radius",
            difficulty_level=3,
            educational_notes="Demonstrates variable radius circular motion"
        )
        
        # Zigzag pattern
        zigzag_pattern = MovementPattern(
            name="zigzag",
            pattern_type=PatternType.ZIGZAG,
            description="Zigzag pattern with alternating directions",
            difficulty_level=2,
            educational_notes="Shows rapid direction changes and acceleration control"
        )
        
        # Figure-eight pattern
        figure_eight_pattern = MovementPattern(
            name="figure_eight",
            pattern_type=PatternType.FIGURE_EIGHT,
            description="Figure-eight pattern with smooth curves",
            difficulty_level=3,
            educational_notes="Complex curved pattern requiring precise trajectory control"
        )
        
        # Star pattern
        star_pattern = MovementPattern(
            name="star",
            pattern_type=PatternType.STAR,
            description="Five-pointed star pattern",
            difficulty_level=2,
            educational_notes="Geometric pattern with multiple angular segments"
        )
        
        # Add patterns to library
        patterns = [
            square_pattern, circle_pattern, triangle_pattern, helix_pattern,
            spiral_pattern, zigzag_pattern, figure_eight_pattern, star_pattern
        ]
        
        for pattern in patterns:
            self._patterns[pattern.name] = pattern
        
        logger.info(f"Initialized {len(patterns)} built-in movement patterns")

    def _generate_pattern_waypoints(self, pattern_type: PatternType, params: PatternParameters) -> List[Waypoint]:
        """
        Generate waypoints for specified pattern type.

        Args:
            pattern_type: Type of pattern to generate
            params: Pattern parameters

        Returns:
            List of waypoints for the pattern
        """
        if pattern_type == PatternType.SQUARE:
            return self._generate_square_pattern(params)
        elif pattern_type == PatternType.CIRCLE:
            return self._generate_circle_pattern(params)
        elif pattern_type == PatternType.TRIANGLE:
            return self._generate_triangle_pattern(params)
        elif pattern_type == PatternType.HELIX:
            return self._generate_helix_pattern(params)
        elif pattern_type == PatternType.SPIRAL:
            return self._generate_spiral_pattern(params)
        elif pattern_type == PatternType.ZIGZAG:
            return self._generate_zigzag_pattern(params)
        elif pattern_type == PatternType.FIGURE_EIGHT:
            return self._generate_figure_eight_pattern(params)
        elif pattern_type == PatternType.STAR:
            return self._generate_star_pattern(params)
        else:
            raise RoboticsError(f"Unsupported pattern type: {pattern_type}")

    def _generate_square_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate square pattern waypoints."""
        waypoints = []
        half_size = params.size / 2
        cx, cy, cz = params.center

        # Define square corners based on plane
        if params.plane == PatternPlane.XY:
            corners = [
                (cx - half_size, cy - half_size, cz),
                (cx + half_size, cy - half_size, cz),
                (cx + half_size, cy + half_size, cz),
                (cx - half_size, cy + half_size, cz),
                (cx - half_size, cy - half_size, cz)  # Return to start
            ]
        elif params.plane == PatternPlane.XZ:
            corners = [
                (cx - half_size, cy, cz - half_size),
                (cx + half_size, cy, cz - half_size),
                (cx + half_size, cy, cz + half_size),
                (cx - half_size, cy, cz + half_size),
                (cx - half_size, cy, cz - half_size)
            ]
        else:  # YZ plane
            corners = [
                (cx, cy - half_size, cz - half_size),
                (cx, cy + half_size, cz - half_size),
                (cx, cy + half_size, cz + half_size),
                (cx, cy - half_size, cz + half_size),
                (cx, cy - half_size, cz - half_size)
            ]

        # Apply rotation if specified
        if params.rotation != 0:
            corners = self._rotate_points(corners, params.rotation, params.center, params.plane)

        # Create waypoints
        for x, y, z in corners:
            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_circle_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate circular pattern waypoints."""
        waypoints = []
        radius = params.size / 2
        cx, cy, cz = params.center

        for i in range(params.points + 1):  # +1 to close the circle
            angle = 2 * math.pi * i / params.points + params.rotation

            if params.plane == PatternPlane.XY:
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                z = cz + params.height_variation * math.sin(4 * angle)  # Optional height variation
            elif params.plane == PatternPlane.XZ:
                x = cx + radius * math.cos(angle)
                y = cy
                z = cz + radius * math.sin(angle)
            else:  # YZ plane
                x = cx
                y = cy + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_triangle_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate triangular pattern waypoints."""
        waypoints = []
        radius = params.size / 2
        cx, cy, cz = params.center

        # Three vertices of equilateral triangle
        angles = [0, 2*math.pi/3, 4*math.pi/3, 0]  # Return to start

        for angle in angles:
            angle += params.rotation

            if params.plane == PatternPlane.XY:
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                z = cz
            elif params.plane == PatternPlane.XZ:
                x = cx + radius * math.cos(angle)
                y = cy
                z = cz + radius * math.sin(angle)
            else:  # YZ plane
                x = cx
                y = cy + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_helix_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate helical pattern waypoints."""
        waypoints = []
        radius = params.size / 4  # Smaller radius for helix
        cx, cy, cz = params.center
        height_per_turn = params.size / 2

        for i in range(params.points):
            t = i / params.points
            angle = 4 * math.pi * t + params.rotation  # 2 full turns

            x = cx + radius * math.cos(angle)
            y = cy + radius * math.sin(angle)
            z = cz + height_per_turn * t

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_spiral_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate spiral pattern waypoints."""
        waypoints = []
        max_radius = params.size / 2
        cx, cy, cz = params.center

        for i in range(params.points):
            t = i / params.points
            angle = 4 * math.pi * t + params.rotation  # 2 full turns
            radius = max_radius * t  # Increasing radius

            if params.plane == PatternPlane.XY:
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                z = cz
            elif params.plane == PatternPlane.XZ:
                x = cx + radius * math.cos(angle)
                y = cy
                z = cz + radius * math.sin(angle)
            else:  # YZ plane
                x = cx
                y = cy + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_zigzag_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate zigzag pattern waypoints."""
        waypoints = []
        cx, cy, cz = params.center
        half_size = params.size / 2

        # Create zigzag in XY plane by default
        num_segments = params.points // 2
        for i in range(num_segments + 1):
            t = i / num_segments

            if params.plane == PatternPlane.XY:
                x = cx + (t * 2 - 1) * half_size
                y = cy + ((-1) ** i) * half_size
                z = cz
            elif params.plane == PatternPlane.XZ:
                x = cx + (t * 2 - 1) * half_size
                y = cy
                z = cz + ((-1) ** i) * half_size
            else:  # YZ plane
                x = cx
                y = cy + (t * 2 - 1) * half_size
                z = cz + ((-1) ** i) * half_size

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_figure_eight_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate figure-eight pattern waypoints."""
        waypoints = []
        radius = params.size / 4
        cx, cy, cz = params.center

        for i in range(params.points):
            t = 2 * math.pi * i / params.points + params.rotation

            # Parametric equations for figure-eight (lemniscate)
            if params.plane == PatternPlane.XY:
                x = cx + radius * math.sin(t)
                y = cy + radius * math.sin(t) * math.cos(t)
                z = cz
            elif params.plane == PatternPlane.XZ:
                x = cx + radius * math.sin(t)
                y = cy
                z = cz + radius * math.sin(t) * math.cos(t)
            else:  # YZ plane
                x = cx
                y = cy + radius * math.sin(t)
                z = cz + radius * math.sin(t) * math.cos(t)

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _generate_star_pattern(self, params: PatternParameters) -> List[Waypoint]:
        """Generate five-pointed star pattern waypoints."""
        waypoints = []
        outer_radius = params.size / 2
        inner_radius = outer_radius * 0.4  # Inner radius is 40% of outer
        cx, cy, cz = params.center

        # Generate 10 points (5 outer, 5 inner) plus return to start
        for i in range(11):
            angle = (2 * math.pi * i / 10) + params.rotation
            radius = outer_radius if i % 2 == 0 else inner_radius

            if params.plane == PatternPlane.XY:
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                z = cz
            elif params.plane == PatternPlane.XZ:
                x = cx + radius * math.cos(angle)
                y = cy
                z = cz + radius * math.sin(angle)
            else:  # YZ plane
                x = cx
                y = cy + radius * math.cos(angle)
                z = cz + radius * math.sin(angle)

            pose = PoseObject(x, y, z, 0, 0, 0)
            waypoints.append(Waypoint(pose=pose))

        return waypoints

    def _rotate_points(self, points: List[Tuple[float, float, float]],
                      angle: float, center: Tuple[float, float, float],
                      plane: PatternPlane) -> List[Tuple[float, float, float]]:
        """
        Rotate points around center in specified plane.

        Args:
            points: Points to rotate
            angle: Rotation angle in radians
            center: Center of rotation
            plane: Plane of rotation

        Returns:
            Rotated points
        """
        rotated_points = []
        cx, cy, cz = center
        cos_a, sin_a = math.cos(angle), math.sin(angle)

        for x, y, z in points:
            if plane == PatternPlane.XY:
                # Rotate in XY plane
                dx, dy = x - cx, y - cy
                new_x = cx + dx * cos_a - dy * sin_a
                new_y = cy + dx * sin_a + dy * cos_a
                new_z = z
            elif plane == PatternPlane.XZ:
                # Rotate in XZ plane
                dx, dz = x - cx, z - cz
                new_x = cx + dx * cos_a - dz * sin_a
                new_y = y
                new_z = cz + dx * sin_a + dz * cos_a
            else:  # YZ plane
                # Rotate in YZ plane
                dy, dz = y - cy, z - cz
                new_x = x
                new_y = cy + dy * cos_a - dz * sin_a
                new_z = cz + dy * sin_a + dz * cos_a

            rotated_points.append((new_x, new_y, new_z))

        return rotated_points

    def _validate_pattern_waypoints(self, waypoints: List[Waypoint]) -> None:
        """
        Validate pattern waypoints against workspace boundaries.

        Args:
            waypoints: Waypoints to validate

        Raises:
            SafetyError: If any waypoint is outside workspace
        """
        boundaries = self._workspace_boundaries

        for i, waypoint in enumerate(waypoints):
            pose = waypoint.pose

            if isinstance(pose, PoseObject):
                if not (boundaries['x'][0] <= pose.x <= boundaries['x'][1]):
                    raise SafetyError(f"Pattern waypoint {i} X coordinate {pose.x} outside workspace")
                if not (boundaries['y'][0] <= pose.y <= boundaries['y'][1]):
                    raise SafetyError(f"Pattern waypoint {i} Y coordinate {pose.y} outside workspace")
                if not (boundaries['z'][0] <= pose.z <= boundaries['z'][1]):
                    raise SafetyError(f"Pattern waypoint {i} Z coordinate {pose.z} outside workspace")

    def _calculate_accuracy_score(self, max_deviation: float, pattern_size: float) -> float:
        """
        Calculate accuracy score based on deviation and pattern size.

        Args:
            max_deviation: Maximum deviation from planned path
            pattern_size: Size of the pattern

        Returns:
            Accuracy score (0-100)
        """
        if pattern_size <= 0:
            return 0.0

        # Calculate relative deviation as percentage of pattern size
        relative_deviation = (max_deviation / pattern_size) * 100

        # Convert to accuracy score (100 - deviation percentage)
        accuracy_score = max(0.0, 100.0 - relative_deviation * 10)  # Scale factor of 10

        return min(100.0, accuracy_score)

    def _execute_workspace_mapping(self) -> PatternResult:
        """Execute workspace mapping calibration routine."""
        logger.info("Starting workspace mapping calibration")

        start_time = time.time()

        try:
            # Define mapping points at workspace boundaries
            boundaries = self._workspace_boundaries
            mapping_points = [
                # Corner points
                (boundaries['x'][0], boundaries['y'][0], boundaries['z'][0]),
                (boundaries['x'][1], boundaries['y'][0], boundaries['z'][0]),
                (boundaries['x'][1], boundaries['y'][1], boundaries['z'][0]),
                (boundaries['x'][0], boundaries['y'][1], boundaries['z'][0]),
                # Center points
                (0, 0, boundaries['z'][0]),
                (0, 0, boundaries['z'][1]),
                # Edge midpoints
                ((boundaries['x'][0] + boundaries['x'][1])/2, 0, boundaries['z'][0]),
                (0, (boundaries['y'][0] + boundaries['y'][1])/2, boundaries['z'][0])
            ]

            waypoints = []
            for x, y, z in mapping_points:
                pose = PoseObject(x, y, z, 0, 0, 0)
                waypoints.append(Waypoint(pose=pose))

            # Execute mapping trajectory
            trajectory_params = TrajectoryParameters(max_speed_percent=30.0)  # Slow for accuracy
            trajectory = self.trajectory_planner.plan_trajectory(waypoints, trajectory_params)
            result = self.trajectory_planner.execute_trajectory(trajectory)

            execution_time = time.time() - start_time
            accuracy_score = self._calculate_accuracy_score(result.max_deviation, 100.0)

            return PatternResult(
                success=result.success,
                pattern_type=PatternType.CUSTOM,
                execution_time=execution_time,
                points_executed=len(waypoints),
                max_deviation=result.max_deviation,
                average_velocity=result.average_velocity,
                accuracy_score=accuracy_score
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return PatternResult(
                success=False,
                pattern_type=PatternType.CUSTOM,
                execution_time=execution_time,
                points_executed=0,
                max_deviation=0.0,
                average_velocity=0.0,
                accuracy_score=0.0,
                error_message=str(e)
            )

    def _execute_accuracy_test(self) -> PatternResult:
        """Execute accuracy test routine."""
        logger.info("Starting accuracy test routine")

        # Execute a precise square pattern for accuracy measurement
        params = PatternParameters(
            size=100.0,
            center=(200.0, 0.0, 200.0),
            points=20,
            speed=25.0  # Very slow for maximum accuracy
        )

        return self.execute_pattern("square", params)

    def _execute_repeatability_test(self) -> PatternResult:
        """Execute repeatability test routine."""
        logger.info("Starting repeatability test routine")

        start_time = time.time()
        deviations = []

        try:
            # Execute same pattern multiple times
            params = PatternParameters(
                size=50.0,
                center=(200.0, 0.0, 200.0),
                points=10,
                speed=50.0
            )

            for i in range(5):  # 5 repetitions
                result = self.execute_pattern("circle", params)
                if result.success:
                    deviations.append(result.max_deviation)
                else:
                    logger.warning(f"Repeatability test iteration {i+1} failed")

            # Calculate repeatability metrics
            if deviations:
                max_deviation = max(deviations)
                avg_deviation = sum(deviations) / len(deviations)
                accuracy_score = self._calculate_accuracy_score(max_deviation, params.size)
            else:
                max_deviation = 0.0
                avg_deviation = 0.0
                accuracy_score = 0.0

            execution_time = time.time() - start_time

            return PatternResult(
                success=len(deviations) > 0,
                pattern_type=PatternType.CUSTOM,
                execution_time=execution_time,
                points_executed=len(deviations) * 10,
                max_deviation=max_deviation,
                average_velocity=0.0,  # Not applicable for repeatability test
                accuracy_score=accuracy_score
            )

        except Exception as e:
            execution_time = time.time() - start_time
            return PatternResult(
                success=False,
                pattern_type=PatternType.CUSTOM,
                execution_time=execution_time,
                points_executed=0,
                max_deviation=0.0,
                average_velocity=0.0,
                accuracy_score=0.0,
                error_message=str(e)
            )

    def _record_pattern_execution(self, execution_data: Dict[str, Any]) -> None:
        """
        Record pattern execution in history.

        Args:
            execution_data: Pattern execution data
        """
        execution_data['timestamp'] = time.time()
        self._execution_history.append(execution_data)

        # Keep only last 100 executions
        if len(self._execution_history) > 100:
            self._execution_history.pop(0)

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        Get pattern execution history.

        Returns:
            List of pattern execution records
        """
        return self._execution_history.copy()

    def clear_execution_history(self) -> None:
        """Clear pattern execution history."""
        self._execution_history.clear()
        logger.info("Pattern execution history cleared")

    def get_pattern_statistics(self) -> Dict[str, Any]:
        """
        Get pattern execution statistics.

        Returns:
            Dictionary with pattern statistics
        """
        if not self._execution_history:
            return {'total_executions': 0, 'success_rate': 0.0}

        total_executions = len(self._execution_history)
        successful_executions = sum(1 for exec_data in self._execution_history if exec_data.get('success', False))
        success_rate = successful_executions / total_executions if total_executions > 0 else 0.0

        # Calculate average accuracy score
        accuracy_scores = [exec_data.get('accuracy_score', 0.0) for exec_data in self._execution_history
                          if exec_data.get('success', False)]
        avg_accuracy = sum(accuracy_scores) / len(accuracy_scores) if accuracy_scores else 0.0

        # Pattern type distribution
        pattern_types = {}
        for exec_data in self._execution_history:
            pattern_type = exec_data.get('pattern_type', 'unknown')
            pattern_types[pattern_type] = pattern_types.get(pattern_type, 0) + 1

        return {
            'total_executions': total_executions,
            'successful_executions': successful_executions,
            'success_rate': success_rate,
            'average_accuracy_score': avg_accuracy,
            'pattern_type_distribution': pattern_types,
            'available_patterns': list(self._patterns.keys())
        }
