"""
Unit tests for Advanced Movement Controller

Tests the advanced movement control capabilities including Cartesian and joint space control,
velocity profiling, and path interpolation.
"""

import pytest
import time
import math
from unittest.mock import Mock, patch, MagicMock

from src.core.advanced_movement import (
    AdvancedMovementController, MovementParameters, VelocityProfile,
    MovementResult, MovementType
)
from src.core.robot_controller import RobotController
from src.utils.error_handler import RoboticsError, SafetyError

try:
    from pyniryo import PoseObject, JointsPosition
except ImportError:
    # Mock classes for testing
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw
    
    class JointsPosition:
        def __init__(self, joints):
            self.joints = joints


class TestAdvancedMovementController:
    """Test suite for AdvancedMovementController."""
    
    @pytest.fixture
    def mock_robot_controller(self):
        """Create mock robot controller."""
        mock_controller = Mock(spec=RobotController)
        mock_controller.is_ready = True
        mock_controller.get_position.return_value = PoseObject(200, 0, 200, 0, 0, 0)
        mock_controller.get_joints.return_value = [0, 0, 0, 0, 0, 0]
        mock_controller.move_to_pose.return_value = True
        mock_controller.move_to_joints.return_value = True
        mock_controller._workspace_boundaries = {
            'x': (-300, 300), 'y': (-300, 300), 'z': (0, 400),
            'roll': (-3.14, 3.14), 'pitch': (-3.14, 3.14), 'yaw': (-3.14, 3.14)
        }
        mock_controller._robot = Mock()
        mock_controller._robot.set_arm_max_velocity = Mock()
        return mock_controller
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        mock_config = Mock()
        mock_config.get_robot_config.return_value = Mock(max_velocity_percent=50)
        return mock_config
    
    @pytest.fixture
    def advanced_movement(self, mock_robot_controller, mock_config_manager):
        """Create AdvancedMovementController instance."""
        return AdvancedMovementController(mock_robot_controller, mock_config_manager)
    
    def test_initialization(self, advanced_movement):
        """Test controller initialization."""
        assert advanced_movement is not None
        assert advanced_movement.default_params is not None
        assert isinstance(advanced_movement.default_params, MovementParameters)
    
    def test_is_ready_property(self, advanced_movement, mock_robot_controller):
        """Test is_ready property."""
        mock_robot_controller.is_ready = True
        assert advanced_movement.is_ready is True
        
        mock_robot_controller.is_ready = False
        assert advanced_movement.is_ready is False
    
    def test_current_position_property(self, advanced_movement, mock_robot_controller):
        """Test current_position property."""
        expected_pose = PoseObject(100, 50, 150, 0, 0, 0)
        mock_robot_controller.get_position.return_value = expected_pose
        
        result = advanced_movement.current_position
        assert result == expected_pose
        mock_robot_controller.get_position.assert_called_once()
    
    def test_current_joints_property(self, advanced_movement, mock_robot_controller):
        """Test current_joints property."""
        expected_joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        mock_robot_controller.get_joints.return_value = expected_joints
        
        result = advanced_movement.current_joints
        assert result == expected_joints
        mock_robot_controller.get_joints.assert_called_once()
    
    def test_set_movement_parameters(self, advanced_movement):
        """Test setting movement parameters."""
        params = MovementParameters(
            max_velocity=75.0,
            acceleration=40.0,
            velocity_profile=VelocityProfile.S_CURVE
        )
        
        advanced_movement.set_movement_parameters(params)
        assert advanced_movement.default_params == params
    
    def test_move_cartesian_success(self, advanced_movement, mock_robot_controller):
        """Test successful Cartesian movement."""
        target = PoseObject(250, 100, 250, 0, 0, 0)
        
        result = advanced_movement.move_cartesian(target)
        
        assert result.success is True
        assert result.execution_time > 0
        assert len(result.actual_path) > 0
        mock_robot_controller.move_to_pose.assert_called()
    
    def test_move_cartesian_robot_not_ready(self, advanced_movement, mock_robot_controller):
        """Test Cartesian movement when robot not ready."""
        mock_robot_controller.is_ready = False
        target = PoseObject(250, 100, 250, 0, 0, 0)
        
        with pytest.raises(RoboticsError, match="Robot is not ready"):
            advanced_movement.move_cartesian(target)
    
    def test_move_cartesian_unsafe_position(self, advanced_movement):
        """Test Cartesian movement to unsafe position."""
        # Position outside workspace boundaries
        target = PoseObject(500, 0, 200, 0, 0, 0)  # X > 300
        
        result = advanced_movement.move_cartesian(target)
        assert result.success is False
        assert "outside workspace boundaries" in result.error_message
    
    def test_move_joints_success(self, advanced_movement, mock_robot_controller):
        """Test successful joint movement."""
        target_joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        
        result = advanced_movement.move_joints(target_joints)
        
        assert result.success is True
        assert result.execution_time > 0
        assert len(result.actual_path) > 0
        mock_robot_controller.move_to_joints.assert_called()
    
    def test_move_joints_with_joints_position(self, advanced_movement, mock_robot_controller):
        """Test joint movement with JointsPosition object."""
        target_joints = JointsPosition([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        
        result = advanced_movement.move_joints(target_joints)
        
        assert result.success is True
        mock_robot_controller.move_to_joints.assert_called()
    
    def test_move_joints_unsafe_positions(self, advanced_movement):
        """Test joint movement with unsafe positions."""
        # Joint positions outside safe limits
        target_joints = [5.0, 0, 0, 0, 0, 0]  # Joint 1 > 3.14
        
        result = advanced_movement.move_joints(target_joints)
        assert result.success is False
        assert "outside safe limits" in result.error_message
    
    def test_validate_cartesian_position_valid(self, advanced_movement):
        """Test validation of valid Cartesian position."""
        pose = PoseObject(200, 100, 200, 1.0, 1.0, 1.0)
        result = advanced_movement._validate_cartesian_position(pose)
        assert result is True
    
    def test_validate_cartesian_position_invalid(self, advanced_movement):
        """Test validation of invalid Cartesian position."""
        pose = PoseObject(400, 0, 200, 0, 0, 0)  # X > 300
        result = advanced_movement._validate_cartesian_position(pose)
        assert result is False
    
    def test_validate_joint_positions_valid(self, advanced_movement):
        """Test validation of valid joint positions."""
        joints = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        result = advanced_movement._validate_joint_positions(joints)
        assert result is True
    
    def test_validate_joint_positions_invalid(self, advanced_movement):
        """Test validation of invalid joint positions."""
        joints = [5.0, 0, 0, 0, 0, 0]  # Joint 1 > 3.14
        result = advanced_movement._validate_joint_positions(joints)
        assert result is False
    
    def test_generate_cartesian_path(self, advanced_movement):
        """Test Cartesian path generation."""
        start = PoseObject(200, 0, 200, 0, 0, 0)
        end = PoseObject(250, 50, 250, 0, 0, 0)
        params = MovementParameters(interpolation_steps=10)
        
        path = advanced_movement._generate_cartesian_path(start, end, params)
        
        assert len(path) == 11  # interpolation_steps + 1
        assert path[0].x == start.x
        assert path[-1].x == end.x
    
    def test_generate_joint_path(self, advanced_movement):
        """Test joint path generation."""
        start = [0, 0, 0, 0, 0, 0]
        end = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        params = MovementParameters(interpolation_steps=5)
        
        path = advanced_movement._generate_joint_path(start, end, params)
        
        assert len(path) == 6  # interpolation_steps + 1
        assert path[0] == start
        assert path[-1] == end
    
    def test_apply_velocity_profile_trapezoidal(self, advanced_movement):
        """Test trapezoidal velocity profile."""
        result = advanced_movement._apply_velocity_profile(0.5, VelocityProfile.TRAPEZOIDAL)
        assert 0 <= result <= 1
    
    def test_apply_velocity_profile_s_curve(self, advanced_movement):
        """Test S-curve velocity profile."""
        result = advanced_movement._apply_velocity_profile(0.5, VelocityProfile.S_CURVE)
        assert 0 <= result <= 1
    
    def test_apply_velocity_profile_sinusoidal(self, advanced_movement):
        """Test sinusoidal velocity profile."""
        result = advanced_movement._apply_velocity_profile(0.5, VelocityProfile.SINUSOIDAL)
        assert 0 <= result <= 1
    
    def test_interpolate_angle(self, advanced_movement):
        """Test angle interpolation with wrap-around."""
        # Test normal interpolation
        result = advanced_movement._interpolate_angle(0, math.pi/2, 0.5)
        assert abs(result - math.pi/4) < 0.01
        
        # Test wrap-around
        result = advanced_movement._interpolate_angle(-math.pi, math.pi, 0.5)
        assert abs(result) < 0.01  # Should be close to 0
    
    def test_calculate_path_deviation(self, advanced_movement):
        """Test path deviation calculation."""
        planned = [PoseObject(0, 0, 0), PoseObject(10, 0, 0)]
        actual = [PoseObject(1, 0, 0), PoseObject(11, 0, 0)]
        
        deviation = advanced_movement._calculate_path_deviation(planned, actual)
        assert abs(deviation - 1.0) < 0.01  # 1mm deviation
    
    def test_calculate_average_velocity(self, advanced_movement):
        """Test average velocity calculation."""
        path = [PoseObject(0, 0, 0), PoseObject(10, 0, 0), PoseObject(20, 0, 0)]
        execution_time = 2.0
        
        velocity = advanced_movement._calculate_average_velocity(path, execution_time)
        assert abs(velocity - 10.0) < 0.01  # 20mm in 2s = 10mm/s
    
    def test_movement_history(self, advanced_movement):
        """Test movement history tracking."""
        # Initially empty
        history = advanced_movement.get_movement_history()
        assert len(history) == 0
        
        # Record a movement
        advanced_movement._record_movement({
            'type': 'test',
            'success': True,
            'execution_time': 1.0
        })
        
        history = advanced_movement.get_movement_history()
        assert len(history) == 1
        assert history[0]['type'] == 'test'
        
        # Clear history
        advanced_movement.clear_movement_history()
        history = advanced_movement.get_movement_history()
        assert len(history) == 0
    
    def test_velocity_profile_parameters(self, advanced_movement):
        """Test different velocity profile parameters."""
        params = MovementParameters(
            max_velocity=30.0,
            velocity_profile=VelocityProfile.S_CURVE,
            interpolation_steps=20
        )
        
        start = PoseObject(200, 0, 200, 0, 0, 0)
        end = PoseObject(250, 0, 200, 0, 0, 0)
        
        path = advanced_movement._generate_cartesian_path(start, end, params)
        assert len(path) == 21  # interpolation_steps + 1
    
    @patch('time.time')
    def test_execution_timing(self, mock_time, advanced_movement, mock_robot_controller):
        """Test execution timing measurement."""
        mock_time.side_effect = [1000.0, 1001.5]  # 1.5 second execution
        
        target = PoseObject(250, 100, 250, 0, 0, 0)
        result = advanced_movement.move_cartesian(target)
        
        assert result.execution_time == 1.5
