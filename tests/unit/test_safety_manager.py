"""
Unit tests for SafetyManager class.

These tests verify the safety monitoring, emergency protocols,
and boundary checking functionality.
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch
import math

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from src.core.safety_manager import (
    SafetyManager, SafetyLevel, SafetyEventType, SafetyEvent, WorkspaceBoundary
)
from src.utils.error_handler import SafetyError


class TestSafetyManager:
    """Test cases for SafetyManager class."""
    
    @pytest.fixture
    def mock_config_manager(self):
        """Create mock configuration manager."""
        config_manager = Mock()
        safety_config = Mock()
        safety_config.emergency_stop_enabled = True
        safety_config.collision_detection_enabled = True
        safety_config.workspace_boundaries_enabled = True
        safety_config.force_limit_newtons = 50.0
        safety_config.safety_check_interval = 0.1
        
        config_manager.get_safety_config.return_value = safety_config
        return config_manager
    
    @pytest.fixture
    def safety_manager(self, mock_config_manager):
        """Create SafetyManager instance with mocked dependencies."""
        with patch('src.core.safety_manager.get_config_manager', return_value=mock_config_manager):
            manager = SafetyManager()
            return manager
    
    def test_initialization(self, safety_manager):
        """Test safety manager initialization."""
        assert not safety_manager.is_emergency_stop_active
        assert safety_manager.is_safety_enabled
        assert not safety_manager._monitoring_active
        assert len(safety_manager.safety_events) == 0
    
    def test_workspace_boundary_loading(self, safety_manager):
        """Test workspace boundary loading."""
        boundary = safety_manager._workspace_boundary
        assert isinstance(boundary, WorkspaceBoundary)
        assert boundary.x_min == -300
        assert boundary.x_max == 300
        assert boundary.y_min == -300
        assert boundary.y_max == 300
        assert boundary.z_min == 0
        assert boundary.z_max == 400
    
    def test_enable_disable_safety(self, safety_manager):
        """Test enabling and disabling safety monitoring."""
        # Test disable
        safety_manager.disable_safety()
        assert not safety_manager.is_safety_enabled
        
        # Test enable
        safety_manager.enable_safety()
        assert safety_manager.is_safety_enabled
    
    def test_emergency_stop_activation(self, safety_manager):
        """Test emergency stop activation."""
        reason = "Test emergency stop"
        safety_manager.emergency_stop(reason)
        
        assert safety_manager.is_emergency_stop_active
        assert len(safety_manager.safety_events) == 1
        
        event = safety_manager.safety_events[0]
        assert event.event_type == SafetyEventType.EMERGENCY_STOP
        assert event.level == SafetyLevel.EMERGENCY
        assert reason in event.message
        assert not event.resolved
    
    def test_emergency_stop_reset(self, safety_manager):
        """Test emergency stop reset."""
        # Activate emergency stop first
        safety_manager.emergency_stop("Test")
        assert safety_manager.is_emergency_stop_active
        
        # Reset emergency stop
        result = safety_manager.reset_emergency_stop()
        
        assert result is True
        assert not safety_manager.is_emergency_stop_active
        
        # Check that emergency stop event is marked as resolved
        event = safety_manager.safety_events[0]
        assert event.resolved
        assert event.resolution_time is not None
    
    def test_emergency_stop_reset_when_not_active(self, safety_manager):
        """Test resetting emergency stop when not active."""
        result = safety_manager.reset_emergency_stop()
        assert result is True
    
    def test_workspace_boundary_checking_valid_positions(self, safety_manager):
        """Test workspace boundary checking with valid positions."""
        # Test center position
        result = safety_manager.check_workspace_boundaries(0, 0, 200)
        assert result is True
        
        # Test boundary positions
        result = safety_manager.check_workspace_boundaries(300, 300, 400)
        assert result is True
        
        result = safety_manager.check_workspace_boundaries(-300, -300, 0)
        assert result is True
    
    def test_workspace_boundary_checking_invalid_positions(self, safety_manager):
        """Test workspace boundary checking with invalid positions."""
        # Test X boundary violation
        result = safety_manager.check_workspace_boundaries(400, 0, 200)
        assert result is False
        assert len(safety_manager.safety_events) == 1
        assert safety_manager.safety_events[0].event_type == SafetyEventType.BOUNDARY_VIOLATION
        
        # Test Y boundary violation
        safety_manager._safety_events.clear()  # Clear previous events
        result = safety_manager.check_workspace_boundaries(0, -400, 200)
        assert result is False
        assert len(safety_manager.safety_events) == 1
        
        # Test Z boundary violation
        safety_manager._safety_events.clear()
        result = safety_manager.check_workspace_boundaries(0, 0, 500)
        assert result is False
        assert len(safety_manager.safety_events) == 1
    
    def test_workspace_boundary_checking_disabled(self, safety_manager):
        """Test workspace boundary checking when disabled."""
        safety_manager.config.workspace_boundaries_enabled = False
        
        # Should return True even for invalid positions
        result = safety_manager.check_workspace_boundaries(1000, 1000, 1000)
        assert result is True
        assert len(safety_manager.safety_events) == 0
    
    def test_workspace_boundary_checking_safety_disabled(self, safety_manager):
        """Test workspace boundary checking when safety is disabled."""
        safety_manager.disable_safety()
        
        # Should return True even for invalid positions
        result = safety_manager.check_workspace_boundaries(1000, 1000, 1000)
        assert result is True
        assert len(safety_manager.safety_events) == 0
    
    def test_orientation_boundary_checking(self, safety_manager):
        """Test orientation boundary checking."""
        # Test valid orientations
        result = safety_manager.check_workspace_boundaries(
            0, 0, 200, roll=0, pitch=0, yaw=0
        )
        assert result is True
        
        # Test invalid roll
        result = safety_manager.check_workspace_boundaries(
            0, 0, 200, roll=4.0, pitch=0, yaw=0
        )
        assert result is False
        assert len(safety_manager.safety_events) == 1
        assert "Roll out of bounds" in safety_manager.safety_events[0].message
    
    def test_force_limit_checking_valid(self, safety_manager):
        """Test force limit checking with valid forces."""
        # Test normal force
        result = safety_manager.check_force_limits(25.0)
        assert result is True
        assert len(safety_manager._force_readings) == 1
        assert safety_manager._force_readings[0] == 25.0
        
        # Test maximum allowed force
        result = safety_manager.check_force_limits(50.0)
        assert result is True
    
    def test_force_limit_checking_invalid(self, safety_manager):
        """Test force limit checking with excessive force."""
        result = safety_manager.check_force_limits(75.0)
        
        assert result is False
        assert len(safety_manager.safety_events) == 1
        
        event = safety_manager.safety_events[0]
        assert event.event_type == SafetyEventType.FORCE_LIMIT_EXCEEDED
        assert event.level == SafetyLevel.CRITICAL
        assert "75.0N" in event.message
        assert event.context["force"] == 75.0
        assert event.context["limit"] == 50.0
    
    def test_force_limit_checking_disabled(self, safety_manager):
        """Test force limit checking when safety is disabled."""
        safety_manager.disable_safety()
        
        result = safety_manager.check_force_limits(100.0)
        assert result is True
        assert len(safety_manager.safety_events) == 0
    
    def test_force_readings_history_limit(self, safety_manager):
        """Test force readings history limit."""
        # Add more readings than the limit
        for i in range(150):
            safety_manager.check_force_limits(float(i))
        
        # Should only keep the last 100 readings
        assert len(safety_manager._force_readings) == 100
        assert safety_manager._force_readings[0] == 50.0  # First kept reading
        assert safety_manager._force_readings[-1] == 149.0  # Last reading
    
    def test_event_callback_registration(self, safety_manager):
        """Test safety event callback registration."""
        callback_called = []
        
        def test_callback(event):
            callback_called.append(event)
        
        # Register callback
        safety_manager.register_event_callback(SafetyEventType.EMERGENCY_STOP, test_callback)
        
        # Trigger event
        safety_manager.emergency_stop("Test callback")
        
        # Check callback was called
        assert len(callback_called) == 1
        assert callback_called[0].event_type == SafetyEventType.EMERGENCY_STOP
    
    def test_multiple_event_callbacks(self, safety_manager):
        """Test multiple callbacks for the same event type."""
        callback1_called = []
        callback2_called = []
        
        def callback1(event):
            callback1_called.append(event)
        
        def callback2(event):
            callback2_called.append(event)
        
        # Register multiple callbacks
        safety_manager.register_event_callback(SafetyEventType.EMERGENCY_STOP, callback1)
        safety_manager.register_event_callback(SafetyEventType.EMERGENCY_STOP, callback2)
        
        # Trigger event
        safety_manager.emergency_stop("Test multiple callbacks")
        
        # Check both callbacks were called
        assert len(callback1_called) == 1
        assert len(callback2_called) == 1
    
    def test_event_callback_exception_handling(self, safety_manager):
        """Test that callback exceptions don't break the system."""
        def failing_callback(event):
            raise Exception("Callback failed")
        
        # Register failing callback
        safety_manager.register_event_callback(SafetyEventType.EMERGENCY_STOP, failing_callback)
        
        # Should not raise exception
        safety_manager.emergency_stop("Test exception handling")
        
        # Event should still be recorded
        assert len(safety_manager.safety_events) == 1
    
    def test_safety_status(self, safety_manager):
        """Test getting safety status."""
        status = safety_manager.get_safety_status()
        
        assert isinstance(status, dict)
        assert "emergency_stop_active" in status
        assert "safety_enabled" in status
        assert "monitoring_active" in status
        assert "recent_events_count" in status
        assert "unresolved_critical_events" in status
        assert "workspace_boundaries_enabled" in status
        assert "collision_detection_enabled" in status
        assert "force_limit" in status
        
        # Check initial values
        assert status["emergency_stop_active"] is False
        assert status["safety_enabled"] is True
        assert status["monitoring_active"] is False
        assert status["recent_events_count"] == 0
        assert status["unresolved_critical_events"] == 0
    
    def test_safety_status_with_events(self, safety_manager):
        """Test safety status with events."""
        # Create some events
        safety_manager.emergency_stop("Test event")
        safety_manager.check_force_limits(100.0)  # Should create force limit event
        
        status = safety_manager.get_safety_status()
        
        assert status["emergency_stop_active"] is True
        assert status["recent_events_count"] == 2
        assert status["unresolved_critical_events"] == 1  # Force limit event
    
    def test_monitoring_thread_start_stop(self, safety_manager):
        """Test starting and stopping monitoring thread."""
        # Start monitoring
        safety_manager.start_monitoring()
        assert safety_manager._monitoring_active is True
        assert safety_manager._monitoring_thread is not None
        assert safety_manager._monitoring_thread.is_alive()
        
        # Stop monitoring
        safety_manager.stop_monitoring()
        assert safety_manager._monitoring_active is False
        
        # Wait a bit for thread to stop
        time.sleep(0.2)
        assert not safety_manager._monitoring_thread.is_alive()
    
    def test_monitoring_thread_already_active(self, safety_manager):
        """Test starting monitoring when already active."""
        safety_manager.start_monitoring()
        first_thread = safety_manager._monitoring_thread
        
        # Try to start again
        safety_manager.start_monitoring()
        
        # Should be the same thread
        assert safety_manager._monitoring_thread == first_thread
        
        safety_manager.stop_monitoring()
    
    def test_context_manager(self, safety_manager):
        """Test safety manager as context manager."""
        with safety_manager:
            assert safety_manager._monitoring_active is True
        
        # Should stop monitoring after context
        time.sleep(0.1)  # Give thread time to stop
        assert safety_manager._monitoring_active is False
    
    def test_event_history_limit(self, safety_manager):
        """Test that event history is limited."""
        # Create many events
        for i in range(1100):
            safety_manager._record_safety_event(SafetyEvent(
                event_type=SafetyEventType.BOUNDARY_VIOLATION,
                level=SafetyLevel.WARNING,
                message=f"Test event {i}",
                timestamp=time.time(),
                context={}
            ))
        
        # Should only keep last 1000 events
        assert len(safety_manager.safety_events) == 1000
        assert "Test event 100" in safety_manager.safety_events[0].message
        assert "Test event 1099" in safety_manager.safety_events[-1].message
    
    def test_is_safe_to_reset(self, safety_manager):
        """Test safety reset conditions."""
        # Should be safe initially
        assert safety_manager._is_safe_to_reset() is True
        
        # Create unresolved critical event
        safety_manager._record_safety_event(SafetyEvent(
            event_type=SafetyEventType.COLLISION_DETECTED,
            level=SafetyLevel.CRITICAL,
            message="Test collision",
            timestamp=time.time(),
            context={}
        ))
        
        # Should not be safe to reset
        assert safety_manager._is_safe_to_reset() is False
        
        # Resolve the event
        safety_manager.safety_events[-1].resolved = True
        
        # Should be safe to reset now
        assert safety_manager._is_safe_to_reset() is True
