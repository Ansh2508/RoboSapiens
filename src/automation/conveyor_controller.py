"""
Conveyor Belt Controller

This module provides comprehensive conveyor belt control capabilities for the Niryo
automation system, enabling bidirectional belt control with variable speed settings
and integrated safety systems.

Features:
- Bidirectional belt control with variable speed (10-100 mm/s)
- Safety interlocks and emergency stop integration
- Real-time status monitoring and diagnostics
- Configuration management for different belt speeds and directions
- Integration with existing robot safety systems
- Performance monitoring and optimization
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError

try:
    from pyniryo import NiryoRobot
except ImportError:
    # Mock for development without hardware
    class NiryoRobot:
        def __init__(self, ip_address):
            self.ip_address = ip_address
        
        def set_conveyor_belt(self, conveyor_id, control_on, speed, direction):
            pass
        
        def get_conveyor_belt_feedback(self, conveyor_id):
            return {"running": False, "speed": 0, "direction": 1}

logger = get_logger(__name__)


class ConveyorDirection(Enum):
    """Conveyor belt direction options."""
    FORWARD = 1
    BACKWARD = -1
    STOPPED = 0


class ConveyorStatus(Enum):
    """Conveyor belt status states."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class ConveyorError(RoboticsError):
    """Conveyor-specific error class."""
    pass


@dataclass
class ConveyorParameters:
    """Conveyor belt configuration parameters."""
    # Speed settings
    min_speed: float = 10.0   # mm/s
    max_speed: float = 100.0  # mm/s
    default_speed: float = 50.0  # mm/s
    
    # Acceleration settings
    acceleration_time: float = 2.0  # seconds to reach full speed
    deceleration_time: float = 1.5  # seconds to stop
    
    # Safety settings
    emergency_stop_time: float = 0.5  # seconds to emergency stop
    max_continuous_runtime: float = 3600.0  # 1 hour max continuous operation
    
    # Monitoring settings
    status_update_interval: float = 0.1  # seconds between status updates
    performance_monitoring: bool = True
    
    # Hardware settings
    conveyor_id: int = 6  # Niryo conveyor ID
    connection_timeout: float = 5.0  # seconds


@dataclass
class ConveyorState:
    """Current conveyor belt state."""
    status: ConveyorStatus = ConveyorStatus.DISCONNECTED
    direction: ConveyorDirection = ConveyorDirection.STOPPED
    speed: float = 0.0  # mm/s
    target_speed: float = 0.0  # mm/s
    runtime: float = 0.0  # seconds of operation
    last_command_time: float = 0.0
    error_message: Optional[str] = None
    
    # Performance metrics
    total_runtime: float = 0.0
    start_count: int = 0
    stop_count: int = 0
    error_count: int = 0


