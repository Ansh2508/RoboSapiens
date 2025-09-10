"""
Minimal logger module for testing.
"""

from loguru import logger as loguru_logger
import sys

def get_logger(name):
    """Get a logger instance."""
    return loguru_logger

def setup_logging(config=None):
    """Setup logging configuration."""
    loguru_logger.info("Logging system initialized")

# Export the logger
logger = loguru_logger
