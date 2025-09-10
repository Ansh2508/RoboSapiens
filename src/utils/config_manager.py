"""
Minimal config manager for testing.
"""

from pathlib import Path
import yaml
from typing import Dict, Any

class ConfigManager:
    """Minimal configuration manager."""
    
    def __init__(self):
        self.config = {}
    
    def load_config(self, config_path: str = None):
        """Load configuration."""
        return self.config
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self.config.get(key, default)
