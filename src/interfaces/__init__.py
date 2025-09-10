"""Interfaces module."""
try:
    from .voice_interface import VoiceInterface
    from .gui_application import GUIApplication
    from .cli_interface import CLIInterface
except ImportError as e:
    print(f"Warning: Could not import interface components: {e}")

__all__ = ['VoiceInterface', 'GUIApplication', 'CLIInterface']
