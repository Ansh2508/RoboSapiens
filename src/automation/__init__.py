"""Automation module."""
try:
    from .conveyor_controller import ConveyorController
    from .coordination_manager import CoordinationManager
    from .sensor_interface import SensorInterface
    from .workflow_executor import WorkflowExecutor
    from .movement_patterns import MovementPatterns
except ImportError as e:
    print(f"Warning: Could not import automation components: {e}")

__all__ = ['ConveyorController', 'CoordinationManager', 'SensorInterface', 'WorkflowExecutor', 'MovementPatterns']
