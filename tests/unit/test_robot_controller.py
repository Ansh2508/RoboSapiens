"""
Unit tests for RobotController class.

These tests verify the core functionality of the robot controller
including connection management, movement control, and error handling.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from typing import List

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.robot_controller import RobotController, RobotState, RobotStatus
from src.utils.config_manager import get_config_manager
from src.utils.error_handler import ConnectionError, CalibrationError, SafetyError, RoboticsError


class TestRobotController:
    """Test cases for RobotController class."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock()
        robot_config = Mock()
        robot_config.ip = "169.254.200.200"
        robot_config.timeout = 10
        robot_config.max_velocity_percent = 50
        robot_config.workspace_boundaries_enabled = True
        robot_config.status_update_interval = 1.0
        
        config_manager.get_robot_config.return_value = robot_config
        return config_manager
    
    @pytest.fixture
    def robot_controller(self, mock_config_manager):
        """Create RobotController instance with mocked dependencies."""
        with patch('src.core.robot_controller.get_config_manager', return_value=mock_config_manager):
            controller = RobotController()
            return controller
    
    @pytest.fixture
    def mock_niryo_robot(self):
        """Create mock NiryoRobot instance."""
        mock_robot = Mock()
        mock_robot.calibrate_auto.return_value = None
        mock_robot.close_connection.return_value = None
        mock_robot.get_pose.return_value = Mock()
        mock_robot.get_joints.return_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        mock_robot.move.return_value = None
        mock_robot.led_ring_flashing.return_value = None
        mock_robot.wait.return_value = None
        mock_robot.move_to_home_pose.return_value = None
        mock_robot.set_arm_max_velocity.return_value = None
        mock_robot.grasp_with_tool.return_value = None
        mock_robot.release_with_tool.return_value = None
        mock_robot.update_tool.return_value = None
        return mock_robot
    
    def test_initialization(self, robot_controller):
        """Test robot controller initialization."""
        assert robot_controller.status.state == RobotState.DISCONNECTED
        assert not robot_controller.is_connected
        assert not robot_controller.is_ready
        assert robot_controller._emergency_stop_active is False
    
    def test_workspace_boundaries_loading(self, robot_controller):
        """Test workspace boundaries are loaded correctly."""
        boundaries = robot_controller._workspace_boundaries
        assert 'x' in boundaries
        assert 'y' in boundaries
        assert 'z' in boundaries
        assert boundaries['x'] == (-300, 300)
        assert boundaries['y'] == (-300, 300)
        assert boundaries['z'] == (0, 400)
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_successful_connection(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test successful robot connection."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Test connection
        result = robot_controller.connect()
        
        assert result is True
        assert robot_controller.is_connected
        assert robot_controller.status.state == RobotState.CONNECTED
        assert robot_controller.status.connection_time is not None
        assert robot_controller.status.last_error is None
        
        # Verify NiryoRobot was called with correct IP
        mock_niryo_class.assert_called_once_with("169.254.200.200")
        mock_niryo_robot.led_ring_flashing.assert_called_once()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_connection_failure(self, mock_niryo_class, robot_controller):
        """Test robot connection failure."""
        mock_niryo_class.side_effect = Exception("Connection failed")
        
        # Test connection failure
        with pytest.raises(ConnectionError):
            robot_controller.connect()
        
        assert not robot_controller.is_connected
        assert robot_controller.status.state == RobotState.ERROR
        assert robot_controller.status.last_error is not None
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_connection_with_custom_ip(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test connection with custom IP address."""
        mock_niryo_class.return_value = mock_niryo_robot
        custom_ip = "192.168.1.100"
        
        result = robot_controller.connect(ip=custom_ip)
        
        assert result is True
        mock_niryo_class.assert_called_once_with(custom_ip)
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_disconnect(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test robot disconnection."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Connect first
        robot_controller.connect()
        assert robot_controller.is_connected
        
        # Test disconnection
        robot_controller.disconnect()
        
        assert not robot_controller.is_connected
        assert robot_controller.status.state == RobotState.DISCONNECTED
        assert robot_controller.status.connection_time is None
        mock_niryo_robot.close_connection.assert_called_once()
    
    def test_disconnect_when_not_connected(self, robot_controller):
        """Test disconnection when not connected."""
        # Should not raise exception
        robot_controller.disconnect()
        assert not robot_controller.is_connected
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_calibration_success(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test successful robot calibration."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Connect first
        robot_controller.connect()
        
        # Test calibration
        result = robot_controller.calibrate()
        
        assert result is True
        assert robot_controller.status.state == RobotState.READY
        assert robot_controller.status.calibration_time is not None
        assert robot_controller.is_ready
        
        mock_niryo_robot.calibrate_auto.assert_called_once()
        mock_niryo_robot.set_arm_max_velocity.assert_called_once_with(50)
        mock_niryo_robot.update_tool.assert_called_once()
    
    def test_calibration_without_connection(self, robot_controller):
        """Test calibration without connection."""
        with pytest.raises(CalibrationError):
            robot_controller.calibrate()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_calibration_failure(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test calibration failure."""
        mock_niryo_class.return_value = mock_niryo_robot
        mock_niryo_robot.calibrate_auto.side_effect = Exception("Calibration failed")
        
        # Connect first
        robot_controller.connect()
        
        # Test calibration failure
        with pytest.raises(CalibrationError):
            robot_controller.calibrate()
        
        assert robot_controller.status.state == RobotState.ERROR
        assert robot_controller.status.last_error is not None
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_get_position(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test getting robot position."""
        mock_niryo_class.return_value = mock_niryo_robot
        mock_pose = Mock()
        mock_niryo_robot.get_pose.return_value = mock_pose
        
        # Connect first
        robot_controller.connect()
        
        # Test position reading
        position = robot_controller.get_position()
        
        assert position == mock_pose
        assert robot_controller.status.position == mock_pose
        mock_niryo_robot.get_pose.assert_called_once()
    
    def test_get_position_without_connection(self, robot_controller):
        """Test getting position without connection."""
        position = robot_controller.get_position()
        assert position is None
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_get_joints(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test getting joint positions."""
        mock_niryo_class.return_value = mock_niryo_robot
        expected_joints = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
        mock_niryo_robot.get_joints.return_value = expected_joints
        
        # Connect first
        robot_controller.connect()
        
        # Test joint reading
        joints = robot_controller.get_joints()
        
        assert joints == expected_joints
        assert robot_controller.status.joints == expected_joints
        mock_niryo_robot.get_joints.assert_called_once()
    
    def test_get_joints_without_connection(self, robot_controller):
        """Test getting joints without connection."""
        joints = robot_controller.get_joints()
        assert joints is None
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_move_to_home(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test moving to home position."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Connect and calibrate first
        robot_controller.connect()
        robot_controller.calibrate()
        
        # Test move to home
        result = robot_controller.move_to_home()
        
        assert result is True
        assert robot_controller.status.state == RobotState.READY
        mock_niryo_robot.move_to_home_pose.assert_called_once()
    
    def test_move_to_home_not_ready(self, robot_controller):
        """Test moving to home when robot is not ready."""
        with pytest.raises(RoboticsError):
            robot_controller.move_to_home()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_grasp_and_release(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test tool grasp and release operations."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Connect and calibrate first
        robot_controller.connect()
        robot_controller.calibrate()
        
        # Test grasp
        result = robot_controller.grasp()
        assert result is True
        mock_niryo_robot.grasp_with_tool.assert_called_once()
        
        # Test release
        result = robot_controller.release()
        assert result is True
        mock_niryo_robot.release_with_tool.assert_called_once()
    
    def test_grasp_not_ready(self, robot_controller):
        """Test grasp when robot is not ready."""
        with pytest.raises(RoboticsError):
            robot_controller.grasp()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_led_control(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test LED control functionality."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Connect first
        robot_controller.connect()
        
        # Test LED control
        color = [255, 0, 0]
        duration = 1.0
        iterations = 3
        
        result = robot_controller.led_control(color, duration, iterations)
        
        assert result is True
        mock_niryo_robot.led_ring_flashing.assert_called_with(color, duration, iterations, True)
    
    def test_led_control_without_connection(self, robot_controller):
        """Test LED control without connection."""
        result = robot_controller.led_control([255, 0, 0])
        assert result is False
    
    def test_emergency_stop(self, robot_controller):
        """Test emergency stop functionality."""
        robot_controller.emergency_stop()
        
        assert robot_controller._emergency_stop_active is True
        assert robot_controller.status.state == RobotState.EMERGENCY_STOP
    
    def test_reset_emergency_stop(self, robot_controller):
        """Test emergency stop reset."""
        # Activate emergency stop first
        robot_controller.emergency_stop()
        assert robot_controller._emergency_stop_active is True
        
        # Reset emergency stop
        robot_controller.reset_emergency_stop()
        assert robot_controller._emergency_stop_active is False
        assert robot_controller.status.state == RobotState.DISCONNECTED
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_context_manager(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test robot controller as context manager."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        with robot_controller:
            # Should be able to use controller within context
            pass
        
        # Should be disconnected after context
        assert not robot_controller.is_connected
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_robot_connection_context_manager(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test robot connection context manager."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        with robot_controller.robot_connection() as robot:
            assert robot == mock_niryo_robot
            assert robot_controller.is_connected
        
        # Should be disconnected after context
        assert not robot_controller.is_connected
    
    def test_position_validation(self, robot_controller):
        """Test position validation functionality."""
        # Mock pose object
        mock_pose = Mock()
        
        # Test validation (should return True for now)
        result = robot_controller._validate_position(mock_pose)
        assert result is True
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_wait_functionality(self, mock_niryo_class, robot_controller, mock_niryo_robot):
        """Test wait functionality."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Test with robot connected
        robot_controller.connect()
        robot_controller.wait(0.1)
        mock_niryo_robot.wait.assert_called_once_with(0.1)
        
        # Test without robot connected
        robot_controller.disconnect()
        start_time = time.time()
        robot_controller.wait(0.1)
        elapsed = time.time() - start_time
        assert elapsed >= 0.1
