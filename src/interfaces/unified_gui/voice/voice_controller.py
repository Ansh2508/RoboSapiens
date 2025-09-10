"""
Voice Controller Integration

Seamless integration of voice commands with the unified GUI,
providing natural language control for robot operations.
"""

import os
import sys
import threading
import time
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# Add src directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    from interfaces.voice_interface import VoiceInterface, VoiceConfig, VoiceLanguage
    VOICE_AVAILABLE = True
except ImportError:
    VOICE_AVAILABLE = False

from utils.logger import get_logger

logger = get_logger(__name__)


class VoiceState(Enum):
    """Voice controller states."""
    INACTIVE = "inactive"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass
class VoiceCommand:
    """Voice command structure."""
    command: str
    confidence: float
    parameters: Dict[str, Any]
    timestamp: float


class VoiceController(QObject):
    """Voice controller for GUI integration."""
    
    # Signals for GUI communication
    state_changed = pyqtSignal(str)
    command_recognized = pyqtSignal(str, dict, float)
    speech_started = pyqtSignal()
    speech_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.voice_interface = None
        self.current_state = VoiceState.INACTIVE
        self.is_enabled = False
        self.session_id = None
        self.command_history = []
        
        # Voice command mappings
        self.command_mappings = self.setup_command_mappings()
        
        # Initialize voice interface if available
        if VOICE_AVAILABLE:
            self.init_voice_interface()
        
        logger.info("Voice controller initialized")
    
    def init_voice_interface(self):
        """Initialize the voice interface."""
        try:
            config = VoiceConfig(
                language=VoiceLanguage.ENGLISH,
                recognition_timeout=5.0,
                phrase_timeout=2.0,
                recognition_threshold=0.7
            )
            self.voice_interface = VoiceInterface(config)
            logger.info("Voice interface initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize voice interface: {e}")
            self.voice_interface = None
    
    def setup_command_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Setup voice command mappings to GUI actions."""
        return {
            # Connection commands
            "connect": {
                "patterns": ["connect", "connect robot", "start connection"],
                "action": "connect",
                "parameters": {}
            },
            "disconnect": {
                "patterns": ["disconnect", "disconnect robot", "stop connection"],
                "action": "disconnect",
                "parameters": {}
            },
            
            # Movement commands
            "home": {
                "patterns": ["go home", "move home", "home position", "return home"],
                "action": "home",
                "parameters": {}
            },
            "calibrate": {
                "patterns": ["calibrate", "calibrate robot", "start calibration"],
                "action": "calibrate",
                "parameters": {}
            },
            "freemove": {
                "patterns": ["free move", "enable free move", "manual mode"],
                "action": "freemove",
                "parameters": {}
            },
            
            # Tool commands
            "open_gripper": {
                "patterns": ["open gripper", "open hand", "release", "let go"],
                "action": "open_gripper",
                "parameters": {}
            },
            "close_gripper": {
                "patterns": ["close gripper", "close hand", "grab", "grasp"],
                "action": "close_gripper",
                "parameters": {}
            },
            "led_on": {
                "patterns": ["turn on led", "led on", "lights on", "illuminate"],
                "action": "led_on",
                "parameters": {}
            },
            "led_off": {
                "patterns": ["turn off led", "led off", "lights off", "turn off lights"],
                "action": "led_off",
                "parameters": {}
            },
            
            # Pattern commands
            "draw_square": {
                "patterns": ["draw square", "make square", "square pattern"],
                "action": "draw_square",
                "parameters": {}
            },
            "draw_circle": {
                "patterns": ["draw circle", "make circle", "circle pattern"],
                "action": "draw_circle",
                "parameters": {}
            },
            
            # Pick and place commands
            "pick": {
                "patterns": ["pick up", "pick object", "grab object", "take object"],
                "action": "pick",
                "parameters": {}
            },
            "place": {
                "patterns": ["place object", "put down", "drop object", "place"],
                "action": "place",
                "parameters": {}
            },
            
            # Emergency commands
            "stop": {
                "patterns": ["stop", "emergency stop", "halt", "freeze"],
                "action": "stop",
                "parameters": {}
            },
            
            # Vision commands
            "start_camera": {
                "patterns": ["start camera", "turn on camera", "enable vision"],
                "action": "start_camera",
                "parameters": {}
            },
            "stop_camera": {
                "patterns": ["stop camera", "turn off camera", "disable vision"],
                "action": "stop_camera",
                "parameters": {}
            },
            
            # Status commands
            "status": {
                "patterns": ["status", "robot status", "what's the status", "how are you"],
                "action": "status",
                "parameters": {}
            }
        }
    
    def start_listening(self):
        """Start voice recognition."""
        if not VOICE_AVAILABLE or not self.voice_interface:
            self.error_occurred.emit("Voice interface not available")
            return False
        
        try:
            if not self.session_id:
                self.session_id = self.voice_interface.start_voice_session("gui_user", VoiceLanguage.ENGLISH)
            
            self.is_enabled = True
            self.set_state(VoiceState.LISTENING)
            
            # Start listening in a separate thread
            self.listening_thread = threading.Thread(target=self._listening_loop, daemon=True)
            self.listening_thread.start()
            
            logger.info("Voice listening started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start voice listening: {e}")
            self.error_occurred.emit(f"Failed to start voice listening: {e}")
            return False
    
    def stop_listening(self):
        """Stop voice recognition."""
        try:
            self.is_enabled = False
            self.set_state(VoiceState.INACTIVE)
            
            if self.session_id and self.voice_interface:
                self.voice_interface.end_voice_session(self.session_id)
                self.session_id = None
            
            logger.info("Voice listening stopped")
            
        except Exception as e:
            logger.error(f"Failed to stop voice listening: {e}")
    
    def _listening_loop(self):
        """Main listening loop running in separate thread."""
        while self.is_enabled and self.voice_interface and self.session_id:
            try:
                self.set_state(VoiceState.LISTENING)
                
                # Process voice command
                success, response = self.voice_interface.process_voice_command(
                    self.session_id, timeout=5.0
                )
                
                if success and response:
                    self.set_state(VoiceState.PROCESSING)
                    self._process_voice_response(response)
                
                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                logger.error(f"Error in listening loop: {e}")
                self.error_occurred.emit(f"Voice recognition error: {e}")
                time.sleep(1.0)  # Wait before retrying
    
    def _process_voice_response(self, response: str):
        """Process voice recognition response."""
        try:
            # Parse the response and match to commands
            command, confidence, parameters = self._parse_voice_command(response)
            
            if command and confidence > 0.7:  # Confidence threshold
                # Add to command history
                voice_command = VoiceCommand(
                    command=command,
                    confidence=confidence,
                    parameters=parameters,
                    timestamp=time.time()
                )
                self.command_history.append(voice_command)
                
                # Emit signal for GUI to handle
                self.command_recognized.emit(command, parameters, confidence)
                
                # Provide voice feedback
                self._provide_voice_feedback(command, parameters)
                
                logger.info(f"Voice command processed: {command} (confidence: {confidence:.2f})")
            else:
                logger.warning(f"Voice command not recognized or low confidence: {response}")
                
        except Exception as e:
            logger.error(f"Failed to process voice response: {e}")
            self.error_occurred.emit(f"Failed to process voice command: {e}")
    
    def _parse_voice_command(self, text: str) -> tuple:
        """Parse voice text into command and parameters."""
        text_lower = text.lower().strip()
        
        # Find matching command
        for command_key, command_info in self.command_mappings.items():
            for pattern in command_info["patterns"]:
                if pattern in text_lower:
                    return (
                        command_info["action"],
                        0.9,  # High confidence for exact pattern match
                        command_info["parameters"].copy()
                    )
        
        # If no exact match, try fuzzy matching
        best_match = None
        best_score = 0.0
        
        for command_key, command_info in self.command_mappings.items():
            for pattern in command_info["patterns"]:
                score = self._calculate_similarity(text_lower, pattern)
                if score > best_score and score > 0.6:  # Minimum similarity threshold
                    best_score = score
                    best_match = command_info
        
        if best_match:
            return (best_match["action"], best_score, best_match["parameters"].copy())
        
        return (None, 0.0, {})
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two text strings."""
        # Simple word-based similarity
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _provide_voice_feedback(self, command: str, parameters: dict):
        """Provide voice feedback for recognized commands."""
        if not self.voice_interface or not self.session_id:
            return
        
        try:
            self.set_state(VoiceState.SPEAKING)
            self.speech_started.emit()
            
            # Generate appropriate feedback message
            feedback_messages = {
                "connect": "Connecting to robot",
                "disconnect": "Disconnecting from robot",
                "home": "Moving to home position",
                "calibrate": "Starting calibration",
                "freemove": "Enabling free move mode",
                "open_gripper": "Opening gripper",
                "close_gripper": "Closing gripper",
                "led_on": "Turning on LED",
                "led_off": "Turning off LED",
                "draw_square": "Drawing square pattern",
                "draw_circle": "Drawing circle pattern",
                "pick": "Picking up object",
                "place": "Placing object",
                "stop": "Emergency stop activated",
                "start_camera": "Starting camera",
                "stop_camera": "Stopping camera",
                "status": "Checking robot status"
            }
            
            message = feedback_messages.get(command, f"Executing {command}")
            
            # Speak the feedback (if TTS is available)
            success = self.voice_interface.speak_text(self.session_id, message)
            
            if success:
                logger.info(f"Voice feedback provided: {message}")
            
            self.speech_finished.emit()
            
        except Exception as e:
            logger.error(f"Failed to provide voice feedback: {e}")
        finally:
            self.set_state(VoiceState.LISTENING)
    
    def set_state(self, state: VoiceState):
        """Set voice controller state."""
        if self.current_state != state:
            self.current_state = state
            self.state_changed.emit(state.value)
    
    def get_state(self) -> VoiceState:
        """Get current voice controller state."""
        return self.current_state
    
    def is_listening(self) -> bool:
        """Check if voice controller is actively listening."""
        return self.current_state == VoiceState.LISTENING
    
    def get_command_history(self) -> List[VoiceCommand]:
        """Get command history."""
        return self.command_history.copy()
    
    def clear_command_history(self):
        """Clear command history."""
        self.command_history.clear()
        logger.info("Voice command history cleared")
    
    def set_language(self, language: VoiceLanguage):
        """Set voice recognition language."""
        if self.voice_interface:
            try:
                # Restart session with new language
                if self.session_id:
                    self.voice_interface.end_voice_session(self.session_id)
                
                self.session_id = self.voice_interface.start_voice_session("gui_user", language)
                logger.info(f"Voice language changed to {language.value}")
                
            except Exception as e:
                logger.error(f"Failed to change voice language: {e}")
                self.error_occurred.emit(f"Failed to change language: {e}")
    
    def test_voice_recognition(self) -> bool:
        """Test voice recognition functionality."""
        if not VOICE_AVAILABLE or not self.voice_interface:
            return False
        
        try:
            # Quick test of voice interface
            test_session = self.voice_interface.start_voice_session("test_user", VoiceLanguage.ENGLISH)
            self.voice_interface.end_voice_session(test_session)
            logger.info("Voice recognition test passed")
            return True
            
        except Exception as e:
            logger.error(f"Voice recognition test failed: {e}")
            return False
