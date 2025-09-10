"""
Position Tracking and Logging System

This module provides comprehensive position tracking and logging capabilities for the Niryo Ned2 robotic arm,
including real-time monitoring, performance metrics analysis, and data export functionality.

Features:
- Real-time position and velocity tracking with timestamps
- Complete movement history logging and analysis
- Statistical analysis of positioning accuracy and repeatability
- Performance metrics calculation and monitoring
- Data export in CSV and JSON formats
- Movement pattern analysis and visualization data
"""

import time
import json
import csv
import math
import threading
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

try:
    from pyniryo import PoseObject, JointsPosition
except ImportError:
    # Mock classes for development without hardware
    class PoseObject:
        def __init__(self, x=0, y=0, z=0, roll=0, pitch=0, yaw=0):
            self.x, self.y, self.z = x, y, z
            self.roll, self.pitch, self.yaw = roll, pitch, yaw
    
    class JointsPosition:
        def __init__(self, joints: List[float]):
            self.joints = joints

from core.robot_controller import RobotController
from utils.config_manager import ConfigManager
from utils.logger import get_loggerndler import RoboticsError

logger = get_logger(__name__)


class TrackingMode(Enum):
    """Position tracking modes."""
    DISABLED = "disabled"
    BASIC = "basic"
    DETAILED = "detailed"
    CONTINUOUS = "continuous"


@dataclass
class PositionReading:
    """Single position reading with timestamp."""
    timestamp: float
    cartesian_pose: Optional[PoseObject] = None
    joint_positions: Optional[List[float]] = None
    velocity: Optional[float] = None
    acceleration: Optional[float] = None
    force_readings: Optional[List[float]] = None
    movement_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MovementSession:
    """Complete movement session record."""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    movement_type: str = "unknown"
    total_distance: float = 0.0
    max_velocity: float = 0.0
    avg_velocity: float = 0.0
    max_acceleration: float = 0.0
    position_readings: List[PositionReading] = field(default_factory=list)
    accuracy_metrics: Dict[str, float] = field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class PerformanceMetrics:
    """Robot performance metrics."""
    total_movements: int = 0
    total_distance: float = 0.0
    total_time: float = 0.0
    average_velocity: float = 0.0
    max_velocity: float = 0.0
    position_accuracy: float = 0.0  # RMS error in mm
    repeatability: float = 0.0  # Standard deviation in mm
    success_rate: float = 0.0
    uptime_percentage: float = 0.0
    last_updated: float = 0.0


