"""
Sensor Interface System

This module provides comprehensive sensor integration capabilities for the Niryo
automation system, enabling infrared sensor monitoring, real-time event handling,
and object tracking along conveyor paths.

Features:
- Infrared sensor monitoring with configurable sensitivity
- Real-time event handling and callback system
- Sensor calibration and validation procedures
- Object detection and tracking along conveyor path
- Integration with Phase 3 vision system for enhanced detection
- Performance monitoring and diagnostics
"""

import time
import threading
from typing import Optional, Dict, Any, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
import json
from pathlib import Path

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError

try:
    from pyniryo import NiryoRobot
    import RPi.GPIO as GPIO  # For Raspberry Pi GPIO access
except ImportError:
    # Mock for development without hardware
    class NiryoRobot:
        def __init__(self, ip_address):
            self.ip_address = ip_address
        
        def get_digital_io_state(self, pin):
            return False  # Mock sensor reading
    
    class GPIO:
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        RISING = "RISING"
        FALLING = "FALLING"
        BOTH = "BOTH"
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod
        def setup(pin, mode, pull_up_down=None): pass
        @staticmethod
        def input(pin): return False
        @staticmethod
        def add_event_detect(pin, edge, callback=None, bouncetime=None): pass
        @staticmethod
        def remove_event_detect(pin): pass
        @staticmethod
        def cleanup(): pass

logger = get_logger(__name__)


class SensorType(Enum):
    """Sensor type options."""
    INFRARED = "infrared"
    PROXIMITY = "proximity"
    PHOTOELECTRIC = "photoelectric"
    MAGNETIC = "magnetic"
    PRESSURE = "pressure"


class SensorState(Enum):
    """Sensor state options."""
    INACTIVE = "inactive"
    ACTIVE = "active"
    TRIGGERED = "triggered"
    ERROR = "error"
    CALIBRATING = "calibrating"


class SensorEvent(Enum):
    """Sensor event types."""
    OBJECT_DETECTED = "object_detected"
    OBJECT_CLEARED = "object_cleared"
    SENSOR_TRIGGERED = "sensor_triggered"
    SENSOR_ERROR = "sensor_error"
    CALIBRATION_COMPLETE = "calibration_complete"


class SensorError(RoboticsError):
    """Sensor-specific error class."""
    pass


@dataclass
class SensorConfiguration:
    """Sensor configuration parameters."""
    sensor_id: str
    sensor_type: SensorType
    pin_number: int
    
    # Sensitivity settings
    trigger_threshold: float = 0.5  # Threshold for triggering (0.0-1.0)
    debounce_time: float = 0.05     # Debounce time in seconds
    
    # Timing settings
    min_trigger_duration: float = 0.01  # Minimum trigger duration
    max_trigger_duration: float = 10.0  # Maximum trigger duration
    
    # Calibration settings
    calibration_samples: int = 100
    calibration_duration: float = 10.0  # seconds
    
    # Position settings (for conveyor tracking)
    position_on_belt: float = 0.0  # Position along conveyor (mm)
    detection_zone_width: float = 50.0  # Detection zone width (mm)
    
    # Advanced settings
    invert_logic: bool = False  # Invert sensor logic
    enable_filtering: bool = True  # Enable signal filtering
    filter_window: int = 5  # Moving average window size


