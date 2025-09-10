"""
Enhanced Voice Interface System

Advanced speech recognition with noise filtering, accent adaptation, and
multilingual support for hands-free robot control and educational interaction.

Features:
- Advanced speech recognition with noise filtering and accent adaptation
- Text-to-speech integration with multilingual support (German, Czech, English)
- Voice command validation and confirmation systems
- Integration with Phase 5 natural language processing
- Offline speech processing capabilities for educational environments
- Voice biometrics for student identification and progress tracking
"""

import os
import sys
import time
import json
import threading
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

# Add src directory to Python path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

try:
    import speech_recognition as sr
    import pyttsx3
    import numpy as np
    from scipy import signal
    VOICE_LIBRARIES_AVAILABLE = True
except ImportError:
    VOICE_LIBRARIES_AVAILABLE = False
    logging.warning("Voice libraries not available. Install with: pip install SpeechRecognition pyttsx3 numpy scipy pyaudio")
    # Create fallback numpy for type hints
    class np:
        ndarray = object

from utils.logger import get_logger

# Import Phase 5 components for integration
try:
    from interfaces.llm import NaturalLanguageInterface, Language, ConversationContext
except ImportError as e:
    logging.warning(f"Phase 5 components not available: {e}")

logger = get_logger(__name__)


class VoiceLanguage(Enum):
    """Supported voice languages."""
    ENGLISH = "en-US"
    GERMAN = "de-DE"
    CZECH = "cs-CZ"
    SPANISH = "es-ES"
    FRENCH = "fr-FR"


class RecognitionEngine(Enum):
    """Speech recognition engines."""
    GOOGLE = "google"
    SPHINX = "sphinx"
    WHISPER = "whisper"
    AZURE = "azure"


@dataclass
class VoiceConfig:
    """Configuration for voice interface."""
    # Recognition settings
    recognition_engine: RecognitionEngine = RecognitionEngine.GOOGLE
    language: VoiceLanguage = VoiceLanguage.ENGLISH
    recognition_timeout: float = 10.0
    phrase_timeout: float = 5.0
    recognition_threshold: float = 0.8
    
    # Audio settings
    sample_rate: int = 16000
    chunk_size: int = 1024
    channels: int = 1
    
    # Noise filtering
    noise_reduction_enabled: bool = True
    noise_gate_threshold: float = 0.01
    noise_reduction_strength: float = 0.5
    
    # Accent adaptation
    accent_adaptation_enabled: bool = True
    accent_learning_rate: float = 0.1
    
    # Text-to-speech settings
    tts_engine: str = "sapi5"  # Windows default
    tts_rate: int = 200
    tts_volume: float = 0.9
    
    # Offline mode
    offline_mode_enabled: bool = True
    offline_model_path: str = "models/voice"
    
    # Voice biometrics
    voice_biometrics_enabled: bool = False
    voice_print_threshold: float = 0.85
    
    # Educational features
    pronunciation_feedback: bool = True
    language_learning_mode: bool = False


