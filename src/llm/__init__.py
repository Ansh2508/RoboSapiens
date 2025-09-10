"""LLM module."""
try:
    from .llm_interface import LLMInterface
    from .natural_language import NaturalLanguageInterface as NaturalLanguage
    from .output_parser import OutputParser
    from .safety_validator import SafetyValidator
    from .task_planner import TaskPlanner
    from .educational_interface import StudentInterface as EducationalInterface
except ImportError as e:
    print(f"Warning: Could not import LLM components: {e}")

__all__ = ['LLMInterface', 'NaturalLanguage', 'OutputParser', 'SafetyValidator', 'TaskPlanner', 'EducationalInterface']
