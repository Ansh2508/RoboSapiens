"""Applications module."""
try:
    from .quality_control import QualityControlSystem
except ImportError as e:
    print(f"Warning: Could not import application components: {e}")

__all__ = ['QualityControlSystem']
