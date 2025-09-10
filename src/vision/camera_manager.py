"""
Camera Manager module for Niryo LLM Robotics Platform.
"""

from vision.camera_interface import CameraInterface
from utils.logger import get_logger

logger = get_logger(__name__)

class CameraManager:
    """Camera management system."""
    
    def __init__(self):
        """Initialize camera manager."""
        self.camera_interface = CameraInterface()
        logger.info("Camera manager initialized")
    
    def get_frame(self):
        """Get current camera frame."""
        return self.camera_interface.get_frame()
    
    def start_capture(self):
        """Start camera capture."""
        return self.camera_interface.start_capture()
    
    def stop_capture(self):
        """Stop camera capture."""
        return self.camera_interface.stop_capture()
