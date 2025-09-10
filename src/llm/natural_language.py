"""
Natural Language Interface Implementation

Voice and text command processing with conversational capabilities,
context-aware dialogue management, and multilingual support.

Features:
- Voice command processing with speech-to-text integration
- Text-based command interface with conversational capabilities
- Context-aware dialogue management for multi-turn conversations
- Command disambiguation and clarification request systems
- Multilingual support for international educational deployment
"""

import re
import time
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    logging.warning("Speech recognition not available. Install with: pip install SpeechRecognition")

from llm.llm_interface import LLMInterface, LLMConfig, LLMProvider
from llm.output_parser import OutputParser, RobotCommand, TaskPlan
from llm.safety_validator import SafetyValidator
from utils.logger import get_logger

logger = get_logger(__name__)


class ConversationState(Enum):
    """Conversation states."""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    WAITING_CLARIFICATION = "waiting_clarification"
    WAITING_APPROVAL = "waiting_approval"
    EXECUTING = "executing"
    ERROR = "error"


class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    GERMAN = "de"
    CZECH = "cs"
    SPANISH = "es"
    FRENCH = "fr"


class CommandIntent(Enum):
    """Command intents."""
    MOVE_ROBOT = "move_robot"
    PICK_OBJECT = "pick_object"
    PLACE_OBJECT = "place_object"
    START_CONVEYOR = "start_conveyor"
    STOP_CONVEYOR = "stop_conveyor"
    TAKE_PHOTO = "take_photo"
    EXECUTE_WORKFLOW = "execute_workflow"
    GET_STATUS = "get_status"
    EMERGENCY_STOP = "emergency_stop"
    HELP = "help"
    UNCLEAR = "unclear"


@dataclass
class ConversationContext:
    """Context for ongoing conversation."""
    session_id: str
    user_id: str
    language: Language = Language.ENGLISH
    
    # Conversation history
    messages: List[Dict[str, str]] = field(default_factory=list)
    last_command: Optional[RobotCommand] = None
    last_plan: Optional[TaskPlan] = None
    
    # State tracking
    state: ConversationState = ConversationState.IDLE
    current_intent: Optional[CommandIntent] = None
    pending_clarifications: List[str] = field(default_factory=list)
    
    # Context variables
    mentioned_objects: List[str] = field(default_factory=list)
    mentioned_positions: List[Dict[str, float]] = field(default_factory=list)
    mentioned_speeds: List[float] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)


