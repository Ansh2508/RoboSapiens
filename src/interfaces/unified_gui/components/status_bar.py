"""
Status Bar Component

Professional bottom status bar with connection status, camera info, power indicator,
system uptime, and auto-save status following Apple design principles.
"""

import os
import sys
from typing import Optional
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QFrame, QProgressBar, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class StatusBar(QWidget):
    """Professional bottom status bar with system information."""
    
    # Signals
    connection_clicked = pyqtSignal()
    camera_settings_clicked = pyqtSignal()
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.start_time = datetime.now()
        self.connection_status = "Disconnected"
        self.robot_ip = "192.168.1.100"
        self.camera_resolution = "1920x1080"
        self.camera_fps = 30
        self.power_level = 100
        self.auto_save_enabled = True
        self.last_save_time = datetime.now()
        
        # Set fixed height for status bar
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        self.init_ui()
        self.apply_theme()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_status_info)
        self.update_timer.start(1000)  # Update every second
        
        logger.info("Status bar initialized")
    
    def init_ui(self):
        """Initialize the status bar UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)
        layout.setSpacing(16)
        
        # Left section: Connection status
        self.create_connection_section(layout)
        
        # Camera section
        self.create_camera_section(layout)
        
        # Add spacer
        layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # Power section
        self.create_power_section(layout)
        
        # Uptime section
        self.create_uptime_section(layout)
        
        # Auto-save section
        self.create_autosave_section(layout)
    
    def create_connection_section(self, layout: QHBoxLayout):
        """Create connection status section."""
        connection_frame = QFrame()
        connection_frame.setObjectName("status-section")
        connection_layout = QHBoxLayout(connection_frame)
        connection_layout.setContentsMargins(8, 2, 8, 2)
        connection_layout.setSpacing(6)
        
        # Connection status indicator
        self.connection_indicator = QLabel()
        self.connection_indicator.setFixedSize(8, 8)
        self.connection_indicator.setObjectName("connection-indicator")
        connection_layout.addWidget(self.connection_indicator)
        
        # Connection text
        self.connection_text = QLabel(f"{self.connection_status} • {self.robot_ip}")
        self.connection_text.setObjectName("status-text")
        connection_layout.addWidget(self.connection_text)
        
        # Make clickable
        connection_frame.mousePressEvent = lambda event: self.connection_clicked.emit()
        connection_frame.setCursor(Qt.PointingHandCursor)
        
        layout.addWidget(connection_frame)
    
    def create_camera_section(self, layout: QHBoxLayout):
        """Create camera information section."""
        camera_frame = QFrame()
        camera_frame.setObjectName("status-section")
        camera_layout = QHBoxLayout(camera_frame)
        camera_layout.setContentsMargins(8, 2, 8, 2)
        camera_layout.setSpacing(6)
        
        # Camera icon (text placeholder)
        camera_icon = QLabel("📷")
        camera_icon.setObjectName("status-icon")
        camera_layout.addWidget(camera_icon)
        
        # Camera info
        self.camera_text = QLabel(f"{self.camera_resolution} @ {self.camera_fps}fps")
        self.camera_text.setObjectName("status-text")
        camera_layout.addWidget(self.camera_text)
        
        # Make clickable
        camera_frame.mousePressEvent = lambda event: self.camera_settings_clicked.emit()
        camera_frame.setCursor(Qt.PointingHandCursor)
        
        layout.addWidget(camera_frame)
    
    def create_power_section(self, layout: QHBoxLayout):
        """Create power/battery indicator section."""
        power_frame = QFrame()
        power_frame.setObjectName("status-section")
        power_layout = QHBoxLayout(power_frame)
        power_layout.setContentsMargins(8, 2, 8, 2)
        power_layout.setSpacing(6)
        
        # Power icon
        power_icon = QLabel("🔋")
        power_icon.setObjectName("status-icon")
        power_layout.addWidget(power_icon)
        
        # Power level
        self.power_text = QLabel(f"{self.power_level}%")
        self.power_text.setObjectName("status-text")
        power_layout.addWidget(self.power_text)
        
        # Power bar
        self.power_bar = QProgressBar()
        self.power_bar.setObjectName("power-bar")
        self.power_bar.setRange(0, 100)
        self.power_bar.setValue(self.power_level)
        self.power_bar.setFixedSize(40, 8)
        self.power_bar.setTextVisible(False)
        power_layout.addWidget(self.power_bar)
        
        layout.addWidget(power_frame)
    
    def create_uptime_section(self, layout: QHBoxLayout):
        """Create system uptime section."""
        uptime_frame = QFrame()
        uptime_frame.setObjectName("status-section")
        uptime_layout = QHBoxLayout(uptime_frame)
        uptime_layout.setContentsMargins(8, 2, 8, 2)
        uptime_layout.setSpacing(6)
        
        # Uptime icon
        uptime_icon = QLabel("⏱️")
        uptime_icon.setObjectName("status-icon")
        uptime_layout.addWidget(uptime_icon)
        
        # Uptime text
        self.uptime_text = QLabel("00:00:00")
        self.uptime_text.setObjectName("status-text")
        uptime_layout.addWidget(self.uptime_text)
        
        layout.addWidget(uptime_frame)
    
    def create_autosave_section(self, layout: QHBoxLayout):
        """Create auto-save status section."""
        autosave_frame = QFrame()
        autosave_frame.setObjectName("status-section")
        autosave_layout = QHBoxLayout(autosave_frame)
        autosave_layout.setContentsMargins(8, 2, 8, 2)
        autosave_layout.setSpacing(6)
        
        # Auto-save icon
        self.autosave_icon = QLabel("💾")
        self.autosave_icon.setObjectName("status-icon")
        autosave_layout.addWidget(self.autosave_icon)
        
        # Auto-save text
        self.autosave_text = QLabel("Auto-save: On")
        self.autosave_text.setObjectName("status-text")
        autosave_layout.addWidget(self.autosave_text)
        
        layout.addWidget(autosave_frame)
    
    def update_connection_status(self, status: str, ip: str = None):
        """Update connection status display."""
        self.connection_status = status
        if ip:
            self.robot_ip = ip
        
        self.connection_text.setText(f"{status} • {self.robot_ip}")
        
        # Update indicator color based on status
        if status == "Connected":
            self.connection_indicator.setStyleSheet("background-color: #34C759; border-radius: 4px;")  # Green
        elif status == "Connecting...":
            self.connection_indicator.setStyleSheet("background-color: #FF9500; border-radius: 4px;")  # Orange
        else:
            self.connection_indicator.setStyleSheet("background-color: #FF3B30; border-radius: 4px;")  # Red
    
    def update_camera_info(self, resolution: str, fps: int):
        """Update camera information display."""
        self.camera_resolution = resolution
        self.camera_fps = fps
        self.camera_text.setText(f"{resolution} @ {fps}fps")
    
    def update_power_level(self, level: int):
        """Update power level display."""
        self.power_level = max(0, min(100, level))
        self.power_text.setText(f"{self.power_level}%")
        self.power_bar.setValue(self.power_level)
        
        # Update color based on power level
        if self.power_level > 50:
            color = "#34C759"  # Green
        elif self.power_level > 20:
            color = "#FF9500"  # Orange
        else:
            color = "#FF3B30"  # Red
        
        self.power_bar.setStyleSheet(f"""
        QProgressBar#power-bar {{
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 4px;
            background-color: {self.theme.colors.secondary_background};
        }}
        QProgressBar#power-bar::chunk {{
            background-color: {color};
            border-radius: 3px;
        }}
        """)
    
    def update_auto_save_status(self, enabled: bool, last_save: datetime = None):
        """Update auto-save status display."""
        self.auto_save_enabled = enabled
        if last_save:
            self.last_save_time = last_save
        
        if enabled:
            time_since_save = datetime.now() - self.last_save_time
            if time_since_save.total_seconds() < 60:
                self.autosave_text.setText("Auto-save: Just now")
            else:
                minutes = int(time_since_save.total_seconds() / 60)
                self.autosave_text.setText(f"Auto-save: {minutes}m ago")
        else:
            self.autosave_text.setText("Auto-save: Off")
    
    def update_status_info(self):
        """Update status information periodically."""
        # Update uptime
        uptime = datetime.now() - self.start_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.uptime_text.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
        
        # Update auto-save status
        if self.auto_save_enabled:
            self.update_auto_save_status(True, self.last_save_time)
    
    def apply_theme(self):
        """Apply Apple-inspired theme styling."""
        self.setStyleSheet(f"""
        QWidget {{
            background-color: {self.theme.colors.primary_background};
            border-top: 1px solid {self.theme.colors.separator};
        }}
        
        QFrame#status-section {{
            background-color: transparent;
            border: none;
            border-radius: 4px;
            padding: 2px;
        }}
        
        QFrame#status-section:hover {{
            background-color: {self.theme.colors.hover_background};
        }}
        
        QLabel#status-text {{
            font-size: 11px;
            color: {self.theme.colors.secondary_text};
            font-weight: 500;
        }}
        
        QLabel#status-icon {{
            font-size: 12px;
        }}
        
        QLabel#connection-indicator {{
            background-color: #FF3B30;
            border-radius: 4px;
        }}
        
        QProgressBar#power-bar {{
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 4px;
            background-color: {self.theme.colors.secondary_background};
        }}
        
        QProgressBar#power-bar::chunk {{
            background-color: #34C759;
            border-radius: 3px;
        }}
        """)
