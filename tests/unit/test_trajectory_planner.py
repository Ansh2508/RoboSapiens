"""
Unit tests for Trajectory Planner

Tests trajectory planning capabilities including path optimization, collision detection,
and waypoint management.
"""

import pytest
import math
from unittest.mock import Mock, patch

from src.core.trajectory_planner import (
    TrajectoryPlanner, Trajectory, TrajectoryParameters, Waypoint,
    PathType, TrajectoryResult, Obstacle
)
from src.core.robot_controller import RobotController
from src.core.advanced_movement import AdvancedMovementController
from src.utils.error_handler import RoboticsError, SafetyError

try:
    from pyniryo import PoseObject
except ImportError:
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw


class TestTrajectoryPlanner:
    """Test suite for TrajectoryPlanner."""
    
    @pytest.fixture
    def mock_robot_controller(self):
        """Create mock robot controller."""
        mock_controller = Mock(spec=RobotController)
        mock_controller.is_ready = True
        mock_controller.get_position.return_value = PoseObject(200, 0, 200, 0, 0, 0)
        mock_controller._workspace_boundaries = {
            'x': (-300, 300), 'y': (-300, 300), 'z': (0, 400)
        }
        return mock_controller
    
    @pytest.fixture
    def mock_movement_controller(self):
        """Create mock movement controller."""
        mock_controller = Mock(spec=AdvancedMovementController)
        mock_controller.move_cartesian.return_value = Mock(
            success=True, execution_time=1.0, max_deviation=0.5, average_velocity=50.0
        )
        return mock_controller
    
    @pytest.fixture
    def trajectory_planner(self, mock_robot_controller, mock_movement_controller):
        """Create TrajectoryPlanner instance."""
        return TrajectoryPlanner(mock_robot_controller, mock_movement_controller)
    
    def test_initialization(self, trajectory_planner):
        """Test planner initialization."""
        assert trajectory_planner is not None
        assert trajectory_planner.default_params is not None
        assert isinstance(trajectory_planner.default_params, TrajectoryParameters)
    
    def test_is_ready_property(self, trajectory_planner, mock_robot_controller):
        """Test is_ready property."""
        mock_robot_controller.is_ready = True
        assert trajectory_planner.is_ready is True
        
        mock_robot_controller.is_ready = False
        assert trajectory_planner.is_ready is False
    
    def test_add_obstacle(self, trajectory_planner):
        """Test adding obstacles."""
        obstacle = Obstacle(
            name="test_obstacle",
            center=(100, 100, 100),
            radius=50.0
        )
        
        trajectory_planner.add_obstacle(obstacle)
        obstacles = trajectory_planner.get_obstacles()
        assert len(obstacles) == 1
        assert obstacles[0].name == "test_obstacle"
    
    def test_remove_obstacle(self, trajectory_planner):
        """Test removing obstacles."""
        obstacle = Obstacle(name="test_obstacle", center=(100, 100, 100), radius=50.0)
        trajectory_planner.add_obstacle(obstacle)
        
        result = trajectory_planner.remove_obstacle("test_obstacle")
        assert result is True
        assert len(trajectory_planner.get_obstacles()) == 0
        
        # Try removing non-existent obstacle
        result = trajectory_planner.remove_obstacle("non_existent")
        assert result is False
    
    def test_clear_obstacles(self, trajectory_planner):
        """Test clearing all obstacles."""
        obstacle1 = Obstacle(name="obs1", center=(100, 100, 100), radius=50.0)
        obstacle2 = Obstacle(name="obs2", center=(200, 200, 200), radius=30.0)
        
        trajectory_planner.add_obstacle(obstacle1)
        trajectory_planner.add_obstacle(obstacle2)
        assert len(trajectory_planner.get_obstacles()) == 2
        
        trajectory_planner.clear_obstacles()
        assert len(trajectory_planner.get_obstacles()) == 0
    
    def test_plan_trajectory_linear(self, trajectory_planner):
        """Test linear trajectory planning."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250)),
            Waypoint(pose=PoseObject(300, 100, 300))
        ]
        
        params = TrajectoryParameters(path_type=PathType.LINEAR)
        trajectory = trajectory_planner.plan_trajectory(waypoints, params)
        
        assert trajectory is not None
        assert trajectory.path_type == PathType.LINEAR
        assert len(trajectory.waypoints) == 3
        assert trajectory.total_distance > 0
        assert trajectory.estimated_duration > 0
    
    def test_plan_trajectory_bezier(self, trajectory_planner):
        """Test Bezier trajectory planning."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250)),
            Waypoint(pose=PoseObject(300, 100, 300))
        ]
        
        params = TrajectoryParameters(path_type=PathType.BEZIER)
        trajectory = trajectory_planner.plan_trajectory(waypoints, params)
        
        assert trajectory is not None
        assert trajectory.path_type == PathType.BEZIER
        assert len(trajectory.interpolated_points) > len(waypoints)
    
    def test_plan_trajectory_spline(self, trajectory_planner):
        """Test spline trajectory planning."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250)),
            Waypoint(pose=PoseObject(300, 100, 300)),
            Waypoint(pose=PoseObject(350, 150, 350))
        ]
        
        params = TrajectoryParameters(path_type=PathType.SPLINE)
        trajectory = trajectory_planner.plan_trajectory(waypoints, params)
        
        assert trajectory is not None
        assert trajectory.path_type == PathType.SPLINE
        assert len(trajectory.interpolated_points) > len(waypoints)
    
    def test_plan_trajectory_circular(self, trajectory_planner):
        """Test circular trajectory planning."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 200)),
            Waypoint(pose=PoseObject(200, 100, 200))
        ]
        
        params = TrajectoryParameters(path_type=PathType.CIRCULAR)
        trajectory = trajectory_planner.plan_trajectory(waypoints, params)
        
        assert trajectory is not None
        assert trajectory.path_type == PathType.CIRCULAR
    
    def test_plan_trajectory_insufficient_waypoints(self, trajectory_planner):
        """Test trajectory planning with insufficient waypoints."""
        waypoints = [Waypoint(pose=PoseObject(200, 0, 200))]
        
        with pytest.raises(RoboticsError, match="At least 2 waypoints required"):
            trajectory_planner.plan_trajectory(waypoints)
    
    def test_execute_trajectory_success(self, trajectory_planner, mock_movement_controller):
        """Test successful trajectory execution."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        result = trajectory_planner.execute_trajectory(trajectory)
        
        assert result.success is True
        assert result.execution_time > 0
        assert mock_movement_controller.move_cartesian.called
    
    def test_execute_trajectory_robot_not_ready(self, trajectory_planner, mock_robot_controller):
        """Test trajectory execution when robot not ready."""
        mock_robot_controller.is_ready = False
        
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        
        with pytest.raises(RoboticsError, match="Robot is not ready"):
            trajectory_planner.execute_trajectory(trajectory)
    
    def test_collision_detection_no_collision(self, trajectory_planner):
        """Test collision detection with no collision."""
        point = (150, 150, 150)
        result = trajectory_planner._check_collision(point)
        assert result is False
    
    def test_collision_detection_with_collision(self, trajectory_planner):
        """Test collision detection with collision."""
        # Add obstacle
        obstacle = Obstacle(name="test", center=(150, 150, 150), radius=50.0)
        trajectory_planner.add_obstacle(obstacle)
        
        # Point inside obstacle
        point = (160, 160, 160)
        result = trajectory_planner._check_collision(point)
        assert result is True
        
        # Point outside obstacle
        point = (250, 250, 250)
        result = trajectory_planner._check_collision(point)
        assert result is False
    
    def test_validate_trajectory_valid(self, trajectory_planner):
        """Test validation of valid trajectory."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        result = trajectory_planner._validate_trajectory(trajectory)
        assert result is True
    
    def test_validate_trajectory_collision(self, trajectory_planner):
        """Test validation of trajectory with collision."""
        # Add obstacle in path
        obstacle = Obstacle(name="blocker", center=(225, 25, 225), radius=30.0)
        trajectory_planner.add_obstacle(obstacle)
        
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        result = trajectory_planner._validate_trajectory(trajectory)
        assert result is False
    
    def test_calculate_distance(self, trajectory_planner):
        """Test distance calculation between points."""
        point1 = (0, 0, 0)
        point2 = (3, 4, 0)
        
        distance = trajectory_planner._calculate_distance(point1, point2)
        assert abs(distance - 5.0) < 0.01  # 3-4-5 triangle
    
    def test_interpolate_linear(self, trajectory_planner):
        """Test linear interpolation."""
        start = PoseObject(0, 0, 0)
        end = PoseObject(10, 10, 10)
        
        points = trajectory_planner._interpolate_linear(start, end, 5)
        assert len(points) == 6  # 5 steps + 1
        assert points[0].x == 0
        assert points[-1].x == 10
        assert points[2].x == 4  # Middle point
    
    def test_generate_bezier_curve(self, trajectory_planner):
        """Test Bezier curve generation."""
        waypoints = [
            Waypoint(pose=PoseObject(0, 0, 0)),
            Waypoint(pose=PoseObject(5, 10, 5)),
            Waypoint(pose=PoseObject(10, 0, 10))
        ]
        
        points = trajectory_planner._generate_bezier_curve(waypoints, 10)
        assert len(points) == 11  # 10 steps + 1
        assert points[0].x == 0
        assert points[-1].x == 10
    
    def test_generate_spline_curve(self, trajectory_planner):
        """Test spline curve generation."""
        waypoints = [
            Waypoint(pose=PoseObject(0, 0, 0)),
            Waypoint(pose=PoseObject(5, 10, 5)),
            Waypoint(pose=PoseObject(10, 5, 10)),
            Waypoint(pose=PoseObject(15, 0, 15))
        ]
        
        points = trajectory_planner._generate_spline_curve(waypoints, 20)
        assert len(points) == 21  # 20 steps + 1
        assert points[0].x == 0
        assert points[-1].x == 15
    
    def test_generate_circular_arc(self, trajectory_planner):
        """Test circular arc generation."""
        waypoints = [
            Waypoint(pose=PoseObject(10, 0, 0)),
            Waypoint(pose=PoseObject(0, 10, 0)),
            Waypoint(pose=PoseObject(-10, 0, 0))
        ]
        
        points = trajectory_planner._generate_circular_arc(waypoints, 12)
        assert len(points) == 13  # 12 steps + 1
        
        # Check that points form an arc
        center_x = sum(p.x for p in points) / len(points)
        center_y = sum(p.y for p in points) / len(points)
        assert abs(center_x) < 1.0  # Should be close to 0
        assert abs(center_y) < 1.0  # Should be close to 0
    
    def test_optimize_trajectory(self, trajectory_planner):
        """Test trajectory optimization."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250)),
            Waypoint(pose=PoseObject(300, 100, 300))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        original_duration = trajectory.estimated_duration
        
        optimized = trajectory_planner._optimize_trajectory(trajectory)
        
        # Optimization should not increase duration significantly
        assert optimized.estimated_duration <= original_duration * 1.1
    
    def test_trajectory_statistics(self, trajectory_planner):
        """Test trajectory statistics calculation."""
        # Execute a few trajectories
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        for _ in range(3):
            trajectory = trajectory_planner.plan_trajectory(waypoints)
            trajectory_planner.execute_trajectory(trajectory)
        
        stats = trajectory_planner.get_trajectory_statistics()
        assert stats['total_trajectories'] == 3
        assert stats['success_rate'] > 0
        assert 'average_execution_time' in stats
    
    def test_trajectory_history(self, trajectory_planner):
        """Test trajectory history tracking."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        trajectory_planner.execute_trajectory(trajectory)
        
        history = trajectory_planner.get_trajectory_history()
        assert len(history) == 1
        assert history[0]['success'] is True
        
        # Clear history
        trajectory_planner.clear_trajectory_history()
        history = trajectory_planner.get_trajectory_history()
        assert len(history) == 0
    
    def test_waypoint_timing(self, trajectory_planner):
        """Test waypoint timing calculation."""
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200), pause_duration=0.5),
            Waypoint(pose=PoseObject(250, 50, 250), pause_duration=1.0),
            Waypoint(pose=PoseObject(300, 100, 300))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        
        # Should include pause durations in timing
        total_pause_time = sum(w.pause_duration for w in waypoints if w.pause_duration)
        assert trajectory.estimated_duration > total_pause_time
    
    @patch('time.time')
    def test_execution_timing(self, mock_time, trajectory_planner, mock_movement_controller):
        """Test execution timing measurement."""
        mock_time.side_effect = [1000.0, 1002.5]  # 2.5 second execution
        
        waypoints = [
            Waypoint(pose=PoseObject(200, 0, 200)),
            Waypoint(pose=PoseObject(250, 50, 250))
        ]
        
        trajectory = trajectory_planner.plan_trajectory(waypoints)
        result = trajectory_planner.execute_trajectory(trajectory)
        
        assert result.execution_time == 2.5