class CommandProcessor:
    """
    Processes natural language commands and converts them to robot actions
    with context awareness and clarification capabilities.
    """
    
    def __init__(self, llm_interface: LLMInterface, safety_validator: SafetyValidator):
        """
        Initialize command processor.
        
        Args:
            llm_interface: LLM interface for processing
            safety_validator: Safety validator for command validation
        """
        self.llm_interface = llm_interface
        self.safety_validator = safety_validator
        self.output_parser = OutputParser()
        
        # Processing statistics
        self.processing_stats = {
            'total_commands': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'clarifications_requested': 0,
            'safety_violations': 0
        }
        
        logger.info("Command processor initialized")
    
    def process_command(self, text: str, context: ConversationContext) -> Tuple[Optional[RobotCommand], str]:
        """
        Process a natural language command.
        
        Args:
            text: Natural language command text
            context: Conversation context
            
        Returns:
            Tuple of (robot_command, response_message)
        """
        self.processing_stats['total_commands'] += 1
        context.last_activity = datetime.now()
        
        try:
            # Add to conversation history
            context.messages.append({
                'role': 'user',
                'content': text,
                'timestamp': datetime.now().isoformat()
            })
            
            # Detect intent
            intent = self._detect_intent(text, context)
            context.current_intent = intent
            
            # Handle special intents
            if intent == CommandIntent.HELP:
                return None, self._get_help_message(context.language)
            elif intent == CommandIntent.GET_STATUS:
                return None, self._get_status_message()
            elif intent == CommandIntent.EMERGENCY_STOP:
                self.safety_validator.emergency_stop("User emergency stop command")
                return None, "Emergency stop activated!"
            
            # Process robot command
            if intent in [CommandIntent.MOVE_ROBOT, CommandIntent.PICK_OBJECT, 
                         CommandIntent.PLACE_OBJECT, CommandIntent.START_CONVEYOR,
                         CommandIntent.STOP_CONVEYOR, CommandIntent.TAKE_PHOTO]:
                
                return self._process_robot_command(text, context)
            
            elif intent == CommandIntent.EXECUTE_WORKFLOW:
                return self._process_workflow_command(text, context)
            
            elif intent == CommandIntent.UNCLEAR:
                self.processing_stats['clarifications_requested'] += 1
                return None, self._request_clarification(text, context)
            
            else:
                return None, "I'm not sure how to help with that. Try saying 'help' for available commands."
        
        except Exception as e:
            self.processing_stats['failed_commands'] += 1
            logger.error(f"Error processing command: {e}")
            return None, f"Sorry, I encountered an error processing your command: {str(e)}"
    
    def _detect_intent(self, text: str, context: ConversationContext) -> CommandIntent:
        """Detect the intent of a natural language command."""
        text_lower = text.lower()
        
        # Emergency stop (highest priority)
        if any(word in text_lower for word in ['emergency', 'stop', 'halt', 'abort']):
            return CommandIntent.EMERGENCY_STOP
        
        # Help requests
        if any(word in text_lower for word in ['help', 'what can', 'how do', 'commands']):
            return CommandIntent.HELP
        
        # Status requests
        if any(word in text_lower for word in ['status', 'state', 'what is', 'where is']):
            return CommandIntent.GET_STATUS
        
        # Movement commands
        if any(word in text_lower for word in ['move', 'go', 'navigate', 'position']):
            return CommandIntent.MOVE_ROBOT
        
        # Pick commands
        if any(word in text_lower for word in ['pick', 'grab', 'grasp', 'take']):
            return CommandIntent.PICK_OBJECT
        
        # Place commands
        if any(word in text_lower for word in ['place', 'put', 'drop', 'set']):
            return CommandIntent.PLACE_OBJECT
        
        # Conveyor commands
        if 'conveyor' in text_lower or 'belt' in text_lower:
            if any(word in text_lower for word in ['start', 'begin', 'run']):
                return CommandIntent.START_CONVEYOR
            elif any(word in text_lower for word in ['stop', 'halt', 'end']):
                return CommandIntent.STOP_CONVEYOR
        
        # Vision commands
        if any(word in text_lower for word in ['photo', 'picture', 'image', 'capture', 'see']):
            return CommandIntent.TAKE_PHOTO
        
        # Workflow commands
        if any(word in text_lower for word in ['workflow', 'sequence', 'routine', 'process']):
            return CommandIntent.EXECUTE_WORKFLOW
        
        return CommandIntent.UNCLEAR
    
    def _process_robot_command(self, text: str, context: ConversationContext) -> Tuple[Optional[RobotCommand], str]:
        """Process a robot command using LLM."""
        try:
            # Create prompt for LLM
            prompt = self._create_command_prompt(text, context)
            
            # Get LLM response
            messages = [{"role": "user", "content": prompt}]
            llm_response = self.llm_interface.complete_sync(messages)
            
            # Parse response into robot command
            robot_command = self.output_parser.parse_robot_command(llm_response.content)
            
            # Validate safety
            safety_validation = self.safety_validator.validate_command(robot_command)
            
            if not safety_validation.is_safe:
                self.processing_stats['safety_violations'] += 1
                return None, f"Safety violation: {'; '.join(safety_validation.errors)}"
            
            # Check if approval required
            if safety_validation.requires_approval:
                approval_id = self.safety_validator.request_approval(robot_command, safety_validation)
                context.state = ConversationState.WAITING_APPROVAL
                return None, f"Command requires approval (ID: {approval_id}). Please wait for approval."
            
            # Store in context
            context.last_command = robot_command
            context.state = ConversationState.EXECUTING
            
            self.processing_stats['successful_commands'] += 1
            return robot_command, "Command processed successfully. Executing..."
            
        except Exception as e:
            logger.error(f"Error processing robot command: {e}")
            return None, f"Error processing command: {str(e)}"
    
    def _process_workflow_command(self, text: str, context: ConversationContext) -> Tuple[Optional[TaskPlan], str]:
        """Process a workflow command using LLM."""
        try:
            # Create prompt for workflow generation
            prompt = self._create_workflow_prompt(text, context)
            
            # Get LLM response
            messages = [{"role": "user", "content": prompt}]
            llm_response = self.llm_interface.complete_sync(messages)
            
            # Parse response into task plan
            task_plan = self.output_parser.parse_task_plan(llm_response.content)
            
            # Validate safety
            safety_validation = self.safety_validator.validate_task_plan(task_plan)
            
            if not safety_validation.is_safe:
                self.processing_stats['safety_violations'] += 1
                return None, f"Safety violation: {'; '.join(safety_validation.errors)}"
            
            # Check if approval required
            if safety_validation.requires_approval:
                approval_id = self.safety_validator.request_approval(task_plan, safety_validation)
                context.state = ConversationState.WAITING_APPROVAL
                return None, f"Workflow requires approval (ID: {approval_id}). Please wait for approval."
            
            # Store in context
            context.last_plan = task_plan
            context.state = ConversationState.EXECUTING
            
            self.processing_stats['successful_commands'] += 1
            return task_plan, f"Workflow '{task_plan.name}' processed successfully. Executing {len(task_plan.steps)} steps..."
            
        except Exception as e:
            logger.error(f"Error processing workflow command: {e}")
            return None, f"Error processing workflow: {str(e)}"
    
    def _create_command_prompt(self, text: str, context: ConversationContext) -> str:
        """Create prompt for robot command generation."""
        base_prompt = f"""
Convert the following natural language command into a structured robot command.

User command: "{text}"

Context:
- Current language: {context.language.value}
- Previous commands: {len(context.messages)} messages
- Available robot capabilities: move, pick, place, rotate, wait, conveyor control, vision

Please respond with a JSON object containing:
{{
    "command_type": "move|pick|place|rotate|wait|conveyor_start|conveyor_stop|vision_capture",
    "position": {{"x": float, "y": float, "z": float}} (if applicable),
    "orientation": {{"roll": float, "pitch": float, "yaw": float}} (if applicable),
    "parameters": {{}} (additional parameters),
    "speed": float (1-100),
    "precision": float (0.1-10.0)
}}

Safety constraints:
- Workspace limits: X: ±800mm, Y: ±800mm, Z: -100 to 400mm
- Maximum speed: 80%
- Always include safety_check: true
"""
        
        # Add context from previous messages
        if context.messages:
            recent_messages = context.messages[-3:]  # Last 3 messages for context
            base_prompt += "\n\nRecent conversation:\n"
            for msg in recent_messages:
                base_prompt += f"- {msg['role']}: {msg['content']}\n"
        
        return base_prompt
    
    def _create_workflow_prompt(self, text: str, context: ConversationContext) -> str:
        """Create prompt for workflow generation."""
        base_prompt = f"""
Convert the following natural language description into a structured task plan/workflow.

User request: "{text}"

Please respond with a JSON object containing:
{{
    "task_id": "unique_id",
    "name": "workflow_name",
    "description": "workflow_description",
    "steps": [
        {{
            "step_id": 1,
            "description": "step_description",
            "command": {{
                "command_type": "move|pick|place|rotate|wait|conveyor_start|conveyor_stop",
                "position": {{"x": float, "y": float, "z": float}} (if applicable),
                "parameters": {{}},
                "speed": float
            }},
            "estimated_duration": float
        }}
    ],
    "priority": "low|normal|high|critical"
}}

Available commands: move, pick, place, rotate, wait, conveyor_start, conveyor_stop, vision_capture
Safety constraints apply to all commands.
"""
        return base_prompt
    
    def _request_clarification(self, text: str, context: ConversationContext) -> str:
        """Request clarification for unclear commands."""
        context.state = ConversationState.WAITING_CLARIFICATION
        
        clarifications = [
            "Could you please be more specific about what you'd like the robot to do?",
            "I need more details. What specific action should the robot perform?",
            "Can you clarify your request? For example: 'move to position X=100, Y=200' or 'pick up the red object'",
            "I'm not sure what you mean. Try commands like 'move robot', 'start conveyor', or 'take a photo'."
        ]
        
        # Choose clarification based on context
        return clarifications[len(context.pending_clarifications) % len(clarifications)]
    
    def _get_help_message(self, language: Language) -> str:
        """Get help message in specified language."""
        help_messages = {
            Language.ENGLISH: """
Available commands:
• Move robot: "Move to X=100, Y=200, Z=50"
• Pick object: "Pick up the red cube"
• Place object: "Place the object at X=200, Y=100"
• Conveyor: "Start conveyor at 50 mm/s" or "Stop conveyor"
• Vision: "Take a photo" or "Capture image"
• Workflow: "Execute pick and place routine"
• Status: "What is the robot status?"
• Emergency: "Emergency stop"

You can speak naturally - I'll understand your intent!
""",
            Language.GERMAN: """
Verfügbare Befehle:
• Roboter bewegen: "Bewege zu X=100, Y=200, Z=50"
• Objekt greifen: "Nimm den roten Würfel"
• Objekt platzieren: "Platziere das Objekt bei X=200, Y=100"
• Förderband: "Starte Förderband mit 50 mm/s" oder "Stoppe Förderband"
• Vision: "Mache ein Foto"
• Workflow: "Führe Pick-and-Place-Routine aus"
• Status: "Wie ist der Roboterstatus?"
• Notfall: "Notstopp"
""",
            Language.CZECH: """
Dostupné příkazy:
• Pohyb robota: "Přesuň na X=100, Y=200, Z=50"
• Uchopení objektu: "Vezmi červenou kostku"
• Umístění objektu: "Umísti objekt na X=200, Y=100"
• Dopravník: "Spusť dopravník na 50 mm/s" nebo "Zastav dopravník"
• Vize: "Vyfoť" nebo "Zachyť obraz"
• Workflow: "Proveď pick-and-place rutinu"
• Status: "Jaký je stav robota?"
• Nouzové: "Nouzové zastavení"
"""
        }
        
        return help_messages.get(language, help_messages[Language.ENGLISH])
    
    def _get_status_message(self) -> str:
        """Get current system status message."""
        stats = self.safety_validator.get_validation_stats()
        
        status_parts = [
            f"System Status:",
            f"• Emergency stop: {'ACTIVE' if stats['emergency_stop_active'] else 'Inactive'}",
            f"• Pending approvals: {stats['pending_approvals']}",
            f"• Commands processed: {self.processing_stats['total_commands']}",
            f"• Success rate: {(self.processing_stats['successful_commands'] / max(1, self.processing_stats['total_commands']) * 100):.1f}%"
        ]
        
        return "\n".join(status_parts)
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get command processing statistics."""
        return self.processing_stats.copy()


class ConversationManager:
    """
    Manages multi-turn conversations with context awareness and
    session management for natural language robot interaction.
    """

    def __init__(self, llm_interface: LLMInterface, safety_validator: SafetyValidator):
        """
        Initialize conversation manager.

        Args:
            llm_interface: LLM interface for processing
            safety_validator: Safety validator for command validation
        """
        self.command_processor = CommandProcessor(llm_interface, safety_validator)
        self.active_contexts: Dict[str, ConversationContext] = {}

        # Session management
        self.session_timeout = 1800  # 30 minutes
        self.max_sessions = 10

        logger.info("Conversation manager initialized")

    def start_conversation(self, user_id: str, language: Language = Language.ENGLISH) -> str:
        """
        Start a new conversation session.

        Args:
            user_id: User identifier
            language: Conversation language

        Returns:
            Session ID
        """
        session_id = f"session_{user_id}_{int(time.time())}"

        context = ConversationContext(
            session_id=session_id,
            user_id=user_id,
            language=language
        )

        # Clean up old sessions if needed
        self._cleanup_expired_sessions()

        # Limit active sessions
        if len(self.active_contexts) >= self.max_sessions:
            oldest_session = min(self.active_contexts.keys(),
                               key=lambda k: self.active_contexts[k].last_activity)
            del self.active_contexts[oldest_session]
            logger.info(f"Removed oldest session: {oldest_session}")

        self.active_contexts[session_id] = context
        logger.info(f"Started conversation session: {session_id} for user: {user_id}")

        return session_id

    def process_message(self, session_id: str, message: str) -> Tuple[Optional[Any], str]:
        """
        Process a message in an existing conversation.

        Args:
            session_id: Session identifier
            message: User message

        Returns:
            Tuple of (command/plan, response_message)
        """
        if session_id not in self.active_contexts:
            return None, "Session not found. Please start a new conversation."

        context = self.active_contexts[session_id]

        # Check session timeout
        if self._is_session_expired(context):
            del self.active_contexts[session_id]
            return None, "Session expired. Please start a new conversation."

        # Process the command
        result, response = self.command_processor.process_command(message, context)

        # Add response to conversation history
        context.messages.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })

        return result, response

    def get_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Get conversation history for a session."""
        if session_id not in self.active_contexts:
            return []

        return self.active_contexts[session_id].messages.copy()

    def end_conversation(self, session_id: str) -> bool:
        """
        End a conversation session.

        Args:
            session_id: Session identifier

        Returns:
            True if session ended successfully
        """
        if session_id in self.active_contexts:
            del self.active_contexts[session_id]
            logger.info(f"Ended conversation session: {session_id}")
            return True
        return False

    def _cleanup_expired_sessions(self) -> None:
        """Clean up expired conversation sessions."""
        current_time = datetime.now()
        expired_sessions = []

        for session_id, context in self.active_contexts.items():
            if (current_time - context.last_activity).total_seconds() > self.session_timeout:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            del self.active_contexts[session_id]
            logger.info(f"Cleaned up expired session: {session_id}")

    def _is_session_expired(self, context: ConversationContext) -> bool:
        """Check if a session has expired."""
        return (datetime.now() - context.last_activity).total_seconds() > self.session_timeout

    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        self._cleanup_expired_sessions()
        return list(self.active_contexts.keys())


