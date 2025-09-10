"""
Unit tests for Movement Pattern Library

Tests movement pattern generation, execution, and calibration routines.
"""

import pytest
import math
from unittest.mock import Mock, patch

from src.automation.movement_patterns import (
    MovementPatternLibrary, PatternType, PatternPlane, PatternParameters,
    PatternResult, MovementPattern
)
from src.core.robot_controller import RobotController
from src.core.advanced_movement import AdvancedMovementController
from src.core.trajectory_planner import TrajectoryPlanner, Waypoint
from src.utils.error_handler import RoboticsError, SafetyError

try:
    from pyniryo import PoseObject
except ImportError:
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw


class TestMovementPatternLibrary:
    """Test suite for MovementPatternLibrary."""
    
    @pytest.fixture
    def mock_robot_controller(self):
        """Create mock robot controller."""
        mock_controller = Mock(spec=RobotController)
        mock_controller.is_ready = True
        mock_controller._workspace_boundaries = {
            'x': (-300, 300), 'y': (-300, 300), 'z': (0, 400)
        }
        return mock_controller
    
    @pytest.fixture
    def mock_movement_controller(self):
        """Create mock movement controller."""
        return Mock(spec=AdvancedMovementController)
    
    @pytest.fixture
    def mock_trajectory_planner(self):
        """Create mock trajectory planner."""
        mock_planner = Mock(spec=TrajectoryPlanner)
        mock_trajectory = Mock()
        mock_trajectory.waypoints = []
        mock_planner.plan_trajectory.return_value = mock_trajectory
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.execution_time = 1.0
        mock_result.max_deviation = 0.5
        mock_result.average_velocity = 50.0
        mock_result.error_message = None
        mock_planner.execute_trajectory.return_value = mock_result
        
        return mock_planner
    
    @pytest.fixture
    def pattern_library(self, mock_robot_controller, mock_movement_controller, mock_trajectory_planner):
        """Create MovementPatternLibrary instance."""
        return MovementPatternLibrary(
            mock_robot_controller,
            mock_movement_controller,
            mock_trajectory_planner
        )
    
    def test_initialization(self, pattern_library):
        """Test pattern library initialization."""
        assert pattern_library is not None
        assert pattern_library.default_params is not None
        assert isinstance(pattern_library.default_params, PatternParameters)
        
        # Check that built-in patterns are loaded
        patterns = pattern_library.get_available_patterns()
        assert len(patterns) > 0
        assert "square" in patterns
        assert "circle" in patterns
        assert "triangle" in patterns
    
    def test_is_ready_property(self, pattern_library, mock_robot_controller):
        """Test is_ready property."""
        mock_robot_controller.is_ready = True
        assert pattern_library.is_ready is True
        
        mock_robot_controller.is_ready = False
        assert pattern_library.is_ready is False
    
    def test_set_default_parameters(self, pattern_library):
        """Test setting default parameters."""
        params = PatternParameters(
            size=150.0,
            center=(250.0, 50.0, 250.0),
            plane=PatternPlane.XZ,
            speed=75.0
        )
        
        pattern_library.set_default_parameters(params)
        assert pattern_library.default_params == params
    
    def test_execute_pattern_square(self, pattern_library):
        """Test executing square pattern."""
        result = pattern_library.execute_pattern("square")
        
        assert result.success is True
        assert result.pattern_type == PatternType.SQUARE
        assert result.execution_time > 0
        assert result.accuracy_score >= 0
    
    def test_execute_pattern_circle(self, pattern_library):
        """Test executing circle pattern."""
        params = PatternParameters(size=80.0, points=16)
        result = pattern_library.execute_pattern("circle", params)
        
        assert result.success is True
        assert result.pattern_type == PatternType.CIRCLE
        assert result.points_executed > 0
    
    def test_execute_pattern_unknown(self, pattern_library):
        """Test executing unknown pattern."""
        with pytest.raises(RoboticsError, match="Unknown pattern"):
            pattern_library.execute_pattern("unknown_pattern")
    
    def test_execute_calibration_routine_workspace_mapping(self, pattern_library):
        """Test workspace mapping calibration routine."""
        result = pattern_library.execute_calibration_routine("workspace_mapping")
        
        assert result.success is True
        assert result.pattern_type == PatternType.CUSTOM
        assert result.execution_time > 0
    
    def test_execute_calibration_routine_accuracy_test(self, pattern_library):
        """Test accuracy test calibration routine."""
        result = pattern_library.execute_calibration_routine("accuracy_test")
        
        assert result.success is True
        assert result.accuracy_score >= 0
    
    def test_execute_calibration_routine_repeatability_test(self, pattern_library):
        """Test repeatability test calibration routine."""
        result = pattern_library.execute_calibration_routine("repeatability_test")
        
        assert result.success is True
        assert result.points_executed > 0
    
    def test_execute_calibration_routine_unknown(self, pattern_library):
        """Test unknown calibration routine."""
        with pytest.raises(RoboticsError, match="Unknown calibration routine"):
            pattern_library.execute_calibration_routine("unknown_routine")
    
    def test_add_custom_pattern(self, pattern_library):
        """Test adding custom pattern."""
        custom_pattern = MovementPattern(
            name="custom_test",
            pattern_type=PatternType.CUSTOM,
            description="Test custom pattern",
            difficulty_level=3
        )
        
        pattern_library.add_custom_pattern(custom_pattern)
        
        patterns = pattern_library.get_available_patterns()
        assert "custom_test" in patterns
        assert patterns["custom_test"].difficulty_level == 3
    
    def test_get_pattern_info(self, pattern_library):
        """Test getting pattern information."""
        info = pattern_library.get_pattern_info("square")
        
        assert info is not None
        assert info.name == "square"
        assert info.pattern_type == PatternType.SQUARE
        assert info.difficulty_level == 1
        
        # Test non-existent pattern
        info = pattern_library.get_pattern_info("non_existent")
        assert info is None
    
    def test_generate_square_pattern(self, pattern_library):
        """Test square pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), plane=PatternPlane.XY)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.SQUARE, params)
        
        assert len(waypoints) == 5  # 4 corners + return to start
        
        # Check that it forms a square
        first_point = waypoints[0].pose
        assert first_point.x == 150  # center_x - half_size
        assert first_point.y == -50  # center_y - half_size
    
    def test_generate_circle_pattern(self, pattern_library):
        """Test circle pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), points=8)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.CIRCLE, params)
        
        assert len(waypoints) == 9  # points + 1 to close circle
        
        # Check that points are on circle
        center_x, center_y = 200, 0
        radius = 50  # size / 2
        
        for waypoint in waypoints[:-1]:  # Exclude last point (duplicate of first)
            pose = waypoint.pose
            distance = math.sqrt((pose.x - center_x)**2 + (pose.y - center_y)**2)
            assert abs(distance - radius) < 0.01
    
    def test_generate_triangle_pattern(self, pattern_library):
        """Test triangle pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200))
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.TRIANGLE, params)
        
        assert len(waypoints) == 4  # 3 vertices + return to start
        
        # Check that points form equilateral triangle
        center_x, center_y = 200, 0
        radius = 50  # size / 2
        
        for waypoint in waypoints[:-1]:  # Exclude last point
            pose = waypoint.pose
            distance = math.sqrt((pose.x - center_x)**2 + (pose.y - center_y)**2)
            assert abs(distance - radius) < 0.01
    
    def test_generate_helix_pattern(self, pattern_library):
        """Test helix pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), points=20)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.HELIX, params)
        
        assert len(waypoints) == 20
        
        # Check that Z coordinates increase
        z_coords = [w.pose.z for w in waypoints]
        assert z_coords[0] < z_coords[-1]  # Should ascend
    
    def test_generate_spiral_pattern(self, pattern_library):
        """Test spiral pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), points=16)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.SPIRAL, params)
        
        assert len(waypoints) == 16
        
        # Check that radius increases
        center_x, center_y = 200, 0
        distances = []
        for waypoint in waypoints:
            pose = waypoint.pose
            distance = math.sqrt((pose.x - center_x)**2 + (pose.y - center_y)**2)
            distances.append(distance)
        
        # Distances should generally increase
        assert distances[0] < distances[-1]
    
    def test_generate_zigzag_pattern(self, pattern_library):
        """Test zigzag pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), points=10)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.ZIGZAG, params)
        
        assert len(waypoints) == 6  # points // 2 + 1
        
        # Check alternating Y coordinates
        y_coords = [w.pose.y for w in waypoints]
        for i in range(1, len(y_coords)):
            if i % 2 == 1:
                assert y_coords[i] != y_coords[i-1]  # Should alternate
    
    def test_generate_figure_eight_pattern(self, pattern_library):
        """Test figure-eight pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200), points=16)
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.FIGURE_EIGHT, params)
        
        assert len(waypoints) == 16
        
        # Check that pattern crosses center
        center_x, center_y = 200, 0
        min_distance = min(
            math.sqrt((w.pose.x - center_x)**2 + (w.pose.y - center_y)**2)
            for w in waypoints
        )
        assert min_distance < 10  # Should pass close to center
    
    def test_generate_star_pattern(self, pattern_library):
        """Test star pattern generation."""
        params = PatternParameters(size=100.0, center=(200, 0, 200))
        waypoints = pattern_library._generate_pattern_waypoints(PatternType.STAR, params)
        
        assert len(waypoints) == 11  # 10 points + return to start
        
        # Check alternating radii (outer and inner points)
        center_x, center_y = 200, 0
        distances = []
        for waypoint in waypoints[:-1]:  # Exclude last point
            pose = waypoint.pose
            distance = math.sqrt((pose.x - center_x)**2 + (pose.y - center_y)**2)
            distances.append(distance)
        
        # Should have two distinct radii
        unique_distances = set(round(d, 1) for d in distances)
        assert len(unique_distances) == 2
    
    def test_rotate_points(self, pattern_library):
        """Test point rotation."""
        points = [(100, 0, 0), (0, 100, 0)]
        angle = math.pi / 2  # 90 degrees
        center = (0, 0, 0)
        
        rotated = pattern_library._rotate_points(points, angle, center, PatternPlane.XY)
        
        # First point (100, 0, 0) should become (0, 100, 0)
        assert abs(rotated[0][0] - 0) < 0.01
        assert abs(rotated[0][1] - 100) < 0.01
        
        # Second point (0, 100, 0) should become (-100, 0, 0)
        assert abs(rotated[1][0] - (-100)) < 0.01
        assert abs(rotated[1][1] - 0) < 0.01
    
    def test_validate_pattern_waypoints_valid(self, pattern_library):
        """Test validation of valid pattern waypoints."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        # Should not raise exception
        pattern_library._validate_pattern_waypoints(waypoints)
    
    def test_validate_pattern_waypoints_invalid(self, pattern_library):
        """Test validation of invalid pattern waypoints."""
        waypoints = [
            Waypoint(pose=PoseObject(500, 0, 200))  # X > 300 (outside workspace)
        ]
        
        with pytest.raises(SafetyError, match="outside workspace"):
            pattern_library._validate_pattern_waypoints(waypoints)
    
    def test_calculate_accuracy_score(self, pattern_library):
        """Test accuracy score calculation."""
        # Perfect accuracy (no deviation)
        score = pattern_library._calculate_accuracy_score(0.0, 100.0)
        assert score == 100.0
        
        # Some deviation
        score = pattern_library._calculate_accuracy_score(5.0, 100.0)
        assert 0 <= score <= 100
        assert score < 100
        
        # Large deviation
        score = pattern_library._calculate_accuracy_score(50.0, 100.0)
        assert score == 0.0
    
    def test_execution_history(self, pattern_library):
        """Test execution history tracking."""
        # Initially empty
        history = pattern_library.get_execution_history()
        assert len(history) == 0
        
        # Execute a pattern
        pattern_library.execute_pattern("square")
        
        history = pattern_library.get_execution_history()
        assert len(history) == 1
        assert history[0]['pattern_name'] == 'square'
        assert 'timestamp' in history[0]
        
        # Clear history
        pattern_library.clear_execution_history()
        history = pattern_library.get_execution_history()
        assert len(history) == 0
    
    def test_pattern_statistics(self, pattern_library):
        """Test pattern statistics."""
        # Execute some patterns
        pattern_library.execute_pattern("square")
        pattern_library.execute_pattern("circle")
        
        stats = pattern_library.get_pattern_statistics()
        
        assert stats['total_executions'] == 2
        assert stats['success_rate'] > 0
        assert 'average_accuracy_score' in stats
        assert 'pattern_type_distribution' in stats
        assert 'available_patterns' in stats
    
    def test_pattern_parameters_different_planes(self, pattern_library):
        """Test pattern generation in different planes."""
        params_xy = PatternParameters(plane=PatternPlane.XY)
        params_xz = PatternParameters(plane=PatternPlane.XZ)
        params_yz = PatternParameters(plane=PatternPlane.YZ)
        
        waypoints_xy = pattern_library._generate_pattern_waypoints(PatternType.SQUARE, params_xy)
        waypoints_xz = pattern_library._generate_pattern_waypoints(PatternType.SQUARE, params_xz)
        waypoints_yz = pattern_library._generate_pattern_waypoints(PatternType.SQUARE, params_yz)
        
        # All should have same number of waypoints
        assert len(waypoints_xy) == len(waypoints_xz) == len(waypoints_yz)
        
        # But different coordinate variations
        xy_z_coords = [w.pose.z for w in waypoints_xy]
        xz_y_coords = [w.pose.y for w in waypoints_xz]
        yz_x_coords = [w.pose.x for w in waypoints_yz]
        
        # XY plane should have constant Z
        assert len(set(xy_z_coords)) == 1
        
        # XZ plane should have constant Y
        assert len(set(xz_y_coords)) == 1
        
        # YZ plane should have constant X
        assert len(set(yz_x_coords)) == 1
    
    @patch('time.time')
    def test_execution_timing(self, mock_time, pattern_library):
        """Test execution timing measurement."""
        mock_time.side_effect = [1000.0, 1001.5]  # 1.5 second execution
        
        result = pattern_library.execute_pattern("square")
        
        assert result.execution_time == 1.5