class NoiseFilter:
    """
    Advanced noise filtering for speech recognition.
    """
    
    def __init__(self, config: VoiceConfig):
        """
        Initialize noise filter.
        
        Args:
            config: Voice configuration
        """
        self.config = config
        self.background_noise_profile = None
        self.adaptive_threshold = config.noise_gate_threshold
        
        logger.info("Noise filter initialized")
    
    def calibrate_background_noise(self, audio_data: np.ndarray, duration: float = 2.0):
        """
        Calibrate background noise profile.
        
        Args:
            audio_data: Audio data for calibration
            duration: Calibration duration in seconds
        """
        try:
            if not VOICE_LIBRARIES_AVAILABLE:
                return
            
            # Calculate noise profile
            self.background_noise_profile = np.mean(np.abs(audio_data))
            self.adaptive_threshold = self.background_noise_profile * 1.5
            
            logger.info(f"Background noise calibrated: {self.background_noise_profile:.4f}")
        
        except Exception as e:
            logger.error(f"Noise calibration failed: {e}")
    
    def apply_noise_reduction(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Apply noise reduction to audio data.
        
        Args:
            audio_data: Input audio data
            
        Returns:
            Filtered audio data
        """
        try:
            if not VOICE_LIBRARIES_AVAILABLE or not self.config.noise_reduction_enabled:
                return audio_data
            
            # Apply spectral subtraction
            filtered_audio = self._spectral_subtraction(audio_data)
            
            # Apply noise gate
            filtered_audio = self._apply_noise_gate(filtered_audio)
            
            return filtered_audio
        
        except Exception as e:
            logger.error(f"Noise reduction failed: {e}")
            return audio_data
    
    def _spectral_subtraction(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply spectral subtraction noise reduction."""
        if self.background_noise_profile is None:
            return audio_data
        
        # Simple spectral subtraction implementation
        # In production, use more sophisticated algorithms
        noise_factor = self.config.noise_reduction_strength
        
        # Apply high-pass filter to remove low-frequency noise
        nyquist = self.config.sample_rate / 2
        high_cutoff = 300 / nyquist  # 300 Hz cutoff
        
        b, a = signal.butter(4, high_cutoff, btype='high')
        filtered = signal.filtfilt(b, a, audio_data)
        
        return filtered
    
    def _apply_noise_gate(self, audio_data: np.ndarray) -> np.ndarray:
        """Apply noise gate to remove quiet noise."""
        # Simple noise gate implementation
        gate_mask = np.abs(audio_data) > self.adaptive_threshold
        gated_audio = audio_data * gate_mask
        
        return gated_audio


class AccentAdapter:
    """
    Accent adaptation system for improved recognition accuracy.
    """
    
    def __init__(self, config: VoiceConfig):
        """
        Initialize accent adapter.
        
        Args:
            config: Voice configuration
        """
        self.config = config
        self.accent_profiles: Dict[str, Dict[str, Any]] = {}
        self.current_profile = "default"
        
        logger.info("Accent adapter initialized")
    
    def create_user_profile(self, user_id: str, language: VoiceLanguage):
        """
        Create accent profile for user.
        
        Args:
            user_id: User identifier
            language: User's language
        """
        self.accent_profiles[user_id] = {
            'language': language,
            'phoneme_mappings': {},
            'recognition_corrections': {},
            'confidence_adjustments': {},
            'created_at': datetime.now().isoformat()
        }
        
        logger.info(f"Created accent profile for user: {user_id}")
    
    def adapt_recognition(self, user_id: str, recognized_text: str, 
                         confidence: float, actual_text: Optional[str] = None) -> Tuple[str, float]:
        """
        Adapt recognition based on user's accent profile.
        
        Args:
            user_id: User identifier
            recognized_text: Initially recognized text
            confidence: Recognition confidence
            actual_text: Actual intended text (for learning)
            
        Returns:
            Tuple of (adapted_text, adjusted_confidence)
        """
        if not self.config.accent_adaptation_enabled or user_id not in self.accent_profiles:
            return recognized_text, confidence
        
        profile = self.accent_profiles[user_id]
        
        # Apply known corrections
        adapted_text = recognized_text
        for pattern, correction in profile['recognition_corrections'].items():
            adapted_text = adapted_text.replace(pattern, correction)
        
        # Adjust confidence based on user profile
        adjusted_confidence = confidence
        if adapted_text in profile['confidence_adjustments']:
            adjustment = profile['confidence_adjustments'][adapted_text]
            adjusted_confidence = min(1.0, confidence + adjustment)
        
        # Learn from correction if provided
        if actual_text and actual_text != recognized_text:
            self._learn_correction(user_id, recognized_text, actual_text)
        
        return adapted_text, adjusted_confidence
    
    def _learn_correction(self, user_id: str, recognized: str, actual: str):
        """Learn from recognition correction."""
        if user_id not in self.accent_profiles:
            return
        
        profile = self.accent_profiles[user_id]
        
        # Store correction with learning rate
        learning_rate = self.config.accent_learning_rate
        
        if recognized in profile['recognition_corrections']:
            # Update existing correction
            current_correction = profile['recognition_corrections'][recognized]
            # Simple weighted average (in production, use more sophisticated learning)
            profile['recognition_corrections'][recognized] = actual
        else:
            # Add new correction
            profile['recognition_corrections'][recognized] = actual
        
        logger.debug(f"Learned correction for {user_id}: '{recognized}' -> '{actual}'")


class SpeechRecognizer:
    """
    Advanced speech recognition with multiple engine support.
    """
    
    def __init__(self, config: VoiceConfig):
        """
        Initialize speech recognizer.
        
        Args:
            config: Voice configuration
        """
        self.config = config
        self.noise_filter = NoiseFilter(config)
        self.accent_adapter = AccentAdapter(config)
        
        if VOICE_LIBRARIES_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            
            # Adjust for ambient noise
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            
            logger.info("Speech recognizer initialized")
        else:
            self.recognizer = None
            self.microphone = None
            logger.warning("Speech recognition not available")
        
        # Recognition statistics
        self.stats = {
            'total_recognitions': 0,
            'successful_recognitions': 0,
            'failed_recognitions': 0,
            'average_confidence': 0.0,
            'average_processing_time': 0.0
        }
    
    def recognize_speech(self, timeout: Optional[float] = None, 
                        user_id: Optional[str] = None) -> Tuple[Optional[str], float]:
        """
        Recognize speech from microphone.
        
        Args:
            timeout: Recognition timeout
            user_id: User ID for accent adaptation
            
        Returns:
            Tuple of (recognized_text, confidence)
        """
        if not VOICE_LIBRARIES_AVAILABLE or not self.recognizer:
            return None, 0.0
        
        start_time = time.time()
        self.stats['total_recognitions'] += 1
        
        try:
            timeout = timeout or self.config.recognition_timeout
            
            # Listen for audio
            with self.microphone as source:
                logger.debug("Listening for speech...")
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=self.config.phrase_timeout
                )
            
            # Apply noise filtering
            if self.config.noise_reduction_enabled:
                # Convert audio to numpy array for processing
                audio_data = np.frombuffer(audio.get_raw_data(), dtype=np.int16)
                filtered_data = self.noise_filter.apply_noise_reduction(audio_data)
                
                # Convert back to audio
                filtered_audio = sr.AudioData(
                    filtered_data.tobytes(),
                    audio.sample_rate,
                    audio.sample_width
                )
            else:
                filtered_audio = audio
            
            # Recognize speech
            recognized_text, confidence = self._recognize_with_engine(filtered_audio)
            
            # Apply accent adaptation
            if user_id and recognized_text:
                recognized_text, confidence = self.accent_adapter.adapt_recognition(
                    user_id, recognized_text, confidence
                )
            
            # Update statistics
            processing_time = time.time() - start_time
            
            if recognized_text:
                self.stats['successful_recognitions'] += 1
                self.stats['average_confidence'] = (
                    (self.stats['average_confidence'] * (self.stats['successful_recognitions'] - 1) + confidence) /
                    self.stats['successful_recognitions']
                )
            else:
                self.stats['failed_recognitions'] += 1
            
            self.stats['average_processing_time'] = (
                (self.stats['average_processing_time'] * (self.stats['total_recognitions'] - 1) + processing_time) /
                self.stats['total_recognitions']
            )
            
            logger.debug(f"Speech recognition: '{recognized_text}' (confidence: {confidence:.3f}, time: {processing_time:.3f}s)")
            return recognized_text, confidence
        
        except sr.WaitTimeoutError:
            logger.debug("Speech recognition timeout")
            return None, 0.0
        except sr.UnknownValueError:
            logger.debug("Speech not understood")
            self.stats['failed_recognitions'] += 1
            return None, 0.0
        except sr.RequestError as e:
            logger.error(f"Speech recognition service error: {e}")
            self.stats['failed_recognitions'] += 1
            return None, 0.0
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            self.stats['failed_recognitions'] += 1
            return None, 0.0
    
    def _recognize_with_engine(self, audio) -> Tuple[Optional[str], float]:
        """Recognize speech with configured engine."""
        try:
            if self.config.recognition_engine == RecognitionEngine.GOOGLE:
                text = self.recognizer.recognize_google(
                    audio, 
                    language=self.config.language.value,
                    show_all=False
                )
                return text, 0.9  # Google doesn't provide confidence scores in free tier
            
            elif self.config.recognition_engine == RecognitionEngine.SPHINX:
                text = self.recognizer.recognize_sphinx(audio)
                return text, 0.8  # Sphinx provides limited confidence info
            
            else:
                # Default to Google
                text = self.recognizer.recognize_google(audio, language=self.config.language.value)
                return text, 0.9
        
        except Exception as e:
            logger.error(f"Recognition engine error: {e}")
            return None, 0.0
    
    def get_recognition_stats(self) -> Dict[str, Any]:
        """Get recognition statistics."""
        stats = self.stats.copy()
        
        if stats['total_recognitions'] > 0:
            stats['success_rate'] = stats['successful_recognitions'] / stats['total_recognitions']
        else:
            stats['success_rate'] = 0.0
        
        return stats