class VoiceInterface:
    """
    Voice command interface with speech-to-text integration
    for hands-free robot control.
    """

    def __init__(self, conversation_manager: ConversationManager):
        """
        Initialize voice interface.

        Args:
            conversation_manager: Conversation manager for processing
        """
        self.conversation_manager = conversation_manager
        self.is_listening = False
        self.recognition_language = "en-US"

        # Initialize speech recognition if available
        if SPEECH_RECOGNITION_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()

            # Adjust for ambient noise
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source)

            logger.info("Voice interface initialized with speech recognition")
        else:
            self.recognizer = None
            self.microphone = None
            logger.warning("Voice interface initialized without speech recognition")

        # Voice processing statistics
        self.voice_stats = {
            'total_voice_commands': 0,
            'successful_recognitions': 0,
            'failed_recognitions': 0,
            'processing_errors': 0
        }

    def start_listening(self, session_id: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """
        Start listening for voice commands.

        Args:
            session_id: Conversation session ID
            timeout: Listening timeout in seconds

        Returns:
            Tuple of (success, message/result)
        """
        if not SPEECH_RECOGNITION_AVAILABLE:
            return False, "Speech recognition not available"

        if self.is_listening:
            return False, "Already listening"

        self.voice_stats['total_voice_commands'] += 1
        self.is_listening = True

        try:
            logger.info("Listening for voice command...")

            # Listen for audio
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=5)

            # Recognize speech
            try:
                text = self.recognizer.recognize_google(audio, language=self.recognition_language)
                logger.info(f"Recognized speech: {text}")

                self.voice_stats['successful_recognitions'] += 1

                # Process the command
                result, response = self.conversation_manager.process_message(session_id, text)

                return True, f"Heard: '{text}' - {response}"

            except sr.UnknownValueError:
                self.voice_stats['failed_recognitions'] += 1
                return False, "Could not understand audio"

            except sr.RequestError as e:
                self.voice_stats['failed_recognitions'] += 1
                return False, f"Speech recognition error: {e}"

        except Exception as e:
            self.voice_stats['processing_errors'] += 1
            logger.error(f"Voice processing error: {e}")
            return False, f"Voice processing error: {e}"

        finally:
            self.is_listening = False

    def set_language(self, language: Language) -> None:
        """
        Set recognition language.

        Args:
            language: Language to use for recognition
        """
        language_codes = {
            Language.ENGLISH: "en-US",
            Language.GERMAN: "de-DE",
            Language.CZECH: "cs-CZ",
            Language.SPANISH: "es-ES",
            Language.FRENCH: "fr-FR"
        }

        self.recognition_language = language_codes.get(language, "en-US")
        logger.info(f"Voice recognition language set to: {self.recognition_language}")

    def get_voice_stats(self) -> Dict[str, Any]:
        """Get voice processing statistics."""
        stats = self.voice_stats.copy()

        if stats['total_voice_commands'] > 0:
            stats['recognition_rate'] = stats['successful_recognitions'] / stats['total_voice_commands']
        else:
            stats['recognition_rate'] = 0.0

        stats['is_listening'] = self.is_listening
        stats['recognition_language'] = self.recognition_language
        stats['speech_recognition_available'] = SPEECH_RECOGNITION_AVAILABLE

        return stats


