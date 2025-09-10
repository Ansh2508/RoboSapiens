"""
Right Panel Component

Contextual right panel with notifications center, live metrics display,
and quick tools panel following Apple design principles.
"""

import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QProgressBar, QGroupBox, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QIcon, QPixmap

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class NotificationItem(QFrame):
    """Individual notification item."""
    
    def __init__(self, title: str, message: str, notification_type: str = "info", timestamp: datetime = None):
        super().__init__()
        self.title = title
        self.message = message
        self.notification_type = notification_type
        self.timestamp = timestamp or datetime.now()
        
        self.setObjectName(f"notification-{notification_type}")
        self.init_ui()
    
    def init_ui(self):
        """Initialize notification item UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Header with title and timestamp
        header_layout = QHBoxLayout()
        
        title_label = QLabel(self.title)
        title_label.setObjectName("notification-title")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        time_label = QLabel(self.timestamp.strftime("%H:%M"))
        time_label.setObjectName("notification-time")
        header_layout.addWidget(time_label)
        
        layout.addLayout(header_layout)
        
        # Message
        message_label = QLabel(self.message)
        message_label.setObjectName("notification-message")
        message_label.setWordWrap(True)
        layout.addWidget(message_label)


class MetricCard(QFrame):
    """Individual metric display card."""
    
    def __init__(self, title: str, value: str, unit: str = "", trend: str = "neutral"):
        super().__init__()
        self.title = title
        self.value = value
        self.unit = unit
        self.trend = trend
        
        self.setObjectName("metric-card")
        self.init_ui()
    
    def init_ui(self):
        """Initialize metric card UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setObjectName("metric-title")
        layout.addWidget(title_label)
        
        # Value with unit
        value_layout = QHBoxLayout()
        
        self.value_label = QLabel(self.value)
        self.value_label.setObjectName("metric-value")
        value_layout.addWidget(self.value_label)
        
        if self.unit:
            unit_label = QLabel(self.unit)
            unit_label.setObjectName("metric-unit")
            value_layout.addWidget(unit_label)
        
        value_layout.addStretch()
        layout.addLayout(value_layout)
    
    def update_value(self, value: str, trend: str = "neutral"):
        """Update metric value and trend."""
        self.value = value
        self.trend = trend
        self.value_label.setText(value)


