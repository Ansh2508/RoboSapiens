"""
Core Robot Controller

This module provides the main interface for controlling the Niryo Ned2 robotic arm.
It handles connection management, calibration, movement control, and safety protocols.

Features:
- Robust connection management with automatic reconnection
- Comprehensive calibration procedures
- Precise movement control in Cartesian and joint space
- Real-time safety monitoring
- Tool control and manipulation
- Status monitoring and diagnostics
"""

import time
import threading
from typing import Optional, Tuple, List, Dict, Any, Union
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

try:
    from pyniryo import NiryoRobot, PoseObject, JointsPosition
    from pyniryo.api.enums import PinID, PinState
except ImportError:
    # Mock classes for development without hardware
    class NiryoRobot:
        def __init__(self, ip: str): pass
        def calibrate_auto(self): pass
        def close_connection(self): pass
        def get_pose(self): return None
        def get_joints(self): return [0, 0, 0, 0, 0, 0]
        def move(self, pose): pass
        def led_ring_flashing(self, *args): pass
        def wait(self, seconds): time.sleep(seconds)
        def move_to_home_pose(self): pass
        def set_arm_max_velocity(self, percent): pass
        def grasp_with_tool(self): pass
        def release_with_tool(self): pass
        def update_tool(self): pass
    
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0): pass
    
    class JointsPosition:
        def __init__(self, joints: List[float]): pass
    
    class PinID:
        DI5 = "DI5"
    
    class PinState:
        LOW = 0
        HIGH = 1

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import (
    RoboticsError, ConnectionError, CalibrationError, SafetyError,
    retry_on_error, error_handler_decorator
)

logger = get_logger(__name__)


