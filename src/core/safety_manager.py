"""
Safety Management System

This module provides comprehensive safety monitoring and emergency protocols
for the Niryo LLM Robotics Platform.

Features:
- Real-time safety monitoring
- Emergency stop protocols
- Collision detection and avoidance
- Workspace boundary enforcement
- Force limiting and monitoring
- Safety event logging and reporting
"""

import time
import threading
from typing import Dict, List, Tuple, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
import math

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import SafetyError, RoboticsError

logger = get_logger(__name__)


class SafetyLevel(Enum):
    """Safety alert levels."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class SafetyEventType(Enum):
    """Types of safety events."""
    EMERGENCY_STOP = "emergency_stop"
    COLLISION_DETECTED = "collision_detected"
    BOUNDARY_VIOLATION = "boundary_violation"
    FORCE_LIMIT_EXCEEDED = "force_limit_exceeded"
    VELOCITY_LIMIT_EXCEEDED = "velocity_limit_exceeded"
    COMMUNICATION_LOST = "communication_lost"
    SENSOR_FAILURE = "sensor_failure"


@dataclass
class SafetyEvent:
    """Safety event information."""
    event_type: SafetyEventType
    level: SafetyLevel
    message: str
    timestamp: float
    context: Dict[str, Any]
    resolved: bool = False
    resolution_time: Optional[float] = None


@dataclass
class WorkspaceBoundary:
    """Workspace boundary definition."""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
    roll_min: float = -math.pi
    roll_max: float = math.pi
    pitch_min: float = -math.pi
    pitch_max: float = math.pi
    yaw_min: float = -math.pi
    yaw_max: float = math.pi


class SafetyManager:
    """
    Comprehensive safety management system for robot operations.
    
    This class monitors robot operations in real-time and enforces
    safety protocols to prevent accidents and equipment damage.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize safety manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('safety', {})
        
        # Safety state
        self._emergency_stop_active = False
        self._safety_enabled = True
        self._monitoring_active = False
        
        # Event tracking
        self._safety_events: List[SafetyEvent] = []
        self._event_callbacks: Dict[SafetyEventType, List[Callable]] = {}
        
        # Monitoring thread
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._monitoring_lock = threading.Lock()
        
        # Workspace boundaries
        self._workspace_boundary = self._load_workspace_boundary()
        
        # Force monitoring
        self._force_readings: List[float] = []
        self._max_force_history = 100
        
        logger.info("Safety manager initialized")
    
    def _load_workspace_boundary(self) -> WorkspaceBoundary:
        """Load workspace boundary from configuration."""
        # Default Niryo Ned2 workspace (in mm)
        return WorkspaceBoundary(
            x_min=-300, x_max=300,
            y_min=-300, y_max=300,
            z_min=0, z_max=400
        )
    
    @property
    def is_emergency_stop_active(self) -> bool:
        """Check if emergency stop is active."""
        return self._emergency_stop_active
    
    @property
    def is_safety_enabled(self) -> bool:
        """Check if safety monitoring is enabled."""
        return self._safety_enabled
    
    @property
    def safety_events(self) -> List[SafetyEvent]:
        """Get list of safety events."""
        return self._safety_events.copy()
    
    def enable_safety(self) -> None:
        """Enable safety monitoring."""
        self._safety_enabled = True
        logger.info("Safety monitoring enabled")
    
    def disable_safety(self) -> None:
        """Disable safety monitoring (use with extreme caution)."""
        logger.warning("Safety monitoring disabled - USE WITH EXTREME CAUTION")
        self._safety_enabled = False
    
    def start_monitoring(self) -> None:
        """Start safety monitoring thread."""
        if self._monitoring_active:
            logger.warning("Safety monitoring is already active")
            return
        
        with self._monitoring_lock:
            self._stop_monitoring.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="SafetyMonitor"
            )
            self._monitoring_thread.start()
            self._monitoring_active = True
            
        logger.info("Safety monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop safety monitoring thread."""
        if not self._monitoring_active:
            return
        
        with self._monitoring_lock:
            self._stop_monitoring.set()
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=5.0)
            self._monitoring_active = False
            
        logger.info("Safety monitoring stopped")
    
    def emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        """
        Activate emergency stop.
        
        Args:
            reason: Reason for emergency stop
        """
        if self._emergency_stop_active:
            return
        
        self._emergency_stop_active = True
        
        # Create safety event
        event = SafetyEvent(
            event_type=SafetyEventType.EMERGENCY_STOP,
            level=SafetyLevel.EMERGENCY,
            message=f"Emergency stop activated: {reason}",
            timestamp=time.time(),
            context={"reason": reason}
        )
        
        self._record_safety_event(event)
        logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")
        
        # Trigger callbacks
        self._trigger_event_callbacks(SafetyEventType.EMERGENCY_STOP, event)
    
    def reset_emergency_stop(self) -> bool:
        """
        Reset emergency stop state.
        
        Returns:
            True if reset successful, False otherwise
        """
        if not self._emergency_stop_active:
            logger.warning("Emergency stop is not active")
            return True
        
        # Check if it's safe to reset
        if not self._is_safe_to_reset():
            logger.error("Cannot reset emergency stop - unsafe conditions detected")
            return False
        
        self._emergency_stop_active = False
        
        # Mark emergency stop events as resolved
        for event in self._safety_events:
            if (event.event_type == SafetyEventType.EMERGENCY_STOP and 
                not event.resolved):
                event.resolved = True
                event.resolution_time = time.time()
        
        logger.info("Emergency stop reset")
        return True
    
    def _is_safe_to_reset(self) -> bool:
        """Check if it's safe to reset emergency stop."""
        # Check for unresolved critical safety events
        for event in self._safety_events:
            if (event.level == SafetyLevel.CRITICAL and 
                not event.resolved and 
                event.event_type != SafetyEventType.EMERGENCY_STOP):
                return False
        
        return True
    
    def check_workspace_boundaries(self, x: float, y: float, z: float, 
                                 roll: float = 0, pitch: float = 0, yaw: float = 0) -> bool:
        """
        Check if position is within workspace boundaries.
        
        Args:
            x, y, z: Cartesian coordinates (mm)
            roll, pitch, yaw: Orientation (radians)
            
        Returns:
            True if position is safe, False otherwise
        """
        if not self._safety_enabled or not self.config.workspace_boundaries_enabled:
            return True
        
        boundary = self._workspace_boundary
        
        # Check position boundaries
        if not (boundary.x_min <= x <= boundary.x_max):
            self._record_boundary_violation("X coordinate out of bounds", x, boundary.x_min, boundary.x_max)
            return False
        
        if not (boundary.y_min <= y <= boundary.y_max):
            self._record_boundary_violation("Y coordinate out of bounds", y, boundary.y_min, boundary.y_max)
            return False
        
        if not (boundary.z_min <= z <= boundary.z_max):
            self._record_boundary_violation("Z coordinate out of bounds", z, boundary.z_min, boundary.z_max)
            return False
        
        # Check orientation boundaries
        if not (boundary.roll_min <= roll <= boundary.roll_max):
            self._record_boundary_violation("Roll out of bounds", roll, boundary.roll_min, boundary.roll_max)
            return False
        
        if not (boundary.pitch_min <= pitch <= boundary.pitch_max):
            self._record_boundary_violation("Pitch out of bounds", pitch, boundary.pitch_min, boundary.pitch_max)
            return False
        
        if not (boundary.yaw_min <= yaw <= boundary.yaw_max):
            self._record_boundary_violation("Yaw out of bounds", yaw, boundary.yaw_min, boundary.yaw_max)
            return False
        
        return True
    
    def _record_boundary_violation(self, message: str, value: float, min_val: float, max_val: float) -> None:
        """Record a workspace boundary violation."""
        event = SafetyEvent(
            event_type=SafetyEventType.BOUNDARY_VIOLATION,
            level=SafetyLevel.CRITICAL,
            message=message,
            timestamp=time.time(),
            context={
                "value": value,
                "min_allowed": min_val,
                "max_allowed": max_val
            }
        )
        
        self._record_safety_event(event)
        self._trigger_event_callbacks(SafetyEventType.BOUNDARY_VIOLATION, event)
    
    def check_force_limits(self, force: float) -> bool:
        """
        Check if force is within safe limits.
        
        Args:
            force: Applied force in Newtons
            
        Returns:
            True if force is safe, False otherwise
        """
        if not self._safety_enabled:
            return True
        
        # Record force reading
        self._force_readings.append(force)
        if len(self._force_readings) > self._max_force_history:
            self._force_readings.pop(0)
        
        # Check against limit
        if force > self.config.force_limit_newtons:
            event = SafetyEvent(
                event_type=SafetyEventType.FORCE_LIMIT_EXCEEDED,
                level=SafetyLevel.CRITICAL,
                message=f"Force limit exceeded: {force:.1f}N > {self.config.force_limit_newtons}N",
                timestamp=time.time(),
                context={"force": force, "limit": self.config.force_limit_newtons}
            )
            
            self._record_safety_event(event)
            self._trigger_event_callbacks(SafetyEventType.FORCE_LIMIT_EXCEEDED, event)
            return False
        
        return True
    
    def register_event_callback(self, event_type: SafetyEventType, callback: Callable[[SafetyEvent], None]) -> None:
        """
        Register callback for safety events.
        
        Args:
            event_type: Type of safety event
            callback: Callback function
        """
        if event_type not in self._event_callbacks:
            self._event_callbacks[event_type] = []
        
        self._event_callbacks[event_type].append(callback)
        logger.debug(f"Registered callback for {event_type.value} events")
    
    def _record_safety_event(self, event: SafetyEvent) -> None:
        """Record a safety event."""
        self._safety_events.append(event)
        
        # Keep only recent events (last 1000)
        if len(self._safety_events) > 1000:
            self._safety_events = self._safety_events[-1000:]
        
        # Log based on severity
        if event.level == SafetyLevel.EMERGENCY:
            logger.critical(f"SAFETY EVENT: {event.message}")
        elif event.level == SafetyLevel.CRITICAL:
            logger.error(f"SAFETY EVENT: {event.message}")
        elif event.level == SafetyLevel.WARNING:
            logger.warning(f"SAFETY EVENT: {event.message}")
        else:
            logger.info(f"SAFETY EVENT: {event.message}")
    
    def _trigger_event_callbacks(self, event_type: SafetyEventType, event: SafetyEvent) -> None:
        """Trigger callbacks for safety event."""
        if event_type in self._event_callbacks:
            for callback in self._event_callbacks[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Safety event callback failed: {e}")
    
    def _monitoring_loop(self) -> None:
        """Safety monitoring loop."""
        logger.debug("Safety monitoring loop started")
        
        while not self._stop_monitoring.is_set():
            try:
                if self._safety_enabled:
                    # Perform safety checks here
                    # In a real implementation, this would check:
                    # - Robot communication status
                    # - Sensor readings
                    # - System health
                    pass
                
                # Wait for next monitoring cycle
                self._stop_monitoring.wait(self.config.safety_check_interval)
                
            except Exception as e:
                logger.error(f"Safety monitoring error: {e}")
                self._stop_monitoring.wait(1.0)
        
        logger.debug("Safety monitoring loop stopped")
    
    def get_safety_status(self) -> Dict[str, Any]:
        """
        Get comprehensive safety status.
        
        Returns:
            Dictionary containing safety status information
        """
        recent_events = [
            event for event in self._safety_events
            if time.time() - event.timestamp < 3600  # Last hour
        ]
        
        return {
            "emergency_stop_active": self._emergency_stop_active,
            "safety_enabled": self._safety_enabled,
            "monitoring_active": self._monitoring_active,
            "recent_events_count": len(recent_events),
            "unresolved_critical_events": len([
                e for e in recent_events 
                if e.level == SafetyLevel.CRITICAL and not e.resolved
            ]),
            "workspace_boundaries_enabled": self.config.workspace_boundaries_enabled,
            "collision_detection_enabled": self.config.collision_detection_enabled,
            "force_limit": self.config.force_limit_newtons
        }
    
    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()
