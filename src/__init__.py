"""
Niryo LLM Robotics Platform - Main Package

This package provides comprehensive robotics control, computer vision,
and AI integration capabilities for the Niryo Ned2 robotic arm.

Modules:
    core: Robot control and movement systems
    vision: Computer vision and image processing
    automation: Pick-and-place and workflow automation
    ai: LLM integration and intelligent decision making
    interfaces: User interfaces and communication
    utils: Utility functions and helpers
"""

__version__ = "1.0.0"
__author__ = "Bavarian-Czech Summer School Team"
__email__ = "robotics@summer-school.edu"

# Package-level imports for convenience
from .core.robot_controller import RobotController
from .utils.config_manager import ConfigManager
from .utils.logger import get_logger

__all__ = [
    "RobotController",
    "ConfigManager", 
    "get_logger"
]
