"""
Manual Control View

Professional manual control interface integrating the existing robot control panel
with the comprehensive 5-section layout.
"""

import os
import sys
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSlider, QSpinBox, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class ManualControlView(QWidget):
    """Professional manual control view with robot control integration."""
    
    # Signals
    joint_position_changed = pyqtSignal(int, float)  # joint_id, position
    cartesian_position_changed = pyqtSignal(str, float)  # axis, position
    tool_action_requested = pyqtSignal(str)  # action
    home_position_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.joint_sliders = {}
        self.cartesian_controls = {}
        
        self.init_ui()
        self.apply_theme()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status)
        self.update_timer.start(1000)  # Update every second
        
        logger.info("Manual control view initialized")
    
    def init_ui(self):
        """Initialize the manual control interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Control mode selection
        mode_group = self.create_control_mode_section()
        layout.addWidget(mode_group)
        
        # Main control area
        control_layout = QHBoxLayout()
        control_layout.setSpacing(20)
        
        # Joint control section
        joint_group = self.create_joint_control_section()
        control_layout.addWidget(joint_group)
        
        # Cartesian control section
        cartesian_group = self.create_cartesian_control_section()
        control_layout.addWidget(cartesian_group)
        
        layout.addLayout(control_layout)
        
        # Tool control section
        tool_group = self.create_tool_control_section()
        layout.addWidget(tool_group)
        
        # Action buttons
        actions_layout = self.create_action_buttons()
        layout.addLayout(actions_layout)
        
        # Status section
        status_group = self.create_status_section()
        layout.addWidget(status_group)
        
        layout.addStretch()
    
    def create_control_mode_section(self) -> QGroupBox:
        """Create control mode selection section."""
        group = QGroupBox("Control Mode")
        group.setObjectName("control-mode-group")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)
        
        # Mode buttons
        self.joint_mode_btn = QPushButton("Joint Control")
        self.joint_mode_btn.setObjectName("mode-button")
        self.joint_mode_btn.setCheckable(True)
        self.joint_mode_btn.setChecked(True)
        layout.addWidget(self.joint_mode_btn)
        
        self.cartesian_mode_btn = QPushButton("Cartesian Control")
        self.cartesian_mode_btn.setObjectName("mode-button")
        self.cartesian_mode_btn.setCheckable(True)
        layout.addWidget(self.cartesian_mode_btn)
        
        self.tool_mode_btn = QPushButton("Tool Control")
        self.tool_mode_btn.setObjectName("mode-button")
        self.tool_mode_btn.setCheckable(True)
        layout.addWidget(self.tool_mode_btn)
        
        layout.addStretch()
        
        return group
    
    def create_joint_control_section(self) -> QGroupBox:
        """Create joint control section."""
        group = QGroupBox("Joint Control")
        group.setObjectName("joint-control-group")
        layout = QGridLayout(group)
        layout.setSpacing(12)
        
        # Joint controls (6 joints for Niryo)
        joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
        
        for i, joint_name in enumerate(joint_names):
            # Joint label
            label = QLabel(joint_name)
            label.setObjectName("joint-label")
            layout.addWidget(label, i, 0)
            
            # Joint slider
            slider = QSlider(Qt.Horizontal)
            slider.setObjectName("joint-slider")
            slider.setRange(-180, 180)
            slider.setValue(0)
            slider.valueChanged.connect(lambda v, j=i: self.on_joint_changed(j, v))
            self.joint_sliders[i] = slider
            layout.addWidget(slider, i, 1)
            
            # Value display
            value_label = QLabel("0°")
            value_label.setObjectName("joint-value")
            value_label.setMinimumWidth(40)
            layout.addWidget(value_label, i, 2)
            
            # Connect slider to value display
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(f"{v}°"))
        
        return group
    
    def create_cartesian_control_section(self) -> QGroupBox:
        """Create cartesian control section."""
        group = QGroupBox("Cartesian Control")
        group.setObjectName("cartesian-control-group")
        layout = QGridLayout(group)
        layout.setSpacing(12)
        
        # Cartesian axes
        axes = [("X", "mm"), ("Y", "mm"), ("Z", "mm"), ("Roll", "°"), ("Pitch", "°"), ("Yaw", "°")]
        
        for i, (axis, unit) in enumerate(axes):
            # Axis label
            label = QLabel(axis)
            label.setObjectName("axis-label")
            layout.addWidget(label, i, 0)
            
            # Position input
            spinbox = QSpinBox()
            spinbox.setObjectName("axis-spinbox")
            if unit == "mm":
                spinbox.setRange(-500, 500)
                spinbox.setSuffix(" mm")
            else:
                spinbox.setRange(-180, 180)
                spinbox.setSuffix("°")
            spinbox.setValue(0)
            spinbox.valueChanged.connect(lambda v, a=axis: self.on_cartesian_changed(a, v))
            self.cartesian_controls[axis] = spinbox
            layout.addWidget(spinbox, i, 1)
            
            # Move button
            move_btn = QPushButton(f"Move {axis}")
            move_btn.setObjectName("move-button")
            move_btn.clicked.connect(lambda _, a=axis: self.move_axis(a))
            layout.addWidget(move_btn, i, 2)
        
        return group
    
    def create_tool_control_section(self) -> QGroupBox:
        """Create tool control section."""
        group = QGroupBox("Tool Control")
        group.setObjectName("tool-control-group")
        layout = QHBoxLayout(group)
        layout.setSpacing(12)
        
        # Tool selection
        tool_combo = QComboBox()
        tool_combo.setObjectName("tool-combo")
        tool_combo.addItems(["Gripper", "Vacuum Pump", "Electromagnet", "Custom Tool"])
        layout.addWidget(tool_combo)
        
        # Tool actions
        open_btn = QPushButton("Open/Activate")
        open_btn.setObjectName("tool-action-button")
        open_btn.clicked.connect(lambda: self.tool_action_requested.emit("open"))
        layout.addWidget(open_btn)
        
        close_btn = QPushButton("Close/Deactivate")
        close_btn.setObjectName("tool-action-button")
        close_btn.clicked.connect(lambda: self.tool_action_requested.emit("close"))
        layout.addWidget(close_btn)
        
        layout.addStretch()
        
        return group
    
    def create_action_buttons(self) -> QHBoxLayout:
        """Create action buttons layout."""
        layout = QHBoxLayout()
        layout.setSpacing(12)
        
        # Home button
        home_btn = QPushButton("Home Position")
        home_btn.setObjectName("action-button-primary")
        home_btn.clicked.connect(self.home_position_requested.emit)
        layout.addWidget(home_btn)
        
        # Stop button
        stop_btn = QPushButton("Emergency Stop")
        stop_btn.setObjectName("action-button-danger")
        stop_btn.clicked.connect(self.stop_requested.emit)
        layout.addWidget(stop_btn)
        
        layout.addStretch()
        
        return layout
    
    def create_status_section(self) -> QGroupBox:
        """Create status section."""
        group = QGroupBox("Robot Status")
        group.setObjectName("status-group")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        
        # Status indicators
        self.connection_status = QLabel("Status: Disconnected")
        self.connection_status.setObjectName("status-text")
        layout.addWidget(self.connection_status, 0, 0)
        
        self.position_status = QLabel("Position: Unknown")
        self.position_status.setObjectName("status-text")
        layout.addWidget(self.position_status, 0, 1)
        
        self.tool_status = QLabel("Tool: Not Connected")
        self.tool_status.setObjectName("status-text")
        layout.addWidget(self.tool_status, 1, 0)
        
        self.mode_status = QLabel("Mode: Manual")
        self.mode_status.setObjectName("status-text")
        layout.addWidget(self.mode_status, 1, 1)
        
        return group
    
    def on_joint_changed(self, joint_id: int, value: float):
        """Handle joint position change."""
        self.joint_position_changed.emit(joint_id, value)
    
    def on_cartesian_changed(self, axis: str, value: float):
        """Handle cartesian position change."""
        self.cartesian_position_changed.emit(axis, value)
    
    def move_axis(self, axis: str):
        """Move specific axis to target position."""
        if axis in self.cartesian_controls:
            value = self.cartesian_controls[axis].value()
            self.cartesian_position_changed.emit(axis, value)
    
    def update_status(self):
        """Update status information."""
        # This would be connected to actual robot status in a real implementation
        pass
    
    def apply_theme(self):
        """Apply theme styling."""
        self.setStyleSheet(f"""
        QGroupBox {{
            font-weight: 600;
            font-size: 14px;
            color: {self.theme.colors.primary_text};
            border: 2px solid {self.theme.colors.border_light};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px 0 8px;
            background-color: {self.theme.colors.primary_background};
        }}
        
        QPushButton#mode-button {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 500;
        }}
        
        QPushButton#mode-button:checked {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
        }}
        
        QPushButton#action-button-primary {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        QPushButton#action-button-danger {{
            background-color: #FF3B30;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        QSlider::groove:horizontal {{
            border: 1px solid {self.theme.colors.border_light};
            height: 6px;
            background: {self.theme.colors.secondary_background};
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            background: {self.theme.colors.accent_blue};
            border: 1px solid {self.theme.colors.accent_blue};
            width: 16px;
            height: 16px;
            border-radius: 8px;
            margin: -6px 0;
        }}
        
        QLabel#status-text {{
            font-size: 12px;
            color: {self.theme.colors.secondary_text};
        }}
        """)