class PositionTracker:
    """
    Advanced position tracking and logging system providing comprehensive
    monitoring, analysis, and data export capabilities.
    """
    
    def __init__(self, robot_controller: RobotController, config_manager=None):
        """
        Initialize position tracker.
        
        Args:
            robot_controller: Robot controller instance
            config_manager: Configuration manager instance
        """
        self.robot_controller = robot_controller
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get("config", {})
        
        # Tracking configuration
        self._tracking_mode = TrackingMode.DISABLED
        self._tracking_interval = 0.1  # seconds
        self._max_history_size = 10000  # maximum position readings to keep
        
        # Data storage
        self._position_history: deque = deque(maxlen=self._max_history_size)
        self._movement_sessions: List[MovementSession] = []
        self._current_session: Optional[MovementSession] = None
        
        # Performance metrics
        self._performance_metrics = PerformanceMetrics()
        
        # Threading for continuous tracking
        self._tracking_thread: Optional[threading.Thread] = None
        self._stop_tracking = threading.Event()
        self._tracking_lock = threading.Lock()
        
        # Data export configuration
        self._export_directory = Path("data/logs")
        self._export_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info("Position tracker initialized")
    
    @property
    def tracking_mode(self) -> TrackingMode:
        """Get current tracking mode."""
        return self._tracking_mode
    
    @property
    def is_tracking(self) -> bool:
        """Check if position tracking is active."""
        return self._tracking_mode != TrackingMode.DISABLED
    
    @property
    def position_history_size(self) -> int:
        """Get current position history size."""
        return len(self._position_history)
    
    def set_tracking_mode(self, mode: TrackingMode, interval: float = 0.1) -> None:
        """
        Set position tracking mode and interval.
        
        Args:
            mode: Tracking mode to set
            interval: Tracking interval in seconds
        """
        # Stop current tracking if active
        if self.is_tracking:
            self.stop_tracking()
        
        self._tracking_mode = mode
        self._tracking_interval = interval
        
        # Start tracking if mode is continuous
        if mode == TrackingMode.CONTINUOUS:
            self.start_continuous_tracking()
        
        logger.info(f"Tracking mode set to {mode.value} with {interval}s interval")
    
    def start_continuous_tracking(self) -> None:
        """Start continuous position tracking in background thread."""
        if self._tracking_thread and self._tracking_thread.is_alive():
            logger.warning("Continuous tracking already active")
            return
        
        self._stop_tracking.clear()
        self._tracking_thread = threading.Thread(target=self._continuous_tracking_loop)
        self._tracking_thread.daemon = True
        self._tracking_thread.start()
        
        logger.info("Continuous position tracking started")
    
    def stop_tracking(self) -> None:
        """Stop continuous position tracking."""
        if self._tracking_thread and self._tracking_thread.is_alive():
            self._stop_tracking.set()
            self._tracking_thread.join(timeout=2.0)
        
        # Finalize current session if active
        if self._current_session:
            self._finalize_current_session()
        
        logger.info("Position tracking stopped")
    
    def start_movement_session(self, movement_type: str = "unknown", 
                              session_id: Optional[str] = None) -> str:
        """
        Start a new movement session for tracking.
        
        Args:
            movement_type: Type of movement being tracked
            session_id: Optional custom session ID
            
        Returns:
            Session ID
        """
        # Finalize previous session if active
        if self._current_session:
            self._finalize_current_session()
        
        # Create new session
        session_id = session_id or f"session_{int(time.time())}"
        self._current_session = MovementSession(
            session_id=session_id,
            start_time=time.time(),
            movement_type=movement_type
        )
        
        logger.info(f"Started movement session: {session_id} ({movement_type})")
        return session_id
    
    def end_movement_session(self, success: bool = True, 
                           error_message: Optional[str] = None) -> Optional[MovementSession]:
        """
        End current movement session.
        
        Args:
            success: Whether the movement was successful
            error_message: Optional error message if unsuccessful
            
        Returns:
            Completed movement session or None if no active session
        """
        if not self._current_session:
            logger.warning("No active movement session to end")
            return None
        
        self._current_session.success = success
        self._current_session.error_message = error_message
        
        completed_session = self._finalize_current_session()
        logger.info(f"Ended movement session: {completed_session.session_id}")
        
        return completed_session
    def record_position(self, movement_id: Optional[str] = None, 
                       metadata: Optional[Dict[str, Any]] = None) -> Optional[PositionReading]:
        """
        Record current robot position.
        
        Args:
            movement_id: Optional movement identifier
            metadata: Optional metadata to include
            
        Returns:
            Position reading or None if robot not available
        """
        if not self.robot_controller.is_connected:
            return None
        
        try:
            # Get current position and joints
            cartesian_pose = self.robot_controller.get_position()
            joint_positions = self.robot_controller.get_joints()
            
            # Calculate velocity if we have previous reading
            velocity = self._calculate_velocity(cartesian_pose)
            
            # Create position reading
            reading = PositionReading(
                timestamp=time.time(),
                cartesian_pose=cartesian_pose,
                joint_positions=joint_positions,
                velocity=velocity,
                movement_id=movement_id,
                metadata=metadata or {}
            )
            
            # Store reading
            with self._tracking_lock:
                self._position_history.append(reading)
                
                # Add to current session if active
                if self._current_session:
                    self._current_session.position_readings.append(reading)
            
            return reading
        
        except Exception as e:
            logger.error(f"Failed to record position: {e}")
            return None

    def _finalize_current_session(self) -> MovementSession:
        """
        Finalize current movement session and calculate metrics.

        Returns:
            Finalized movement session
        """
        if not self._current_session:
            raise RoboticsError("No active session to finalize")

        session = self._current_session
        session.end_time = time.time()

        # Calculate session metrics
        if session.position_readings:
            session.total_distance = self._calculate_session_distance(session)
            velocities = [r.velocity for r in session.position_readings if r.velocity is not None]

            if velocities:
                session.max_velocity = max(velocities)
                session.avg_velocity = sum(velocities) / len(velocities)

            # Calculate accuracy metrics
            session.accuracy_metrics = self._calculate_accuracy_metrics(session)

        # Add to session history
        self._movement_sessions.append(session)
        self._current_session = None

        # Update performance metrics
        self._update_performance_metrics()

        return session

    def _calculate_session_distance(self, session: MovementSession) -> float:
        """Calculate total distance traveled in session."""
        total_distance = 0.0

        for i in range(1, len(session.position_readings)):
            prev_reading = session.position_readings[i-1]
            curr_reading = session.position_readings[i]

            if prev_reading.cartesian_pose and curr_reading.cartesian_pose:
                prev_pose = prev_reading.cartesian_pose
                curr_pose = curr_reading.cartesian_pose

                distance = math.sqrt(
                    (curr_pose.x - prev_pose.x) ** 2 +
                    (curr_pose.y - prev_pose.y) ** 2 +
                    (curr_pose.z - prev_pose.z) ** 2
                )
                total_distance += distance

        return total_distance

    def _calculate_accuracy_metrics(self, session: MovementSession) -> Dict[str, float]:
        """Calculate accuracy metrics for session."""
        metrics = {}

        if len(session.position_readings) < 2:
            return metrics

        # Calculate position deviations
        deviations = []
        for i in range(1, len(session.position_readings)):
            prev_reading = session.position_readings[i-1]
            curr_reading = session.position_readings[i]

            if prev_reading.cartesian_pose and curr_reading.cartesian_pose:
                # Simple deviation calculation (could be enhanced with target positions)
                deviation = abs(curr_reading.velocity or 0) - abs(prev_reading.velocity or 0)
                deviations.append(abs(deviation))

        if deviations:
            metrics['rms_error'] = math.sqrt(sum(d**2 for d in deviations) / len(deviations))
            metrics['max_deviation'] = max(deviations)
            metrics['avg_deviation'] = sum(deviations) / len(deviations)
            metrics['std_deviation'] = math.sqrt(
                sum((d - metrics['avg_deviation'])**2 for d in deviations) / len(deviations)
            )

        return metrics

    def _update_performance_metrics(self) -> None:
        """Update overall performance metrics."""
        if not self._movement_sessions:
            return

        # Calculate aggregate metrics
        total_movements = len(self._movement_sessions)
        successful_movements = sum(1 for s in self._movement_sessions if s.success)

        total_distance = sum(s.total_distance for s in self._movement_sessions)
        total_time = sum((s.end_time or s.start_time) - s.start_time for s in self._movement_sessions)

        velocities = []
        accuracies = []

        for session in self._movement_sessions:
            if session.max_velocity > 0:
                velocities.append(session.max_velocity)

            if 'rms_error' in session.accuracy_metrics:
                accuracies.append(session.accuracy_metrics['rms_error'])

        # Update metrics
        self._performance_metrics.total_movements = total_movements
        self._performance_metrics.total_distance = total_distance
        self._performance_metrics.total_time = total_time
        self._performance_metrics.success_rate = successful_movements / total_movements if total_movements > 0 else 0.0

        if velocities:
            self._performance_metrics.average_velocity = sum(velocities) / len(velocities)
            self._performance_metrics.max_velocity = max(velocities)

        if accuracies:
            self._performance_metrics.position_accuracy = sum(accuracies) / len(accuracies)
            self._performance_metrics.repeatability = math.sqrt(
                sum((a - self._performance_metrics.position_accuracy)**2 for a in accuracies) / len(accuracies)
            )

        self._performance_metrics.last_updated = time.time()

    def get_performance_metrics(self) -> PerformanceMetrics:
        """
        Get current performance metrics.

        Returns:
            Performance metrics
        """
        return self._performance_metrics

    def get_movement_sessions(self, limit: Optional[int] = None) -> List[MovementSession]:
        """
        Get movement session history.

        Args:
            limit: Optional limit on number of sessions to return

        Returns:
            List of movement sessions
        """
        sessions = self._movement_sessions.copy()
        if limit:
            sessions = sessions[-limit:]
        return sessions

    def get_position_history(self, limit: Optional[int] = None,
                           start_time: Optional[float] = None,
                           end_time: Optional[float] = None) -> List[PositionReading]:
        """
        Get position reading history with optional filtering.

        Args:
            limit: Optional limit on number of readings
            start_time: Optional start time filter
            end_time: Optional end time filter

        Returns:
            List of position readings
        """
        with self._tracking_lock:
            readings = list(self._position_history)

        # Apply time filters
        if start_time or end_time:
            filtered_readings = []
            for reading in readings:
                if start_time and reading.timestamp < start_time:
                    continue
                if end_time and reading.timestamp > end_time:
                    continue
                filtered_readings.append(reading)
            readings = filtered_readings

        # Apply limit
        if limit:
            readings = readings[-limit:]

        return readings
    def export_data(self, format_type: str = "csv",
                   filename: Optional[str] = None,
                   include_sessions: bool = True,
                   include_positions: bool = True) -> str:
        """
        Export tracking data to file.

        Args:
            format_type: Export format ("csv" or "json")
            filename: Optional custom filename
            include_sessions: Include movement sessions
            include_positions: Include position readings

        Returns:
            Path to exported file
        """
        if format_type not in ["csv", "json"]:
            raise ValueError("Format must be 'csv' or 'json'")

        # Generate filename if not provided
        if not filename:
            timestamp = int(time.time())
            filename = f"robot_tracking_data_{timestamp}.{format_type}"

        filepath = self._export_directory / filename

        try:
            if format_type == "csv":
                self._export_csv(filepath, include_sessions, include_positions)
            else:
                self._export_json(filepath, include_sessions, include_positions)

            logger.info(f"Data exported to {filepath}")
            return str(filepath)

        except Exception as e:
            error_msg = f"Failed to export data: {e}"
            logger.error(error_msg)
            raise RoboticsError(error_msg)

    def _export_csv(self, filepath: Path, include_sessions: bool, include_positions: bool) -> None:
        """Export data to CSV format."""
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Export performance metrics
            writer.writerow(["Performance Metrics"])
            writer.writerow(["Metric", "Value"])
            metrics = asdict(self._performance_metrics)
            for key, value in metrics.items():
                writer.writerow([key, value])
            writer.writerow([])  # Empty row

            # Export movement sessions
            if include_sessions and self._movement_sessions:
                writer.writerow(["Movement Sessions"])
                writer.writerow([
                    "Session ID", "Start Time", "End Time", "Movement Type",
                    "Total Distance", "Max Velocity", "Avg Velocity", "Success"
                ])

                for session in self._movement_sessions:
                    writer.writerow([
                        session.session_id,
                        session.start_time,
                        session.end_time or "",
                        session.movement_type,
                        session.total_distance,
                        session.max_velocity,
                        session.avg_velocity,
                        session.success
                    ])
                writer.writerow([])  # Empty row

            # Export position readings
            if include_positions:
                writer.writerow(["Position Readings"])
                writer.writerow([
                    "Timestamp", "X", "Y", "Z", "Roll", "Pitch", "Yaw",
                    "Joint1", "Joint2", "Joint3", "Joint4", "Joint5", "Joint6",
                    "Velocity", "Movement ID"
                ])

                with self._tracking_lock:
                    for reading in self._position_history:
                        pose = reading.cartesian_pose
                        joints = reading.joint_positions or [0] * 6

                        writer.writerow([
                            reading.timestamp,
                            pose.x if pose else "",
                            pose.y if pose else "",
                            pose.z if pose else "",
                            pose.roll if pose else "",
                            pose.pitch if pose else "",
                            pose.yaw if pose else "",
                            *joints[:6],  # Ensure 6 joint values
                            reading.velocity or "",
                            reading.movement_id or ""
                        ])

    def _export_json(self, filepath: Path, include_sessions: bool, include_positions: bool) -> None:
        """Export data to JSON format."""
        export_data = {
            "export_timestamp": time.time(),
            "performance_metrics": asdict(self._performance_metrics)
        }

        if include_sessions:
            export_data["movement_sessions"] = []
            for session in self._movement_sessions:
                session_data = asdict(session)
                # Convert position readings to serializable format
                session_data["position_readings"] = [
                    self._position_reading_to_dict(reading)
                    for reading in session.position_readings
                ]
                export_data["movement_sessions"].append(session_data)

        if include_positions:
            with self._tracking_lock:
                export_data["position_readings"] = [
                    self._position_reading_to_dict(reading)
                    for reading in self._position_history
                ]

        with open(filepath, 'w', encoding='utf-8') as jsonfile:
            json.dump(export_data, jsonfile, indent=2, default=str)

    def _position_reading_to_dict(self, reading: PositionReading) -> Dict[str, Any]:
        """Convert position reading to dictionary for JSON export."""
        data = {
            "timestamp": reading.timestamp,
            "velocity": reading.velocity,
            "acceleration": reading.acceleration,
            "movement_id": reading.movement_id,
            "metadata": reading.metadata
        }

        if reading.cartesian_pose:
            data["cartesian_pose"] = {
                "x": reading.cartesian_pose.x,
                "y": reading.cartesian_pose.y,
                "z": reading.cartesian_pose.z,
                "roll": reading.cartesian_pose.roll,
                "pitch": reading.cartesian_pose.pitch,
                "yaw": reading.cartesian_pose.yaw
            }

        if reading.joint_positions:
            data["joint_positions"] = reading.joint_positions

        if reading.force_readings:
            data["force_readings"] = reading.force_readings

        return data

    def clear_history(self, confirm: bool = False) -> None:
        """
        Clear all tracking history.

        Args:
            confirm: Confirmation flag to prevent accidental clearing
        """
        if not confirm:
            raise ValueError("Must set confirm=True to clear history")

        with self._tracking_lock:
            self._position_history.clear()
            self._movement_sessions.clear()
            self._performance_metrics = PerformanceMetrics()

        logger.info("All tracking history cleared")

    def get_tracking_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive tracking statistics.

        Returns:
            Dictionary with tracking statistics
        """
        with self._tracking_lock:
            position_count = len(self._position_history)

        session_count = len(self._movement_sessions)

        # Calculate time span
        if self._movement_sessions:
            start_time = min(s.start_time for s in self._movement_sessions)
            end_time = max((s.end_time or s.start_time) for s in self._movement_sessions)
            time_span = end_time - start_time
        else:
            time_span = 0.0

        return {
            "tracking_mode": self._tracking_mode.value,
            "tracking_interval": self._tracking_interval,
            "position_readings_count": position_count,
            "movement_sessions_count": session_count,
            "tracking_time_span": time_span,
            "max_history_size": self._max_history_size,
            "performance_metrics": asdict(self._performance_metrics),
            "is_tracking_active": self.is_tracking,
            "current_session_active": self._current_session is not None
        }
    
    def _continuous_tracking_loop(self) -> None:
        """Continuous tracking loop running in background thread."""
        logger.debug("Starting continuous tracking loop")
        
        while not self._stop_tracking.is_set():
            try:
                self.record_position(movement_id="continuous")
                time.sleep(self._tracking_interval)
            except Exception as e:
                logger.error(f"Error in continuous tracking: {e}")
                time.sleep(1.0)  # Wait longer on error
        
        logger.debug("Continuous tracking loop stopped")
    
    def _calculate_velocity(self, current_pose: Optional[PoseObject]) -> Optional[float]:
        """
        Calculate velocity based on position change.
        
        Args:
            current_pose: Current robot pose
            
        Returns:
            Velocity in mm/s or None if cannot calculate
        """
        if not current_pose or len(self._position_history) == 0:
            return None
        
        # Get last position reading
        last_reading = self._position_history[-1]
        if not last_reading.cartesian_pose:
            return None
        
        # Calculate distance and time difference
        last_pose = last_reading.cartesian_pose
        distance = math.sqrt(
            (current_pose.x - last_pose.x) ** 2 +
            (current_pose.y - last_pose.y) ** 2 +
            (current_pose.z - last_pose.z) ** 2
        )
        
        time_diff = time.time() - last_reading.timestamp
        
        if time_diff > 0:
            return distance / time_diff  # mm/s
        
        return None
