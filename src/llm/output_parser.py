"""
Structured Output Processing System

Pydantic models for reliable parsing of LLM responses into structured data
with comprehensive validation schemas and error recovery mechanisms.

Features:
- Pydantic models for robot commands and task plans
- Validation schemas with safety constraints
- Error recovery for malformed LLM outputs
- Comprehensive logging and debugging tools
- Data sanitization and security validation
"""

import json
import re
from enum import Enum
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime
from pydantic import BaseModel, Field, model_validator, validator
import logging

from utils.logger import get_logger

logger = get_logger(__name__)


class ParseError(Exception):
    """Exception raised when parsing LLM output fails."""
    pass


class CommandType(Enum):
    """Types of robot commands."""
    MOVE = "move"
    PICK = "pick"
    PLACE = "place"
    ROTATE = "rotate"
    WAIT = "wait"
    STOP = "stop"
    HOME = "home"
    CALIBRATE = "calibrate"
    CONVEYOR_START = "conveyor_start"
    CONVEYOR_STOP = "conveyor_stop"
    VISION_CAPTURE = "vision_capture"
    WORKFLOW_EXECUTE = "workflow_execute"


class CoordinateSystem(Enum):
    """Coordinate system types."""
    CARTESIAN = "cartesian"
    JOINT = "joint"
    RELATIVE = "relative"


