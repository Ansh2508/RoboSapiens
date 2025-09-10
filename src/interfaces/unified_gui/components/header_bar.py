"""
Header Bar Component

Professional header bar with connection status, robot model display, emergency stop,
settings dropdown, and user profile section following Apple design principles.
"""

import os
import sys
from typing import Optional, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QMenu, QAction, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap, QPainter, QPen, QColor

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class HeaderBar(QWidget):
    """Professional header bar with connection status and controls."""
    
    # Signals
    emergency_stop_triggered = pyqtSignal()
    settings_requested = pyqtSignal(str)  # settings type
    robot_model_changed = pyqtSignal(str)
    connection_requested = pyqtSignal()
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.robot_ip = "192.168.1.100"
        self.robot_model = "Niryo Ned2"
        self.connection_status = "Disconnected"
        self.is_connected = False
        
        # Set fixed height for header
        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.init_ui()
        self.setup_connections()
        self.apply_theme()
        
        # Setup status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
        
        logger.info("Header bar initialized")
    
    def init_ui(self):
        """Initialize the header bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(16)
        
        # Left section: Connection status and robot info
        self.create_connection_section(layout)
        
        # Center section: Title and branding
        self.create_title_section(layout)
        
        # Right section: Controls and user profile
        self.create_controls_section(layout)
    
    def create_connection_section(self, layout: QHBoxLayout):
        """Create connection status section."""
        connection_frame = QFrame()
        connection_frame.setObjectName("connection-frame")
        connection_layout = QHBoxLayout(connection_frame)
        connection_layout.setContentsMargins(12, 4, 12, 4)
        connection_layout.setSpacing(8)
        
        # Connection status indicator
        self.status_indicator = QLabel()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setObjectName("status-indicator")
        connection_layout.addWidget(self.status_indicator)
        
        # Connection info
        connection_info = QVBoxLayout()
        connection_info.setSpacing(2)
        
        self.connection_label = QLabel(self.connection_status)
        self.connection_label.setObjectName("connection-status")
        connection_info.addWidget(self.connection_label)
        
        self.robot_ip_label = QLabel(f"IP: {self.robot_ip}")
        self.robot_ip_label.setObjectName("connection-ip")
        connection_info.addWidget(self.robot_ip_label)
        
        connection_layout.addLayout(connection_info)
        
        # Robot model selector
        self.robot_model_combo = QComboBox()
        self.robot_model_combo.setObjectName("robot-model-combo")
        self.robot_model_combo.addItems(["Niryo Ned2", "Niryo One", "Custom"])
        self.robot_model_combo.setCurrentText(self.robot_model)
        connection_layout.addWidget(self.robot_model_combo)
        
        layout.addWidget(connection_frame)
    
    def create_title_section(self, layout: QHBoxLayout):
        """Create title and branding section."""
        # Add spacer to center the title
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        title_frame = QFrame()
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)
        
        # Main title
        self.title_label = QLabel("Niryo LLM Robotics Platform")
        self.title_label.setObjectName("main-title")
        self.title_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(self.title_label)
        
        # Subtitle
        self.subtitle_label = QLabel("Professional Robotics Control Interface")
        self.subtitle_label.setObjectName("subtitle")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(self.subtitle_label)
        
        layout.addWidget(title_frame)
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
    
    def create_controls_section(self, layout: QHBoxLayout):
        """Create controls and user profile section."""
        controls_frame = QFrame()
        controls_layout = QHBoxLayout(controls_frame)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(12)
        
        # Emergency stop button
        self.emergency_btn = QPushButton("EMERGENCY STOP")
        self.emergency_btn.setObjectName("emergency-button")
        self.emergency_btn.setFixedSize(120, 40)
        controls_layout.addWidget(self.emergency_btn)
        
        # Settings dropdown
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setObjectName("settings-button")
        self.setup_settings_menu()
        controls_layout.addWidget(self.settings_btn)
        
        # User profile section
        profile_frame = QFrame()
        profile_frame.setObjectName("profile-frame")
        profile_layout = QHBoxLayout(profile_frame)
        profile_layout.setContentsMargins(8, 4, 8, 4)
        profile_layout.setSpacing(8)
        
        # User avatar (placeholder)
        self.user_avatar = QLabel()
        self.user_avatar.setFixedSize(32, 32)
        self.user_avatar.setObjectName("user-avatar")
        self.user_avatar.setText("U")
        self.user_avatar.setAlignment(Qt.AlignCenter)
        profile_layout.addWidget(self.user_avatar)
        
        # User info
        user_info = QVBoxLayout()
        user_info.setSpacing(2)
        
        self.user_name = QLabel("Operator")
        self.user_name.setObjectName("user-name")
        user_info.addWidget(self.user_name)
        
        self.user_role = QLabel("Administrator")
        self.user_role.setObjectName("user-role")
        user_info.addWidget(self.user_role)
        
        profile_layout.addLayout(user_info)
        controls_layout.addWidget(profile_frame)
        
        layout.addWidget(controls_frame)
    
    def setup_settings_menu(self):
        """Setup settings dropdown menu."""
        self.settings_menu = QMenu(self)
        
        # Add settings options
        settings_options = [
            ("Robot Settings", "robot"),
            ("Network Configuration", "network"),
            ("Camera Settings", "camera"),
            ("Voice Settings", "voice"),
            ("System Preferences", "system"),
            ("About", "about")
        ]
        
        for title, setting_type in settings_options:
            action = QAction(title, self)
            action.triggered.connect(lambda checked, st=setting_type: self.settings_requested.emit(st))
            self.settings_menu.addAction(action)
        
        self.settings_btn.setMenu(self.settings_menu)
    
    def setup_connections(self):
        """Setup signal connections."""
        self.emergency_btn.clicked.connect(self.emergency_stop_triggered.emit)
        self.robot_model_combo.currentTextChanged.connect(self.robot_model_changed.emit)
    
    def update_connection_status(self, status: str, ip: str = None, is_connected: bool = False):
        """Update connection status display."""
        self.connection_status = status
        self.is_connected = is_connected
        
        if ip:
            self.robot_ip = ip
            self.robot_ip_label.setText(f"IP: {ip}")
        
        self.connection_label.setText(status)
        
        # Update status indicator color
        if is_connected:
            self.status_indicator.setStyleSheet("background-color: #34C759; border-radius: 6px;")  # Green
        elif status == "Connecting...":
            self.status_indicator.setStyleSheet("background-color: #FF9500; border-radius: 6px;")  # Orange
        else:
            self.status_indicator.setStyleSheet("background-color: #FF3B30; border-radius: 6px;")  # Red
    
    def update_status(self):
        """Update status information periodically."""
        # This would typically update with real system information
        pass
    
    def apply_theme(self):
        """Apply Apple-inspired theme styling."""
        self.setStyleSheet(f"""
        QWidget#HeaderBar {{
            background-color: {self.theme.colors.primary_background};
            border-bottom: 1px solid {self.theme.colors.separator};
        }}
        
        QFrame#connection-frame {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 8px;
            padding: 4px;
        }}
        
        QLabel#connection-status {{
            font-weight: 600;
            font-size: 12px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#connection-ip {{
            font-size: 10px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QLabel#main-title {{
            font-weight: 700;
            font-size: 16px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#subtitle {{
            font-size: 11px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QPushButton#emergency-button {{
            background-color: #FF3B30;
            color: white;
            border: none;
            border-radius: 8px;
            font-weight: 700;
            font-size: 12px;
        }}
        
        QPushButton#emergency-button:hover {{
            background-color: #D70015;
        }}
        
        QPushButton#emergency-button:pressed {{
            background-color: #A20010;
        }}
        
        QPushButton#settings-button {{
            background-color: {self.theme.colors.secondary_background};
            color: {self.theme.colors.primary_text};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
        }}
        
        QPushButton#settings-button:hover {{
            background-color: {self.theme.colors.hover_background};
        }}
        
        QFrame#profile-frame {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 8px;
        }}
        
        QLabel#user-avatar {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
            border-radius: 16px;
            font-weight: 600;
            font-size: 14px;
        }}
        
        QLabel#user-name {{
            font-weight: 600;
            font-size: 12px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#user-role {{
            font-size: 10px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QComboBox#robot-model-combo {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            padding: 4px 8px;
            font-size: 11px;
            min-width: 100px;
        }}
        """)
