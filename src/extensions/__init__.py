"""Extensions module."""
try:
    from .plugin_framework import PluginFramework
except ImportError as e:
    print(f"Warning: Could not import extension components: {e}")

__all__ = ['PluginFramework']