class Priority(Enum):
    """Task priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class Position(BaseModel):
    """3D position with validation."""
    x: float = Field(..., ge=-1000, le=1000, description="X coordinate in mm")
    y: float = Field(..., ge=-1000, le=1000, description="Y coordinate in mm")
    z: float = Field(..., ge=-200, le=500, description="Z coordinate in mm")
    
    @validator('x', 'y', 'z')
    def validate_coordinates(cls, v):
        """Validate coordinate values."""
        if not isinstance(v, (int, float)):
            raise ValueError("Coordinates must be numeric")
        return float(v)


class Orientation(BaseModel):
    """3D orientation with validation."""
    roll: float = Field(..., ge=-180, le=180, description="Roll angle in degrees")
    pitch: float = Field(..., ge=-180, le=180, description="Pitch angle in degrees")
    yaw: float = Field(..., ge=-180, le=180, description="Yaw angle in degrees")
    
    @validator('roll', 'pitch', 'yaw')
    def validate_angles(cls, v):
        """Validate angle values."""
        if not isinstance(v, (int, float)):
            raise ValueError("Angles must be numeric")
        return float(v)


class JointAngles(BaseModel):
    """Joint angles with validation."""
    j1: float = Field(..., ge=-180, le=180, description="Joint 1 angle in degrees")
    j2: float = Field(..., ge=-180, le=180, description="Joint 2 angle in degrees")
    j3: float = Field(..., ge=-180, le=180, description="Joint 3 angle in degrees")
    j4: float = Field(..., ge=-180, le=180, description="Joint 4 angle in degrees")
    j5: float = Field(..., ge=-180, le=180, description="Joint 5 angle in degrees")
    j6: float = Field(..., ge=-180, le=180, description="Joint 6 angle in degrees")
    
    @validator('j1', 'j2', 'j3', 'j4', 'j5', 'j6')
    def validate_joint_angles(cls, v):
        """Validate joint angle values."""
        if not isinstance(v, (int, float)):
            raise ValueError("Joint angles must be numeric")
        return float(v)


class RobotCommand(BaseModel):
    """Individual robot command with validation."""
    command_type: CommandType = Field(..., description="Type of robot command")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Command parameters")
    
    # Optional position and orientation
    position: Optional[Position] = Field(None, description="Target position")
    orientation: Optional[Orientation] = Field(None, description="Target orientation")
    joint_angles: Optional[JointAngles] = Field(None, description="Target joint angles")
    
    # Command properties
    coordinate_system: CoordinateSystem = Field(CoordinateSystem.CARTESIAN, description="Coordinate system")
    speed: float = Field(50.0, ge=1.0, le=100.0, description="Movement speed percentage")
    precision: float = Field(1.0, ge=0.1, le=10.0, description="Movement precision in mm")
    
    # Safety and validation
    safety_check: bool = Field(True, description="Perform safety validation")
    timeout: float = Field(30.0, ge=1.0, le=300.0, description="Command timeout in seconds")
    
    @validator('parameters')
    def validate_parameters(cls, v, values):
        """Validate command parameters based on command type."""
        command_type = values.get('command_type')
        
        if command_type == CommandType.WAIT:
            if 'duration' not in v:
                raise ValueError("WAIT command requires 'duration' parameter")
            if not isinstance(v['duration'], (int, float)) or v['duration'] <= 0:
                raise ValueError("Wait duration must be positive number")
        
        elif command_type == CommandType.CONVEYOR_START:
            if 'speed' not in v:
                raise ValueError("CONVEYOR_START requires 'speed' parameter")
            if not isinstance(v['speed'], (int, float)) or not (10 <= v['speed'] <= 100):
                raise ValueError("Conveyor speed must be between 10-100 mm/s")
        
        return v
    
    @model_validator(mode="before")
    @classmethod
    def validate_command_consistency(cls, values):
        """Validate command consistency."""
        command_type = values.get('command_type')
        position = values.get('position')
        joint_angles = values.get('joint_angles')
        coordinate_system = values.get('coordinate_system')
        
        # Movement commands need position or joint angles
        if command_type in [CommandType.MOVE, CommandType.PICK, CommandType.PLACE]:
            if coordinate_system == CoordinateSystem.CARTESIAN and not position:
                raise ValueError(f"{command_type.value} command with Cartesian coordinates requires position")
            if coordinate_system == CoordinateSystem.JOINT and not joint_angles:
                raise ValueError(f"{command_type.value} command with joint coordinates requires joint_angles")
        
        return values


class TaskStep(BaseModel):
    """Individual step in a task plan."""
    step_id: int = Field(..., ge=1, description="Step identifier")
    description: str = Field(..., min_length=1, description="Human-readable step description")
    command: RobotCommand = Field(..., description="Robot command for this step")
    dependencies: List[int] = Field(default_factory=list, description="Step dependencies")
    estimated_duration: float = Field(10.0, ge=0.1, description="Estimated duration in seconds")
    
    @validator('dependencies')
    def validate_dependencies(cls, v, values):
        """Validate step dependencies."""
        step_id = values.get('step_id')
        if step_id and step_id in v:
            raise ValueError("Step cannot depend on itself")
        return v


class TaskPlan(BaseModel):
    """Complete task plan with validation."""
    task_id: str = Field(..., min_length=1, description="Unique task identifier")
    name: str = Field(..., min_length=1, description="Task name")
    description: str = Field(..., min_length=1, description="Task description")
    
    steps: List[TaskStep] = Field(..., min_items=1, description="Task steps")
    priority: Priority = Field(Priority.NORMAL, description="Task priority")
    
    # Metadata
    estimated_total_duration: float = Field(0.0, ge=0.0, description="Total estimated duration")
    safety_level: str = Field("standard", description="Required safety level")
    requires_human_approval: bool = Field(False, description="Requires human approval")
    
    # Context
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    created_by: str = Field("llm", description="Creator identifier")
    
    @validator('steps')
    def validate_steps(cls, v):
        """Validate task steps."""
        if not v:
            raise ValueError("Task must have at least one step")
        
        # Check step IDs are unique and sequential
        step_ids = [step.step_id for step in v]
        if len(set(step_ids)) != len(step_ids):
            raise ValueError("Step IDs must be unique")
        
        # Check dependencies are valid
        for step in v:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    raise ValueError(f"Step {step.step_id} depends on non-existent step {dep_id}")
                if dep_id >= step.step_id:
                    raise ValueError(f"Step {step.step_id} cannot depend on later step {dep_id}")
        
        return v
    
    @model_validator(mode="before")
    @classmethod
    def calculate_total_duration(cls, values):
        """Calculate total estimated duration."""
        steps = values.get('steps', [])
        if steps:
            values['estimated_total_duration'] = sum(step.estimated_duration for step in steps)
        return values


class SafetyValidation(BaseModel):
    """Safety validation result."""
    is_safe: bool = Field(..., description="Whether the command/plan is safe")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in safety assessment")
    
    # Validation details
    checks_performed: List[str] = Field(default_factory=list, description="Safety checks performed")
    warnings: List[str] = Field(default_factory=list, description="Safety warnings")
    errors: List[str] = Field(default_factory=list, description="Safety errors")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Safety recommendations")
    requires_approval: bool = Field(False, description="Requires human approval")
    
    # Metadata
    validated_at: datetime = Field(default_factory=datetime.now, description="Validation timestamp")
    validator_version: str = Field("1.0.0", description="Validator version")


class OutputParser:
    """
    Parser for converting LLM outputs into structured data with comprehensive
    validation and error recovery mechanisms.
    """
    
    def __init__(self):
        """Initialize output parser."""
        self.parsing_stats = {
            'total_parses': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0
        }
        
        logger.info("Output parser initialized")
    
    def parse_robot_command(self, llm_output: str) -> RobotCommand:
        """
        Parse LLM output into a robot command.
        
        Args:
            llm_output: Raw LLM output text
            
        Returns:
            Parsed robot command
            
        Raises:
            ParseError: If parsing fails
        """
        self.parsing_stats['total_parses'] += 1
        
        try:
            # Try to extract JSON from the output
            json_data = self._extract_json(llm_output)
            
            # Parse into RobotCommand
            command = RobotCommand(**json_data)
            
            self.parsing_stats['successful_parses'] += 1
            logger.debug(f"Successfully parsed robot command: {command.command_type.value}")
            
            return command
            
        except Exception as e:
            self.parsing_stats['failed_parses'] += 1
            logger.error(f"Failed to parse robot command: {e}")
            
            # Attempt recovery
            try:
                recovered_command = self._recover_robot_command(llm_output)
                self.parsing_stats['successful_recoveries'] += 1
                return recovered_command
            except Exception as recovery_error:
                logger.error(f"Command recovery failed: {recovery_error}")
                raise ParseError(f"Failed to parse robot command: {e}")
    
    def parse_task_plan(self, llm_output: str) -> TaskPlan:
        """
        Parse LLM output into a task plan.
        
        Args:
            llm_output: Raw LLM output text
            
        Returns:
            Parsed task plan
            
        Raises:
            ParseError: If parsing fails
        """
        self.parsing_stats['total_parses'] += 1
        
        try:
            # Try to extract JSON from the output
            json_data = self._extract_json(llm_output)
            
            # Parse into TaskPlan
            task_plan = TaskPlan(**json_data)
            
            self.parsing_stats['successful_parses'] += 1
            logger.debug(f"Successfully parsed task plan: {task_plan.name}")
            
            return task_plan
            
        except Exception as e:
            self.parsing_stats['failed_parses'] += 1
            logger.error(f"Failed to parse task plan: {e}")
            
            # Attempt recovery
            try:
                recovered_plan = self._recover_task_plan(llm_output)
                self.parsing_stats['successful_recoveries'] += 1
                return recovered_plan
            except Exception as recovery_error:
                logger.error(f"Task plan recovery failed: {recovery_error}")
                raise ParseError(f"Failed to parse task plan: {e}")
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text."""
        # Try to find JSON in the text
        json_pattern = r'\{.*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        if not matches:
            raise ParseError("No JSON found in text")
        
        # Try to parse each match
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        raise ParseError("No valid JSON found in text")

    def _recover_robot_command(self, text: str) -> RobotCommand:
        """Attempt to recover a robot command from malformed text."""
        self.parsing_stats['recovery_attempts'] += 1

        # Try to extract command type
        command_type = self._extract_command_type(text)
        if not command_type:
            raise ParseError("Cannot determine command type")

        # Build basic command structure
        command_data = {
            'command_type': command_type,
            'parameters': {}
        }

        # Try to extract position if mentioned
        position = self._extract_position(text)
        if position:
            command_data['position'] = position

        # Try to extract other parameters
        speed = self._extract_speed(text)
        if speed:
            command_data['speed'] = speed

        return RobotCommand(**command_data)

    def _recover_task_plan(self, text: str) -> TaskPlan:
        """Attempt to recover a task plan from malformed text."""
        self.parsing_stats['recovery_attempts'] += 1

        # Create basic task plan structure
        task_data = {
            'task_id': f"recovered_task_{int(datetime.now().timestamp())}",
            'name': "Recovered Task",
            'description': "Task recovered from malformed LLM output",
            'steps': []
        }

        # Try to extract steps from text
        steps = self._extract_steps(text)
        if steps:
            task_data['steps'] = steps
        else:
            # Create a single step with basic move command
            task_data['steps'] = [{
                'step_id': 1,
                'description': "Basic movement",
                'command': {
                    'command_type': 'move',
                    'parameters': {}
                }
            }]

        return TaskPlan(**task_data)

    def _extract_command_type(self, text: str) -> Optional[str]:
        """Extract command type from text."""
        text_lower = text.lower()

        # Check for command keywords
        command_keywords = {
            'move': ['move', 'go', 'navigate'],
            'pick': ['pick', 'grab', 'grasp'],
            'place': ['place', 'put', 'drop'],
            'rotate': ['rotate', 'turn', 'spin'],
            'wait': ['wait', 'pause', 'delay'],
            'stop': ['stop', 'halt', 'emergency'],
            'home': ['home', 'origin', 'zero'],
            'conveyor_start': ['conveyor', 'belt', 'start'],
            'conveyor_stop': ['conveyor', 'belt', 'stop']
        }

        for command, keywords in command_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return command

        return None

    def _extract_position(self, text: str) -> Optional[Dict[str, float]]:
        """Extract position coordinates from text."""
        # Look for coordinate patterns
        coord_patterns = [
            r'x[:\s]*(-?\d+\.?\d*)',
            r'y[:\s]*(-?\d+\.?\d*)',
            r'z[:\s]*(-?\d+\.?\d*)'
        ]

        position = {}
        for i, pattern in enumerate(coord_patterns):
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                coord_name = ['x', 'y', 'z'][i]
                try:
                    position[coord_name] = float(matches[0])
                except ValueError:
                    continue

        return position if len(position) >= 2 else None

    def _extract_speed(self, text: str) -> Optional[float]:
        """Extract speed value from text."""
        speed_patterns = [
            r'speed[:\s]*(\d+\.?\d*)',
            r'velocity[:\s]*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*%'
        ]

        for pattern in speed_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    speed = float(matches[0])
                    if 1.0 <= speed <= 100.0:
                        return speed
                except ValueError:
                    continue

        return None

    def _extract_steps(self, text: str) -> List[Dict[str, Any]]:
        """Extract task steps from text."""
        steps = []

        # Look for numbered steps
        step_pattern = r'(\d+)[\.\)]\s*([^\n]+)'
        matches = re.findall(step_pattern, text)

        for i, (step_num, description) in enumerate(matches, 1):
            # Try to determine command type from description
            command_type = self._extract_command_type(description)
            if not command_type:
                command_type = 'move'  # Default

            step = {
                'step_id': i,
                'description': description.strip(),
                'command': {
                    'command_type': command_type,
                    'parameters': {}
                }
            }

            # Try to extract position from description
            position = self._extract_position(description)
            if position:
                step['command']['position'] = position

            steps.append(step)

        return steps

    def validate_safety(self, command_or_plan: Union[RobotCommand, TaskPlan]) -> SafetyValidation:
        """
        Validate safety of a command or task plan.

        Args:
            command_or_plan: Robot command or task plan to validate

        Returns:
            Safety validation result
        """
        checks_performed = []
        warnings = []
        errors = []
        recommendations = []

        if isinstance(command_or_plan, RobotCommand):
            # Validate single command
            is_safe, command_checks, command_warnings, command_errors = self._validate_command_safety(command_or_plan)
            checks_performed.extend(command_checks)
            warnings.extend(command_warnings)
            errors.extend(command_errors)

        elif isinstance(command_or_plan, TaskPlan):
            # Validate task plan
            is_safe = True
            checks_performed.append("task_plan_validation")

            for step in command_or_plan.steps:
                step_safe, step_checks, step_warnings, step_errors = self._validate_command_safety(step.command)
                checks_performed.extend(step_checks)
                warnings.extend(step_warnings)
                errors.extend(step_errors)

                if not step_safe:
                    is_safe = False

        else:
            raise ValueError("Invalid input type for safety validation")

        # Determine if human approval is required
        requires_approval = len(errors) > 0 or len(warnings) > 2

        # Calculate confidence
        confidence = 1.0 - (len(errors) * 0.3 + len(warnings) * 0.1)
        confidence = max(0.0, min(1.0, confidence))

        return SafetyValidation(
            is_safe=is_safe and len(errors) == 0,
            confidence=confidence,
            checks_performed=checks_performed,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            requires_approval=requires_approval
        )

    def _validate_command_safety(self, command: RobotCommand) -> Tuple[bool, List[str], List[str], List[str]]:
        """Validate safety of a single command."""
        checks = []
        warnings = []
        errors = []
        is_safe = True

        # Check position limits
        if command.position:
            checks.append("position_limits")
            pos = command.position

            # Workspace limits (example values)
            if abs(pos.x) > 800:
                errors.append(f"X position {pos.x} exceeds workspace limits (±800mm)")
                is_safe = False
            if abs(pos.y) > 800:
                errors.append(f"Y position {pos.y} exceeds workspace limits (±800mm)")
                is_safe = False
            if pos.z < -100 or pos.z > 400:
                errors.append(f"Z position {pos.z} exceeds workspace limits (-100 to 400mm)")
                is_safe = False

        # Check speed limits
        checks.append("speed_limits")
        if command.speed > 80:
            warnings.append(f"High speed {command.speed}% may be unsafe")
        elif command.speed > 95:
            errors.append(f"Speed {command.speed}% exceeds safe limits")
            is_safe = False

        # Check command-specific safety
        if command.command_type == CommandType.CONVEYOR_START:
            checks.append("conveyor_safety")
            conveyor_speed = command.parameters.get('speed', 0)
            if conveyor_speed > 80:
                warnings.append(f"High conveyor speed {conveyor_speed} mm/s")

        return is_safe, checks, warnings, errors

    def get_parsing_stats(self) -> Dict[str, Any]:
        """Get parsing statistics."""
        stats = self.parsing_stats.copy()
        if stats['total_parses'] > 0:
            stats['success_rate'] = stats['successful_parses'] / stats['total_parses']
            stats['recovery_rate'] = stats['successful_recoveries'] / max(1, stats['recovery_attempts'])
        else:
            stats['success_rate'] = 0.0
            stats['recovery_rate'] = 0.0

        return stats

    def reset_stats(self) -> None:
        """Reset parsing statistics."""
        self.parsing_stats = {
            'total_parses': 0,
            'successful_parses': 0,
            'failed_parses': 0,
            'recovery_attempts': 0,
            'successful_recoveries': 0
        }
        logger.info("Parsing statistics reset")


# Convenience functions
def parse_command(llm_output: str) -> RobotCommand:
    """Quick command parsing."""
    parser = OutputParser()
    return parser.parse_robot_command(llm_output)


def parse_plan(llm_output: str) -> TaskPlan:
    """Quick plan parsing."""
    parser = OutputParser()
    return parser.parse_task_plan(llm_output)


def validate_safety(command_or_plan: Union[RobotCommand, TaskPlan]) -> SafetyValidation:
    """Quick safety validation."""
    parser = OutputParser()
    return parser.validate_safety(command_or_plan)