@dataclass
class SensorReading:
    """Individual sensor reading data."""
    sensor_id: str
    timestamp: float
    raw_value: float
    filtered_value: float
    state: SensorState
    triggered: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SensorEvent:
    """Sensor event data."""
    event_type: SensorEvent
    sensor_id: str
    timestamp: float
    reading: SensorReading
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ObjectTrackingData:
    """Object tracking information."""
    object_id: str
    first_detection_time: float
    last_detection_time: float
    sensors_triggered: List[str]
    estimated_speed: Optional[float] = None  # mm/s
    estimated_position: Optional[float] = None  # mm along belt
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SensorInterface:
    """
    Advanced sensor interface system providing infrared sensor monitoring,
    real-time event handling, and object tracking capabilities.
    """
    
    def __init__(self, robot_ip: str = "127.0.0.1", config_manager=None):
        """
        Initialize sensor interface.
        
        Args:
            robot_ip: IP address of Niryo robot
            config_manager: Configuration manager instance
        """
        self.robot_ip = robot_ip
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Sensor configurations
        self.sensors: Dict[str, SensorConfiguration] = {}
        
        # Robot connection
        self._robot: Optional[NiryoRobot] = None
        self._connected = False
        
        # Monitoring and event handling
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_monitoring = threading.Event()
        self._event_queue = Queue()
        
        # Sensor readings and state
        self._sensor_readings: Dict[str, List[SensorReading]] = {}
        self._sensor_states: Dict[str, SensorState] = {}
        self._last_readings: Dict[str, SensorReading] = {}
        
        # Object tracking
        self._tracked_objects: Dict[str, ObjectTrackingData] = {}
        self._object_counter = 0
        
        # Event callbacks
        self._event_callbacks: Dict[SensorEvent, List[Callable]] = {
            event_type: [] for event_type in SensorEvent
        }
        
        # Performance monitoring
        self._performance_monitor = PerformanceMonitor()
        self._statistics = {
            'total_readings': 0,
            'total_events': 0,
            'objects_tracked': 0,
            'calibrations_performed': 0,
            'errors_detected': 0
        }
        
        # Calibration data storage
        self._calibration_file = Path("data/sensor_calibration.json")
        self._calibration_file.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info("Sensor interface initialized")
    
    @property
    def is_connected(self) -> bool:
        """Check if sensor interface is connected."""
        return self._connected
    
    @property
    def active_sensors(self) -> List[str]:
        """Get list of active sensor IDs."""
        return [sensor_id for sensor_id, state in self._sensor_states.items() 
                if state == SensorState.ACTIVE]
    
    @property
    def tracked_objects_count(self) -> int:
        """Get number of currently tracked objects."""
        return len(self._tracked_objects)
    
    def connect(self) -> bool:
        """
        Connect to sensor interface system.
        
        Returns:
            True if connection successful
        """
        logger.info(f"Connecting to sensor interface at {self.robot_ip}...")
        
        try:
            self._robot = NiryoRobot(self.robot_ip)
            self._connected = True
            
            # Initialize GPIO for direct sensor access
            GPIO.setmode(GPIO.BCM)
            
            # Load calibration data
            self._load_calibration_data()
            
            # Start monitoring thread
            self._start_monitoring()
            
            logger.info("Sensor interface connected successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to connect to sensor interface: {e}"
            logger.error(error_msg)
            return False
    
    def disconnect(self) -> None:
        """Disconnect from sensor interface system."""
        logger.info("Disconnecting from sensor interface...")
        
        try:
            # Stop monitoring
            self._stop_monitoring_thread()
            
            # Cleanup GPIO
            GPIO.cleanup()
            
            # Save calibration data
            self._save_calibration_data()
            
            # Disconnect robot
            self._robot = None
            self._connected = False
            
            logger.info("Sensor interface disconnected")
            
        except Exception as e:
            logger.error(f"Error during sensor interface disconnect: {e}")
    
    def add_sensor(self, config: SensorConfiguration) -> bool:
        """
        Add sensor to monitoring system.
        
        Args:
            config: Sensor configuration
            
        Returns:
            True if sensor added successfully
        """
        logger.info(f"Adding sensor: {config.sensor_id} (type: {config.sensor_type.value})")
        
        try:
            # Setup GPIO pin
            GPIO.setup(config.pin_number, GPIO.IN)
            
            # Add sensor configuration
            self.sensors[config.sensor_id] = config
            self._sensor_states[config.sensor_id] = SensorState.INACTIVE
            self._sensor_readings[config.sensor_id] = []
            
            logger.info(f"Sensor {config.sensor_id} added successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add sensor {config.sensor_id}: {e}"
            logger.error(error_msg)
            return False
    
    def remove_sensor(self, sensor_id: str) -> bool:
        """
        Remove sensor from monitoring system.
        
        Args:
            sensor_id: ID of sensor to remove
            
        Returns:
            True if sensor removed successfully
        """
        if sensor_id not in self.sensors:
            logger.warning(f"Sensor {sensor_id} not found")
            return False
        
        logger.info(f"Removing sensor: {sensor_id}")
        
        try:
            # Remove GPIO event detection
            config = self.sensors[sensor_id]
            GPIO.remove_event_detect(config.pin_number)
            
            # Remove from tracking
            del self.sensors[sensor_id]
            del self._sensor_states[sensor_id]
            del self._sensor_readings[sensor_id]
            
            if sensor_id in self._last_readings:
                del self._last_readings[sensor_id]
            
            logger.info(f"Sensor {sensor_id} removed successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to remove sensor {sensor_id}: {e}"
            logger.error(error_msg)
            return False
    
    def activate_sensor(self, sensor_id: str) -> bool:
        """
        Activate sensor for monitoring.
        
        Args:
            sensor_id: ID of sensor to activate
            
        Returns:
            True if sensor activated successfully
        """
        if sensor_id not in self.sensors:
            raise SensorError(f"Sensor {sensor_id} not found")
        
        logger.info(f"Activating sensor: {sensor_id}")
        
        try:
            config = self.sensors[sensor_id]
            
            # Setup event detection
            GPIO.add_event_detect(
                config.pin_number,
                GPIO.BOTH,  # Detect both rising and falling edges
                callback=lambda channel: self._gpio_callback(sensor_id, channel),
                bouncetime=int(config.debounce_time * 1000)  # Convert to milliseconds
            )
            
            # Update state
            self._sensor_states[sensor_id] = SensorState.ACTIVE
            
            logger.info(f"Sensor {sensor_id} activated successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to activate sensor {sensor_id}: {e}"
            logger.error(error_msg)
            self._sensor_states[sensor_id] = SensorState.ERROR
            return False
    
    def deactivate_sensor(self, sensor_id: str) -> bool:
        """
        Deactivate sensor monitoring.
        
        Args:
            sensor_id: ID of sensor to deactivate
            
        Returns:
            True if sensor deactivated successfully
        """
        if sensor_id not in self.sensors:
            raise SensorError(f"Sensor {sensor_id} not found")
        
        logger.info(f"Deactivating sensor: {sensor_id}")
        
        try:
            config = self.sensors[sensor_id]
            
            # Remove event detection
            GPIO.remove_event_detect(config.pin_number)
            
            # Update state
            self._sensor_states[sensor_id] = SensorState.INACTIVE
            
            logger.info(f"Sensor {sensor_id} deactivated successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to deactivate sensor {sensor_id}: {e}"
            logger.error(error_msg)
            return False
    def calibrate_sensor(self, sensor_id: str) -> bool:
        """
        Calibrate sensor for optimal performance.

        Args:
            sensor_id: ID of sensor to calibrate

        Returns:
            True if calibration successful
        """
        if sensor_id not in self.sensors:
            raise SensorError(f"Sensor {sensor_id} not found")

        config = self.sensors[sensor_id]
        logger.info(f"Starting calibration for sensor: {sensor_id}")

        try:
            # Set calibration state
            self._sensor_states[sensor_id] = SensorState.CALIBRATING

            # Collect calibration samples
            samples = []
            start_time = time.time()

            while (len(samples) < config.calibration_samples and
                   time.time() - start_time < config.calibration_duration):

                # Read sensor value
                raw_value = self._read_sensor_raw(sensor_id)
                samples.append(raw_value)

                time.sleep(0.1)  # 10Hz sampling rate

            if len(samples) < config.calibration_samples // 2:
                raise SensorError(f"Insufficient calibration samples: {len(samples)}")

            # Calculate calibration parameters
            mean_value = sum(samples) / len(samples)
            variance = sum((x - mean_value) ** 2 for x in samples) / len(samples)
            std_dev = variance ** 0.5

            # Update sensor configuration with calibration data
            calibration_data = {
                'mean': mean_value,
                'std_dev': std_dev,
                'samples': len(samples),
                'timestamp': time.time(),
                'threshold': mean_value + (2 * std_dev)  # 2-sigma threshold
            }

            # Store calibration data
            self._store_sensor_calibration(sensor_id, calibration_data)

            # Update sensor state
            self._sensor_states[sensor_id] = SensorState.ACTIVE
            self._statistics['calibrations_performed'] += 1

            # Trigger calibration complete event
            self._trigger_event(SensorEvent.CALIBRATION_COMPLETE, sensor_id, None)

            logger.info(f"Sensor {sensor_id} calibrated successfully")
            return True

        except Exception as e:
            error_msg = f"Failed to calibrate sensor {sensor_id}: {e}"
            logger.error(error_msg)
            self._sensor_states[sensor_id] = SensorState.ERROR
            self._statistics['errors_detected'] += 1
            return False

    def _read_sensor_raw(self, sensor_id: str) -> float:
        """
        Read raw sensor value.

        Args:
            sensor_id: ID of sensor to read

        Returns:
            Raw sensor value (0.0-1.0)
        """
        if sensor_id not in self.sensors:
            raise SensorError(f"Sensor {sensor_id} not found")

        config = self.sensors[sensor_id]

        try:
            # Read digital value from GPIO
            digital_value = GPIO.input(config.pin_number)

            # Convert to normalized float (0.0-1.0)
            raw_value = 1.0 if digital_value else 0.0

            # Apply logic inversion if configured
            if config.invert_logic:
                raw_value = 1.0 - raw_value

            return raw_value

        except Exception as e:
            logger.error(f"Failed to read sensor {sensor_id}: {e}")
            return 0.0

    def _gpio_callback(self, sensor_id: str, channel: int) -> None:
        """
        GPIO interrupt callback for sensor events.

        Args:
            sensor_id: ID of sensor that triggered
            channel: GPIO channel number
        """
        try:
            # Read current sensor value
            raw_value = self._read_sensor_raw(sensor_id)

            # Create sensor reading
            reading = SensorReading(
                sensor_id=sensor_id,
                timestamp=time.time(),
                raw_value=raw_value,
                filtered_value=self._apply_filtering(sensor_id, raw_value),
                state=self._sensor_states.get(sensor_id, SensorState.INACTIVE),
                triggered=raw_value > self.sensors[sensor_id].trigger_threshold
            )

            # Store reading
            self._store_reading(reading)

            # Process sensor event
            self._process_sensor_reading(reading)

        except Exception as e:
            logger.error(f"Error in GPIO callback for sensor {sensor_id}: {e}")

    def _apply_filtering(self, sensor_id: str, raw_value: float) -> float:
        """
        Apply filtering to sensor reading.

        Args:
            sensor_id: ID of sensor
            raw_value: Raw sensor value

        Returns:
            Filtered sensor value
        """
        config = self.sensors[sensor_id]

        if not config.enable_filtering:
            return raw_value

        # Get recent readings for moving average
        recent_readings = self._sensor_readings.get(sensor_id, [])

        if len(recent_readings) < config.filter_window:
            return raw_value

        # Calculate moving average
        recent_values = [r.raw_value for r in recent_readings[-config.filter_window:]]
        filtered_value = sum(recent_values) / len(recent_values)

        return filtered_value

    def _store_reading(self, reading: SensorReading) -> None:
        """
        Store sensor reading in history.

        Args:
            reading: Sensor reading to store
        """
        sensor_id = reading.sensor_id

        # Add to readings history
        if sensor_id not in self._sensor_readings:
            self._sensor_readings[sensor_id] = []

        self._sensor_readings[sensor_id].append(reading)

        # Keep only last 1000 readings per sensor
        if len(self._sensor_readings[sensor_id]) > 1000:
            self._sensor_readings[sensor_id].pop(0)

        # Update last reading
        self._last_readings[sensor_id] = reading

        # Update statistics
        self._statistics['total_readings'] += 1

    def _start_monitoring(self) -> None:
        """Start monitoring thread for sensor readings."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._stop_monitoring.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop,
            daemon=True
        )
        self._monitoring_thread.start()
        logger.debug("Sensor monitoring started")

    def _stop_monitoring_thread(self) -> None:
        """Stop monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._stop_monitoring.set()
            self._monitoring_thread.join(timeout=2.0)
        logger.debug("Sensor monitoring stopped")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for sensor readings."""
        logger.debug("Starting sensor monitoring loop")

        while not self._stop_monitoring.is_set():
            try:
                # Process event queue
                try:
                    event = self._event_queue.get_nowait()
                    logger.debug(f"Processing event: {event.event_type.value}")
                except Empty:
                    pass

                # Periodic sensor health checks
                self._perform_health_checks()

                # Clean up old tracked objects
                self._cleanup_tracked_objects()

                # Sleep for monitoring interval
                self._stop_monitoring.wait(0.1)  # 10Hz monitoring

            except Exception as e:
                logger.warning(f"Error in sensor monitoring loop: {e}")
                time.sleep(1.0)

        logger.debug("Sensor monitoring loop stopped")

    def _perform_health_checks(self) -> None:
        """Perform periodic health checks on sensors."""
        current_time = time.time()

        for sensor_id, state in self._sensor_states.items():
            if state == SensorState.ACTIVE:
                # Check if sensor is responding
                last_reading = self._last_readings.get(sensor_id)
                if last_reading and (current_time - last_reading.timestamp) > 10.0:
                    logger.warning(f"Sensor {sensor_id} not responding")
                    self._sensor_states[sensor_id] = SensorState.ERROR

    def _cleanup_tracked_objects(self) -> None:
        """Clean up old tracked objects."""
        current_time = time.time()
        cleanup_threshold = 30.0  # 30 seconds

        objects_to_remove = []
        for object_id, tracking_data in self._tracked_objects.items():
            if (current_time - tracking_data.last_detection_time) > cleanup_threshold:
                objects_to_remove.append(object_id)

        for object_id in objects_to_remove:
            del self._tracked_objects[object_id]
            logger.debug(f"Cleaned up tracked object: {object_id}")

    def _store_sensor_calibration(self, sensor_id: str, calibration_data: Dict[str, Any]) -> None:
        """Store sensor calibration data."""
        try:
            # Load existing calibration data
            if self._calibration_file.exists():
                with open(self._calibration_file, 'r') as f:
                    all_calibrations = json.load(f)
            else:
                all_calibrations = {}

            # Update calibration for this sensor
            all_calibrations[sensor_id] = calibration_data

            # Save updated calibration data
            with open(self._calibration_file, 'w') as f:
                json.dump(all_calibrations, f, indent=2)

            logger.debug(f"Stored calibration data for sensor {sensor_id}")

        except Exception as e:
            logger.error(f"Failed to store calibration data: {e}")

    def _load_calibration_data(self) -> None:
        """Load sensor calibration data."""
        try:
            if self._calibration_file.exists():
                with open(self._calibration_file, 'r') as f:
                    calibration_data = json.load(f)

                logger.info(f"Loaded calibration data for {len(calibration_data)} sensors")
            else:
                logger.info("No calibration data file found")

        except Exception as e:
            logger.error(f"Failed to load calibration data: {e}")

    def _save_calibration_data(self) -> None:
        """Save current calibration data."""
        # This is handled by _store_sensor_calibration
        pass

    def get_sensor_status(self, sensor_id: str) -> Dict[str, Any]:
        """
        Get comprehensive sensor status.

        Args:
            sensor_id: ID of sensor

        Returns:
            Dictionary with sensor status information
        """
        if sensor_id not in self.sensors:
            raise SensorError(f"Sensor {sensor_id} not found")

        config = self.sensors[sensor_id]
        state = self._sensor_states[sensor_id]
        last_reading = self._last_readings.get(sensor_id)
        readings_count = len(self._sensor_readings.get(sensor_id, []))

        return {
            'sensor_id': sensor_id,
            'type': config.sensor_type.value,
            'state': state.value,
            'pin_number': config.pin_number,
            'position_on_belt': config.position_on_belt,
            'trigger_threshold': config.trigger_threshold,
            'last_reading': {
                'timestamp': last_reading.timestamp if last_reading else None,
                'raw_value': last_reading.raw_value if last_reading else None,
                'filtered_value': last_reading.filtered_value if last_reading else None,
                'triggered': last_reading.triggered if last_reading else False
            } if last_reading else None,
            'readings_count': readings_count,
            'calibrated': state != SensorState.INACTIVE
        }

    def get_all_sensor_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status for all sensors.

        Returns:
            Dictionary mapping sensor IDs to status information
        """
        return {sensor_id: self.get_sensor_status(sensor_id)
                for sensor_id in self.sensors.keys()}

    def get_tracked_objects(self) -> Dict[str, Dict[str, Any]]:
        """
        Get information about currently tracked objects.

        Returns:
            Dictionary mapping object IDs to tracking information
        """
        result = {}
        for object_id, tracking_data in self._tracked_objects.items():
            result[object_id] = {
                'object_id': object_id,
                'first_detection_time': tracking_data.first_detection_time,
                'last_detection_time': tracking_data.last_detection_time,
                'sensors_triggered': tracking_data.sensors_triggered,
                'estimated_speed': tracking_data.estimated_speed,
                'estimated_position': tracking_data.estimated_position,
                'confidence': tracking_data.confidence,
                'age': time.time() - tracking_data.first_detection_time
            }
        return result

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get sensor interface statistics.

        Returns:
            Dictionary with statistics information
        """
        return {
            'connected': self.is_connected,
            'active_sensors': len(self.active_sensors),
            'total_sensors': len(self.sensors),
            'tracked_objects': self.tracked_objects_count,
            'statistics': self._statistics.copy(),
            'uptime': time.time() - (self._statistics.get('start_time', time.time()))
        }

    def reset_statistics(self) -> None:
        """Reset sensor interface statistics."""
        self._statistics = {
            'total_readings': 0,
            'total_events': 0,
            'objects_tracked': 0,
            'calibrations_performed': 0,
            'errors_detected': 0,
            'start_time': time.time()
        }
        logger.info("Sensor interface statistics reset")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