class NaturalLanguageInterface:
    """
    Complete natural language interface combining text and voice processing
    with conversation management and multilingual support.
    """

    def __init__(self, llm_config: Optional[LLMConfig] = None):
        """
        Initialize natural language interface.

        Args:
            llm_config: LLM configuration
        """
        # Initialize components
        self.llm_interface = LLMInterface(llm_config or LLMConfig())
        self.safety_validator = SafetyValidator()
        self.conversation_manager = ConversationManager(self.llm_interface, self.safety_validator)
        self.voice_interface = VoiceInterface(self.conversation_manager)

        logger.info("Natural language interface initialized")

    def start_session(self, user_id: str, language: Language = Language.ENGLISH) -> str:
        """Start a new conversation session."""
        session_id = self.conversation_manager.start_conversation(user_id, language)
        self.voice_interface.set_language(language)
        return session_id

    def process_text_command(self, session_id: str, text: str) -> Tuple[Optional[Any], str]:
        """Process a text command."""
        return self.conversation_manager.process_message(session_id, text)

    def process_voice_command(self, session_id: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Process a voice command."""
        return self.voice_interface.start_listening(session_id, timeout)

    def end_session(self, session_id: str) -> bool:
        """End a conversation session."""
        return self.conversation_manager.end_conversation(session_id)

    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics."""
        return {
            'llm_stats': self.llm_interface.get_usage_stats(),
            'safety_stats': self.safety_validator.get_validation_stats(),
            'processing_stats': self.conversation_manager.command_processor.get_processing_stats(),
            'voice_stats': self.voice_interface.get_voice_stats(),
            'active_sessions': len(self.conversation_manager.get_active_sessions())
        }


# Convenience functions
def create_natural_language_interface(llm_config: Optional[LLMConfig] = None) -> NaturalLanguageInterface:
    """Create and initialize natural language interface."""
    return NaturalLanguageInterface(llm_config)


def quick_text_command(text: str, user_id: str = "default") -> Tuple[Optional[Any], str]:
    """Quick text command processing."""
    interface = create_natural_language_interface()
    session_id = interface.start_session(user_id)
    result, response = interface.process_text_command(session_id, text)
    interface.end_session(session_id)
    return result, response
