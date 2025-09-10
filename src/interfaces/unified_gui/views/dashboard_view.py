"""
Dashboard View

Main dashboard view with system status cards, real-time metrics charts,
recent activities log, and camera preview following Apple design principles.
"""

import os
import sys
from typing import Dict, List, Any
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QGroupBox, QScrollArea, QProgressBar, QSizePolicy, QSpacerItem
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QPainter, QPen, QColor

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class StatusCard(QFrame):
    """Individual status card for dashboard."""
    
    def __init__(self, title: str, value: str, status: str = "normal", description: str = ""):
        super().__init__()
        self.title = title
        self.value = value
        self.status = status
        self.description = description
        
        self.setObjectName(f"status-card-{status}")
        self.init_ui()
    
    def init_ui(self):
        """Initialize status card UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Title
        title_label = QLabel(self.title)
        title_label.setObjectName("card-title")
        layout.addWidget(title_label)
        
        # Value
        self.value_label = QLabel(self.value)
        self.value_label.setObjectName("card-value")
        layout.addWidget(self.value_label)
        
        # Description
        if self.description:
            desc_label = QLabel(self.description)
            desc_label.setObjectName("card-description")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
        
        # Status indicator
        self.status_indicator = QFrame()
        self.status_indicator.setFixedHeight(4)
        self.status_indicator.setObjectName(f"status-indicator-{self.status}")
        layout.addWidget(self.status_indicator)
    
    def update_value(self, value: str, status: str = None):
        """Update card value and status."""
        self.value = value
        self.value_label.setText(value)
        
        if status and status != self.status:
            self.status = status
            self.setObjectName(f"status-card-{status}")
            self.status_indicator.setObjectName(f"status-indicator-{status}")
            self.style().unpolish(self)
            self.style().polish(self)


class ActivityItem(QFrame):
    """Individual activity log item."""
    
    def __init__(self, timestamp: datetime, activity: str, status: str = "info"):
        super().__init__()
        self.timestamp = timestamp
        self.activity = activity
        self.status = status
        
        self.setObjectName("activity-item")
        self.init_ui()
    
    def init_ui(self):
        """Initialize activity item UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Timestamp
        time_label = QLabel(self.timestamp.strftime("%H:%M:%S"))
        time_label.setObjectName("activity-time")
        time_label.setFixedWidth(60)
        layout.addWidget(time_label)
        
        # Status indicator
        status_dot = QLabel()
        status_dot.setFixedSize(8, 8)
        status_dot.setObjectName(f"activity-status-{self.status}")
        layout.addWidget(status_dot)
        
        # Activity text
        activity_label = QLabel(self.activity)
        activity_label.setObjectName("activity-text")
        activity_label.setWordWrap(True)
        layout.addWidget(activity_label)
        
        layout.addStretch()