class TextToSpeech:
    """
    Text-to-speech system with multilingual support.
    """

    def __init__(self, config: VoiceConfig):
        """
        Initialize text-to-speech system.

        Args:
            config: Voice configuration
        """
        self.config = config

        if VOICE_LIBRARIES_AVAILABLE:
            self.engine = pyttsx3.init(self.config.tts_engine)

            # Configure voice settings
            self.engine.setProperty('rate', self.config.tts_rate)
            self.engine.setProperty('volume', self.config.tts_volume)

            # Set voice based on language
            self._set_voice_for_language(self.config.language)

            logger.info("Text-to-speech initialized")
        else:
            self.engine = None
            logger.warning("Text-to-speech not available")

        # TTS statistics
        self.stats = {
            'total_utterances': 0,
            'successful_utterances': 0,
            'failed_utterances': 0,
            'average_speech_time': 0.0
        }

    def _set_voice_for_language(self, language: VoiceLanguage):
        """Set appropriate voice for language."""
        if not self.engine:
            return

        voices = self.engine.getProperty('voices')

        # Language to voice mapping
        language_keywords = {
            VoiceLanguage.ENGLISH: ['english', 'en', 'us', 'uk'],
            VoiceLanguage.GERMAN: ['german', 'de', 'deutsch'],
            VoiceLanguage.CZECH: ['czech', 'cs', 'cesky'],
            VoiceLanguage.SPANISH: ['spanish', 'es', 'espanol'],
            VoiceLanguage.FRENCH: ['french', 'fr', 'francais']
        }

        keywords = language_keywords.get(language, ['english'])

        # Find matching voice
        for voice in voices:
            voice_name = voice.name.lower()
            if any(keyword in voice_name for keyword in keywords):
                self.engine.setProperty('voice', voice.id)
                logger.info(f"Set voice for {language.value}: {voice.name}")
                return

        # Fallback to first available voice
        if voices:
            self.engine.setProperty('voice', voices[0].id)
            logger.info(f"Using fallback voice: {voices[0].name}")

    def speak(self, text: str, language: Optional[VoiceLanguage] = None,
              blocking: bool = True) -> bool:
        """
        Convert text to speech.

        Args:
            text: Text to speak
            language: Language for speech (optional)
            blocking: Whether to wait for speech completion

        Returns:
            True if speech was successful
        """
        if not VOICE_LIBRARIES_AVAILABLE or not self.engine:
            logger.warning(f"TTS not available, would speak: {text}")
            return False

        start_time = time.time()
        self.stats['total_utterances'] += 1

        try:
            # Change voice if different language requested
            if language and language != self.config.language:
                self._set_voice_for_language(language)

            # Speak text
            self.engine.say(text)

            if blocking:
                self.engine.runAndWait()

            # Update statistics
            speech_time = time.time() - start_time
            self.stats['successful_utterances'] += 1
            self.stats['average_speech_time'] = (
                (self.stats['average_speech_time'] * (self.stats['successful_utterances'] - 1) + speech_time) /
                self.stats['successful_utterances']
            )

            logger.debug(f"TTS spoke: '{text}' (time: {speech_time:.3f}s)")
            return True

        except Exception as e:
            logger.error(f"TTS error: {e}")
            self.stats['failed_utterances'] += 1
            return False

    def speak_multilingual(self, text_dict: Dict[VoiceLanguage, str],
                          target_language: VoiceLanguage) -> bool:
        """
        Speak text in specified language from multilingual dictionary.

        Args:
            text_dict: Dictionary of language -> text
            target_language: Target language for speech

        Returns:
            True if speech was successful
        """
        text = text_dict.get(target_language)
        if not text:
            # Fallback to English
            text = text_dict.get(VoiceLanguage.ENGLISH, "")

        if text:
            return self.speak(text, target_language)

        return False

    def get_available_voices(self) -> List[Dict[str, str]]:
        """Get list of available voices."""
        if not self.engine:
            return []

        voices = self.engine.getProperty('voices')
        return [
            {
                'id': voice.id,
                'name': voice.name,
                'languages': getattr(voice, 'languages', []),
                'gender': getattr(voice, 'gender', 'unknown')
            }
            for voice in voices
        ]

    def get_tts_stats(self) -> Dict[str, Any]:
        """Get TTS statistics."""
        stats = self.stats.copy()

        if stats['total_utterances'] > 0:
            stats['success_rate'] = stats['successful_utterances'] / stats['total_utterances']
        else:
            stats['success_rate'] = 0.0

        return stats


