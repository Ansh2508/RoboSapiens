"""
Professional Robot Control Panel

Clean, professional robot control interface without emojis,
with proper typography and organized layout.
"""

import os
import sys
from typing import Dict, Any, Optional, Callable
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QSlider, QLineEdit, QComboBox, QSpinBox,
    QProgressBar, QFrame, QSizePolicy, QScrollArea
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPixmap, QResizeEvent

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class ProfessionalRobotControlPanel(QWidget):
    """Professional robot control panel with clean design and proper typography."""
    
    # Signals for robot control
    position_changed = pyqtSignal(dict)
    tool_action_requested = pyqtSignal(str, dict)
    robot_command_requested = pyqtSignal(str, dict)
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.robot_controller = None
        self.current_position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rx': 0.0, 'ry': 0.0, 'rz': 0.0}
        self.is_connected = False
        self.current_breakpoint = "desktop"
        
        # Set responsive size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.init_ui()
        self.setup_connections()
        
        logger.info("Professional robot control panel initialized")
    
    def init_ui(self):
        """Initialize the professional user interface."""
        # Main scroll area for responsive design
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Main content widget
        content = QWidget()
        scroll.setWidget(content)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        # Content layout
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # Connection section
        connection_group = self.create_connection_section()
        layout.addWidget(connection_group)
        
        # Position monitoring section
        position_group = self.create_position_section()
        layout.addWidget(position_group)
        
        # Movement controls section
        movement_group = self.create_movement_section()
        layout.addWidget(movement_group)
        
        # Tool controls section
        tools_group = self.create_tools_section()
        layout.addWidget(tools_group)
        
        # Quick actions section
        actions_group = self.create_actions_section()
        layout.addWidget(actions_group)
        
        # Add stretch to push content to top
        layout.addStretch()
    
    def create_connection_section(self) -> QGroupBox:
        """Create professional connection control section."""
        group = QGroupBox("Robot Connection")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Connection status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setObjectName("section-label")
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setObjectName("status-value")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.connection_status)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Connection controls
        controls_layout = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary-button")
        self.connect_btn.clicked.connect(self.connect_robot)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setObjectName("secondary-button")
        self.disconnect_btn.clicked.connect(self.disconnect_robot)
        self.disconnect_btn.setEnabled(False)
        
        controls_layout.addWidget(self.connect_btn)
        controls_layout.addWidget(self.disconnect_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        return group
    
    def create_position_section(self) -> QGroupBox:
        """Create position monitoring section."""
        group = QGroupBox("Current Position")
        group.setObjectName("control-group")
        
        layout = QGridLayout(group)
        layout.setSpacing(12)
        
        # Position labels and values
        self.position_labels = {}
        axes = [('X', 'x'), ('Y', 'y'), ('Z', 'z'), ('RX', 'rx'), ('RY', 'ry'), ('RZ', 'rz')]
        
        for i, (display_name, axis) in enumerate(axes):
            row = i // 3
            col = (i % 3) * 2
            
            # Axis label
            axis_label = QLabel(f"{display_name}:")
            axis_label.setObjectName("axis-label")
            layout.addWidget(axis_label, row, col)
            
            # Position value
            pos_label = QLabel("0.000")
            pos_label.setObjectName("position-value")
            pos_label.setMinimumWidth(80)
            self.position_labels[axis] = pos_label
            layout.addWidget(pos_label, row, col + 1)
        
        return group
    
    def create_movement_section(self) -> QGroupBox:
        """Create movement controls section."""
        group = QGroupBox("Movement Controls")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Basic movement controls
        basic_layout = QHBoxLayout()
        
        self.home_btn = QPushButton("Home Position")
        self.home_btn.setObjectName("primary-button")
        self.home_btn.clicked.connect(self.go_home)
        self.home_btn.setEnabled(False)
        
        self.calibrate_btn = QPushButton("Calibrate")
        self.calibrate_btn.setObjectName("secondary-button")
        self.calibrate_btn.clicked.connect(self.calibrate_robot)
        self.calibrate_btn.setEnabled(False)
        
        self.freemove_btn = QPushButton("Free Move")
        self.freemove_btn.setObjectName("secondary-button")
        self.freemove_btn.clicked.connect(self.toggle_freemove)
        self.freemove_btn.setEnabled(False)
        
        basic_layout.addWidget(self.home_btn)
        basic_layout.addWidget(self.calibrate_btn)
        basic_layout.addWidget(self.freemove_btn)
        
        layout.addLayout(basic_layout)
        
        # Robot state display
        state_layout = QHBoxLayout()
        state_label = QLabel("State:")
        state_label.setObjectName("section-label")
        self.robot_state_label = QLabel("Idle")
        self.robot_state_label.setObjectName("status-value")
        
        state_layout.addWidget(state_label)
        state_layout.addWidget(self.robot_state_label)
        state_layout.addStretch()
        
        layout.addLayout(state_layout)
        
        return group
    
    def create_tools_section(self) -> QGroupBox:
        """Create tool controls section."""
        group = QGroupBox("Tool Controls")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Gripper controls
        gripper_layout = QHBoxLayout()
        gripper_label = QLabel("Gripper:")
        gripper_label.setObjectName("section-label")
        
        self.gripper_open_btn = QPushButton("Open")
        self.gripper_open_btn.setObjectName("tool-button")
        self.gripper_open_btn.clicked.connect(lambda: self.control_gripper("open"))
        self.gripper_open_btn.setEnabled(False)
        
        self.gripper_close_btn = QPushButton("Close")
        self.gripper_close_btn.setObjectName("tool-button")
        self.gripper_close_btn.clicked.connect(lambda: self.control_gripper("close"))
        self.gripper_close_btn.setEnabled(False)
        
        gripper_layout.addWidget(gripper_label)
        gripper_layout.addWidget(self.gripper_open_btn)
        gripper_layout.addWidget(self.gripper_close_btn)
        gripper_layout.addStretch()
        
        layout.addLayout(gripper_layout)
        
        # LED controls
        led_layout = QHBoxLayout()
        led_label = QLabel("LED Ring:")
        led_label.setObjectName("section-label")
        
        self.led_on_btn = QPushButton("On")
        self.led_on_btn.setObjectName("tool-button")
        self.led_on_btn.clicked.connect(lambda: self.control_led("on"))
        self.led_on_btn.setEnabled(False)
        
        self.led_off_btn = QPushButton("Off")
        self.led_off_btn.setObjectName("tool-button")
        self.led_off_btn.clicked.connect(lambda: self.control_led("off"))
        self.led_off_btn.setEnabled(False)
        
        led_layout.addWidget(led_label)
        led_layout.addWidget(self.led_on_btn)
        led_layout.addWidget(self.led_off_btn)
        led_layout.addStretch()
        
        layout.addLayout(led_layout)
        
        return group
    
    def create_actions_section(self) -> QGroupBox:
        """Create quick actions section."""
        group = QGroupBox("Quick Actions")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Pattern actions
        pattern_layout = QHBoxLayout()
        pattern_label = QLabel("Patterns:")
        pattern_label.setObjectName("section-label")
        
        self.square_btn = QPushButton("Draw Square")
        self.square_btn.setObjectName("action-button")
        self.square_btn.clicked.connect(lambda: self.execute_pattern("square"))
        self.square_btn.setEnabled(False)
        
        self.circle_btn = QPushButton("Draw Circle")
        self.circle_btn.setObjectName("action-button")
        self.circle_btn.clicked.connect(lambda: self.execute_pattern("circle"))
        self.circle_btn.setEnabled(False)
        
        pattern_layout.addWidget(pattern_label)
        pattern_layout.addWidget(self.square_btn)
        pattern_layout.addWidget(self.circle_btn)
        pattern_layout.addStretch()
        
        layout.addLayout(pattern_layout)
        
        # Object manipulation
        object_layout = QHBoxLayout()
        object_label = QLabel("Objects:")
        object_label.setObjectName("section-label")
        
        self.pick_btn = QPushButton("Pick Object")
        self.pick_btn.setObjectName("action-button")
        self.pick_btn.clicked.connect(self.pick_object)
        self.pick_btn.setEnabled(False)
        
        self.place_btn = QPushButton("Place Object")
        self.place_btn.setObjectName("action-button")
        self.place_btn.clicked.connect(self.place_object)
        self.place_btn.setEnabled(False)
        
        object_layout.addWidget(object_label)
        object_layout.addWidget(self.pick_btn)
        object_layout.addWidget(self.place_btn)
        object_layout.addStretch()
        
        layout.addLayout(object_layout)
        
        # Emergency stop
        emergency_layout = QHBoxLayout()
        emergency_layout.addStretch()
        
        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setObjectName("emergency-button")
        self.emergency_btn.clicked.connect(self.emergency_stop)
        
        emergency_layout.addWidget(self.emergency_btn)
        emergency_layout.addStretch()
        
        layout.addLayout(emergency_layout)

        return group

    def setup_connections(self):
        """Setup signal connections and timers."""
        # Setup position update timer
        self.position_timer = QTimer()
        self.position_timer.timeout.connect(self.update_position_display)
        self.position_timer.start(100)  # Update every 100ms

    # Robot Control Methods

    def connect_robot(self):
        """Connect to the robot."""
        try:
            self.robot_command_requested.emit("connect", {})
            self.connection_status.setText("Connecting...")
            self.connection_status.setStyleSheet("color: #FF9500;")  # Orange
            self.connect_btn.setEnabled(False)
            logger.info("Robot connection requested")
        except Exception as e:
            logger.error(f"Failed to connect to robot: {e}")
            self.connection_status.setText("Connection Failed")
            self.connection_status.setStyleSheet("color: #FF3B30;")  # Red
            self.connect_btn.setEnabled(True)

    def disconnect_robot(self):
        """Disconnect from the robot."""
        try:
            self.robot_command_requested.emit("disconnect", {})
            self.update_connection_status(False)
            logger.info("Robot disconnection requested")
        except Exception as e:
            logger.error(f"Failed to disconnect from robot: {e}")

    def calibrate_robot(self):
        """Calibrate the robot."""
        try:
            self.robot_command_requested.emit("calibrate", {})
            self.robot_state_label.setText("Calibrating...")
            logger.info("Robot calibration requested")
        except Exception as e:
            logger.error(f"Failed to calibrate robot: {e}")

    def go_home(self):
        """Move robot to home position."""
        try:
            self.robot_command_requested.emit("home", {})
            self.robot_state_label.setText("Moving to home...")
            logger.info("Robot home position requested")
        except Exception as e:
            logger.error(f"Failed to move robot home: {e}")

    def toggle_freemove(self):
        """Toggle free move mode."""
        try:
            self.robot_command_requested.emit("freemove", {})
            logger.info("Robot free move toggle requested")
        except Exception as e:
            logger.error(f"Failed to toggle free move: {e}")

    def control_gripper(self, action: str):
        """Control gripper (open/close)."""
        try:
            self.tool_action_requested.emit("gripper", {"action": action})
            logger.info(f"Gripper {action} requested")
        except Exception as e:
            logger.error(f"Failed to control gripper: {e}")

    def control_led(self, action: str):
        """Control LED ring (on/off)."""
        try:
            self.tool_action_requested.emit("led", {"action": action})
            logger.info(f"LED {action} requested")
        except Exception as e:
            logger.error(f"Failed to control LED: {e}")

    def execute_pattern(self, pattern: str):
        """Execute movement pattern."""
        try:
            self.robot_command_requested.emit("pattern", {"pattern": pattern})
            self.robot_state_label.setText(f"Executing {pattern}...")
            logger.info(f"Pattern {pattern} execution requested")
        except Exception as e:
            logger.error(f"Failed to execute pattern: {e}")

    def pick_object(self):
        """Pick up object."""
        try:
            self.robot_command_requested.emit("pick", {})
            self.robot_state_label.setText("Picking object...")
            logger.info("Pick object requested")
        except Exception as e:
            logger.error(f"Failed to pick object: {e}")

    def place_object(self):
        """Place object."""
        try:
            self.robot_command_requested.emit("place", {})
            self.robot_state_label.setText("Placing object...")
            logger.info("Place object requested")
        except Exception as e:
            logger.error(f"Failed to place object: {e}")

    def emergency_stop(self):
        """Emergency stop."""
        try:
            self.robot_command_requested.emit("emergency_stop", {})
            self.robot_state_label.setText("EMERGENCY STOP")
            self.robot_state_label.setStyleSheet("color: #FF3B30; font-weight: bold;")
            logger.warning("Emergency stop requested")
        except Exception as e:
            logger.error(f"Failed to execute emergency stop: {e}")

    # Status Update Methods

    def update_connection_status(self, connected: bool):
        """Update connection status and enable/disable controls."""
        self.is_connected = connected

        if connected:
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: #34C759;")  # Green
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)

            # Enable all controls
            self.calibrate_btn.setEnabled(True)
            self.home_btn.setEnabled(True)
            self.freemove_btn.setEnabled(True)
            self.gripper_open_btn.setEnabled(True)
            self.gripper_close_btn.setEnabled(True)
            self.led_on_btn.setEnabled(True)
            self.led_off_btn.setEnabled(True)
            self.square_btn.setEnabled(True)
            self.circle_btn.setEnabled(True)
            self.pick_btn.setEnabled(True)
            self.place_btn.setEnabled(True)
        else:
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: #FF3B30;")  # Red
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)

            # Disable all controls
            self.calibrate_btn.setEnabled(False)
            self.home_btn.setEnabled(False)
            self.freemove_btn.setEnabled(False)
            self.gripper_open_btn.setEnabled(False)
            self.gripper_close_btn.setEnabled(False)
            self.led_on_btn.setEnabled(False)
            self.led_off_btn.setEnabled(False)
            self.square_btn.setEnabled(False)
            self.circle_btn.setEnabled(False)
            self.pick_btn.setEnabled(False)
            self.place_btn.setEnabled(False)

    def update_position_display(self):
        """Update position display with current robot position."""
        if self.is_connected and self.current_position:
            for axis, value in self.current_position.items():
                if axis in self.position_labels:
                    self.position_labels[axis].setText(f"{value:.3f}")

    def update_robot_state(self, state: str):
        """Update robot state display."""
        self.robot_state_label.setText(f"{state}")
        self.robot_state_label.setStyleSheet("")  # Reset style
