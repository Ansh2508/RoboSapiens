"""
Vision System View

Professional vision system interface with camera feed, object detection,
and workspace configuration.
"""

import os
import sys
from typing import Optional, List, Dict, Any
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel, QPushButton,
    QGroupBox, QGridLayout, QComboBox, QCheckBox, QSlider, QSpinBox,
    QListWidget, QListWidgetItem, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QFont, QPixmap, QPainter, QColor, QPen

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class VisionSystemView(QWidget):
    """Professional vision system view with camera and detection capabilities."""
    
    # Signals
    camera_started = pyqtSignal()
    camera_stopped = pyqtSignal()
    detection_enabled = pyqtSignal(bool)
    workspace_calibrated = pyqtSignal()
    object_detected = pyqtSignal(dict)  # object info
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.camera_active = False
        self.detection_active = False
        self.detected_objects = []
        
        self.init_ui()
        self.apply_theme()
        
        # Setup update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_camera_feed)
        
        logger.info("Vision system view initialized")
    
    def init_ui(self):
        """Initialize the vision system interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Left side - Camera feed and controls
        left_layout = QVBoxLayout()
        left_layout.setSpacing(16)
        
        # Camera feed section
        camera_group = self.create_camera_feed_section()
        left_layout.addWidget(camera_group)
        
        # Camera controls
        controls_group = self.create_camera_controls_section()
        left_layout.addWidget(controls_group)
        
        layout.addLayout(left_layout, 2)  # 2/3 of the width
        
        # Right side - Detection and workspace
        right_layout = QVBoxLayout()
        right_layout.setSpacing(16)
        
        # Detection settings
        detection_group = self.create_detection_settings_section()
        right_layout.addWidget(detection_group)
        
        # Detected objects
        objects_group = self.create_detected_objects_section()
        right_layout.addWidget(objects_group)
        
        # Workspace configuration
        workspace_group = self.create_workspace_section()
        right_layout.addWidget(workspace_group)
        
        layout.addLayout(right_layout, 1)  # 1/3 of the width
    
    def create_camera_feed_section(self) -> QGroupBox:
        """Create camera feed section."""
        group = QGroupBox("Camera Feed")
        group.setObjectName("camera-feed-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Camera display area
        self.camera_display = QLabel("Camera Not Active")
        self.camera_display.setObjectName("camera-display")
        self.camera_display.setMinimumSize(640, 480)
        self.camera_display.setAlignment(Qt.AlignCenter)
        self.camera_display.setStyleSheet(f"""
            background-color: {self.theme.colors.tertiary_background};
            border: 2px dashed {self.theme.colors.border_light};
            border-radius: 8px;
            color: {self.theme.colors.secondary_text};
            font-size: 16px;
        """)
        layout.addWidget(self.camera_display)
        
        # Camera status
        self.camera_status = QLabel("Status: Disconnected")
        self.camera_status.setObjectName("camera-status")
        layout.addWidget(self.camera_status)
        
        return group
    
    def create_camera_controls_section(self) -> QGroupBox:
        """Create camera controls section."""
        group = QGroupBox("Camera Controls")
        group.setObjectName("camera-controls-group")
        layout = QGridLayout(group)
        layout.setSpacing(12)
        
        # Start/Stop camera
        self.camera_toggle_btn = QPushButton("Start Camera")
        self.camera_toggle_btn.setObjectName("camera-toggle-button")
        self.camera_toggle_btn.clicked.connect(self.toggle_camera)
        layout.addWidget(self.camera_toggle_btn, 0, 0, 1, 2)
        
        # Camera settings
        layout.addWidget(QLabel("Resolution:"), 1, 0)
        self.resolution_combo = QComboBox()
        self.resolution_combo.setObjectName("resolution-combo")
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080"])
        self.resolution_combo.setCurrentText("640x480")
        layout.addWidget(self.resolution_combo, 1, 1)
        
        layout.addWidget(QLabel("FPS:"), 2, 0)
        self.fps_combo = QComboBox()
        self.fps_combo.setObjectName("fps-combo")
        self.fps_combo.addItems(["15", "30", "60"])
        self.fps_combo.setCurrentText("30")
        layout.addWidget(self.fps_combo, 2, 1)
        
        # Brightness and contrast
        layout.addWidget(QLabel("Brightness:"), 3, 0)
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setObjectName("brightness-slider")
        self.brightness_slider.setRange(0, 100)
        self.brightness_slider.setValue(50)
        layout.addWidget(self.brightness_slider, 3, 1)
        
        layout.addWidget(QLabel("Contrast:"), 4, 0)
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setObjectName("contrast-slider")
        self.contrast_slider.setRange(0, 100)
        self.contrast_slider.setValue(50)
        layout.addWidget(self.contrast_slider, 4, 1)
        
        return group
    
    def create_detection_settings_section(self) -> QGroupBox:
        """Create detection settings section."""
        group = QGroupBox("Object Detection")
        group.setObjectName("detection-settings-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Enable detection
        self.detection_checkbox = QCheckBox("Enable Object Detection")
        self.detection_checkbox.setObjectName("detection-checkbox")
        self.detection_checkbox.toggled.connect(self.toggle_detection)
        layout.addWidget(self.detection_checkbox)
        
        # Detection settings
        settings_layout = QGridLayout()
        settings_layout.setSpacing(8)
        
        settings_layout.addWidget(QLabel("Confidence:"), 0, 0)
        self.confidence_slider = QSlider(Qt.Horizontal)
        self.confidence_slider.setObjectName("confidence-slider")
        self.confidence_slider.setRange(10, 100)
        self.confidence_slider.setValue(70)
        settings_layout.addWidget(self.confidence_slider, 0, 1)
        
        self.confidence_label = QLabel("70%")
        self.confidence_label.setObjectName("confidence-label")
        settings_layout.addWidget(self.confidence_label, 0, 2)
        
        settings_layout.addWidget(QLabel("Min Size:"), 1, 0)
        self.min_size_spinbox = QSpinBox()
        self.min_size_spinbox.setObjectName("min-size-spinbox")
        self.min_size_spinbox.setRange(10, 1000)
        self.min_size_spinbox.setValue(50)
        self.min_size_spinbox.setSuffix(" px")
        settings_layout.addWidget(self.min_size_spinbox, 1, 1, 1, 2)
        
        layout.addLayout(settings_layout)
        
        # Connect confidence slider to label
        self.confidence_slider.valueChanged.connect(
            lambda v: self.confidence_label.setText(f"{v}%")
        )
        
        return group
    
    def create_detected_objects_section(self) -> QGroupBox:
        """Create detected objects section."""
        group = QGroupBox("Detected Objects")
        group.setObjectName("detected-objects-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Objects list
        self.objects_list = QListWidget()
        self.objects_list.setObjectName("objects-list")
        self.objects_list.setMaximumHeight(150)
        layout.addWidget(self.objects_list)
        
        # Object details
        self.object_details = QTextEdit()
        self.object_details.setObjectName("object-details")
        self.object_details.setMaximumHeight(100)
        self.object_details.setPlaceholderText("Select an object to view details...")
        self.object_details.setReadOnly(True)
        layout.addWidget(self.object_details)
        
        # Connect list selection to details
        self.objects_list.currentItemChanged.connect(self.show_object_details)
        
        return group
    
    def create_workspace_section(self) -> QGroupBox:
        """Create workspace configuration section."""
        group = QGroupBox("Workspace Setup")
        group.setObjectName("workspace-group")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)
        
        # Calibration button
        calibrate_btn = QPushButton("Calibrate Workspace")
        calibrate_btn.setObjectName("calibrate-button")
        calibrate_btn.clicked.connect(self.calibrate_workspace)
        layout.addWidget(calibrate_btn)
        
        # Workspace status
        self.workspace_status = QLabel("Status: Not Calibrated")
        self.workspace_status.setObjectName("workspace-status")
        layout.addWidget(self.workspace_status)
        
        # Workspace bounds
        bounds_layout = QGridLayout()
        bounds_layout.setSpacing(8)
        
        bounds_layout.addWidget(QLabel("X Range:"), 0, 0)
        self.x_min_spinbox = QSpinBox()
        self.x_min_spinbox.setRange(-500, 500)
        self.x_min_spinbox.setValue(-200)
        self.x_min_spinbox.setSuffix(" mm")
        bounds_layout.addWidget(self.x_min_spinbox, 0, 1)
        
        self.x_max_spinbox = QSpinBox()
        self.x_max_spinbox.setRange(-500, 500)
        self.x_max_spinbox.setValue(200)
        self.x_max_spinbox.setSuffix(" mm")
        bounds_layout.addWidget(self.x_max_spinbox, 0, 2)
        
        bounds_layout.addWidget(QLabel("Y Range:"), 1, 0)
        self.y_min_spinbox = QSpinBox()
        self.y_min_spinbox.setRange(-500, 500)
        self.y_min_spinbox.setValue(-200)
        self.y_min_spinbox.setSuffix(" mm")
        bounds_layout.addWidget(self.y_min_spinbox, 1, 1)
        
        self.y_max_spinbox = QSpinBox()
        self.y_max_spinbox.setRange(-500, 500)
        self.y_max_spinbox.setValue(200)
        self.y_max_spinbox.setSuffix(" mm")
        bounds_layout.addWidget(self.y_max_spinbox, 1, 2)
        
        layout.addLayout(bounds_layout)
        
        return group
    
    def toggle_camera(self):
        """Toggle camera on/off."""
        if self.camera_active:
            self.stop_camera()
        else:
            self.start_camera()
    
    def start_camera(self):
        """Start camera feed."""
        self.camera_active = True
        self.camera_toggle_btn.setText("Stop Camera")
        self.camera_status.setText("Status: Active")
        self.camera_display.setText("Camera Feed Active\n(Simulated)")
        self.update_timer.start(100)  # Update at 10 FPS for simulation
        self.camera_started.emit()
        logger.info("Camera started")
    
    def stop_camera(self):
        """Stop camera feed."""
        self.camera_active = False
        self.camera_toggle_btn.setText("Start Camera")
        self.camera_status.setText("Status: Disconnected")
        self.camera_display.setText("Camera Not Active")
        self.update_timer.stop()
        self.camera_stopped.emit()
        logger.info("Camera stopped")
    
    def toggle_detection(self, enabled: bool):
        """Toggle object detection."""
        self.detection_active = enabled
        self.detection_enabled.emit(enabled)
        if enabled:
            logger.info("Object detection enabled")
        else:
            logger.info("Object detection disabled")
            self.objects_list.clear()
            self.object_details.clear()
    
    def calibrate_workspace(self):
        """Calibrate workspace bounds."""
        self.workspace_status.setText("Status: Calibrated")
        self.workspace_calibrated.emit()
        logger.info("Workspace calibrated")
    
    def update_camera_feed(self):
        """Update camera feed (simulation)."""
        if self.camera_active and self.detection_active:
            # Simulate object detection
            import random
            if random.random() < 0.1:  # 10% chance to detect object
                self.simulate_object_detection()
    
    def simulate_object_detection(self):
        """Simulate object detection for demonstration."""
        import random
        objects = ["Cube", "Cylinder", "Sphere", "Tool", "Part"]
        colors = ["Red", "Blue", "Green", "Yellow", "Black"]
        
        obj_type = random.choice(objects)
        obj_color = random.choice(colors)
        obj_id = len(self.detected_objects) + 1
        
        obj_info = {
            "id": obj_id,
            "type": obj_type,
            "color": obj_color,
            "confidence": random.randint(70, 95),
            "position": {
                "x": random.randint(-150, 150),
                "y": random.randint(-150, 150),
                "z": random.randint(0, 50)
            },
            "size": {
                "width": random.randint(20, 80),
                "height": random.randint(20, 80)
            }
        }
        
        self.detected_objects.append(obj_info)
        
        # Add to list
        item_text = f"{obj_color} {obj_type} ({obj_info['confidence']}%)"
        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, obj_info)
        self.objects_list.addItem(item)
        
        # Limit to 10 objects
        if self.objects_list.count() > 10:
            self.objects_list.takeItem(0)
            self.detected_objects.pop(0)
        
        self.object_detected.emit(obj_info)
    
    def show_object_details(self, current, previous):
        """Show details for selected object."""
        if current:
            obj_info = current.data(Qt.UserRole)
            if obj_info:
                details = f"""Object ID: {obj_info['id']}
Type: {obj_info['type']}
Color: {obj_info['color']}
Confidence: {obj_info['confidence']}%
Position: X={obj_info['position']['x']}mm, Y={obj_info['position']['y']}mm, Z={obj_info['position']['z']}mm
Size: {obj_info['size']['width']}x{obj_info['size']['height']}px"""
                self.object_details.setText(details)
    
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
        
        QPushButton#camera-toggle-button {{
            background-color: {self.theme.colors.accent_blue};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: 600;
        }}
        
        QPushButton#calibrate-button {{
            background-color: {self.theme.colors.accent_green};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-size: 13px;
            font-weight: 500;
        }}
        
        QCheckBox#detection-checkbox {{
            font-size: 13px;
            font-weight: 500;
        }}
        
        QListWidget#objects-list {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            font-size: 12px;
        }}
        
        QTextEdit#object-details {{
            background-color: {self.theme.colors.secondary_background};
            border: 1px solid {self.theme.colors.border_light};
            border-radius: 6px;
            font-size: 11px;
            font-family: monospace;
        }}
        """)
