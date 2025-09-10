"""
Professional Voice Control Panel

Clean, professional voice interface without emojis,
with proper typography and organized layout.
"""

import os
import sys
from typing import Dict, Any, Optional, List
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox,
    QLabel, QPushButton, QTextEdit, QListWidget, QListWidgetItem,
    QProgressBar, QFrame, QSizePolicy, QScrollArea, QSlider
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


class ProfessionalVoiceControlPanel(QWidget):
    """Professional voice control panel with clean design and proper typography."""
    
    # Signals for voice control
    voice_command_received = pyqtSignal(str, dict)
    voice_status_changed = pyqtSignal(bool)
    
    def __init__(self, theme: AppleTheme):
        super().__init__()
        self.theme = theme
        self.voice_controller = None
        self.is_listening = False
        self.is_voice_active = False
        self.command_history = []
        self.current_breakpoint = "desktop"
        
        # Set responsive size policy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.init_ui()
        self.setup_connections()
        
        logger.info("Professional voice control panel initialized")
    
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
        
        # Voice control section
        voice_group = self.create_voice_control_section()
        layout.addWidget(voice_group)
        
        # Command feedback section
        feedback_group = self.create_feedback_section()
        layout.addWidget(feedback_group)
        
        # Command history section
        history_group = self.create_history_section()
        layout.addWidget(history_group)
        
        # Voice settings section
        settings_group = self.create_settings_section()
        layout.addWidget(settings_group)
        
        # Add stretch to push content to top
        layout.addStretch()
    
    def create_voice_control_section(self) -> QGroupBox:
        """Create professional voice control section."""
        group = QGroupBox("Voice Control")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Voice status
        status_layout = QHBoxLayout()
        status_label = QLabel("Status:")
        status_label.setObjectName("section-label")
        self.voice_status = QLabel("Inactive")
        self.voice_status.setObjectName("status-value")
        
        status_layout.addWidget(status_label)
        status_layout.addWidget(self.voice_status)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # Voice controls
        controls_layout = QHBoxLayout()
        
        self.start_voice_btn = QPushButton("Start Voice Control")
        self.start_voice_btn.setObjectName("primary-button")
        self.start_voice_btn.clicked.connect(self.start_voice_control)
        
        self.stop_voice_btn = QPushButton("Stop Voice Control")
        self.stop_voice_btn.setObjectName("secondary-button")
        self.stop_voice_btn.clicked.connect(self.stop_voice_control)
        self.stop_voice_btn.setEnabled(False)
        
        controls_layout.addWidget(self.start_voice_btn)
        controls_layout.addWidget(self.stop_voice_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        # Listening indicator
        listening_layout = QHBoxLayout()
        listening_label = QLabel("Listening:")
        listening_label.setObjectName("section-label")
        self.listening_status = QLabel("Not Listening")
        self.listening_status.setObjectName("status-value")
        
        listening_layout.addWidget(listening_label)
        listening_layout.addWidget(self.listening_status)
        listening_layout.addStretch()
        
        layout.addLayout(listening_layout)
        
        return group
    
    def create_feedback_section(self) -> QGroupBox:
        """Create command feedback section."""
        group = QGroupBox("Voice Feedback")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Last command
        last_cmd_layout = QHBoxLayout()
        last_cmd_label = QLabel("Last Command:")
        last_cmd_label.setObjectName("section-label")
        self.last_command = QLabel("None")
        self.last_command.setObjectName("command-value")
        
        last_cmd_layout.addWidget(last_cmd_label)
        last_cmd_layout.addWidget(self.last_command)
        last_cmd_layout.addStretch()
        
        layout.addLayout(last_cmd_layout)
        
        # Command confidence
        confidence_layout = QHBoxLayout()
        confidence_label = QLabel("Confidence:")
        confidence_label.setObjectName("section-label")
        self.confidence_bar = QProgressBar()
        self.confidence_bar.setObjectName("confidence-bar")
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setValue(0)
        self.confidence_bar.setTextVisible(True)
        
        confidence_layout.addWidget(confidence_label)
        confidence_layout.addWidget(self.confidence_bar)
        
        layout.addLayout(confidence_layout)
        
        # Recognition status
        recognition_layout = QHBoxLayout()
        recognition_label = QLabel("Recognition:")
        recognition_label.setObjectName("section-label")
        self.recognition_status = QLabel("Ready")
        self.recognition_status.setObjectName("status-value")
        
        recognition_layout.addWidget(recognition_label)
        recognition_layout.addWidget(self.recognition_status)
        recognition_layout.addStretch()
        
        layout.addLayout(recognition_layout)
        
        return group
    
    def create_history_section(self) -> QGroupBox:
        """Create command history section."""
        group = QGroupBox("Command History")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # History controls
        history_controls = QHBoxLayout()
        
        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.setObjectName("secondary-button")
        self.clear_history_btn.clicked.connect(self.clear_command_history)
        
        history_controls.addWidget(self.clear_history_btn)
        history_controls.addStretch()
        
        layout.addLayout(history_controls)
        
        # Command history list
        self.history_list = QListWidget()
        self.history_list.setObjectName("history-list")
        self.history_list.setMaximumHeight(200)
        layout.addWidget(self.history_list)
        
        return group
    
    def create_settings_section(self) -> QGroupBox:
        """Create voice settings section."""
        group = QGroupBox("Voice Settings")
        group.setObjectName("control-group")
        
        layout = QVBoxLayout(group)
        layout.setSpacing(16)
        
        # Microphone sensitivity
        sensitivity_layout = QHBoxLayout()
        sensitivity_label = QLabel("Microphone Sensitivity:")
        sensitivity_label.setObjectName("section-label")
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setObjectName("setting-slider")
        self.sensitivity_slider.setRange(1, 10)
        self.sensitivity_slider.setValue(5)
        self.sensitivity_value = QLabel("5")
        self.sensitivity_value.setObjectName("slider-value")
        
        self.sensitivity_slider.valueChanged.connect(
            lambda v: self.sensitivity_value.setText(str(v))
        )
        
        sensitivity_layout.addWidget(sensitivity_label)
        sensitivity_layout.addWidget(self.sensitivity_slider)
        sensitivity_layout.addWidget(self.sensitivity_value)
        
        layout.addLayout(sensitivity_layout)
        
        # Voice timeout
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Command Timeout (seconds):")
        timeout_label.setObjectName("section-label")
        self.timeout_slider = QSlider(Qt.Horizontal)
        self.timeout_slider.setObjectName("setting-slider")
        self.timeout_slider.setRange(1, 10)
        self.timeout_slider.setValue(3)
        self.timeout_value = QLabel("3")
        self.timeout_value.setObjectName("slider-value")
        
        self.timeout_slider.valueChanged.connect(
            lambda v: self.timeout_value.setText(str(v))
        )
        
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_slider)
        timeout_layout.addWidget(self.timeout_value)
        
        layout.addLayout(timeout_layout)
        
        # Available commands info
        commands_label = QLabel("Available Commands:")
        commands_label.setObjectName("section-label")
        layout.addWidget(commands_label)
        
        commands_text = QTextEdit()
        commands_text.setObjectName("commands-text")
        commands_text.setMaximumHeight(120)
        commands_text.setReadOnly(True)
        commands_text.setPlainText(
            "• Connect / Disconnect\n"
            "• Home / Calibrate\n"
            "• Open gripper / Close gripper\n"
            "• LED on / LED off\n"
            "• Draw square / Draw circle\n"
            "• Pick object / Place object\n"
            "• Emergency stop"
        )
        layout.addWidget(commands_text)
        
        return group

    def setup_connections(self):
        """Setup signal connections and timers."""
        # Setup listening status update timer
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_listening_status)
        self.status_timer.start(500)  # Update every 500ms

    # Voice Control Methods

    def start_voice_control(self):
        """Start voice control system."""
        try:
            self.is_voice_active = True
            self.voice_status.setText("Active")
            self.voice_status.setStyleSheet("color: #34C759;")  # Green

            self.start_voice_btn.setEnabled(False)
            self.stop_voice_btn.setEnabled(True)

            self.voice_status_changed.emit(True)
            logger.info("Voice control started")

            # Add to history
            self.add_to_history("Voice control started", "System")

        except Exception as e:
            logger.error(f"Failed to start voice control: {e}")
            self.voice_status.setText("Error")
            self.voice_status.setStyleSheet("color: #FF3B30;")  # Red

    def stop_voice_control(self):
        """Stop voice control system."""
        try:
            self.is_voice_active = False
            self.is_listening = False

            self.voice_status.setText("Inactive")
            self.voice_status.setStyleSheet("color: #FF3B30;")  # Red
            self.listening_status.setText("Not Listening")
            self.listening_status.setStyleSheet("color: #8E8E93;")  # Gray

            self.start_voice_btn.setEnabled(True)
            self.stop_voice_btn.setEnabled(False)

            self.voice_status_changed.emit(False)
            logger.info("Voice control stopped")

            # Add to history
            self.add_to_history("Voice control stopped", "System")

        except Exception as e:
            logger.error(f"Failed to stop voice control: {e}")

    def process_voice_command(self, command: str, confidence: float = 0.0):
        """Process a recognized voice command."""
        try:
            # Update UI
            self.last_command.setText(command)
            self.confidence_bar.setValue(int(confidence * 100))

            # Update recognition status
            if confidence > 0.8:
                self.recognition_status.setText("Excellent")
                self.recognition_status.setStyleSheet("color: #34C759;")  # Green
            elif confidence > 0.6:
                self.recognition_status.setText("Good")
                self.recognition_status.setStyleSheet("color: #FF9500;")  # Orange
            else:
                self.recognition_status.setText("Poor")
                self.recognition_status.setStyleSheet("color: #FF3B30;")  # Red

            # Add to history
            self.add_to_history(command, f"Voice ({confidence:.1%})")

            # Parse and emit command
            parsed_command = self.parse_voice_command(command)
            if parsed_command:
                self.voice_command_received.emit(parsed_command['action'], parsed_command['params'])
                logger.info(f"Voice command processed: {command} -> {parsed_command}")
            else:
                logger.warning(f"Could not parse voice command: {command}")
                self.recognition_status.setText("Unknown Command")
                self.recognition_status.setStyleSheet("color: #FF3B30;")  # Red

        except Exception as e:
            logger.error(f"Failed to process voice command: {e}")

    def parse_voice_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Parse voice command into action and parameters."""
        command = command.lower().strip()

        # Command mapping
        command_map = {
            # Connection commands
            "connect": {"action": "connect", "params": {}},
            "disconnect": {"action": "disconnect", "params": {}},

            # Movement commands
            "home": {"action": "home", "params": {}},
            "calibrate": {"action": "calibrate", "params": {}},
            "free move": {"action": "freemove", "params": {}},

            # Gripper commands
            "open gripper": {"action": "open_gripper", "params": {}},
            "close gripper": {"action": "close_gripper", "params": {}},
            "gripper open": {"action": "open_gripper", "params": {}},
            "gripper close": {"action": "close_gripper", "params": {}},

            # LED commands
            "led on": {"action": "led_on", "params": {}},
            "led off": {"action": "led_off", "params": {}},
            "turn on led": {"action": "led_on", "params": {}},
            "turn off led": {"action": "led_off", "params": {}},

            # Pattern commands
            "draw square": {"action": "draw_square", "params": {}},
            "draw circle": {"action": "draw_circle", "params": {}},
            "make square": {"action": "draw_square", "params": {}},
            "make circle": {"action": "draw_circle", "params": {}},

            # Object manipulation
            "pick object": {"action": "pick", "params": {}},
            "place object": {"action": "place", "params": {}},
            "pick up": {"action": "pick", "params": {}},
            "put down": {"action": "place", "params": {}},

            # Emergency
            "stop": {"action": "stop", "params": {}},
            "emergency stop": {"action": "stop", "params": {}},
            "halt": {"action": "stop", "params": {}},
        }

        # Direct match
        if command in command_map:
            return command_map[command]

        # Partial matches
        for key, value in command_map.items():
            if key in command or command in key:
                return value

        return None

    def add_to_history(self, command: str, source: str):
        """Add command to history list."""
        try:
            # Create history item
            item_text = f"[{source}] {command}"
            item = QListWidgetItem(item_text)

            # Add to list (newest at top)
            self.history_list.insertItem(0, item)

            # Limit history size
            while self.history_list.count() > 50:
                self.history_list.takeItem(self.history_list.count() - 1)

            # Add to internal history
            self.command_history.insert(0, {
                'command': command,
                'source': source,
                'timestamp': self.get_timestamp()
            })

            # Limit internal history
            if len(self.command_history) > 50:
                self.command_history = self.command_history[:50]

        except Exception as e:
            logger.error(f"Failed to add command to history: {e}")

    def clear_command_history(self):
        """Clear command history."""
        try:
            self.history_list.clear()
            self.command_history.clear()
            logger.info("Command history cleared")
        except Exception as e:
            logger.error(f"Failed to clear command history: {e}")

    def update_listening_status(self):
        """Update listening status indicator."""
        if self.is_voice_active:
            # Simulate listening detection (in real implementation, this would check microphone)
            if self.is_listening:
                self.listening_status.setText("Listening...")
                self.listening_status.setStyleSheet("color: #34C759;")  # Green
            else:
                self.listening_status.setText("Ready")
                self.listening_status.setStyleSheet("color: #007AFF;")  # Blue
        else:
            self.listening_status.setText("Not Listening")
            self.listening_status.setStyleSheet("color: #8E8E93;")  # Gray

    def get_timestamp(self) -> str:
        """Get current timestamp string."""
        from datetime import datetime
        return datetime.now().strftime("%H:%M:%S")

    # Status Update Methods

    def update_voice_status(self, active: bool):
        """Update voice control status."""
        if active and not self.is_voice_active:
            self.start_voice_control()
        elif not active and self.is_voice_active:
            self.stop_voice_control()

    def set_listening_state(self, listening: bool):
        """Set listening state."""
        self.is_listening = listening

    # Responsive Design Methods

    def update_breakpoint(self, breakpoint: str):
        """Update panel layout based on responsive breakpoint."""
        self.current_breakpoint = breakpoint
        self.update_responsive_layout()

    def update_responsive_layout(self):
        """Update layout based on current breakpoint."""
        # Professional layout remains consistent across breakpoints
        # Only adjust spacing and component sizes
        if self.current_breakpoint == "mobile":
            self.setStyleSheet(self.get_mobile_stylesheet())
        elif self.current_breakpoint == "tablet":
            self.setStyleSheet(self.get_tablet_stylesheet())
        else:
            self.setStyleSheet(self.get_desktop_stylesheet())

    def get_mobile_stylesheet(self) -> str:
        """Get mobile-optimized stylesheet."""
        return """
        QPushButton {
            min-height: 44px;
            font-size: 14px;
            padding: 10px 16px;
        }
        QSlider {
            min-height: 44px;
        }
        """

    def get_tablet_stylesheet(self) -> str:
        """Get tablet-optimized stylesheet."""
        return """
        QPushButton {
            min-height: 40px;
            font-size: 15px;
            padding: 8px 16px;
        }
        QSlider {
            min-height: 40px;
        }
        """

    def get_desktop_stylesheet(self) -> str:
        """Get desktop-optimized stylesheet."""
        return """
        QPushButton {
            min-height: 36px;
            font-size: 14px;
            padding: 8px 16px;
        }
        QSlider {
            min-height: 36px;
        }
        """

    def resizeEvent(self, event: QResizeEvent):
        """Handle resize events for responsive behavior."""
        super().resizeEvent(event)

        # Update layout based on new size
        width = event.size().width()
        if width < 400:
            self.current_breakpoint = "mobile"
        elif width < 600:
            self.current_breakpoint = "tablet"
        else:
            self.current_breakpoint = "desktop"

        self.update_responsive_layout()