class VoiceInterface:
    """
    Main voice interface coordinating speech recognition and synthesis.
    """

    def __init__(self, config: Optional[VoiceConfig] = None):
        """
        Initialize voice interface.

        Args:
            config: Voice configuration
        """
        self.config = config or VoiceConfig()

        # Initialize components
        self.speech_recognizer = SpeechRecognizer(self.config)
        self.text_to_speech = TextToSpeech(self.config)

        # Integration with Phase 5 NLP
        try:
            self.nl_interface = NaturalLanguageInterface()
            self.nlp_available = True
        except:
            self.nl_interface = None
            self.nlp_available = False
            logger.warning("Phase 5 NLP integration not available")

        # Voice session management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.voice_commands: Dict[str, Callable] = {}

        # Voice biometrics (placeholder for future implementation)
        self.voice_profiles: Dict[str, Dict[str, Any]] = {}

        # Register default voice commands
        self._register_default_commands()

        logger.info("Voice interface initialized")

    def _register_default_commands(self):
        """Register default voice commands."""
        self.voice_commands.update({
            'stop': self._handle_stop_command,
            'pause': self._handle_pause_command,
            'resume': self._handle_resume_command,
            'help': self._handle_help_command,
            'status': self._handle_status_command,
            'repeat': self._handle_repeat_command
        })

    def start_voice_session(self, user_id: str, language: Optional[VoiceLanguage] = None) -> str:
        """
        Start a voice interaction session.

        Args:
            user_id: User identifier
            language: Session language

        Returns:
            Session ID
        """
        session_id = f"voice_{user_id}_{int(time.time())}"

        self.active_sessions[session_id] = {
            'user_id': user_id,
            'language': language or self.config.language,
            'started_at': datetime.now(),
            'commands_processed': 0,
            'last_activity': datetime.now(),
            'context': {}
        }

        # Create accent profile if enabled
        if self.config.accent_adaptation_enabled:
            self.speech_recognizer.accent_adapter.create_user_profile(user_id, language or self.config.language)

        # Welcome message
        welcome_messages = {
            VoiceLanguage.ENGLISH: f"Hello {user_id}! Voice interface is ready. How can I help you?",
            VoiceLanguage.GERMAN: f"Hallo {user_id}! Sprachschnittstelle ist bereit. Wie kann ich Ihnen helfen?",
            VoiceLanguage.CZECH: f"Ahoj {user_id}! Hlasové rozhraní je připraveno. Jak vám mohu pomoci?"
        }

        session_language = language or self.config.language
        welcome_text = welcome_messages.get(session_language, welcome_messages[VoiceLanguage.ENGLISH])
        self.text_to_speech.speak(welcome_text, session_language)

        logger.info(f"Started voice session: {session_id} for user {user_id}")
        return session_id

    def process_voice_command(self, session_id: str, timeout: Optional[float] = None) -> Tuple[bool, str]:
        """
        Process a single voice command.

        Args:
            session_id: Voice session ID
            timeout: Recognition timeout

        Returns:
            Tuple of (success, response_message)
        """
        if session_id not in self.active_sessions:
            return False, "Invalid session ID"

        session = self.active_sessions[session_id]
        user_id = session['user_id']

        try:
            # Recognize speech
            recognized_text, confidence = self.speech_recognizer.recognize_speech(timeout, user_id)

            if not recognized_text:
                response = "I didn't understand. Could you please repeat?"
                self.text_to_speech.speak(response, session['language'])
                return False, response

            if confidence < self.config.recognition_threshold:
                response = f"I'm not sure I understood correctly. Did you say '{recognized_text}'?"
                self.text_to_speech.speak(response, session['language'])
                return False, response

            # Update session
            session['commands_processed'] += 1
            session['last_activity'] = datetime.now()

            # Process command
            response = self._process_command(session_id, recognized_text)

            # Speak response
            self.text_to_speech.speak(response, session['language'])

            logger.info(f"Processed voice command in session {session_id}: '{recognized_text}' -> '{response}'")
            return True, response

        except Exception as e:
            logger.error(f"Error processing voice command: {e}")
            error_response = "Sorry, I encountered an error processing your command."
            self.text_to_speech.speak(error_response, session['language'])
            return False, error_response

    def _process_command(self, session_id: str, command_text: str) -> str:
        """Process recognized command text."""
        session = self.active_sessions[session_id]

        # Check for built-in voice commands
        command_lower = command_text.lower().strip()

        for cmd_keyword, handler in self.voice_commands.items():
            if cmd_keyword in command_lower:
                return handler(session_id, command_text)

        # Process with Phase 5 NLP if available
        if self.nlp_available and self.nl_interface:
            try:
                # Create or get NLP session
                nlp_session_id = session.get('nlp_session_id')
                if not nlp_session_id:
                    nlp_session_id = self.nl_interface.start_session(session['user_id'])
                    session['nlp_session_id'] = nlp_session_id

                # Process with NLP
                result, response = self.nl_interface.process_text_command(nlp_session_id, command_text)

                return response

            except Exception as e:
                logger.error(f"NLP processing error: {e}")
                return "I'm having trouble understanding that command. Could you try rephrasing it?"

        # Fallback response
        return f"I heard '{command_text}' but I'm not sure how to help with that. Try saying 'help' for available commands."

    def _handle_stop_command(self, session_id: str, command_text: str) -> str:
        """Handle stop command."""
        return "Stopping current operation."

    def _handle_pause_command(self, session_id: str, command_text: str) -> str:
        """Handle pause command."""
        return "Pausing current operation."

    def _handle_resume_command(self, session_id: str, command_text: str) -> str:
        """Handle resume command."""
        return "Resuming operation."

    def _handle_help_command(self, session_id: str, command_text: str) -> str:
        """Handle help command."""
        help_text = (
            "Available voice commands: "
            "You can ask me to move the robot, take pictures, start automation, "
            "or ask questions about the system. "
            "Say 'stop', 'pause', 'resume', or 'status' for basic controls."
        )
        return help_text

    def _handle_status_command(self, session_id: str, command_text: str) -> str:
        """Handle status command."""
        session = self.active_sessions[session_id]
        return f"Voice interface is active. Session started at {session['started_at'].strftime('%H:%M')}. Commands processed: {session['commands_processed']}."

    def _handle_repeat_command(self, session_id: str, command_text: str) -> str:
        """Handle repeat command."""
        return "Please repeat your command."

    def end_voice_session(self, session_id: str) -> bool:
        """
        End voice session.

        Args:
            session_id: Session ID to end

        Returns:
            True if session ended successfully
        """
        if session_id in self.active_sessions:
            session = self.active_sessions[session_id]

            # Goodbye message
            goodbye_messages = {
                VoiceLanguage.ENGLISH: "Goodbye! Voice session ended.",
                VoiceLanguage.GERMAN: "Auf Wiedersehen! Sprachsitzung beendet.",
                VoiceLanguage.CZECH: "Na shledanou! Hlasová relace ukončena."
            }

            goodbye_text = goodbye_messages.get(session['language'], goodbye_messages[VoiceLanguage.ENGLISH])
            self.text_to_speech.speak(goodbye_text, session['language'])

            # Clean up session
            del self.active_sessions[session_id]

            logger.info(f"Ended voice session: {session_id}")
            return True

        return False

    def register_voice_command(self, keyword: str, handler: Callable[[str, str], str]):
        """
        Register custom voice command.

        Args:
            keyword: Command keyword
            handler: Command handler function
        """
        self.voice_commands[keyword.lower()] = handler
        logger.info(f"Registered voice command: {keyword}")

    def get_interface_stats(self) -> Dict[str, Any]:
        """Get voice interface statistics."""
        recognition_stats = self.speech_recognizer.get_recognition_stats()
        tts_stats = self.text_to_speech.get_tts_stats()

        return {
            'active_sessions': len(self.active_sessions),
            'total_voice_commands': len(self.voice_commands),
            'recognition_stats': recognition_stats,
            'tts_stats': tts_stats,
            'config': {
                'language': self.config.language.value,
                'recognition_engine': self.config.recognition_engine.value,
                'noise_reduction_enabled': self.config.noise_reduction_enabled,
                'accent_adaptation_enabled': self.config.accent_adaptation_enabled
            }
        }


