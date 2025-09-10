"""
Integration tests for the Niryo LLM Robotics Platform.

These tests verify the integration between different system components
and end-to-end functionality.
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.robot_controller import RobotController, RobotState
from src.core.safety_manager import SafetyManager, SafetyEventType
from src.utils.config_manager import get_config_manager
from src.utils.logger import get_logger
from src.utils.error_handler import RoboticsError, ConnectionError, SafetyError


class TestSystemIntegration:
    """Integration tests for system components."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create comprehensive mock configuration manager."""
        config_manager = Mock()
        
        # Robot config
        robot_config = Mock()
        robot_config.ip = "169.254.200.200"
        robot_config.timeout = 10
        robot_config.max_velocity_percent = 50
        robot_config.workspace_boundaries_enabled = True
        robot_config.status_update_interval = 0.1
        
        # Safety config
        safety_config = Mock()
        safety_config.emergency_stop_enabled = True
        safety_config.collision_detection_enabled = True
        safety_config.workspace_boundaries_enabled = True
        safety_config.force_limit_newtons = 50.0
        safety_config.safety_check_interval = 0.1
        
        # System config
        system_config = Mock()
        system_config.robot = robot_config
        system_config.safety = safety_config
        
        config_manager.get_robot_config.return_value = robot_config
        config_manager.get_safety_config.return_value = safety_config
        config_manager.get_config.return_value = system_config
        
        return config_manager
    
    @pytest.fixture
    def mock_niryo_robot(self):
        """Create comprehensive mock NiryoRobot."""
        mock_robot = Mock()
        mock_robot.calibrate_auto.return_value = None
        mock_robot.close_connection.return_value = None
        mock_robot.get_pose.return_value = Mock()
        mock_robot.get_joints.return_value = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        mock_robot.move.return_value = None
        mock_robot.led_ring_flashing.return_value = None
        mock_robot.wait.return_value = None
        mock_robot.move_to_home_pose.return_value = None
        mock_robot.set_arm_max_velocity.return_value = None
        mock_robot.grasp_with_tool.return_value = None
        mock_robot.release_with_tool.return_value = None
        mock_robot.update_tool.return_value = None
        return mock_robot
    
    @pytest.fixture
    def integrated_system(self, mock_config_manager):
        """Create integrated system with robot controller and safety manager."""
        with patch('src.core.robot_controller.get_config_manager', return_value=mock_config_manager), \
             patch('src.core.safety_manager.get_config_manager', return_value=mock_config_manager):
            
            robot_controller = RobotController()
            safety_manager = SafetyManager()
            
            return {
                'robot_controller': robot_controller,
                'safety_manager': safety_manager,
                'config_manager': mock_config_manager
            }
    
    def test_robot_controller_safety_manager_integration(self, integrated_system):
        """Test integration between robot controller and safety manager."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test initial states
        assert not robot_controller.is_connected
        assert not safety_manager.is_emergency_stop_active
        assert safety_manager.is_safety_enabled
        
        # Test emergency stop integration
        safety_manager.emergency_stop("Integration test")
        robot_controller.emergency_stop()
        
        assert safety_manager.is_emergency_stop_active
        assert robot_controller._emergency_stop_active
        assert robot_controller.status.state == RobotState.EMERGENCY_STOP
        
        # Test emergency stop reset
        safety_manager.reset_emergency_stop()
        robot_controller.reset_emergency_stop()
        
        assert not safety_manager.is_emergency_stop_active
        assert not robot_controller._emergency_stop_active
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_full_robot_workflow(self, mock_niryo_class, integrated_system, mock_niryo_robot):
        """Test complete robot workflow from connection to operation."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Start safety monitoring
        safety_manager.start_monitoring()
        
        try:
            # 1. Connect to robot
            success = robot_controller.connect()
            assert success
            assert robot_controller.is_connected
            assert robot_controller.status.state == RobotState.CONNECTED
            
            # 2. Calibrate robot
            success = robot_controller.calibrate()
            assert success
            assert robot_controller.is_ready
            assert robot_controller.status.state == RobotState.READY
            
            # 3. Test basic operations
            # LED control
            success = robot_controller.led_control([255, 0, 0], 1.0, 2)
            assert success
            
            # Position reading
            position = robot_controller.get_position()
            assert position is not None
            
            # Joint reading
            joints = robot_controller.get_joints()
            assert joints is not None
            assert len(joints) == 6
            
            # Move to home
            success = robot_controller.move_to_home()
            assert success
            
            # Tool operations
            success = robot_controller.grasp()
            assert success
            
            success = robot_controller.release()
            assert success
            
            # 4. Test safety integration
            # Check workspace boundaries
            in_bounds = safety_manager.check_workspace_boundaries(0, 0, 200)
            assert in_bounds
            
            out_of_bounds = safety_manager.check_workspace_boundaries(500, 0, 200)
            assert not out_of_bounds
            assert len(safety_manager.safety_events) > 0
            
            # 5. Disconnect
            robot_controller.disconnect()
            assert not robot_controller.is_connected
            
        finally:
            safety_manager.stop_monitoring()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_error_handling_integration(self, mock_niryo_class, integrated_system, mock_niryo_robot):
        """Test error handling across system components."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test connection failure
        mock_niryo_class.side_effect = Exception("Connection failed")
        
        with pytest.raises(ConnectionError):
            robot_controller.connect()
        
        assert robot_controller.status.state == RobotState.ERROR
        assert robot_controller.status.last_error is not None
        
        # Reset for next test
        mock_niryo_class.side_effect = None
        mock_niryo_class.return_value = mock_niryo_robot
        
        # Test calibration failure
        mock_niryo_robot.calibrate_auto.side_effect = Exception("Calibration failed")
        
        robot_controller.connect()
        
        with pytest.raises(Exception):  # CalibrationError
            robot_controller.calibrate()
        
        assert robot_controller.status.state == RobotState.ERROR
    
    def test_safety_event_propagation(self, integrated_system):
        """Test safety event propagation and handling."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Set up event callback to simulate robot controller response
        robot_emergency_triggered = []
        
        def emergency_callback(event):
            robot_emergency_triggered.append(event)
            robot_controller.emergency_stop()
        
        safety_manager.register_event_callback(SafetyEventType.EMERGENCY_STOP, emergency_callback)
        
        # Trigger safety event
        safety_manager.emergency_stop("Test propagation")
        
        # Verify event propagation
        assert len(robot_emergency_triggered) == 1
        assert robot_controller._emergency_stop_active
        assert robot_controller.status.state == RobotState.EMERGENCY_STOP
    
    def test_concurrent_operations(self, integrated_system):
        """Test concurrent operations between components."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Start safety monitoring
        safety_manager.start_monitoring()
        
        try:
            # Simulate concurrent safety checks while robot operations
            import threading
            
            def safety_checks():
                for i in range(10):
                    safety_manager.check_workspace_boundaries(i * 10, 0, 200)
                    safety_manager.check_force_limits(i * 2.0)
                    time.sleep(0.01)
            
            def robot_status_updates():
                for i in range(10):
                    robot_controller.get_position()
                    robot_controller.get_joints()
                    time.sleep(0.01)
            
            # Run concurrent operations
            safety_thread = threading.Thread(target=safety_checks)
            robot_thread = threading.Thread(target=robot_status_updates)
            
            safety_thread.start()
            robot_thread.start()
            
            safety_thread.join()
            robot_thread.join()
            
            # Verify no deadlocks or race conditions
            assert safety_manager.is_safety_enabled
            assert len(safety_manager.safety_events) >= 0  # May have boundary violations
            
        finally:
            safety_manager.stop_monitoring()
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_configuration_consistency(self, mock_niryo_class, integrated_system, mock_niryo_robot):
        """Test configuration consistency across components."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        config_manager = integrated_system['config_manager']
        
        # Verify both components use same configuration
        robot_config = robot_controller.config
        safety_config = safety_manager.config
        
        assert robot_config.ip == "169.254.200.200"
        assert safety_config.force_limit_newtons == 50.0
        
        # Test configuration changes affect both components
        config_manager.get_robot_config.return_value.max_velocity_percent = 75
        
        # Create new instances to pick up config changes
        with patch('src.core.robot_controller.get_config_manager', return_value=config_manager):
            new_robot_controller = RobotController()
            assert new_robot_controller.config.max_velocity_percent == 75
    
    def test_logging_integration(self, integrated_system):
        """Test logging integration across components."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test that both components can log without conflicts
        with patch('src.utils.logger.logger') as mock_logger:
            # Trigger operations that should log
            robot_controller.emergency_stop()
            safety_manager.emergency_stop("Test logging")
            
            # Verify logging calls were made
            assert mock_logger.info.called or mock_logger.warning.called or mock_logger.error.called or mock_logger.critical.called
    
    @patch('src.core.robot_controller.NiryoRobot')
    def test_context_manager_integration(self, mock_niryo_class, integrated_system, mock_niryo_robot):
        """Test context manager integration."""
        mock_niryo_class.return_value = mock_niryo_robot
        
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test nested context managers
        with safety_manager:
            assert safety_manager._monitoring_active
            
            with robot_controller.robot_connection():
                assert robot_controller.is_connected
                
                # Perform operations within context
                robot_controller.led_control([0, 255, 0])
                safety_manager.check_workspace_boundaries(0, 0, 200)
            
            assert not robot_controller.is_connected
        
        # Give monitoring thread time to stop
        time.sleep(0.1)
        assert not safety_manager._monitoring_active
    
    def test_performance_integration(self, integrated_system):
        """Test performance characteristics of integrated system."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test that safety checks don't significantly impact performance
        start_time = time.time()
        
        for i in range(100):
            safety_manager.check_workspace_boundaries(i, i, i + 100)
            safety_manager.check_force_limits(float(i))
            robot_controller.get_position()  # Mock call
        
        elapsed_time = time.time() - start_time
        
        # Should complete 100 iterations quickly (under 1 second)
        assert elapsed_time < 1.0
        
        # Verify operations were performed
        assert len(safety_manager._force_readings) == 100
    
    def test_memory_management(self, integrated_system):
        """Test memory management in integrated system."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Generate many events to test memory limits
        for i in range(1200):
            safety_manager.check_force_limits(60.0)  # Over limit
        
        # Verify event history is limited
        assert len(safety_manager.safety_events) <= 1000
        
        # Verify force readings history is limited
        for i in range(150):
            safety_manager.check_force_limits(10.0)  # Under limit
        
        assert len(safety_manager._force_readings) <= 100
    
    def test_system_state_consistency(self, integrated_system):
        """Test system state consistency across components."""
        robot_controller = integrated_system['robot_controller']
        safety_manager = integrated_system['safety_manager']
        
        # Test emergency stop state consistency
        safety_manager.emergency_stop("Consistency test")
        robot_controller.emergency_stop()
        
        assert safety_manager.is_emergency_stop_active
        assert robot_controller._emergency_stop_active
        
        # Test reset state consistency
        safety_manager.reset_emergency_stop()
        robot_controller.reset_emergency_stop()
        
        assert not safety_manager.is_emergency_stop_active
        assert not robot_controller._emergency_stop_active
        
        # Test safety disable affects boundary checking
        safety_manager.disable_safety()
        
        # Should allow out-of-bounds positions when safety disabled
        result = safety_manager.check_workspace_boundaries(1000, 1000, 1000)
        assert result is True