class ConveyorController:
    """
    Advanced conveyor belt controller providing bidirectional control,
    variable speed settings, and integrated safety systems.
    """
    
    def __init__(self, robot_ip: str = "127.0.0.1", config_manager=None):
        """
        Initialize conveyor controller.
        
        Args:
            robot_ip: IP address of Niryo robot
            config_manager: Configuration manager instance
        """
        self.robot_ip = robot_ip
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('automation', {})
        
        # Conveyor parameters
        self.parameters = ConveyorParameters()
        
        # Conveyor state
        self.state = ConveyorState()
        
        # Robot connection
        self._robot: Optional[NiryoRobot] = None
        self._connected = False
        
        # Threading for monitoring
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._command_queue = Queue()
        
        # Safety callbacks
        self._emergency_stop_callbacks: List[Callable] = []
        self._status_change_callbacks: List[Callable] = []
        
        # Performance monitoring
        self._operation_history: List[Dict[str, Any]] = []
        
        # Safety state
        self._emergency_stopped = False
        self._safety_enabled = True
        
        logger.info("Conveyor controller initialized")
    
    @property
    def is_connected(self) -> bool:
        """Check if conveyor is connected."""
        return self._connected
    
    @property
    def is_running(self) -> bool:
        """Check if conveyor is currently running."""
        return self.state.status == ConveyorStatus.RUNNING
    
    @property
    def current_speed(self) -> float:
        """Get current conveyor speed in mm/s."""
        return self.state.speed
    
    @property
    def current_direction(self) -> ConveyorDirection:
        """Get current conveyor direction."""
        return self.state.direction
    
    def connect(self) -> bool:
        """
        Connect to conveyor belt system.
        
        Returns:
            True if connection successful
        """
        logger.info(f"Connecting to conveyor at {self.robot_ip}...")
        
        try:
            self._robot = NiryoRobot(self.robot_ip)
            self._connected = True
            self.state.status = ConveyorStatus.CONNECTED
            
            # Start monitoring thread
            self._start_monitoring()
            
            logger.info("Conveyor connected successfully")
            self._notify_status_change()
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to conveyor: {e}"
            logger.error(error_msg)
            self.state.error_message = error_msg
            self.state.status = ConveyorStatus.ERROR
            return False
    
    def disconnect(self) -> None:
        """Disconnect from conveyor belt system."""
        logger.info("Disconnecting from conveyor...")
        
        try:
            # Stop conveyor if running
            if self.is_running:
                self.stop()
            
            # Stop monitoring
            self._stop_monitoring_thread()
            
            # Disconnect robot
            self._robot = None
            self._connected = False
            self.state.status = ConveyorStatus.DISCONNECTED
            
            logger.info("Conveyor disconnected")
            self._notify_status_change()
            
        except Exception as e:
            logger.error(f"Error during conveyor disconnect: {e}")
    
    def set_parameters(self, parameters: ConveyorParameters) -> None:
        """
        Set conveyor parameters.
        
        Args:
            parameters: Conveyor parameters to set
        """
        self.parameters = parameters
        logger.info("Conveyor parameters updated")
    def start(self, speed: float, direction: ConveyorDirection = ConveyorDirection.FORWARD) -> bool:
        """
        Start conveyor belt with specified speed and direction.
        
        Args:
            speed: Belt speed in mm/s (10-100 range)
            direction: Belt direction
            
        Returns:
            True if start command successful
        """
        if not self.is_connected:
            raise ConveyorError("Conveyor not connected")
        
        if self._emergency_stopped:
            raise ConveyorError("Conveyor in emergency stop state")
        
        # Validate speed
        if not (self.parameters.min_speed <= speed <= self.parameters.max_speed):
            raise ConveyorError(f"Speed {speed} mm/s outside valid range "
                              f"({self.parameters.min_speed}-{self.parameters.max_speed} mm/s)")
        
        logger.info(f"Starting conveyor: {speed} mm/s, direction: {direction.name}")
        
        try:
            # Convert speed to Niryo units (assuming direct mapping)
            niryo_speed = int(speed)
            niryo_direction = direction.value
            
            # Send command to robot
            self._robot.set_conveyor_belt(
                self.parameters.conveyor_id,
                True,  # control_on
                niryo_speed,
                niryo_direction
            )
            
            # Update state
            self.state.target_speed = speed
            self.state.direction = direction
            self.state.status = ConveyorStatus.RUNNING
            self.state.last_command_time = time.time()
            self.state.start_count += 1
            
            # Record operation
            self._record_operation({
                'action': 'start',
                'speed': speed,
                'direction': direction.name,
                'timestamp': time.time()
            })
            
            logger.info(f"Conveyor started successfully")
            self._notify_status_change()
            return True
            
        except Exception as e:
            error_msg = f"Failed to start conveyor: {e}"
            logger.error(error_msg)
            self.state.error_message = error_msg
            self.state.status = ConveyorStatus.ERROR
            self.state.error_count += 1
            return False
    def stop(self, emergency: bool = False) -> bool:
        """
        Stop conveyor belt.
        
        Args:
            emergency: If True, perform emergency stop
            
        Returns:
            True if stop command successful
        """
        if not self.is_connected:
            raise ConveyorError("Conveyor not connected")
        
        stop_type = "emergency" if emergency else "normal"
        logger.info(f"Stopping conveyor ({stop_type} stop)")
        
        try:
            # Send stop command to robot
            self._robot.set_conveyor_belt(
                self.parameters.conveyor_id,
                False,  # control_on (stop)
                0,      # speed
                0       # direction
            )
            
            # Update state
            self.state.speed = 0.0
            self.state.target_speed = 0.0
            self.state.direction = ConveyorDirection.STOPPED
            self.state.last_command_time = time.time()
            self.state.stop_count += 1
            
            if emergency:
                self.state.status = ConveyorStatus.EMERGENCY_STOP
                self._emergency_stopped = True
                self._notify_emergency_stop()
            else:
                self.state.status = ConveyorStatus.STOPPED
            
            # Record operation
            self._record_operation({
                'action': 'stop',
                'emergency': emergency,
                'timestamp': time.time()
            })
            
            logger.info(f"Conveyor stopped successfully ({stop_type})")
            self._notify_status_change()
            return True
            
        except Exception as e:
            error_msg = f"Failed to stop conveyor: {e}"
            logger.error(error_msg)
            self.state.error_message = error_msg
            self.state.status = ConveyorStatus.ERROR
            self.state.error_count += 1
            return False
    
    def emergency_stop(self) -> bool:
        """
        Perform emergency stop of conveyor belt.
        
        Returns:
            True if emergency stop successful
        """
        logger.critical("CONVEYOR EMERGENCY STOP ACTIVATED")
        return self.stop(emergency=True)
    
    def reset_emergency_stop(self) -> bool:
        """
        Reset emergency stop state.
        
        Returns:
            True if reset successful
        """
        if not self._emergency_stopped:
            return True
        
        logger.info("Resetting conveyor emergency stop")
        
        try:
            self._emergency_stopped = False
            self.state.status = ConveyorStatus.STOPPED
            self.state.error_message = None
            
            logger.info("Emergency stop reset successfully")
            self._notify_status_change()
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset emergency stop: {e}")
            return False

    def change_speed(self, new_speed: float) -> bool:
        """
        Change conveyor speed while running.

        Args:
            new_speed: New speed in mm/s

        Returns:
            True if speed change successful
        """
        if not self.is_running:
            raise ConveyorError("Conveyor not running")

        # Validate speed
        if not (self.parameters.min_speed <= new_speed <= self.parameters.max_speed):
            raise ConveyorError(f"Speed {new_speed} mm/s outside valid range")

        logger.info(f"Changing conveyor speed to {new_speed} mm/s")

        try:
            # Send new speed command
            niryo_speed = int(new_speed)
            self._robot.set_conveyor_belt(
                self.parameters.conveyor_id,
                True,  # keep running
                niryo_speed,
                self.state.direction.value
            )

            # Update state
            self.state.target_speed = new_speed
            self.state.last_command_time = time.time()

            # Record operation
            self._record_operation({
                'action': 'speed_change',
                'old_speed': self.state.speed,
                'new_speed': new_speed,
                'timestamp': time.time()
            })

            logger.info(f"Conveyor speed changed successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to change conveyor speed: {e}"
            logger.error(error_msg)
            self.state.error_message = error_msg
            return False

    def reverse_direction(self) -> bool:
        """
        Reverse conveyor direction while maintaining speed.

        Returns:
            True if direction change successful
        """
        if not self.is_running:
            raise ConveyorError("Conveyor not running")

        # Determine new direction
        new_direction = (ConveyorDirection.BACKWARD if self.state.direction == ConveyorDirection.FORWARD
                        else ConveyorDirection.FORWARD)

        logger.info(f"Reversing conveyor direction to {new_direction.name}")

        try:
            # Send direction change command
            self._robot.set_conveyor_belt(
                self.parameters.conveyor_id,
                True,  # keep running
                int(self.state.target_speed),
                new_direction.value
            )

            # Update state
            self.state.direction = new_direction
            self.state.last_command_time = time.time()

            # Record operation
            self._record_operation({
                'action': 'direction_change',
                'new_direction': new_direction.name,
                'timestamp': time.time()
            })

            logger.info(f"Conveyor direction reversed successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to reverse conveyor direction: {e}"
            logger.error(error_msg)
            self.state.error_message = error_msg
            return False

    def _start_monitoring(self) -> None:
        """Start monitoring thread for conveyor status."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitoring_thread.start()
        logger.debug("Conveyor monitoring started")

    def _stop_monitoring_thread(self) -> None:
        """Stop monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=2.0)
        logger.debug("Conveyor monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for conveyor status."""
        logger.debug("Starting conveyor monitoring loop")

        while not self._stop_monitoring.is_set():
            try:
                if self._robot and self._connected:
                    # Get feedback from robot
                    feedback = self._robot.get_conveyor_belt_feedback(self.parameters.conveyor_id)

                    # Update state based on feedback
                    if feedback:
                        self.state.speed = float(feedback.get('speed', 0))

                        # Update runtime if running
                        if self.state.status == ConveyorStatus.RUNNING:
                            current_time = time.time()
                            if self.state.last_command_time > 0:
                                self.state.runtime += current_time - self.state.last_command_time
                                self.state.total_runtime += current_time - self.state.last_command_time
                            self.state.last_command_time = current_time

                        # Check for safety violations
                        self._check_safety_conditions()

                # Sleep for monitoring interval
                self._stop_monitoring.wait(self.parameters.status_update_interval)

            except Exception as e:
                logger.warning(f"Error in conveyor monitoring loop: {e}")
                time.sleep(1.0)  # Wait longer on error

        logger.debug("Conveyor monitoring loop stopped")

    def _check_safety_conditions(self) -> None:
        """Check safety conditions and take action if needed."""
        if not self._safety_enabled:
            return

        # Check maximum continuous runtime
        if (self.state.runtime > self.parameters.max_continuous_runtime and
            self.state.status == ConveyorStatus.RUNNING):

            logger.warning(f"Maximum continuous runtime exceeded: {self.state.runtime:.1f}s")
            self.stop()
            self.state.error_message = "Maximum continuous runtime exceeded"

    def add_emergency_stop_callback(self, callback: Callable) -> None:
        """
        Add callback for emergency stop events.

        Args:
            callback: Function to call on emergency stop
        """
        self._emergency_stop_callbacks.append(callback)
        logger.info(f"Added emergency stop callback: {callback.__name__}")

    def add_status_change_callback(self, callback: Callable) -> None:
        """
        Add callback for status change events.

        Args:
            callback: Function to call on status change
        """
        self._status_change_callbacks.append(callback)
        logger.info(f"Added status change callback: {callback.__name__}")

    def _notify_emergency_stop(self) -> None:
        """Notify all emergency stop callbacks."""
        for callback in self._emergency_stop_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Emergency stop callback error: {e}")

    def _notify_status_change(self) -> None:
        """Notify all status change callbacks."""
        for callback in self._status_change_callbacks:
            try:
                callback(self.state.status)
            except Exception as e:
                logger.error(f"Status change callback error: {e}")

    def _record_operation(self, operation_data: Dict[str, Any]) -> None:
        """
        Record operation in history.

        Args:
            operation_data: Operation data to record
        """
        self._operation_history.append(operation_data)

        # Keep only last 1000 operations
        if len(self._operation_history) > 1000:
            self._operation_history.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive conveyor status.

        Returns:
            Dictionary with conveyor status information
        """
        return {
            'connected': self.is_connected,
            'running': self.is_running,
            'status': self.state.status.value,
            'speed': self.state.speed,
            'target_speed': self.state.target_speed,
            'direction': self.state.direction.name,
            'runtime': self.state.runtime,
            'total_runtime': self.state.total_runtime,
            'emergency_stopped': self._emergency_stopped,
            'error_message': self.state.error_message,
            'parameters': {
                'min_speed': self.parameters.min_speed,
                'max_speed': self.parameters.max_speed,
                'conveyor_id': self.parameters.conveyor_id
            },
            'statistics': {
                'start_count': self.state.start_count,
                'stop_count': self.state.stop_count,
                'error_count': self.state.error_count,
                'operation_history_size': len(self._operation_history)
            }
        }

    def reset_statistics(self) -> None:
        """Reset conveyor statistics."""
        self.state.total_runtime = 0.0
        self.state.start_count = 0
        self.state.stop_count = 0
        self.state.error_count = 0
        self._operation_history.clear()
        logger.info("Conveyor statistics reset")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