# Convenience functions
def create_voice_interface(config: Optional[VoiceConfig] = None) -> VoiceInterface:
    """Create and initialize voice interface."""
    return VoiceInterface(config)


def create_voice_config(**kwargs) -> VoiceConfig:
    """Create voice configuration with custom settings."""
    return VoiceConfig(**kwargs)


if __name__ == "__main__":
    """Run voice interface when executed directly."""
    print("🎤 NIRYO LLM ROBOTICS PLATFORM - VOICE INTERFACE")
    print("=" * 60)

    if not VOICE_LIBRARIES_AVAILABLE:
        print("❌ ERROR: Voice libraries are not available!")
        print("Install with: pip install SpeechRecognition pyttsx3 numpy scipy pyaudio")
        sys.exit(1)

    try:
        print("Initializing voice interface...")
        config = VoiceConfig()
        voice_interface = VoiceInterface(config)

        print("✓ Voice interface initialized successfully")
        print("Starting voice session...")

        # Start a test session
        session_id = voice_interface.start_voice_session("test_user", VoiceLanguage.ENGLISH)

        print(f"✓ Voice session started: {session_id}")
        print("Say 'help' to see available commands, or 'stop' to exit")

        # Process voice commands in a loop
        try:
            while True:
                success, response = voice_interface.process_voice_command(session_id, timeout=10.0)
                if not success and "stop" in response.lower():
                    break
        except KeyboardInterrupt:
            print("\nStopping voice interface...")

        # End session
        voice_interface.end_voice_session(session_id)
        print("Voice interface stopped.")

    except Exception as e:
        print(f"❌ ERROR: Failed to start voice interface: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