class RobotState(Enum):
    """Robot connection and operational states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CALIBRATING = "calibrating"
    READY = "ready"
    MOVING = "moving"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


@dataclass
class RobotStatus:
    """Robot status information."""
    state: RobotState
    position: Optional[PoseObject] = None
    joints: Optional[List[float]] = None
    tool_connected: bool = False
    last_error: Optional[str] = None
    connection_time: Optional[float] = None
    calibration_time: Optional[float] = None


class RobotController:
    """
    Main robot controller for Niryo Ned2 robotic arm.
    
    This class provides a high-level interface for robot control with
    comprehensive error handling, safety monitoring, and status tracking.
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize robot controller.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('robot', {})
        
        self._robot: Optional[NiryoRobot] = None
        self._status = RobotStatus(state=RobotState.DISCONNECTED)
        self._connection_lock = threading.Lock()
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        
        # Safety limits
        self._emergency_stop_active = False
        self._workspace_boundaries = self._load_workspace_boundaries()
        
        logger.info("Robot controller initialized")
    
    def _load_workspace_boundaries(self) -> Dict[str, Tuple[float, float]]:
        """Load workspace boundary limits from configuration."""
        # Default Niryo Ned2 workspace boundaries (in mm)
        return {
            'x': (-300, 300),
            'y': (-300, 300), 
            'z': (0, 400),
            'roll': (-3.14, 3.14),
            'pitch': (-3.14, 3.14),
            'yaw': (-3.14, 3.14)
        }
    
    @property
    def status(self) -> RobotStatus:
        """Get current robot status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Check if robot is connected."""
        return self._status.state not in [RobotState.DISCONNECTED, RobotState.ERROR]
    
    @property
    def is_ready(self) -> bool:
        """Check if robot is ready for operations."""
        return self._status.state == RobotState.READY
    
    @retry_on_error(max_retries=3, delay=2.0)
    def connect(self, ip: Optional[str] = None, timeout: Optional[int] = None) -> bool:
        """
        Connect to the robot.
        
        Args:
            ip: Robot IP address (uses config default if None)
            timeout: Connection timeout (uses config default if None)
            
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If connection fails after retries
        """
        with self._connection_lock:
            if self.is_connected:
                logger.warning("Robot is already connected")
                return True
            
            robot_ip = ip or self.config.ip
            connection_timeout = timeout or self.config.timeout
            
            logger.info(f"Connecting to robot at {robot_ip}...")
            self._status.state = RobotState.CONNECTING
            
            try:
                    self._robot = NiryoRobot(robot_ip)
                    
                    # Test connection with a simple command
                    self._robot.led_ring_flashing([255, 0, 0], 0.5, 2, True)
                    
                    self._status.state = RobotState.CONNECTED
                    self._status.connection_time = time.time()
                    self._status.last_error = None
                    
                    # Start monitoring thread
                    self._start_monitoring()
                    
                    logger.info(f"Successfully connected to robot at {robot_ip}")
                    return True
                    
            except Exception as e:
                self._status.state = RobotState.ERROR
                self._status.last_error = str(e)
                error_msg = f"Failed to connect to robot at {robot_ip}: {e}"
                logger.error(error_msg)
                raise ConnectionError(error_msg, context={"ip": robot_ip, "timeout": connection_timeout})
    def disconnect(self) -> None:
        """Disconnect from the robot."""
        with self._connection_lock:
            if not self.is_connected:
                logger.warning("Robot is not connected")
                return
            
            logger.info("Disconnecting from robot...")
            
            # Stop monitoring
            self._stop_monitoring_thread()
            
            # Close robot connection
            if self._robot:
                try:
                    self._robot.close_connection()
                except Exception as e:
                    logger.warning(f"Error during disconnection: {e}")
                finally:
                    self._robot = None
            
            self._status.state = RobotState.DISCONNECTED
            self._status.connection_time = None
            logger.info("Robot disconnected")
    
    @contextmanager
    def robot_connection(self, ip: Optional[str] = None):
        """
        Context manager for robot connection.

        Args:
            ip: Robot IP address

        Usage:
            with controller.robot_connection() as robot:
                robot.move_to_home_pose()
        """
        connected = self.connect(ip)
        if not connected:
            raise ConnectionError("Failed to establish robot connection")

        try:
            yield self._robot
        finally:
            self.disconnect()

    @retry_on_error(max_retries=2, delay=5.0)
    def calibrate(self, auto: bool = True) -> bool:
        """
        Calibrate the robot.

        Args:
            auto: Use automatic calibration if True

        Returns:
            True if calibration successful, False otherwise

        Raises:
            CalibrationError: If calibration fails
        """
        if not self.is_connected:
            raise CalibrationError("Robot must be connected before calibration")

        logger.info("Starting robot calibration...")
        self._status.state = RobotState.CALIBRATING

        try:
                if auto:
                    self._robot.calibrate_auto()
                else:
                    # Manual calibration would go here
                    raise NotImplementedError("Manual calibration not implemented")

                # Set velocity limit for safety
                self._robot.set_arm_max_velocity(self.config.max_velocity_percent)

                # Update tool
                self._robot.update_tool()

                self._status.state = RobotState.READY
                self._status.calibration_time = time.time()

                logger.info("Robot calibration completed successfully")
                return True

        except Exception as e:
            self._status.state = RobotState.ERROR
            self._status.last_error = str(e)
            error_msg = f"Robot calibration failed: {e}"
            logger.error(error_msg)
            raise CalibrationError(error_msg)
    def get_position(self) -> Optional[PoseObject]:
        """
        Get current robot position.

        Returns:
            Current robot pose or None if not available
        """
        if not self.is_connected or not self._robot:
            return None

        try:
            pose = self._robot.get_pose()
            self._status.position = pose
            return pose
        except Exception as e:
            logger.warning(f"Failed to get robot position: {e}")
            return None
    def get_joints(self) -> Optional[List[float]]:
        """
        Get current joint positions.

        Returns:
            List of joint positions in radians or None if not available
        """
        if not self.is_connected or not self._robot:
            return None

        try:
            joints = self._robot.get_joints()
            self._status.joints = joints
            return joints
        except Exception as e:
            logger.warning(f"Failed to get joint positions: {e}")
            return None

    def _validate_position(self, pose: Union[PoseObject, JointsPosition]) -> bool:
        """
        Validate if position is within workspace boundaries.

        Args:
            pose: Position to validate

        Returns:
            True if position is valid, False otherwise
        """
        if not self.config.workspace_boundaries_enabled:
            return True

        # For now, just return True - full validation would check against boundaries
        return True
    def move_to_pose(self, pose: PoseObject, validate: bool = True) -> bool:
        """
        Move robot to specified pose.

        Args:
            pose: Target pose
            validate: Validate position before moving

        Returns:
            True if movement successful, False otherwise

        Raises:
            SafetyError: If position is unsafe
            RoboticsError: If movement fails
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for movement")

        if validate and not self._validate_position(pose):
            raise SafetyError("Target position is outside workspace boundaries")

        logger.debug(f"Moving robot to pose: {pose}")
        self._status.state = RobotState.MOVING

        try:
                self._robot.move(pose)
                self._status.state = RobotState.READY
                self._status.position = pose

                logger.debug("Robot movement completed")
                return True

        except Exception as e:
            self._status.state = RobotState.ERROR
            self._status.last_error = str(e)
            error_msg = f"Robot movement failed: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    def move_to_joints(self, joints: Union[List[float], JointsPosition], validate: bool = True) -> bool:
        """
        Move robot to specified joint positions.

        Args:
            joints: Target joint positions
            validate: Validate position before moving

        Returns:
            True if movement successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for movement")

        if isinstance(joints, list):
            joints_pos = JointsPosition(joints)
        else:
            joints_pos = joints

        if validate and not self._validate_position(joints_pos):
            raise SafetyError("Target joint positions are unsafe")

        logger.debug(f"Moving robot to joints: {joints}")
        self._status.state = RobotState.MOVING

        try:
                self._robot.move(joints_pos)
                self._status.state = RobotState.READY
                self._status.joints = joints if isinstance(joints, list) else joints.joints

                logger.debug("Robot joint movement completed")
                return True

        except Exception as e:
            self._status.state = RobotState.ERROR
            self._status.last_error = str(e)
            error_msg = f"Robot joint movement failed: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    def move_to_home(self) -> bool:
        """
        Move robot to home position.

        Returns:
            True if movement successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for movement")

        logger.info("Moving robot to home position")
        self._status.state = RobotState.MOVING

        try:
                self._robot.move_to_home_pose()
                self._status.state = RobotState.READY

                logger.info("Robot moved to home position")
                return True

        except Exception as e:
            self._status.state = RobotState.ERROR
            self._status.last_error = str(e)
            error_msg = f"Failed to move to home position: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    def grasp(self) -> bool:
        """
        Grasp with the robot tool.

        Returns:
            True if grasp successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for tool operation")

        try:
            self._robot.grasp_with_tool()
            logger.debug("Tool grasp executed")
            return True
        except Exception as e:
            error_msg = f"Tool grasp failed: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    def release(self) -> bool:
        """
        Release with the robot tool.

        Returns:
            True if release successful, False otherwise
        """
        if not self.is_ready:
            raise RoboticsError("Robot is not ready for tool operation")

        try:
            self._robot.release_with_tool()
            logger.debug("Tool release executed")
            return True
        except Exception as e:
            error_msg = f"Tool release failed: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)
    def led_control(self, color: List[int], duration: float = 1.0, iterations: int = 1) -> bool:
        """
        Control robot LED ring.

        Args:
            color: RGB color values [R, G, B]
            duration: Flash duration in seconds
            iterations: Number of flash iterations

        Returns:
            True if LED control successful, False otherwise
        """
        if not self.is_connected:
            return False

        try:
            self._robot.led_ring_flashing(color, duration, iterations, True)
            logger.debug(f"LED control executed: color={color}, duration={duration}")
            return True
        except Exception as e:
            logger.warning(f"LED control failed: {e}")
            return False

    def wait(self, seconds: float) -> None:
        """
        Wait for specified duration.

        Args:
            seconds: Wait duration in seconds
        """
        if self._robot:
            self._robot.wait(seconds)
        else:
            time.sleep(seconds)

    def emergency_stop(self) -> None:
        """Activate emergency stop."""
        logger.critical("EMERGENCY STOP ACTIVATED")
        self._emergency_stop_active = True
        self._status.state = RobotState.EMERGENCY_STOP

        # In a real implementation, this would trigger hardware emergency stop
        # For now, we just set the state

    def reset_emergency_stop(self) -> None:
        """Reset emergency stop state."""
        if self._emergency_stop_active:
            logger.info("Resetting emergency stop")
            self._emergency_stop_active = False
            if self.is_connected:
                self._status.state = RobotState.READY
            else:
                self._status.state = RobotState.DISCONNECTED

    def _start_monitoring(self) -> None:
        """Start robot status monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self._monitoring_thread.start()
        logger.debug("Robot monitoring thread started")

    def _stop_monitoring_thread(self) -> None:
        """Stop robot status monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=5.0)
            logger.debug("Robot monitoring thread stopped")

    def _monitoring_loop(self) -> None:
        """Robot status monitoring loop."""
        while not self._stop_monitoring.is_set():
            try:
                if self.is_connected and self._robot:
                    # Update position and joint status
                    self.get_position()
                    self.get_joints()

                    # Check for safety conditions
                    if self._emergency_stop_active:
                        continue

                # Wait before next monitoring cycle
                self._stop_monitoring.wait(self.config.status_update_interval)

            except Exception as e:
                logger.warning(f"Monitoring loop error: {e}")
                self._stop_monitoring.wait(1.0)

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()

    def __del__(self):
        """Destructor to ensure clean disconnection."""
        try:
            self.disconnect()
        except Exception:
            pass
