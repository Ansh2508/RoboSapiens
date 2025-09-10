"""
Educational Interface for LLM Integration

Student-friendly interfaces for natural language robot programming with
progressive complexity, visual debugging tools, and comprehensive educational
materials for the Bavarian-Czech Summer School 2025.

Features:
- Student-friendly LLM interaction interfaces
- Progressive complexity from simple commands to advanced AI planning
- Visual debugging tools showing AI decision-making processes
- Workshop activities demonstrating AI capabilities and limitations
- Performance metrics and progress tracking for educational assessment
"""

import time
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

from llm.natural_language import NaturalLanguageInterface, ConversationContext, Language
from llm.task_planner import TaskPlanner, PlanningContext
from llm.safety_validator import SafetyValidator
from llm.llm_interface import LLMInterface, LLMConfig
from utils.logger import get_logger

logger = get_logger(__name__)


class SkillLevel(Enum):
    """Student skill levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class LessonType(Enum):
    """Types of educational lessons."""
    INTRODUCTION = "introduction"
    BASIC_COMMANDS = "basic_commands"
    COMPLEX_PLANNING = "complex_planning"
    SAFETY_CONCEPTS = "safety_concepts"
    AI_LIMITATIONS = "ai_limitations"
    CREATIVE_PROJECT = "creative_project"


@dataclass
class StudentProfile:
    """Student profile for personalized learning."""
    student_id: str
    name: str
    skill_level: SkillLevel = SkillLevel.BEGINNER
    preferred_language: Language = Language.ENGLISH
    
    # Progress tracking
    lessons_completed: List[str] = field(default_factory=list)
    commands_attempted: int = 0
    successful_commands: int = 0
    total_session_time: float = 0.0
    
    # Learning preferences
    prefers_voice: bool = False
    needs_extra_help: bool = False
    learning_pace: str = "normal"  # slow, normal, fast
    
    # Achievements
    achievements: List[str] = field(default_factory=list)
    current_streak: int = 0
    best_streak: int = 0
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)


@dataclass
class LessonPlan:
    """Educational lesson plan."""
    lesson_id: str
    title: str
    description: str
    lesson_type: LessonType
    skill_level: SkillLevel
    
    # Content
    objectives: List[str]
    activities: List[Dict[str, Any]]
    example_commands: List[str]
    
    # Requirements
    prerequisites: List[str] = field(default_factory=list)
    estimated_duration: float = 30.0  # minutes
    required_equipment: List[str] = field(default_factory=list)
    
    # Assessment
    success_criteria: List[str] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)


class StudentInterface:
    """
    Student-friendly interface for LLM robot programming with
    progressive complexity and educational guidance.
    """
    
    def __init__(self, natural_language_interface: NaturalLanguageInterface):
        """
        Initialize student interface.
        
        Args:
            natural_language_interface: Natural language interface for processing
        """
        self.nl_interface = natural_language_interface
        self.student_profiles: Dict[str, StudentProfile] = {}
        self.active_sessions: Dict[str, str] = {}  # session_id -> student_id
        
        # Educational content
        self.lesson_plans = self._initialize_lesson_plans()
        self.achievement_system = self._initialize_achievements()
        
        # Statistics
        self.educational_stats = {
            'total_students': 0,
            'active_sessions': 0,
            'lessons_completed': 0,
            'commands_processed': 0,
            'average_success_rate': 0.0
        }
        
        logger.info("Student interface initialized")
    
    def _initialize_lesson_plans(self) -> Dict[str, LessonPlan]:
        """Initialize educational lesson plans."""
        return {
            'intro_ai_robotics': LessonPlan(
                lesson_id='intro_ai_robotics',
                title='Introduction to AI Robotics',
                description='Basic concepts of AI-controlled robotics',
                lesson_type=LessonType.INTRODUCTION,
                skill_level=SkillLevel.BEGINNER,
                objectives=[
                    'Understand what AI robotics means',
                    'Learn basic robot capabilities',
                    'Try first voice/text commands'
                ],
                activities=[
                    {'type': 'demonstration', 'content': 'Watch robot respond to simple commands'},
                    {'type': 'interaction', 'content': 'Try saying "Hello robot" and "Show me your status"'},
                    {'type': 'discussion', 'content': 'What makes this robot "intelligent"?'}
                ],
                example_commands=[
                    'Hello robot',
                    'What can you do?',
                    'Show me your status',
                    'Move your arm up'
                ],
                estimated_duration=20.0
            ),
            
            'basic_movement': LessonPlan(
                lesson_id='basic_movement',
                title='Basic Robot Movement Commands',
                description='Learn to control robot movement with natural language',
                lesson_type=LessonType.BASIC_COMMANDS,
                skill_level=SkillLevel.BEGINNER,
                objectives=[
                    'Control robot arm movement',
                    'Understand coordinate systems',
                    'Practice safety awareness'
                ],
                activities=[
                    {'type': 'guided_practice', 'content': 'Move robot to specific positions'},
                    {'type': 'free_exploration', 'content': 'Try your own movement commands'},
                    {'type': 'safety_discussion', 'content': 'Why did some commands get rejected?'}
                ],
                example_commands=[
                    'Move to position X=100, Y=200, Z=50',
                    'Move the arm up slowly',
                    'Go to the center of the workspace',
                    'Return to home position'
                ],
                prerequisites=['intro_ai_robotics'],
                estimated_duration=30.0
            ),
            
            'pick_and_place': LessonPlan(
                lesson_id='pick_and_place',
                title='Pick and Place Operations',
                description='Learn object manipulation with AI guidance',
                lesson_type=LessonType.BASIC_COMMANDS,
                skill_level=SkillLevel.INTERMEDIATE,
                objectives=[
                    'Understand object manipulation',
                    'Learn pick and place sequences',
                    'Practice with different objects'
                ],
                activities=[
                    {'type': 'demonstration', 'content': 'Watch AI plan pick and place'},
                    {'type': 'guided_practice', 'content': 'Command robot to pick up objects'},
                    {'type': 'challenge', 'content': 'Sort objects by color or shape'}
                ],
                example_commands=[
                    'Pick up the red cube',
                    'Place the object at X=200, Y=100',
                    'Sort the objects by color',
                    'Move all cubes to the left side'
                ],
                prerequisites=['basic_movement'],
                estimated_duration=45.0
            ),
            
            'ai_task_planning': LessonPlan(
                lesson_id='ai_task_planning',
                title='AI Task Planning and Complex Workflows',
                description='Understand how AI breaks down complex tasks',
                lesson_type=LessonType.COMPLEX_PLANNING,
                skill_level=SkillLevel.ADVANCED,
                objectives=[
                    'Understand AI task decomposition',
                    'Create complex multi-step workflows',
                    'Analyze AI decision-making process'
                ],
                activities=[
                    {'type': 'analysis', 'content': 'Watch AI plan a complex task step-by-step'},
                    {'type': 'creation', 'content': 'Design your own complex workflow'},
                    {'type': 'debugging', 'content': 'Fix a failed AI plan'}
                ],
                example_commands=[
                    'Create a quality inspection workflow',
                    'Sort all objects on the conveyor belt',
                    'Organize the workspace efficiently',
                    'Execute a pick-and-place assembly sequence'
                ],
                prerequisites=['pick_and_place'],
                estimated_duration=60.0
            )
        }
    
    def _initialize_achievements(self) -> Dict[str, Dict[str, Any]]:
        """Initialize achievement system."""
        return {
            'first_command': {
                'title': 'First Steps',
                'description': 'Successfully executed your first robot command',
                'icon': '🤖',
                'points': 10
            },
            'voice_commander': {
                'title': 'Voice Commander',
                'description': 'Used voice commands to control the robot',
                'icon': '🎤',
                'points': 15
            },
            'safety_conscious': {
                'title': 'Safety First',
                'description': 'Understood why a command was rejected for safety',
                'icon': '🛡️',
                'points': 20
            },
            'task_planner': {
                'title': 'Task Planner',
                'description': 'Created a complex multi-step workflow',
                'icon': '📋',
                'points': 30
            },
            'ai_debugger': {
                'title': 'AI Debugger',
                'description': 'Successfully fixed a failed AI plan',
                'icon': '🔧',
                'points': 40
            },
            'streak_master': {
                'title': 'Streak Master',
                'description': 'Achieved 10 successful commands in a row',
                'icon': '🔥',
                'points': 50
            }
        }
    
    def register_student(self, student_id: str, name: str, skill_level: SkillLevel = SkillLevel.BEGINNER,
                        language: Language = Language.ENGLISH) -> StudentProfile:
        """
        Register a new student.
        
        Args:
            student_id: Unique student identifier
            name: Student name
            skill_level: Initial skill level
            language: Preferred language
            
        Returns:
            Student profile
        """
        profile = StudentProfile(
            student_id=student_id,
            name=name,
            skill_level=skill_level,
            preferred_language=language
        )
        
        self.student_profiles[student_id] = profile
        self.educational_stats['total_students'] += 1
        
        logger.info(f"Registered student: {name} ({student_id}) - Level: {skill_level.value}")
        return profile
    
    def start_student_session(self, student_id: str) -> str:
        """
        Start a learning session for a student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            Session ID
        """
        if student_id not in self.student_profiles:
            raise ValueError(f"Student {student_id} not registered")
        
        profile = self.student_profiles[student_id]
        session_id = self.nl_interface.start_session(student_id, profile.preferred_language)
        
        self.active_sessions[session_id] = student_id
        profile.last_active = datetime.now()
        
        self.educational_stats['active_sessions'] += 1
        
        logger.info(f"Started session for student {profile.name}: {session_id}")
        return session_id
    
    def process_student_command(self, session_id: str, command: str, 
                               is_voice: bool = False) -> Tuple[Optional[Any], str, Dict[str, Any]]:
        """
        Process a student command with educational feedback.
        
        Args:
            session_id: Session identifier
            command: Student command
            is_voice: Whether command was given via voice
            
        Returns:
            Tuple of (result, response, educational_feedback)
        """
        if session_id not in self.active_sessions:
            return None, "Session not found", {}
        
        student_id = self.active_sessions[session_id]
        profile = self.student_profiles[student_id]
        
        # Update statistics
        profile.commands_attempted += 1
        profile.last_active = datetime.now()
        
        # Process command
        result, response = self.nl_interface.process_text_command(session_id, command)
        
        # Generate educational feedback
        educational_feedback = self._generate_educational_feedback(
            command, result, response, profile, is_voice
        )
        
        # Update progress
        if result is not None:  # Command was successful
            profile.successful_commands += 1
            profile.current_streak += 1
            profile.best_streak = max(profile.best_streak, profile.current_streak)
            
            # Check for achievements
            self._check_achievements(profile, command, is_voice, result)
        else:
            profile.current_streak = 0
        
        # Update educational statistics
        self.educational_stats['commands_processed'] += 1
        if self.educational_stats['commands_processed'] > 0:
            total_successful = sum(p.successful_commands for p in self.student_profiles.values())
            total_attempted = sum(p.commands_attempted for p in self.student_profiles.values())
            self.educational_stats['average_success_rate'] = total_successful / total_attempted
        
        return result, response, educational_feedback
    
    def _generate_educational_feedback(self, command: str, result: Any, response: str, 
                                     profile: StudentProfile, is_voice: bool) -> Dict[str, Any]:
        """Generate educational feedback for student learning."""
        feedback = {
            'success': result is not None,
            'skill_level_appropriate': True,
            'suggestions': [],
            'learning_points': [],
            'next_steps': []
        }
        
        # Analyze command complexity vs skill level
        command_complexity = self._assess_command_complexity(command)
        
        if command_complexity > profile.skill_level.value:
            feedback['skill_level_appropriate'] = False
            feedback['suggestions'].append(
                f"This command might be advanced for your current level. "
                f"Try starting with simpler commands like 'move robot up' or 'show status'."
            )
        
        # Success feedback
        if result is not None:
            feedback['learning_points'].append("Great! Your command was understood and executed safely.")
            
            if is_voice:
                feedback['learning_points'].append("Excellent use of voice commands!")
            
            # Suggest next steps based on what they accomplished
            if 'move' in command.lower():
                feedback['next_steps'].append("Try picking up an object: 'pick up the red cube'")
            elif 'pick' in command.lower():
                feedback['next_steps'].append("Now try placing it somewhere: 'place it at X=200, Y=100'")
        
        # Failure feedback with learning opportunities
        else:
            if 'safety' in response.lower():
                feedback['learning_points'].append(
                    "The robot's AI safety system prevented this command. "
                    "This is good - it means the robot is protecting itself and you!"
                )
                feedback['suggestions'].append(
                    "Try a command within the safe workspace limits, like 'move to X=100, Y=100, Z=50'"
                )
            elif 'unclear' in response.lower():
                feedback['learning_points'].append(
                    "The AI didn't understand your command. Try being more specific."
                )
                feedback['suggestions'].append(
                    "Use clear commands like 'move robot to position X=100, Y=200' "
                    "or 'pick up the blue object'"
                )
        
        return feedback
    
    def _assess_command_complexity(self, command: str) -> float:
        """Assess the complexity of a command (0.0 to 1.0)."""
        complexity = 0.0
        command_lower = command.lower()
        
        # Basic commands
        if any(word in command_lower for word in ['hello', 'status', 'help']):
            complexity = 0.1
        
        # Simple movement
        elif any(word in command_lower for word in ['move', 'go', 'up', 'down']):
            complexity = 0.3
        
        # Object manipulation
        elif any(word in command_lower for word in ['pick', 'place', 'grab']):
            complexity = 0.5
        
        # Complex workflows
        elif any(word in command_lower for word in ['workflow', 'sequence', 'sort', 'organize']):
            complexity = 0.8
        
        # Add complexity for specific coordinates
        if any(char in command for char in ['=', 'X', 'Y', 'Z']):
            complexity += 0.2
        
        # Add complexity for multiple objects
        if any(word in command_lower for word in ['all', 'multiple', 'several']):
            complexity += 0.2
        
        return min(1.0, complexity)
    
    def _check_achievements(self, profile: StudentProfile, command: str, 
                          is_voice: bool, result: Any) -> None:
        """Check and award achievements."""
        new_achievements = []
        
        # First command achievement
        if profile.successful_commands == 1 and 'first_command' not in profile.achievements:
            profile.achievements.append('first_command')
            new_achievements.append('first_command')
        
        # Voice command achievement
        if is_voice and 'voice_commander' not in profile.achievements:
            profile.achievements.append('voice_commander')
            new_achievements.append('voice_commander')
        
        # Streak achievement
        if profile.current_streak >= 10 and 'streak_master' not in profile.achievements:
            profile.achievements.append('streak_master')
            new_achievements.append('streak_master')
        
        # Task planning achievement
        if ('workflow' in command.lower() or 'sequence' in command.lower()) and \
           'task_planner' not in profile.achievements:
            profile.achievements.append('task_planner')
            new_achievements.append('task_planner')
        
        # Log new achievements
        for achievement in new_achievements:
            achievement_info = self.achievement_system[achievement]
            logger.info(f"Student {profile.name} earned achievement: {achievement_info['title']}")
    
    def get_student_progress(self, student_id: str) -> Dict[str, Any]:
        """Get comprehensive student progress report."""
        if student_id not in self.student_profiles:
            return {}
        
        profile = self.student_profiles[student_id]
        
        # Calculate success rate
        success_rate = 0.0
        if profile.commands_attempted > 0:
            success_rate = profile.successful_commands / profile.commands_attempted
        
        # Get achievement details
        achievements_detail = []
        for achievement_id in profile.achievements:
            if achievement_id in self.achievement_system:
                achievement_info = self.achievement_system[achievement_id].copy()
                achievement_info['id'] = achievement_id
                achievements_detail.append(achievement_info)
        
        return {
            'student_info': {
                'name': profile.name,
                'skill_level': profile.skill_level.value,
                'preferred_language': profile.preferred_language.value
            },
            'progress': {
                'commands_attempted': profile.commands_attempted,
                'successful_commands': profile.successful_commands,
                'success_rate': success_rate,
                'current_streak': profile.current_streak,
                'best_streak': profile.best_streak,
                'lessons_completed': len(profile.lessons_completed),
                'total_session_time': profile.total_session_time
            },
            'achievements': achievements_detail,
            'next_lessons': self._get_recommended_lessons(profile),
            'last_active': profile.last_active.isoformat()
        }
    
    def _get_recommended_lessons(self, profile: StudentProfile) -> List[str]:
        """Get recommended lessons for a student."""
        recommendations = []
        
        for lesson_id, lesson in self.lesson_plans.items():
            # Skip completed lessons
            if lesson_id in profile.lessons_completed:
                continue
            
            # Check skill level match
            if lesson.skill_level.value > profile.skill_level.value:
                continue
            
            # Check prerequisites
            if all(prereq in profile.lessons_completed for prereq in lesson.prerequisites):
                recommendations.append(lesson_id)
        
        return recommendations[:3]  # Return top 3 recommendations