class DashboardView(QWidget):
    """Main dashboard view with system overview."""
    
    # Signals
    camera_preview_clicked = pyqtSignal()
    status_card_clicked = pyqtSignal(str)  # card type
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.status_cards = {}
        self.activities = []
        
        self.init_ui()
        self.setup_connections()
        self.apply_theme()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_dashboard)
        self.update_timer.start(2000)  # Update every 2 seconds
        
        # Initialize with default data
        self.initialize_dashboard()
        
        logger.info("Dashboard view initialized")
    
    def init_ui(self):
        """Initialize the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)
        
        # Top section: Status cards
        self.create_status_cards_section(layout)
        
        # Middle section: Charts and camera preview
        self.create_middle_section(layout)
        
        # Bottom section: Recent activities
        self.create_activities_section(layout)
    
    def create_status_cards_section(self, layout: QVBoxLayout):
        """Create status cards section."""
        cards_group = QGroupBox("System Status")
        cards_group.setObjectName("dashboard-group")
        cards_layout = QGridLayout(cards_group)
        cards_layout.setContentsMargins(16, 20, 16, 16)
        cards_layout.setSpacing(16)
        
        # Create status cards
        cards_data = [
            ("Robot Status", "Disconnected", "warning", "Robot connection status"),
            ("Camera Status", "Ready", "normal", "Camera system status"),
            ("Operations Today", "0", "normal", "Completed operations"),
            ("Success Rate", "0%", "normal", "Operation success rate")
        ]
        
        for i, (title, value, status, description) in enumerate(cards_data):
            card = StatusCard(title, value, status, description)
            self.status_cards[title.lower().replace(" ", "_")] = card
            
            row = i // 2
            col = i % 2
            cards_layout.addWidget(card, row, col)
        
        layout.addWidget(cards_group)
    
    def create_middle_section(self, layout: QVBoxLayout):
        """Create middle section with charts and camera preview."""
        middle_layout = QHBoxLayout()
        middle_layout.setSpacing(24)
        
        # Metrics chart placeholder
        metrics_group = QGroupBox("Performance Metrics")
        metrics_group.setObjectName("dashboard-group")
        metrics_layout = QVBoxLayout(metrics_group)
        metrics_layout.setContentsMargins(16, 20, 16, 16)
        
        # Chart placeholder
        chart_placeholder = QFrame()
        chart_placeholder.setObjectName("chart-placeholder")
        chart_placeholder.setFixedHeight(200)
        
        chart_layout = QVBoxLayout(chart_placeholder)
        chart_layout.setAlignment(Qt.AlignCenter)
        
        chart_label = QLabel("Performance Chart")
        chart_label.setObjectName("placeholder-text")
        chart_label.setAlignment(Qt.AlignCenter)
        chart_layout.addWidget(chart_label)
        
        chart_desc = QLabel("Real-time performance metrics will be displayed here")
        chart_desc.setObjectName("placeholder-description")
        chart_desc.setAlignment(Qt.AlignCenter)
        chart_layout.addWidget(chart_desc)
        
        metrics_layout.addWidget(chart_placeholder)
        middle_layout.addWidget(metrics_group)
        
        # Camera preview
        camera_group = QGroupBox("Camera Preview")
        camera_group.setObjectName("dashboard-group")
        camera_layout = QVBoxLayout(camera_group)
        camera_layout.setContentsMargins(16, 20, 16, 16)
        
        # Camera preview placeholder
        self.camera_preview = QFrame()
        self.camera_preview.setObjectName("camera-preview")
        self.camera_preview.setFixedHeight(200)
        self.camera_preview.setCursor(Qt.PointingHandCursor)
        
        preview_layout = QVBoxLayout(self.camera_preview)
        preview_layout.setAlignment(Qt.AlignCenter)
        
        camera_icon = QLabel("📷")
        camera_icon.setObjectName("camera-icon")
        camera_icon.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(camera_icon)
        
        camera_text = QLabel("Click to open camera")
        camera_text.setObjectName("placeholder-text")
        camera_text.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(camera_text)
        
        camera_layout.addWidget(self.camera_preview)
        middle_layout.addWidget(camera_group)
        
        layout.addLayout(middle_layout)
    
    def create_activities_section(self, layout: QVBoxLayout):
        """Create recent activities section."""
        activities_group = QGroupBox("Recent Activities")
        activities_group.setObjectName("dashboard-group")
        activities_layout = QVBoxLayout(activities_group)
        activities_layout.setContentsMargins(16, 20, 16, 16)
        activities_layout.setSpacing(8)
        
        # Activities scroll area
        self.activities_scroll = QScrollArea()
        self.activities_scroll.setObjectName("activities-scroll")
        self.activities_scroll.setWidgetResizable(True)
        self.activities_scroll.setMaximumHeight(200)
        
        self.activities_widget = QWidget()
        self.activities_layout = QVBoxLayout(self.activities_widget)
        self.activities_layout.setContentsMargins(0, 0, 0, 0)
        self.activities_layout.setSpacing(4)
        
        # Add stretch to push activities to top
        self.activities_layout.addStretch()
        
        self.activities_scroll.setWidget(self.activities_widget)
        activities_layout.addWidget(self.activities_scroll)
        
        layout.addWidget(activities_group)
    
    def setup_connections(self):
        """Setup signal connections."""
        self.camera_preview.mousePressEvent = lambda event: self.camera_preview_clicked.emit()
    
    def initialize_dashboard(self):
        """Initialize dashboard with default data."""
        # Add initial activities
        initial_activities = [
            (datetime.now(), "Dashboard initialized", "info"),
            (datetime.now(), "System ready for operation", "success"),
            (datetime.now(), "Comprehensive 5-section layout loaded", "info"),
        ]

        for timestamp, activity, status in initial_activities:
            self.add_activity(timestamp, activity, status)
    
    def add_activity(self, timestamp: datetime, activity: str, status: str = "info"):
        """Add a new activity to the log."""
        activity_item = ActivityItem(timestamp, activity, status)
        
        # Insert at the beginning (most recent first)
        self.activities_layout.insertWidget(0, activity_item)
        self.activities.append(activity_item)
        
        # Limit to 20 activities
        if len(self.activities) > 20:
            old_activity = self.activities.pop(0)
            old_activity.deleteLater()
        
        logger.info(f"Added activity: {activity}")
    
    def update_status_card(self, card_name: str, value: str, status: str = "normal"):
        """Update a status card."""
        if card_name in self.status_cards:
            self.status_cards[card_name].update_value(value, status)
    
    def update_dashboard(self):
        """Update dashboard with current system data."""
        # This would typically get real system data
        # For now, we'll simulate some updates
        import random
        
        # Simulate operations count
        operations = random.randint(0, 50)
        self.update_status_card("operations_today", str(operations))
        
        # Simulate success rate
        success_rate = random.uniform(85.0, 99.9)
        self.update_status_card("success_rate", f"{success_rate:.1f}%")
        
        # Occasionally add random activities
        if random.random() < 0.1:  # 10% chance
            activities = [
                "Position updated",
                "Tool calibrated",
                "Vision system activated",
                "Movement completed"
            ]
            activity = random.choice(activities)
            self.add_activity(datetime.now(), activity, "info")
    
    def apply_theme(self):
        """Apply Apple-inspired theme styling."""
        self.setStyleSheet(f"""
        QWidget {{
            background-color: {self.theme.colors.primary_background};
        }}
        
        QGroupBox#dashboard-group {{
            font-weight: 600;
            font-size: 14px;
            color: {self.theme.colors.primary_text};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 12px;
            margin-top: 12px;
            padding-top: 12px;
        }}
        
        QGroupBox#dashboard-group::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px 0 8px;
        }}
        
        QFrame#status-card-normal {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 8px;
        }}
        
        QFrame#status-card-warning {{
            background-color: #FFF3CD;
            border: 1px solid #FFEAA7;
            border-radius: 8px;
        }}
        
        QFrame#status-card-error {{
            background-color: #F8D7DA;
            border: 1px solid #F5C6CB;
            border-radius: 8px;
        }}
        
        QLabel#card-title {{
            font-weight: 600;
            font-size: 13px;
            color: {self.theme.colors.secondary_text};
        }}
        
        QLabel#card-value {{
            font-weight: 700;
            font-size: 24px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#card-description {{
            font-size: 11px;
            color: {self.theme.colors.tertiary_text};
        }}
        
        QFrame#status-indicator-normal {{
            background-color: #34C759;
            border-radius: 2px;
        }}
        
        QFrame#status-indicator-warning {{
            background-color: #FF9500;
            border-radius: 2px;
        }}
        
        QFrame#status-indicator-error {{
            background-color: #FF3B30;
            border-radius: 2px;
        }}
        
        QFrame#chart-placeholder, QFrame#camera-preview {{
            background-color: {self.theme.colors.secondary_background};
            border: 2px dashed {self.theme.colors.border_medium};
            border-radius: 8px;
        }}
        
        QFrame#camera-preview:hover {{
            border-color: {self.theme.colors.accent_blue};
            background-color: {self.theme.colors.hover_background};
        }}
        
        QLabel#placeholder-text {{
            font-size: 16px;
            font-weight: 600;
            color: {self.theme.colors.secondary_text};
        }}
        
        QLabel#placeholder-description {{
            font-size: 12px;
            color: {self.theme.colors.tertiary_text};
        }}
        
        QLabel#camera-icon {{
            font-size: 48px;
        }}
        
        QFrame#activity-item {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            margin: 2px;
        }}
        
        QLabel#activity-time {{
            font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
            font-size: 10px;
            color: {self.theme.colors.tertiary_text};
        }}
        
        QLabel#activity-text {{
            font-size: 12px;
            color: {self.theme.colors.primary_text};
        }}
        
        QLabel#activity-status-info {{
            background-color: {self.theme.colors.accent_blue};
            border-radius: 4px;
        }}
        
        QLabel#activity-status-success {{
            background-color: #34C759;
            border-radius: 4px;
        }}
        
        QLabel#activity-status-warning {{
            background-color: #FF9500;
            border-radius: 4px;
        }}
        
        QLabel#activity-status-error {{
            background-color: #FF3B30;
            border-radius: 4px;
        }}
        
        QScrollArea#activities-scroll {{
            border: none;
            background-color: transparent;
        }}
        """)
