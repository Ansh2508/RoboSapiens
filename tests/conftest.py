"""
Pytest configuration and shared fixtures for the Niryo LLM Robotics Platform tests.

This module provides common test fixtures, configuration, and utilities
used across all test modules.
"""

import pytest
import sys
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import logging

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logging


@pytest.fixture(scope="session")
def test_data_dir():
    """Create temporary directory for test data."""
    temp_dir = tempfile.mkdtemp(prefix="niryo_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="session")
def test_config_dir(test_data_dir):
    """Create test configuration directory."""
    config_dir = test_data_dir / "config"
    config_dir.mkdir(exist_ok=True)
    
    # Create test configuration files
    robot_config = {
        "ip": "169.254.200.200",
        "timeout": 10,
        "max_velocity_percent": 50,
        "workspace_boundaries_enabled": True,
        "status_update_interval": 1.0
    }
    
    safety_config = {
        "emergency_stop_enabled": True,
        "collision_detection_enabled": True,
        "workspace_boundaries_enabled": True,
        "force_limit_newtons": 50.0,
        "safety_check_interval": 0.1
    }
    
    vision_config = {
        "camera_index": 0,
        "resolution_width": 640,
        "resolution_height": 480,
        "fps": 30
    }
    
    ai_config = {
        "openai_api_key": "test_key",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    network_config = {
        "timeout": 30,
        "retry_attempts": 3,
        "retry_delay": 1.0
    }
    
    logging_config = {
        "level": "INFO",
        "format": "{time} | {level} | {name} | {message}",
        "rotation": "10 MB",
        "retention": "1 week"
    }
    
    # Write configuration files
    import yaml
    
    with open(config_dir / "robot_config.yaml", "w") as f:
        yaml.dump(robot_config, f)
    
    with open(config_dir / "safety_config.yaml", "w") as f:
        yaml.dump(safety_config, f)
    
    with open(config_dir / "vision_config.yaml", "w") as f:
        yaml.dump(vision_config, f)
    
    with open(config_dir / "ai_config.yaml", "w") as f:
        yaml.dump(ai_config, f)
    
    with open(config_dir / "network_config.yaml", "w") as f:
        yaml.dump(network_config, f)
    
    with open(config_dir / "logging_config.yaml", "w") as f:
        yaml.dump(logging_config, f)
    
    return config_dir


@pytest.fixture
def test_config_manager(test_config_dir):
    """Create ConfigManager instance with test configuration."""
    with patch.dict(os.environ, {"CONFIG_PATH": str(test_config_dir)}):
        config_manager = ConfigManager()
        return config_manager


@pytest.fixture
def mock_niryo_robot():
    """Create mock NiryoRobot for testing."""
    mock_robot = Mock()
    
    # Configure mock methods
    mock_robot.calibrate_auto.return_value = None
    mock_robot.close_connection.return_value = None
    mock_robot.get_pose.return_value = Mock(x=0, y=0, z=200, roll=0, pitch=0, yaw=0)
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
def mock_robot_config():
    """Create mock robot configuration."""
    config = Mock()
    config.ip = "169.254.200.200"
    config.timeout = 10
    config.max_velocity_percent = 50
    config.workspace_boundaries_enabled = True
    config.status_update_interval = 1.0
    return config


@pytest.fixture
def mock_safety_config():
    """Create mock safety configuration."""
    config = Mock()
    config.emergency_stop_enabled = True
    config.collision_detection_enabled = True
    config.workspace_boundaries_enabled = True
    config.force_limit_newtons = 50.0
    config.safety_check_interval = 0.1
    return config


@pytest.fixture
def mock_vision_config():
    """Create mock vision configuration."""
    config = Mock()
    config.camera_index = 0
    config.resolution_width = 640
    config.resolution_height = 480
    config.fps = 30
    config.detection_confidence_threshold = 0.5
    config.tracking_enabled = True
    return config


@pytest.fixture
def mock_ai_config():
    """Create mock AI configuration."""
    config = Mock()
    config.openai_api_key = "test_key"
    config.model = "gpt-4"
    config.temperature = 0.7
    config.max_tokens = 1000
    config.ollama_base_url = "http://localhost:11434"
    config.ollama_model = "llama2"
    return config


@pytest.fixture
def mock_system_config(mock_robot_config, mock_safety_config, mock_vision_config, mock_ai_config):
    """Create mock system configuration."""
    config = Mock()
    config.robot = mock_robot_config
    config.safety = mock_safety_config
    config.vision = mock_vision_config
    config.ai = mock_ai_config
    return config


@pytest.fixture
def suppress_logging():
    """Suppress logging during tests."""
    logging.getLogger().setLevel(logging.CRITICAL)
    yield
    logging.getLogger().setLevel(logging.INFO)


@pytest.fixture(autouse=True)
def setup_test_logging():
    """Setup logging for tests."""
    # Configure minimal logging for tests
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s - %(name)s - %(message)s"
    )
    
    # Suppress specific loggers that are too verbose in tests
    logging.getLogger("urllib3").setLevel(logging.ERROR)
    logging.getLogger("requests").setLevel(logging.ERROR)


@pytest.fixture
def mock_pose_object():
    """Create mock PoseObject."""
    pose = Mock()
    pose.x = 0.0
    pose.y = 0.0
    pose.z = 200.0
    pose.roll = 0.0
    pose.pitch = 0.0
    pose.yaw = 0.0
    return pose


@pytest.fixture
def mock_joints_position():
    """Create mock JointsPosition."""
    joints = Mock()
    joints.joints = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    return joints


@pytest.fixture
def sample_image_data():
    """Create sample image data for vision tests."""
    import numpy as np
    
    # Create a simple test image (100x100 RGB)
    image = np.zeros((100, 100, 3), dtype=np.uint8)
    
    # Add some simple patterns
    image[25:75, 25:75] = [255, 0, 0]  # Red square
    image[40:60, 40:60] = [0, 255, 0]  # Green square in center
    
    return image


@pytest.fixture
def sample_workspace_boundaries():
    """Create sample workspace boundaries."""
    return {
        'x': (-300, 300),
        'y': (-300, 300),
        'z': (0, 400),
        'roll': (-3.14, 3.14),
        'pitch': (-3.14, 3.14),
        'yaw': (-3.14, 3.14)
    }


@pytest.fixture
def temp_log_file(test_data_dir):
    """Create temporary log file for testing."""
    log_file = test_data_dir / "test.log"
    yield log_file
    if log_file.exists():
        log_file.unlink()


@pytest.fixture
def mock_environment_variables():
    """Mock environment variables for testing."""
    env_vars = {
        "NIRYO_IP": "169.254.200.200",
        "OPENAI_API_KEY": "test_key",
        "LOG_LEVEL": "INFO",
        "CONFIG_PATH": "/test/config"
    }
    
    with patch.dict(os.environ, env_vars):
        yield env_vars


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "hardware: mark test as requiring hardware"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add integration marker to integration tests
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add slow marker to tests that might be slow
        if any(keyword in item.name.lower() for keyword in ["connection", "calibration", "workflow"]):
            item.add_marker(pytest.mark.slow)
        
        # Add network marker to tests that require network
        if any(keyword in item.name.lower() for keyword in ["connection", "network", "ping"]):
            item.add_marker(pytest.mark.network)


# Custom assertions
def assert_robot_state(robot_controller, expected_state):
    """Assert robot controller is in expected state."""
    assert robot_controller.status.state == expected_state, \
        f"Expected robot state {expected_state}, got {robot_controller.status.state}"


def assert_safety_event_recorded(safety_manager, event_type):
    """Assert that a specific safety event was recorded."""
    events = safety_manager.safety_events
    assert any(event.event_type == event_type for event in events), \
        f"Expected safety event {event_type} not found in recorded events"


def assert_within_tolerance(actual, expected, tolerance=0.001):
    """Assert that actual value is within tolerance of expected value."""
    assert abs(actual - expected) <= tolerance, \
        f"Expected {expected} ± {tolerance}, got {actual}"


# Make custom assertions available to all tests
pytest.assert_robot_state = assert_robot_state
pytest.assert_safety_event_recorded = assert_safety_event_recorded
pytest.assert_within_tolerance = assert_within_tolerance
