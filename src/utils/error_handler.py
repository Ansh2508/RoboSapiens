"""
Error Handling and Recovery System

This module provides comprehensive error handling, custom exceptions,
and recovery mechanisms for the Niryo LLM Robotics Platform.

Features:
- Custom exception hierarchy
- Error recovery strategies
- Graceful degradation
- Error reporting and logging
"""

from typing import Optional, Dict, Any, Callable
from enum import Enum
import traceback
import functools

from utils.logger import get_logger

logger = get_logger(__name__)


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(Enum):
    """Error categories for classification."""
    HARDWARE = "hardware"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    SAFETY = "safety"
    AI = "ai"
    VISION = "vision"
    USER_INPUT = "user_input"
    SYSTEM = "system"


class RoboticsError(Exception):
    """Base exception for robotics platform errors."""
    
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        recoverable: bool = True,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.recoverable = recoverable
        self.context = context or {}
        
        # Log the error
        logger.error(
            f"RoboticsError [{category.value}|{severity.value}]: {message}",
            extra={"context": self.context}
        )


class ConnectionError(RoboticsError):
    """Robot connection related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class SafetyError(RoboticsError):
    """Safety-related errors that require immediate attention."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.SAFETY,
            severity=ErrorSeverity.CRITICAL,
            recoverable=False,
            **kwargs
        )


class CalibrationError(RoboticsError):
    """Robot calibration errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.HARDWARE,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class VisionError(RoboticsError):
    """Computer vision related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.VISION,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class AIError(RoboticsError):
    """AI and LLM related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.AI,
            severity=ErrorSeverity.MEDIUM,
            **kwargs
        )


class ConfigurationError(RoboticsError):
    """Configuration related errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            **kwargs
        )


class ErrorHandler:
    """Centralized error handling and recovery system."""
    
    def __init__(self):
        self.recovery_strategies: Dict[ErrorCategory, Callable] = {}
        self.error_counts: Dict[str, int] = {}
        self.max_retries = 3
    
    def register_recovery_strategy(
        self,
        category: ErrorCategory,
        strategy: Callable[[RoboticsError], bool]
    ) -> None:
        """
        Register a recovery strategy for a specific error category.
        
        Args:
            category: Error category
            strategy: Recovery function that returns True if recovery succeeded
        """
        self.recovery_strategies[category] = strategy
        logger.info(f"Registered recovery strategy for {category.value} errors")
    
    def handle_error(self, error: RoboticsError) -> bool:
        """
        Handle an error with appropriate recovery strategy.
        
        Args:
            error: The error to handle
            
        Returns:
            True if error was recovered, False otherwise
        """
        error_key = f"{error.category.value}:{error.__class__.__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        logger.error(
            f"Handling error: {error.message} "
            f"(occurrence #{self.error_counts[error_key]})"
        )
        
        # Check if error is recoverable
        if not error.recoverable:
            logger.critical(f"Non-recoverable error: {error.message}")
            return False
        
        # Check retry limit
        if self.error_counts[error_key] > self.max_retries:
            logger.error(
                f"Max retries exceeded for {error_key}. "
                f"Giving up after {self.max_retries} attempts."
            )
            return False
        
        # Try recovery strategy
        if error.category in self.recovery_strategies:
            try:
                recovery_func = self.recovery_strategies[error.category]
                success = recovery_func(error)
                
                if success:
                    logger.info(f"Successfully recovered from {error_key}")
                    # Reset error count on successful recovery
                    self.error_counts[error_key] = 0
                    return True
                else:
                    logger.warning(f"Recovery strategy failed for {error_key}")
                    
            except Exception as e:
                logger.error(f"Recovery strategy raised exception: {e}")
        
        return False
    
    def reset_error_counts(self) -> None:
        """Reset all error counts."""
        self.error_counts.clear()
        logger.info("Error counts reset")


def safe_execute(
    func: Callable,
    error_handler: Optional[ErrorHandler] = None,
    default_return: Any = None,
    reraise: bool = False
) -> Any:
    """
    Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        error_handler: Error handler instance
        default_return: Default return value on error
        reraise: Whether to reraise the exception after handling
        
    Returns:
        Function result or default_return on error
    """
    try:
        return func()
    except RoboticsError as e:
        if error_handler:
            recovered = error_handler.handle_error(e)
            if recovered and not reraise:
                # Try executing again after recovery
                try:
                    return func()
                except Exception:
                    pass
        
        if reraise:
            raise
        return default_return
    except Exception as e:
        # Convert generic exceptions to RoboticsError
        robotics_error = RoboticsError(
            f"Unexpected error in {func.__name__}: {str(e)}",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.MEDIUM,
            context={"traceback": traceback.format_exc()}
        )
        
        if error_handler:
            error_handler.handle_error(robotics_error)
        
        if reraise:
            raise robotics_error
        return default_return


def error_handler_decorator(
    error_handler: Optional[ErrorHandler] = None,
    default_return: Any = None,
    reraise: bool = True
):
    """
    Decorator for automatic error handling.
    
    Args:
        error_handler: Error handler instance
        default_return: Default return value on error
        reraise: Whether to reraise exceptions
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return safe_execute(
                lambda: func(*args, **kwargs),
                error_handler=error_handler,
                default_return=default_return,
                reraise=reraise
            )
        return wrapper
    return decorator


def retry_on_error(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (RoboticsError,)
):
    """
    Decorator for retrying functions on specific errors.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exceptions to retry on
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(
                            f"Function {func.__name__} failed after "
                            f"{max_retries} retries: {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay}s..."
                    )
                    
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
        return wrapper
    return decorator


# Global error handler instance
_global_error_handler = ErrorHandler()


def get_error_handler() -> ErrorHandler:
    """Get the global error handler instance."""
    return _global_error_handler
