"""
Camera Interface Module

This module provides comprehensive camera interface capabilities for the Niryo Vision Set,
including real-time image capture, streaming, parameter control, and error handling.

Features:
- Real-time image capture and streaming at 30fps minimum
- Camera parameter control (exposure, focus, resolution, white balance)
- Image format conversion and optimization
- Error handling for camera disconnection and automatic recovery
- Performance monitoring and frame rate optimization
- Educational debugging and visualization tools
"""

import cv2
import numpy as np
import time
import threading
from typing import Optional, Tuple, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum
from queue import Queue, Empty
from pathlib import Path

from utils.config_manager import ConfigManager
from utils.logger import get_logger
from utils.error_handler import RoboticsError, VisionError

logger = get_logger(__name__)


class CameraStatus(Enum):
    """Camera connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    ERROR = "error"


class ImageFormat(Enum):
    """Supported image formats."""
    BGR = "bgr"
    RGB = "rgb"
    GRAY = "gray"
    HSV = "hsv"
    LAB = "lab"


@dataclass
class CameraParameters:
    """Camera configuration parameters."""
    resolution: Tuple[int, int] = (640, 480)  # Width, Height
    fps: int = 30
    exposure: float = -1  # Auto exposure if -1
    brightness: float = 0.5
    contrast: float = 0.5
    saturation: float = 0.5
    hue: float = 0.0
    white_balance: float = -1  # Auto white balance if -1
    focus: float = -1  # Auto focus if -1
    zoom: float = 1.0
    auto_exposure: bool = True
    auto_white_balance: bool = True
    auto_focus: bool = True


@dataclass
class FrameInfo:
    """Information about captured frame."""
    timestamp: float
    frame_number: int
    resolution: Tuple[int, int]
    format: ImageFormat
    file_size: int = 0
    processing_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CameraStats:
    """Camera performance statistics."""
    frames_captured: int = 0
    frames_dropped: int = 0
    average_fps: float = 0.0
    current_fps: float = 0.0
    total_capture_time: float = 0.0
    last_frame_time: float = 0.0
    connection_uptime: float = 0.0
    error_count: int = 0
    last_error: Optional[str] = None


class CameraInterface:
    """
    Advanced camera interface providing real-time image capture,
    streaming, and comprehensive camera control for the Niryo Vision Set.
    """
    
    def __init__(self, camera_id: int = 0, config_manager=None):
        """
        Initialize camera interface.
        
        Args:
            camera_id: Camera device ID (0 for default camera)
            config_manager: Configuration manager instance
        """
        self.camera_id = camera_id
        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.get('vision', {})
        
        # Camera objects and state
        self._camera: Optional[cv2.VideoCapture] = None
        self._status = CameraStatus.DISCONNECTED
        self._parameters = CameraParameters()
        self._stats = CameraStats()
        
        # Streaming and threading
        self._streaming = False
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_queue: Queue = Queue(maxsize=10)
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        
        # Current frame data
        self._current_frame: Optional[np.ndarray] = None
        self._current_frame_info: Optional[FrameInfo] = None
        self._frame_counter = 0
        
        # Performance monitoring
        self._connection_start_time = 0.0
        self._last_fps_calculation = time.time()
        self._fps_frame_count = 0
        
        # Callbacks for frame processing
        self._frame_callbacks: List[Callable[[np.ndarray, FrameInfo], None]] = []
        
        # Image save directory
        self._save_directory = Path("data/images/captured")
        self._save_directory.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Camera interface initialized for camera ID: {camera_id}")
    
    @property
    def status(self) -> CameraStatus:
        """Get current camera status."""
        return self._status
    
    @property
    def is_connected(self) -> bool:
        """Check if camera is connected."""
        return self._status in [CameraStatus.CONNECTED, CameraStatus.STREAMING]
    
    @property
    def is_streaming(self) -> bool:
        """Check if camera is streaming."""
        return self._status == CameraStatus.STREAMING
    
    @property
    def current_frame(self) -> Optional[np.ndarray]:
        """Get current frame (thread-safe)."""
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    @property
    def current_frame_info(self) -> Optional[FrameInfo]:
        """Get current frame information."""
        return self._current_frame_info
    
    @property
    def parameters(self) -> CameraParameters:
        """Get current camera parameters."""
        return self._parameters
    
    @property
    def stats(self) -> CameraStats:
        """Get camera performance statistics."""
        return self._stats
    
    def connect(self, parameters: Optional[CameraParameters] = None) -> bool:
        """
        Connect to camera and initialize with parameters.
        
        Args:
            parameters: Camera parameters to set
            
        Returns:
            True if connection successful
        """
        if self.is_connected:
            logger.warning("Camera already connected")
            return True
        
        logger.info(f"Connecting to camera {self.camera_id}...")
        self._status = CameraStatus.CONNECTING
        
        try:
            # Initialize camera
            self._camera = cv2.VideoCapture(self.camera_id)
            
            if not self._camera.isOpened():
                raise VisionError(f"Failed to open camera {self.camera_id}")
            
            # Set parameters
            if parameters:
                self._parameters = parameters
            
            self._apply_camera_parameters()
            
            # Test capture
            ret, frame = self._camera.read()
            if not ret or frame is None:
                raise VisionError("Failed to capture test frame")
            
            # Update status and stats
            self._status = CameraStatus.CONNECTED
            self._connection_start_time = time.time()
            self._stats.error_count = 0
            self._stats.last_error = None
            
            logger.info(f"Camera connected successfully: {self._parameters.resolution[0]}x{self._parameters.resolution[1]} @ {self._parameters.fps}fps")
            return True
            
        except Exception as e:
            self._status = CameraStatus.ERROR
            self._stats.error_count += 1
            self._stats.last_error = str(e)
            
            if self._camera:
                self._camera.release()
                self._camera = None
            
            error_msg = f"Failed to connect to camera: {e}"
            logger.error(error_msg)
            raise VisionError(error_msg)
    
    def disconnect(self) -> None:
        """Disconnect from camera and cleanup resources."""
        logger.info("Disconnecting camera...")
        
        # Stop streaming if active
        if self.is_streaming:
            self.stop_streaming()
        
        # Release camera
        if self._camera:
            self._camera.release()
            self._camera = None
        
        # Update status
        self._status = CameraStatus.DISCONNECTED
        self._connection_start_time = 0.0
        
        # Clear current frame
        with self._frame_lock:
            self._current_frame = None
            self._current_frame_info = None
        
        logger.info("Camera disconnected")
    
    def set_parameters(self, parameters: CameraParameters) -> bool:
        """
        Set camera parameters.
        
        Args:
            parameters: Camera parameters to set
            
        Returns:
            True if parameters set successfully
        """
        if not self.is_connected:
            raise VisionError("Camera not connected")
        
        logger.info("Setting camera parameters...")
        
        try:
            self._parameters = parameters
            self._apply_camera_parameters()
            
            logger.info("Camera parameters updated successfully")
            return True
            
        except Exception as e:
            error_msg = f"Failed to set camera parameters: {e}"
            logger.error(error_msg)
            self._stats.error_count += 1
            self._stats.last_error = error_msg
            return False
    
    def _apply_camera_parameters(self) -> None:
        """Apply camera parameters to the camera device."""
        if not self._camera:
            return
        
        params = self._parameters
        
        # Set resolution
        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, params.resolution[0])
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, params.resolution[1])
        
        # Set FPS
        self._camera.set(cv2.CAP_PROP_FPS, params.fps)
        
        # Set exposure
        if params.auto_exposure:
            self._camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)  # Auto exposure
        else:
            self._camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Manual exposure
            self._camera.set(cv2.CAP_PROP_EXPOSURE, params.exposure)
        
        # Set other parameters
        self._camera.set(cv2.CAP_PROP_BRIGHTNESS, params.brightness)
        self._camera.set(cv2.CAP_PROP_CONTRAST, params.contrast)
        self._camera.set(cv2.CAP_PROP_SATURATION, params.saturation)
        self._camera.set(cv2.CAP_PROP_HUE, params.hue)
        
        # Set white balance
        if params.auto_white_balance:
            self._camera.set(cv2.CAP_PROP_AUTO_WB, 1)
        else:
            self._camera.set(cv2.CAP_PROP_AUTO_WB, 0)
            self._camera.set(cv2.CAP_PROP_WB_TEMPERATURE, params.white_balance)
        
        # Set focus
        if params.auto_focus:
            self._camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        else:
            self._camera.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            self._camera.set(cv2.CAP_PROP_FOCUS, params.focus)
        
        # Set zoom
        self._camera.set(cv2.CAP_PROP_ZOOM, params.zoom)
    def capture_frame(self, format: ImageFormat = ImageFormat.BGR) -> Tuple[Optional[np.ndarray], Optional[FrameInfo]]:
        """
        Capture a single frame from camera.
        
        Args:
            format: Desired image format
            
        Returns:
            Tuple of (frame, frame_info) or (None, None) if capture failed
        """
        if not self.is_connected:
            raise VisionError("Camera not connected")
        
        start_time = time.time()
        
        try:
            # Capture frame
            ret, frame = self._camera.read()
            
            if not ret or frame is None:
                self._stats.frames_dropped += 1
                return None, None
            
            # Convert format if needed
            converted_frame = self._convert_image_format(frame, format)
            
            # Create frame info
            processing_time = time.time() - start_time
            frame_info = FrameInfo(
                timestamp=start_time,
                frame_number=self._frame_counter,
                resolution=(frame.shape[1], frame.shape[0]),
                format=format,
                file_size=frame.nbytes,
                processing_time=processing_time
            )
            
            # Update stats
            self._frame_counter += 1
            self._stats.frames_captured += 1
            self._stats.total_capture_time += processing_time
            self._stats.last_frame_time = start_time
            
            # Update current frame (thread-safe)
            with self._frame_lock:
                self._current_frame = converted_frame.copy()
                self._current_frame_info = frame_info
            
            return converted_frame, frame_info
            
        except Exception as e:
            self._stats.frames_dropped += 1
            self._stats.error_count += 1
            self._stats.last_error = str(e)
            
            error_msg = f"Failed to capture frame: {e}"
            logger.error(error_msg)
            return None, None

    def start_streaming(self, format: ImageFormat = ImageFormat.BGR) -> bool:
        """
        Start continuous frame streaming in background thread.

        Args:
            format: Image format for streaming

        Returns:
            True if streaming started successfully
        """
        if not self.is_connected:
            raise VisionError("Camera not connected")

        if self.is_streaming:
            logger.warning("Camera already streaming")
            return True

        logger.info("Starting camera streaming...")

        try:
            # Clear stop event and frame queue
            self._stop_event.clear()
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except Empty:
                    break

            # Start capture thread
            self._streaming = True
            self._capture_thread = threading.Thread(
                target=self._streaming_loop,
                args=(format,),
                daemon=True
            )
            self._capture_thread.start()

            # Update status
            self._status = CameraStatus.STREAMING

            logger.info("Camera streaming started successfully")
            return True

        except Exception as e:
            self._streaming = False
            self._status = CameraStatus.CONNECTED

            error_msg = f"Failed to start streaming: {e}"
            logger.error(error_msg)
            self._stats.error_count += 1
            self._stats.last_error = error_msg
            return False

    def stop_streaming(self) -> None:
        """Stop continuous frame streaming."""
        if not self.is_streaming:
            return

        logger.info("Stopping camera streaming...")

        # Signal stop and wait for thread
        self._stop_event.set()
        self._streaming = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)

        # Update status
        self._status = CameraStatus.CONNECTED if self.is_connected else CameraStatus.DISCONNECTED

        logger.info("Camera streaming stopped")

    def _streaming_loop(self, format: ImageFormat) -> None:
        """Main streaming loop running in background thread."""
        logger.debug("Starting streaming loop")

        fps_counter = 0
        fps_start_time = time.time()

        while not self._stop_event.is_set() and self._streaming:
            try:
                # Capture frame
                frame, frame_info = self.capture_frame(format)

                if frame is not None and frame_info is not None:
                    # Add to queue (non-blocking)
                    try:
                        self._frame_queue.put_nowait((frame, frame_info))
                    except:
                        # Queue full, drop oldest frame
                        try:
                            self._frame_queue.get_nowait()
                            self._frame_queue.put_nowait((frame, frame_info))
                        except Empty:
                            pass

                    # Call frame callbacks
                    for callback in self._frame_callbacks:
                        try:
                            callback(frame, frame_info)
                        except Exception as e:
                            logger.warning(f"Frame callback error: {e}")

                    # Update FPS calculation
                    fps_counter += 1
                    current_time = time.time()

                    if current_time - fps_start_time >= 1.0:
                        self._stats.current_fps = fps_counter / (current_time - fps_start_time)

                        # Update average FPS
                        if self._stats.frames_captured > 0:
                            total_time = current_time - self._connection_start_time
                            self._stats.average_fps = self._stats.frames_captured / total_time

                        fps_counter = 0
                        fps_start_time = current_time

                # Small delay to prevent excessive CPU usage
                time.sleep(0.001)

            except Exception as e:
                logger.error(f"Error in streaming loop: {e}")
                self._stats.error_count += 1
                self._stats.last_error = str(e)
                time.sleep(0.1)  # Wait longer on error

        logger.debug("Streaming loop stopped")

    def get_latest_frame(self, timeout: float = 1.0) -> Tuple[Optional[np.ndarray], Optional[FrameInfo]]:
        """
        Get latest frame from streaming queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Tuple of (frame, frame_info) or (None, None) if timeout
        """
        if not self.is_streaming:
            return self.capture_frame()

        try:
            return self._frame_queue.get(timeout=timeout)
        except Empty:
            return None, None

    def _convert_image_format(self, frame: np.ndarray, target_format: ImageFormat) -> np.ndarray:
        """
        Convert image to target format.

        Args:
            frame: Input frame (assumed to be BGR)
            target_format: Target image format

        Returns:
            Converted frame
        """
        if target_format == ImageFormat.BGR:
            return frame
        elif target_format == ImageFormat.RGB:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        elif target_format == ImageFormat.GRAY:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        elif target_format == ImageFormat.HSV:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        elif target_format == ImageFormat.LAB:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        else:
            return frame

    def save_frame(self, frame: Optional[np.ndarray] = None,
                   filename: Optional[str] = None) -> Optional[str]:
        """
        Save frame to disk.

        Args:
            frame: Frame to save (uses current frame if None)
            filename: Custom filename (auto-generated if None)

        Returns:
            Path to saved file or None if failed
        """
        # Use current frame if none provided
        if frame is None:
            frame = self.current_frame

        if frame is None:
            logger.warning("No frame available to save")
            return None

        # Generate filename if not provided
        if filename is None:
            timestamp = int(time.time() * 1000)
            filename = f"frame_{timestamp}.jpg"

        filepath = self._save_directory / filename

        try:
            success = cv2.imwrite(str(filepath), frame)
            if success:
                logger.info(f"Frame saved to: {filepath}")
                return str(filepath)
            else:
                logger.error("Failed to save frame")
                return None

        except Exception as e:
            logger.error(f"Error saving frame: {e}")
            return None

    def add_frame_callback(self, callback: Callable[[np.ndarray, FrameInfo], None]) -> None:
        """
        Add callback function for frame processing.

        Args:
            callback: Function to call for each frame
        """
        self._frame_callbacks.append(callback)
        logger.info(f"Added frame callback: {callback.__name__}")

    def remove_frame_callback(self, callback: Callable[[np.ndarray, FrameInfo], None]) -> bool:
        """
        Remove frame callback.

        Args:
            callback: Callback function to remove

        Returns:
            True if callback was removed
        """
        try:
            self._frame_callbacks.remove(callback)
            logger.info(f"Removed frame callback: {callback.__name__}")
            return True
        except ValueError:
            return False

    def get_camera_info(self) -> Dict[str, Any]:
        """
        Get comprehensive camera information.

        Returns:
            Dictionary with camera information
        """
        info = {
            'camera_id': self.camera_id,
            'status': self._status.value,
            'is_connected': self.is_connected,
            'is_streaming': self.is_streaming,
            'parameters': {
                'resolution': self._parameters.resolution,
                'fps': self._parameters.fps,
                'exposure': self._parameters.exposure,
                'brightness': self._parameters.brightness,
                'contrast': self._parameters.contrast,
                'saturation': self._parameters.saturation,
                'auto_exposure': self._parameters.auto_exposure,
                'auto_white_balance': self._parameters.auto_white_balance,
                'auto_focus': self._parameters.auto_focus
            },
            'statistics': {
                'frames_captured': self._stats.frames_captured,
                'frames_dropped': self._stats.frames_dropped,
                'current_fps': self._stats.current_fps,
                'average_fps': self._stats.average_fps,
                'connection_uptime': time.time() - self._connection_start_time if self._connection_start_time > 0 else 0,
                'error_count': self._stats.error_count,
                'last_error': self._stats.last_error
            }
        }

        return info

    def reset_statistics(self) -> None:
        """Reset camera performance statistics."""
        self._stats = CameraStats()
        self._frame_counter = 0
        self._connection_start_time = time.time() if self.is_connected else 0.0
        logger.info("Camera statistics reset")

    def test_camera_performance(self, duration: float = 10.0) -> Dict[str, Any]:
        """
        Test camera performance over specified duration.

        Args:
            duration: Test duration in seconds

        Returns:
            Performance test results
        """
        if not self.is_connected:
            raise VisionError("Camera not connected")

        logger.info(f"Starting camera performance test for {duration} seconds...")

        # Reset stats for clean test
        initial_stats = self._stats
        self.reset_statistics()

        # Start streaming if not already active
        was_streaming = self.is_streaming
        if not was_streaming:
            self.start_streaming()

        # Wait for test duration
        start_time = time.time()
        time.sleep(duration)
        end_time = time.time()

        # Stop streaming if we started it
        if not was_streaming:
            self.stop_streaming()

        # Calculate results
        actual_duration = end_time - start_time
        results = {
            'test_duration': actual_duration,
            'frames_captured': self._stats.frames_captured,
            'frames_dropped': self._stats.frames_dropped,
            'average_fps': self._stats.frames_captured / actual_duration,
            'target_fps': self._parameters.fps,
            'fps_efficiency': (self._stats.frames_captured / actual_duration) / self._parameters.fps,
            'error_count': self._stats.error_count,
            'success_rate': (self._stats.frames_captured / (self._stats.frames_captured + self._stats.frames_dropped)) if (self._stats.frames_captured + self._stats.frames_dropped) > 0 else 0
        }

        # Restore original stats
        self._stats = initial_stats

        logger.info(f"Performance test completed: {results['average_fps']:.1f} fps average")
        return results

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