class RightPanel(QWidget):
    """Contextual right panel with notifications and metrics."""
    
    # Signals
    screenshot_requested = pyqtSignal()
    video_recording_requested = pyqtSignal(bool)  # start/stop
    position_save_requested = pyqtSignal()
    notification_cleared = pyqtSignal(str)  # notification id
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.notifications = []
        self.metrics = {}
        self.is_recording = False
        
        # Set fixed width for right panel
        self.setFixedWidth(320)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        self.init_ui()
        self.setup_connections()
        self.apply_theme()
        
        # Setup metrics update timer
        self.metrics_timer = QTimer()
        self.metrics_timer.timeout.connect(self.update_metrics)
        self.metrics_timer.start(2000)  # Update every 2 seconds
        
        # Add some initial metrics
        self.add_initial_metrics()
        
        logger.info("Right panel initialized")
    
    def init_ui(self):
        """Initialize the right panel UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Notifications section
        self.create_notifications_section(layout)
        
        # Metrics section
        self.create_metrics_section(layout)
        
        # Quick tools section
        self.create_quick_tools_section(layout)
        
        # Add stretch to push everything to top
        layout.addStretch()
    
    def create_notifications_section(self, layout: QVBoxLayout):
        """Create notifications center section."""
        notifications_group = QGroupBox("Notifications")
        notifications_group.setObjectName("section-group")
        notifications_layout = QVBoxLayout(notifications_group)
        notifications_layout.setContentsMargins(8, 12, 8, 8)
        notifications_layout.setSpacing(8)
        
        # Notifications scroll area
        self.notifications_scroll = QScrollArea()
        self.notifications_scroll.setObjectName("notifications-scroll")
        self.notifications_scroll.setWidgetResizable(True)
        self.notifications_scroll.setMaximumHeight(200)
        
        self.notifications_widget = QWidget()
        self.notifications_layout = QVBoxLayout(self.notifications_widget)
        self.notifications_layout.setContentsMargins(0, 0, 0, 0)
        self.notifications_layout.setSpacing(4)
        
        # Add stretch to push notifications to top
        self.notifications_layout.addStretch()
        
        self.notifications_scroll.setWidget(self.notifications_widget)
        notifications_layout.addWidget(self.notifications_scroll)
        
        # Clear all button
        clear_btn = QPushButton("Clear All")
        clear_btn.setObjectName("clear-button")
        clear_btn.clicked.connect(self.clear_all_notifications)
        notifications_layout.addWidget(clear_btn)
        
        layout.addWidget(notifications_group)
    
    def create_metrics_section(self, layout: QVBoxLayout):
        """Create live metrics section."""
        metrics_group = QGroupBox("Live Metrics")
        metrics_group.setObjectName("section-group")
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setContentsMargins(8, 12, 8, 8)
        metrics_layout.setSpacing(8)
        
        # Metrics container
        self.metrics_widget = QWidget()
        self.metrics_layout = QVBoxLayout(self.metrics_widget)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setSpacing(8)
        
        metrics_layout.addWidget(self.metrics_widget)
        layout.addWidget(metrics_group)
    
    def create_quick_tools_section(self, layout: QVBoxLayout):
        """Create quick tools section."""
        tools_group = QGroupBox("Quick Tools")
        tools_group.setObjectName("section-group")
        tools_layout = QVBoxLayout(tools_group)
        tools_layout.setContentsMargins(8, 12, 8, 8)
        tools_layout.setSpacing(8)
        
        # Screenshot button
        self.screenshot_btn = QPushButton("Take Screenshot")
        self.screenshot_btn.setObjectName("tool-button")
        tools_layout.addWidget(self.screenshot_btn)
        
        # Video recording button
        self.video_btn = QPushButton("Start Recording")
        self.video_btn.setObjectName("tool-button")
        tools_layout.addWidget(self.video_btn)
        
        # Save position button
        self.save_position_btn = QPushButton("Save Position")
        self.save_position_btn.setObjectName("tool-button")
        tools_layout.addWidget(self.save_position_btn)
        
        layout.addWidget(tools_group)
    
    def setup_connections(self):
        """Setup signal connections."""
        self.screenshot_btn.clicked.connect(self.screenshot_requested.emit)
        self.video_btn.clicked.connect(self.toggle_video_recording)
        self.save_position_btn.clicked.connect(self.position_save_requested.emit)
    
    def add_notification(self, title: str, message: str, notification_type: str = "info"):
        """Add a new notification."""
        notification = NotificationItem(title, message, notification_type)
        
        # Insert at the beginning (most recent first)
        self.notifications_layout.insertWidget(0, notification)
        self.notifications.append(notification)
        
        # Limit to 10 notifications
        if len(self.notifications) > 10:
            old_notification = self.notifications.pop(0)
            old_notification.deleteLater()
        
        logger.info(f"Added notification: {title} - {message}")
    
    def clear_all_notifications(self):
        """Clear all notifications."""
        for notification in self.notifications:
            notification.deleteLater()
        self.notifications.clear()
        logger.info("Cleared all notifications")
    
    def add_initial_metrics(self):
        """Add initial metric cards."""
        metrics_data = [
            ("Operations", "0", "total"),
            ("Success Rate", "0.0", "%"),
            ("Avg. Time", "0.0", "sec"),
            ("Uptime", "00:00:00", "")
        ]
        
        for title, value, unit in metrics_data:
            metric_card = MetricCard(title, value, unit)
            self.metrics[title.lower().replace(" ", "_")] = metric_card
            self.metrics_layout.addWidget(metric_card)
    
    def update_metric(self, metric_name: str, value: str, trend: str = "neutral"):
        """Update a specific metric."""
        if metric_name in self.metrics:
            self.metrics[metric_name].update_value(value, trend)
    
    def update_metrics(self):
        """Update metrics with current system data."""
        # This would typically get real system metrics
        # For now, we'll simulate some data
        import random
        
        # Simulate operations count
        operations = random.randint(0, 100)
        self.update_metric("operations", str(operations))
        
        # Simulate success rate
        success_rate = random.uniform(85.0, 99.9)
        self.update_metric("success_rate", f"{success_rate:.1f}")
        
        # Simulate average time
        avg_time = random.uniform(1.0, 5.0)
        self.update_metric("avg._time", f"{avg_time:.1f}")
    
    def toggle_video_recording(self):
        """Toggle video recording."""
        self.is_recording = not self.is_recording
        
        if self.is_recording:
            self.video_btn.setText("Stop Recording")
            self.video_btn.setObjectName("tool-button-active")
            self.add_notification("Recording", "Video recording started", "info")
        else:
            self.video_btn.setText("Start Recording")
            self.video_btn.setObjectName("tool-button")
            self.add_notification("Recording", "Video recording stopped", "info")
        
        self.video_btn.style().unpolish(self.video_btn)
        self.video_btn.style().polish(self.video_btn)
        
        self.video_recording_requested.emit(self.is_recording)
    
    def apply_theme(self):
        """Apply Apple-inspired theme styling."""
        self.setStyleSheet(f"""
        QWidget {{
            background-color: {self.theme.colors.primary_background};
        }}
        
        QGroupBox#section-group {{
            font-weight: 600;
            font-size: 13px;
            color: {self.theme.colors.primary_text};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 8px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        
        QGroupBox#section-group::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
        }}
        
        QFrame#notification-info {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            margin: 2px;
        }}
        
        QFrame#notification-warning {{
            background-color: #FFF3CD;
            border: 1px solid #FFEAA7;
            border-radius: 6px;
            margin: 2px;
        }}
        
        QFrame#notification-error {{
            background-color: #F8D7DA;
            border: 1px solid #F5C6CB;
            border-radius: 6px;
            margin: 2px;
        }}
        
        QLabel#notification-title {{
            font-weight: 600;
            font-size: 12px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#notification-message {{
            font-size: 11px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QLabel#notification-time {{
            font-size: 10px;
            color: {self.theme.colors.tertiary_text};
        }}
        
        QFrame#metric-card {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            margin: 2px;
        }}
        
        QLabel#metric-title {{
            font-size: 11px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QLabel#metric-value {{
            font-weight: 700;
            font-size: 18px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#metric-unit {{
            font-size: 12px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QPushButton#tool-button {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        QPushButton#tool-button:hover {{
            background-color: {self.theme.colors.accent_blue_hover};
        }}
        
        QPushButton#tool-button-active {{
            background-color: #FF3B30;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 12px;
            font-weight: 600;
        }}
        
        QPushButton#clear-button {{
            background-color: {self.theme.colors.secondary_background};
            color: {self.theme.colors.primary_text};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 11px;
        }}
        
        QPushButton#clear-button:hover {{
            background-color: {self.theme.colors.hover_background};
        }}
        
        QScrollArea#notifications-scroll {{
            border: none;
            background-color: transparent;
        }}
        """)
