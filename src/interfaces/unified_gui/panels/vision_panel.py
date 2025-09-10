"""
Vision Panel

Camera feed display and object detection interface with Apple-inspired design.
"""

import os
import sys
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton,
    QFrame, QComboBox, QSlider, QCheckBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from interfaces.unified_gui.themes.apple_theme import AppleTheme
from utils.logger import get_logger

logger = get_logger(__name__)


class VisionPanel(QWidget):
    """Vision panel for camera feed and object detection."""
    
    # Signals for vision control
    camera_started = pyqtSignal()
    camera_stopped = pyqtSignal()
    detection_enabled = pyqtSignal(bool)
    detection_settings_changed = pyqtSignal(dict)
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.camera_active = False
        self.detection_active = False
        self.current_frame = None
        
        self.init_ui()
        self.setup_connections()
        
        logger.info("Vision panel initialized")
    
    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Camera controls section
        self.camera_controls = self.create_camera_controls()
        layout.addWidget(self.camera_controls)
        
        # Camera feed display
        self.camera_display = self.create_camera_display()
        layout.addWidget(self.camera_display)
        
        # Detection controls section
        self.detection_controls = self.create_detection_controls()
        layout.addWidget(self.detection_controls)
        
        # Detection results section
        self.detection_results = self.create_detection_results()
        layout.addWidget(self.detection_results)
    
    def create_camera_controls(self) -> QGroupBox:
        """Create camera control interface."""
        group = QGroupBox("Camera Control")
        group.setObjectName("control-group")
        layout = QVBoxLayout(group)
        
        # Camera status
        status_layout = QHBoxLayout()
        
        self.camera_status = QLabel("📷 Camera: Inactive")
        self.camera_status.setObjectName("status-indicator")
        status_layout.addWidget(self.camera_status)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Camera control buttons
        button_layout = QHBoxLayout()
        
        self.start_camera_btn = QPushButton("▶️ Start Camera")
        self.start_camera_btn.setObjectName("primary-button")
        self.start_camera_btn.clicked.connect(self.start_camera)
        button_layout.addWidget(self.start_camera_btn)
        
        self.stop_camera_btn = QPushButton("⏹️ Stop Camera")
        self.stop_camera_btn.setObjectName("secondary-button")
        self.stop_camera_btn.clicked.connect(self.stop_camera)
        self.stop_camera_btn.setEnabled(False)
        button_layout.addWidget(self.stop_camera_btn)
        
        layout.addLayout(button_layout)
        
        # Camera settings
        settings_layout = QHBoxLayout()
        
        resolution_label = QLabel("Resolution:")
        settings_layout.addWidget(resolution_label)
        
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["640x480", "1280x720", "1920x1080"])
        self.resolution_combo.setCurrentText("1280x720")
        settings_layout.addWidget(self.resolution_combo)
        
        layout.addLayout(settings_layout)
        
        return group
    
    def create_camera_display(self) -> QFrame:
        """Create camera feed display area."""
        frame = QFrame()
        frame.setObjectName("camera-display")
        frame.setMinimumHeight(300)
        frame.setStyleSheet(f"""
            #camera-display {{
                background-color: {self.theme.colors.secondary_background};
                border: 2px solid {self.theme.colors.border_light};
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        
        # Camera feed label
        self.camera_feed = QLabel("Camera Feed")
        self.camera_feed.setAlignment(Qt.AlignCenter)
        self.camera_feed.setStyleSheet(f"""
            color: {self.theme.colors.secondary_text};
            font-size: 16px;
            padding: 40px;
        """)
        layout.addWidget(self.camera_feed)
        
        return frame
    
    def create_detection_controls(self) -> QGroupBox:
        """Create object detection controls."""
        group = QGroupBox("Object Detection")
        group.setObjectName("control-group")
        layout = QVBoxLayout(group)
        
        # Detection toggle
        detection_layout = QHBoxLayout()
        
        self.detection_checkbox = QCheckBox("Enable Object Detection")
        self.detection_checkbox.setObjectName("detection-toggle")
        self.detection_checkbox.toggled.connect(self.toggle_detection)
        detection_layout.addWidget(self.detection_checkbox)
        
        detection_layout.addStretch()
        layout.addLayout(detection_layout)
        
        # Detection algorithm selection
        algo_layout = QHBoxLayout()
        
        algo_label = QLabel("Algorithm:")
        algo_layout.addWidget(algo_label)
        
        self.algorithm_combo = QComboBox()
        self.algorithm_combo.addItems([
            "Built-in Shapes",
            "Color Detection",
            "Custom Algorithm",
            "YOLO Detection"
        ])
        self.algorithm_combo.currentTextChanged.connect(self.change_detection_algorithm)
        algo_layout.addWidget(self.algorithm_combo)
        
        layout.addLayout(algo_layout)
        
        # Detection sensitivity
        sensitivity_layout = QHBoxLayout()
        
        sensitivity_label = QLabel("Sensitivity:")
        sensitivity_layout.addWidget(sensitivity_label)
        
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 100)
        self.sensitivity_slider.setValue(50)
        self.sensitivity_slider.valueChanged.connect(self.change_sensitivity)
        sensitivity_layout.addWidget(self.sensitivity_slider)
        
        self.sensitivity_value = QLabel("50%")
        sensitivity_layout.addWidget(self.sensitivity_value)
        
        layout.addLayout(sensitivity_layout)
        
        return group
    
    def create_detection_results(self) -> QGroupBox:
        """Create detection results display."""
        group = QGroupBox("Detection Results")
        group.setObjectName("control-group")
        layout = QVBoxLayout(group)
        
        # Results display
        self.results_label = QLabel("No objects detected")
        self.results_label.setObjectName("results-text")
        self.results_label.setAlignment(Qt.AlignCenter)
        self.results_label.setStyleSheet(f"""
            background-color: {self.theme.colors.tertiary_background};
            border-radius: 6px;
            padding: 16px;
            color: {self.theme.colors.secondary_text};
        """)
        layout.addWidget(self.results_label)
        
        # Calibration button
        self.calibrate_workspace_btn = QPushButton("🎯 Calibrate Workspace")
        self.calibrate_workspace_btn.setObjectName("secondary-button")
        self.calibrate_workspace_btn.clicked.connect(self.calibrate_workspace)
        layout.addWidget(self.calibrate_workspace_btn)
        
        return group
    
    def setup_connections(self):
        """Setup signal connections."""
        # Timer for camera feed updates
        self.camera_timer = QTimer()
        self.camera_timer.timeout.connect(self.update_camera_feed)
        
        # Timer for detection updates
        self.detection_timer = QTimer()
        self.detection_timer.timeout.connect(self.update_detection_results)
    
    def start_camera(self):
        """Start camera feed."""
        try:
            self.camera_active = True
            self.camera_status.setText("📷 Camera: Active")
            self.camera_status.setStyleSheet(f"color: {self.theme.colors.success_green};")
            
            self.start_camera_btn.setEnabled(False)
            self.stop_camera_btn.setEnabled(True)
            
            # Start camera timer
            self.camera_timer.start(33)  # ~30 FPS
            
            # Update camera feed display
            self.camera_feed.setText("🎥 Live Camera Feed\n(Simulated)")
            self.camera_feed.setStyleSheet(f"""
                color: {self.theme.colors.success_green};
                font-size: 14px;
                padding: 40px;
            """)
            
            self.camera_started.emit()
            logger.info("Camera started")
            
        except Exception as e:
            logger.error(f"Failed to start camera: {e}")
            self.camera_status.setText("📷 Camera: Error")
            self.camera_status.setStyleSheet(f"color: {self.theme.colors.error_red};")
    
    def stop_camera(self):
        """Stop camera feed."""
        try:
            self.camera_active = False
            self.camera_status.setText("📷 Camera: Inactive")
            self.camera_status.setStyleSheet(f"color: {self.theme.colors.secondary_text};")
            
            self.start_camera_btn.setEnabled(True)
            self.stop_camera_btn.setEnabled(False)
            
            # Stop camera timer
            self.camera_timer.stop()
            
            # Reset camera feed display
            self.camera_feed.setText("Camera Feed")
            self.camera_feed.setStyleSheet(f"""
                color: {self.theme.colors.secondary_text};
                font-size: 16px;
                padding: 40px;
            """)
            
            # Stop detection if active
            if self.detection_active:
                self.detection_checkbox.setChecked(False)
            
            self.camera_stopped.emit()
            logger.info("Camera stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop camera: {e}")
    
    def toggle_detection(self, enabled: bool):
        """Toggle object detection."""
        if enabled and not self.camera_active:
            # Can't enable detection without camera
            self.detection_checkbox.setChecked(False)
            return
        
        self.detection_active = enabled
        
        if enabled:
            self.detection_timer.start(100)  # Update detection every 100ms
            self.results_label.setText("🔍 Detecting objects...")
            self.results_label.setStyleSheet(f"""
                background-color: {self.theme.colors.tertiary_background};
                border-radius: 6px;
                padding: 16px;
                color: {self.theme.colors.accent_blue};
            """)
        else:
            self.detection_timer.stop()
            self.results_label.setText("No objects detected")
            self.results_label.setStyleSheet(f"""
                background-color: {self.theme.colors.tertiary_background};
                border-radius: 6px;
                padding: 16px;
                color: {self.theme.colors.secondary_text};
            """)
        
        self.detection_enabled.emit(enabled)
        logger.info(f"Object detection {'enabled' if enabled else 'disabled'}")
    
    def change_detection_algorithm(self, algorithm: str):
        """Change detection algorithm."""
        settings = {
            'algorithm': algorithm,
            'sensitivity': self.sensitivity_slider.value()
        }
        self.detection_settings_changed.emit(settings)
        logger.info(f"Detection algorithm changed to: {algorithm}")
    
    def change_sensitivity(self, value: int):
        """Change detection sensitivity."""
        self.sensitivity_value.setText(f"{value}%")
        
        settings = {
            'algorithm': self.algorithm_combo.currentText(),
            'sensitivity': value
        }
        self.detection_settings_changed.emit(settings)
    
    def calibrate_workspace(self):
        """Calibrate workspace for object detection."""
        try:
            # Simulate workspace calibration
            self.results_label.setText("🎯 Calibrating workspace...")
            self.results_label.setStyleSheet(f"""
                background-color: {self.theme.colors.tertiary_background};
                border-radius: 6px;
                padding: 16px;
                color: {self.theme.colors.warning_orange};
            """)
            
            # Reset after 2 seconds
            QTimer.singleShot(2000, self.calibration_complete)
            
            logger.info("Workspace calibration started")
            
        except Exception as e:
            logger.error(f"Failed to calibrate workspace: {e}")
    
    def calibration_complete(self):
        """Handle calibration completion."""
        self.results_label.setText("✅ Workspace calibrated successfully")
        self.results_label.setStyleSheet(f"""
            background-color: {self.theme.colors.tertiary_background};
            border-radius: 6px;
            padding: 16px;
            color: {self.theme.colors.success_green};
        """)
        
        # Reset after 3 seconds
        QTimer.singleShot(3000, lambda: self.results_label.setText("No objects detected"))
    
    def update_camera_feed(self):
        """Update camera feed display."""
        if self.camera_active:
            # Simulate camera feed updates
            # In a real implementation, this would update with actual camera frames
            pass
    
    def update_detection_results(self):
        """Update object detection results."""
        if self.detection_active:
            # Simulate detection results
            import random
            
            if random.random() < 0.3:  # 30% chance of detecting something
                objects = ["Red Circle", "Blue Square", "Green Triangle"]
                detected = random.choice(objects)
                confidence = random.randint(75, 95)
                
                self.results_label.setText(f"🎯 Detected: {detected}\nConfidence: {confidence}%")
                self.results_label.setStyleSheet(f"""
                    background-color: {self.theme.colors.tertiary_background};
                    border-radius: 6px;
                    padding: 16px;
                    color: {self.theme.colors.success_green};
                """)
            else:
                self.results_label.setText("🔍 Scanning for objects...")
                self.results_label.setStyleSheet(f"""
                    background-color: {self.theme.colors.tertiary_background};
                    border-radius: 6px;
                    padding: 16px;
                    color: {self.theme.colors.accent_blue};
                """)
    
    def handle_voice_command(self, command: str, params: dict):
        """Handle voice commands for vision control."""
        if command == "start_camera":
            if not self.camera_active:
                self.start_camera()
        elif command == "stop_camera":
            if self.camera_active:
                self.stop_camera()
        elif command == "enable_detection":
            if self.camera_active and not self.detection_active:
                self.detection_checkbox.setChecked(True)
        elif command == "disable_detection":
            if self.detection_active:
                self.detection_checkbox.setChecked(False)
        elif command == "calibrate_workspace":
            self.calibrate_workspace()
        else:
            logger.warning(f"Unknown vision voice command: {command}")
    
    def is_camera_active(self) -> bool:
        """Check if camera is active."""
        return self.camera_active
    
    def is_detection_active(self) -> bool:
        """Check if object detection is active."""
        return self.detection_active
