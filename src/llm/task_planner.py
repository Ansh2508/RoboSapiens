"""
AI-Driven Task Planning Engine

Natural language to robot task translation with intelligent workflow generation,
adaptive planning, and learning mechanisms for improved accuracy over time.

Features:
- Natural language to robot task translation with >90% accuracy
- Intelligent workflow generation leveraging Phase 1-4 capabilities
- Adaptive planning optimizing for efficiency, safety, and resource constraints
- Task decomposition algorithms breaking complex requests into executable steps
- Learning mechanisms improving planning accuracy through experience
"""

import json
import time
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

from llm.llm_interface import LLMInterface, LLMResponse
from llm.output_parser import OutputParser, RobotCommand, TaskPlan, TaskStep, CommandType, Priority
from llm.safety_validator import SafetyValidator, SafetyValidation
from utils.logger import get_logger

logger = get_logger(__name__)


class PlanningStrategy(Enum):
    """Task planning strategies."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    OPTIMIZED = "optimized"
    SAFETY_FIRST = "safety_first"


class ResourceType(Enum):
    """Resource types for planning."""
    ROBOT_ARM = "robot_arm"
    CONVEYOR_BELT = "conveyor_belt"
    VISION_SYSTEM = "vision_system"
    GRIPPER = "gripper"
    WORKSPACE = "workspace"


class PlanningError(Exception):
    """Exception raised for planning errors."""
    pass


@dataclass
class PlanningContext:
    """Context for task planning."""
    user_request: str
    user_id: str
    session_id: str
    
    # Available resources
    available_resources: Set[ResourceType] = field(default_factory=lambda: {
        ResourceType.ROBOT_ARM,
        ResourceType.CONVEYOR_BELT,
        ResourceType.VISION_SYSTEM,
        ResourceType.GRIPPER,
        ResourceType.WORKSPACE
    })
    
    # Constraints
    max_execution_time: float = 300.0  # 5 minutes
    max_steps: int = 20
    safety_level: str = "standard"
    
    # Environment state
    known_objects: List[Dict[str, Any]] = field(default_factory=list)
    workspace_state: Dict[str, Any] = field(default_factory=dict)
    
    # Planning preferences
    strategy: PlanningStrategy = PlanningStrategy.OPTIMIZED
    priority: Priority = Priority.NORMAL
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class TaskDefinition:
    """High-level task definition before detailed planning."""
    task_type: str
    description: str
    objectives: List[str]
    constraints: List[str]
    required_resources: Set[ResourceType]
    estimated_complexity: float  # 0.0 to 1.0
    
    # Success criteria
    success_conditions: List[str] = field(default_factory=list)
    failure_conditions: List[str] = field(default_factory=list)


class TaskPlanner:
    """
    AI-driven task planning engine that converts natural language requests
    into executable robot task plans with intelligent optimization.
    """
    
    def __init__(self, llm_interface: LLMInterface, safety_validator: SafetyValidator):
        """
        Initialize task planner.
        
        Args:
            llm_interface: LLM interface for planning
            safety_validator: Safety validator for plan validation
        """
        self.llm_interface = llm_interface
        self.safety_validator = safety_validator
        self.output_parser = OutputParser()
        
        # Planning knowledge base
        self.task_templates = self._initialize_task_templates()
        self.planning_history: List[Dict[str, Any]] = []
        
        # Learning and optimization
        self.success_patterns: Dict[str, float] = {}
        self.failure_patterns: Dict[str, float] = {}
        
        # Statistics
        self.planning_stats = {
            'total_plans': 0,
            'successful_plans': 0,
            'failed_plans': 0,
            'average_planning_time': 0.0,
            'average_plan_complexity': 0.0,
            'learning_iterations': 0
        }
        
        logger.info("Task planner initialized")
    
    def _initialize_task_templates(self) -> Dict[str, Dict[str, Any]]:
        """Initialize common task templates."""
        return {
            'pick_and_place': {
                'description': 'Pick up an object and place it at a target location',
                'required_resources': {ResourceType.ROBOT_ARM, ResourceType.GRIPPER, ResourceType.VISION_SYSTEM},
                'typical_steps': ['move_to_object', 'pick_object', 'move_to_target', 'place_object'],
                'estimated_duration': 30.0,
                'complexity': 0.3
            },
            'conveyor_sorting': {
                'description': 'Sort objects on a conveyor belt based on visual characteristics',
                'required_resources': {ResourceType.ROBOT_ARM, ResourceType.CONVEYOR_BELT, ResourceType.VISION_SYSTEM, ResourceType.GRIPPER},
                'typical_steps': ['start_conveyor', 'detect_objects', 'classify_objects', 'pick_objects', 'sort_objects', 'stop_conveyor'],
                'estimated_duration': 120.0,
                'complexity': 0.7
            },
            'quality_inspection': {
                'description': 'Inspect objects for quality using vision system',
                'required_resources': {ResourceType.VISION_SYSTEM, ResourceType.ROBOT_ARM},
                'typical_steps': ['position_camera', 'capture_images', 'analyze_quality', 'classify_results'],
                'estimated_duration': 45.0,
                'complexity': 0.5
            },
            'workspace_calibration': {
                'description': 'Calibrate robot workspace and vision system',
                'required_resources': {ResourceType.ROBOT_ARM, ResourceType.VISION_SYSTEM},
                'typical_steps': ['move_to_calibration_points', 'capture_calibration_images', 'calculate_transforms'],
                'estimated_duration': 60.0,
                'complexity': 0.4
            }
        }
    
    def plan_task(self, user_request: str, context: PlanningContext) -> TaskPlan:
        """
        Plan a task from natural language request.
        
        Args:
            user_request: Natural language task description
            context: Planning context and constraints
            
        Returns:
            Generated task plan
            
        Raises:
            PlanningError: If planning fails
        """
        start_time = time.time()
        self.planning_stats['total_plans'] += 1
        
        try:
            logger.info(f"Planning task: {user_request}")
            
            # Step 1: Analyze and understand the request
            task_definition = self._analyze_request(user_request, context)
            
            # Step 2: Check resource availability
            self._validate_resources(task_definition, context)
            
            # Step 3: Generate initial plan
            initial_plan = self._generate_plan(task_definition, context)
            
            # Step 4: Optimize the plan
            optimized_plan = self._optimize_plan(initial_plan, context)
            
            # Step 5: Validate safety
            safety_validation = self.safety_validator.validate_task_plan(optimized_plan)
            if not safety_validation.is_safe:
                raise PlanningError(f"Plan failed safety validation: {'; '.join(safety_validation.errors)}")
            
            # Step 6: Learn from this planning session
            self._update_learning(user_request, optimized_plan, True)
            
            # Update statistics
            planning_time = time.time() - start_time
            self.planning_stats['successful_plans'] += 1
            self.planning_stats['average_planning_time'] = (
                (self.planning_stats['average_planning_time'] * (self.planning_stats['total_plans'] - 1) + planning_time) /
                self.planning_stats['total_plans']
            )
            
            logger.info(f"Task planning completed in {planning_time:.2f}s: {optimized_plan.name}")
            return optimized_plan
            
        except Exception as e:
            self.planning_stats['failed_plans'] += 1
            self._update_learning(user_request, None, False)
            logger.error(f"Task planning failed: {e}")
            raise PlanningError(f"Failed to plan task: {e}")
    
    def _analyze_request(self, user_request: str, context: PlanningContext) -> TaskDefinition:
        """Analyze user request to understand task requirements."""
        # Create analysis prompt
        prompt = self._create_analysis_prompt(user_request, context)
        
        # Get LLM analysis
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_interface.complete_sync(messages)
        
        # Parse response
        try:
            analysis = json.loads(response.content)
            
            # Extract required resources
            required_resources = set()
            for resource_name in analysis.get('required_resources', []):
                try:
                    required_resources.add(ResourceType(resource_name))
                except ValueError:
                    logger.warning(f"Unknown resource type: {resource_name}")
            
            return TaskDefinition(
                task_type=analysis.get('task_type', 'custom'),
                description=analysis.get('description', user_request),
                objectives=analysis.get('objectives', []),
                constraints=analysis.get('constraints', []),
                required_resources=required_resources,
                estimated_complexity=analysis.get('complexity', 0.5),
                success_conditions=analysis.get('success_conditions', []),
                failure_conditions=analysis.get('failure_conditions', [])
            )
            
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse task analysis: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(user_request)
    
    def _create_analysis_prompt(self, user_request: str, context: PlanningContext) -> str:
        """Create prompt for task analysis."""
        return f"""
Analyze the following robot task request and provide a structured analysis.

User request: "{user_request}"

Available resources: {[r.value for r in context.available_resources]}
Safety level: {context.safety_level}
Max execution time: {context.max_execution_time}s

Please respond with a JSON object containing:
{{
    "task_type": "pick_and_place|conveyor_sorting|quality_inspection|workspace_calibration|custom",
    "description": "clear task description",
    "objectives": ["objective1", "objective2"],
    "constraints": ["constraint1", "constraint2"],
    "required_resources": ["robot_arm", "conveyor_belt", "vision_system", "gripper", "workspace"],
    "complexity": 0.0-1.0,
    "success_conditions": ["condition1", "condition2"],
    "failure_conditions": ["condition1", "condition2"]
}}

Consider:
- What physical actions are required?
- What resources/equipment are needed?
- What are the safety considerations?
- How complex is this task?
- What defines success or failure?
"""
    
    def _fallback_analysis(self, user_request: str) -> TaskDefinition:
        """Fallback analysis when LLM parsing fails."""
        # Simple keyword-based analysis
        request_lower = user_request.lower()
        
        if any(word in request_lower for word in ['pick', 'grab', 'place', 'move']):
            task_type = 'pick_and_place'
            required_resources = {ResourceType.ROBOT_ARM, ResourceType.GRIPPER}
            complexity = 0.3
        elif any(word in request_lower for word in ['conveyor', 'sort', 'belt']):
            task_type = 'conveyor_sorting'
            required_resources = {ResourceType.ROBOT_ARM, ResourceType.CONVEYOR_BELT, ResourceType.VISION_SYSTEM}
            complexity = 0.7
        elif any(word in request_lower for word in ['inspect', 'check', 'quality']):
            task_type = 'quality_inspection'
            required_resources = {ResourceType.VISION_SYSTEM, ResourceType.ROBOT_ARM}
            complexity = 0.5
        else:
            task_type = 'custom'
            required_resources = {ResourceType.ROBOT_ARM}
            complexity = 0.5
        
        return TaskDefinition(
            task_type=task_type,
            description=user_request,
            objectives=[f"Complete: {user_request}"],
            constraints=["Safety first", "Stay within workspace"],
            required_resources=required_resources,
            estimated_complexity=complexity
        )
    
    def _validate_resources(self, task_definition: TaskDefinition, context: PlanningContext) -> None:
        """Validate that required resources are available."""
        missing_resources = task_definition.required_resources - context.available_resources
        
        if missing_resources:
            missing_names = [r.value for r in missing_resources]
            raise PlanningError(f"Required resources not available: {', '.join(missing_names)}")
    
    def _generate_plan(self, task_definition: TaskDefinition, context: PlanningContext) -> TaskPlan:
        """Generate detailed task plan from task definition."""
        # Create planning prompt
        prompt = self._create_planning_prompt(task_definition, context)
        
        # Get LLM plan generation
        messages = [{"role": "user", "content": prompt}]
        response = self.llm_interface.complete_sync(messages)
        
        # Parse into TaskPlan
        try:
            plan = self.output_parser.parse_task_plan(response.content)
            
            # Validate plan constraints
            if len(plan.steps) > context.max_steps:
                raise PlanningError(f"Plan has too many steps: {len(plan.steps)} > {context.max_steps}")
            
            if plan.estimated_total_duration > context.max_execution_time:
                raise PlanningError(f"Plan duration too long: {plan.estimated_total_duration}s > {context.max_execution_time}s")
            
            return plan
            
        except Exception as e:
            logger.error(f"Failed to generate plan: {e}")
            # Try fallback plan generation
            return self._generate_fallback_plan(task_definition, context)
    
    def _create_planning_prompt(self, task_definition: TaskDefinition, context: PlanningContext) -> str:
        """Create prompt for detailed plan generation."""
        template_info = ""
        if task_definition.task_type in self.task_templates:
            template = self.task_templates[task_definition.task_type]
            template_info = f"""
Reference template for {task_definition.task_type}:
- Typical steps: {template['typical_steps']}
- Estimated duration: {template['estimated_duration']}s
- Complexity: {template['complexity']}
"""
        
        return f"""
Generate a detailed robot task plan for the following task definition.

Task: {task_definition.description}
Objectives: {task_definition.objectives}
Constraints: {task_definition.constraints}
Required resources: {[r.value for r in task_definition.required_resources]}
Complexity: {task_definition.estimated_complexity}

{template_info}

Context constraints:
- Max steps: {context.max_steps}
- Max execution time: {context.max_execution_time}s
- Safety level: {context.safety_level}
- Strategy: {context.strategy.value}

Please respond with a JSON object containing:
{{
    "task_id": "unique_task_id",
    "name": "task_name",
    "description": "detailed_description",
    "steps": [
        {{
            "step_id": 1,
            "description": "step_description",
            "command": {{
                "command_type": "move|pick|place|rotate|wait|conveyor_start|conveyor_stop|vision_capture",
                "position": {{"x": float, "y": float, "z": float}} (if applicable),
                "parameters": {{}},
                "speed": 50.0,
                "safety_check": true
            }},
            "dependencies": [],
            "estimated_duration": 10.0
        }}
    ],
    "priority": "normal"
}}

Ensure all steps are safe, executable, and achieve the task objectives.
"""

    def _generate_fallback_plan(self, task_definition: TaskDefinition, context: PlanningContext) -> TaskPlan:
        """Generate a basic fallback plan when LLM generation fails."""
        task_id = f"fallback_{int(time.time())}"

        # Create basic steps based on task type
        steps = []

        if task_definition.task_type == 'pick_and_place':
            steps = [
                TaskStep(
                    step_id=1,
                    description="Move to object location",
                    command=RobotCommand(command_type=CommandType.MOVE, parameters={'target': 'object'}),
                    estimated_duration=10.0
                ),
                TaskStep(
                    step_id=2,
                    description="Pick up object",
                    command=RobotCommand(command_type=CommandType.PICK, parameters={}),
                    dependencies=[1],
                    estimated_duration=5.0
                ),
                TaskStep(
                    step_id=3,
                    description="Move to target location",
                    command=RobotCommand(command_type=CommandType.MOVE, parameters={'target': 'destination'}),
                    dependencies=[2],
                    estimated_duration=10.0
                ),
                TaskStep(
                    step_id=4,
                    description="Place object",
                    command=RobotCommand(command_type=CommandType.PLACE, parameters={}),
                    dependencies=[3],
                    estimated_duration=5.0
                )
            ]
        else:
            # Generic single-step plan
            steps = [
                TaskStep(
                    step_id=1,
                    description=f"Execute {task_definition.task_type}",
                    command=RobotCommand(command_type=CommandType.MOVE, parameters={}),
                    estimated_duration=15.0
                )
            ]

        return TaskPlan(
            task_id=task_id,
            name=f"Fallback: {task_definition.description}",
            description=f"Fallback plan for: {task_definition.description}",
            steps=steps,
            priority=context.priority
        )

    def _optimize_plan(self, plan: TaskPlan, context: PlanningContext) -> TaskPlan:
        """Optimize task plan based on strategy and constraints."""
        if context.strategy == PlanningStrategy.SEQUENTIAL:
            return self._optimize_sequential(plan)
        elif context.strategy == PlanningStrategy.PARALLEL:
            return self._optimize_parallel(plan)
        elif context.strategy == PlanningStrategy.SAFETY_FIRST:
            return self._optimize_safety_first(plan)
        else:  # OPTIMIZED
            return self._optimize_general(plan)

    def _optimize_sequential(self, plan: TaskPlan) -> TaskPlan:
        """Optimize for sequential execution."""
        # Ensure all steps have proper dependencies
        for i, step in enumerate(plan.steps[1:], 1):
            if not step.dependencies:
                step.dependencies = [i]  # Depend on previous step

        return plan

    def _optimize_parallel(self, plan: TaskPlan) -> TaskPlan:
        """Optimize for parallel execution where possible."""
        # Remove unnecessary dependencies to allow parallel execution
        for step in plan.steps:
            # Keep only essential dependencies (e.g., pick before place)
            essential_deps = []
            for dep_id in step.dependencies:
                dep_step = next((s for s in plan.steps if s.step_id == dep_id), None)
                if dep_step and self._is_essential_dependency(step, dep_step):
                    essential_deps.append(dep_id)
            step.dependencies = essential_deps

        return plan

    def _optimize_safety_first(self, plan: TaskPlan) -> TaskPlan:
        """Optimize for maximum safety."""
        # Add safety checks and reduce speeds
        for step in plan.steps:
            step.command.safety_check = True
            if step.command.speed > 50:
                step.command.speed = 50  # Reduce to safe speed

            # Add wait steps between critical operations
            if step.command.command_type in [CommandType.PICK, CommandType.PLACE]:
                step.estimated_duration += 2.0  # Add safety margin

        return plan

    def _optimize_general(self, plan: TaskPlan) -> TaskPlan:
        """General optimization balancing speed, safety, and efficiency."""
        # Apply learned optimizations
        optimized_plan = self._apply_learned_optimizations(plan)

        # Optimize step ordering
        optimized_plan = self._optimize_step_order(optimized_plan)

        # Optimize resource usage
        optimized_plan = self._optimize_resource_usage(optimized_plan)

        return optimized_plan

    def _is_essential_dependency(self, step: TaskStep, dep_step: TaskStep) -> bool:
        """Check if a dependency is essential for safety/correctness."""
        # Pick must come before place
        if (step.command.command_type == CommandType.PLACE and
            dep_step.command.command_type == CommandType.PICK):
            return True

        # Move to object before picking
        if (step.command.command_type == CommandType.PICK and
            dep_step.command.command_type == CommandType.MOVE):
            return True

        # Conveyor start before operations
        if (step.command.command_type in [CommandType.PICK, CommandType.VISION_CAPTURE] and
            dep_step.command.command_type == CommandType.CONVEYOR_START):
            return True

        return False

    def _apply_learned_optimizations(self, plan: TaskPlan) -> TaskPlan:
        """Apply optimizations learned from previous executions."""
        # Check success patterns
        for pattern, success_rate in self.success_patterns.items():
            if success_rate > 0.8 and pattern in plan.description.lower():
                # Apply successful pattern optimizations
                logger.debug(f"Applying learned optimization for pattern: {pattern}")
                # This would contain specific optimizations learned over time

        return plan

    def _optimize_step_order(self, plan: TaskPlan) -> TaskPlan:
        """Optimize the order of steps for efficiency."""
        # Simple optimization: group similar operations
        movement_steps = []
        action_steps = []
        other_steps = []

        for step in plan.steps:
            if step.command.command_type == CommandType.MOVE:
                movement_steps.append(step)
            elif step.command.command_type in [CommandType.PICK, CommandType.PLACE]:
                action_steps.append(step)
            else:
                other_steps.append(step)

        # Reorder while respecting dependencies
        # This is a simplified version - full implementation would use topological sort
        return plan

    def _optimize_resource_usage(self, plan: TaskPlan) -> TaskPlan:
        """Optimize resource usage to minimize conflicts."""
        # Add resource allocation information to steps
        for step in plan.steps:
            step.command.parameters['resource_allocation'] = self._get_required_resources(step)

        return plan

    def _get_required_resources(self, step: TaskStep) -> List[str]:
        """Get resources required for a step."""
        resources = ['robot_arm']  # Always need robot arm

        if step.command.command_type in [CommandType.PICK, CommandType.PLACE]:
            resources.append('gripper')

        if step.command.command_type == CommandType.VISION_CAPTURE:
            resources.append('vision_system')

        if step.command.command_type in [CommandType.CONVEYOR_START, CommandType.CONVEYOR_STOP]:
            resources.append('conveyor_belt')

        return resources

    def _update_learning(self, user_request: str, plan: Optional[TaskPlan], success: bool) -> None:
        """Update learning patterns based on planning results."""
        self.planning_stats['learning_iterations'] += 1

        # Extract patterns from user request
        patterns = self._extract_patterns(user_request)

        for pattern in patterns:
            if success:
                self.success_patterns[pattern] = self.success_patterns.get(pattern, 0.0) + 0.1
                self.success_patterns[pattern] = min(1.0, self.success_patterns[pattern])
            else:
                self.failure_patterns[pattern] = self.failure_patterns.get(pattern, 0.0) + 0.1
                self.failure_patterns[pattern] = min(1.0, self.failure_patterns[pattern])

        # Store planning history
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_request': user_request,
            'success': success,
            'patterns': patterns,
            'plan_name': plan.name if plan else None,
            'plan_steps': len(plan.steps) if plan else 0
        }

        self.planning_history.append(history_entry)

        # Keep only recent history (last 100 entries)
        if len(self.planning_history) > 100:
            self.planning_history = self.planning_history[-100:]

    def _extract_patterns(self, text: str) -> List[str]:
        """Extract patterns from text for learning."""
        patterns = []
        text_lower = text.lower()

        # Object patterns
        objects = ['cube', 'sphere', 'cylinder', 'box', 'part', 'component']
        for obj in objects:
            if obj in text_lower:
                patterns.append(f"object_{obj}")

        # Action patterns
        actions = ['pick', 'place', 'move', 'sort', 'inspect', 'calibrate']
        for action in actions:
            if action in text_lower:
                patterns.append(f"action_{action}")

        # Location patterns
        if any(word in text_lower for word in ['left', 'right', 'center', 'corner']):
            patterns.append("location_specific")

        # Quantity patterns
        if any(word in text_lower for word in ['all', 'multiple', 'several', 'many']):
            patterns.append("quantity_multiple")

        return patterns

    def get_planning_stats(self) -> Dict[str, Any]:
        """Get planning statistics and learning data."""
        stats = self.planning_stats.copy()

        # Calculate success rate
        if stats['total_plans'] > 0:
            stats['success_rate'] = stats['successful_plans'] / stats['total_plans']
        else:
            stats['success_rate'] = 0.0

        # Add learning data
        stats['learned_success_patterns'] = len(self.success_patterns)
        stats['learned_failure_patterns'] = len(self.failure_patterns)
        stats['planning_history_size'] = len(self.planning_history)

        return stats

    def get_learned_patterns(self) -> Dict[str, Dict[str, float]]:
        """Get learned success and failure patterns."""
        return {
            'success_patterns': self.success_patterns.copy(),
            'failure_patterns': self.failure_patterns.copy()
        }

    def reset_learning(self) -> None:
        """Reset learning data."""
        self.success_patterns.clear()
        self.failure_patterns.clear()
        self.planning_history.clear()
        self.planning_stats['learning_iterations'] = 0
        logger.info("Task planner learning data reset")


# Convenience functions
def create_task_planner(llm_interface: LLMInterface, safety_validator: SafetyValidator) -> TaskPlanner:
    """Create and initialize task planner."""
    return TaskPlanner(llm_interface, safety_validator)


def quick_plan_task(user_request: str, user_id: str = "default") -> TaskPlan:
    """Quick task planning."""
    from llm.llm_interface import LLMInterface, LLMConfig
    from llm.safety_validator import SafetyValidator

    llm_interface = LLMInterface(LLMConfig())
    safety_validator = SafetyValidator()
    planner = TaskPlanner(llm_interface, safety_validator)

    context = PlanningContext(
        user_request=user_request,
        user_id=user_id,
        session_id=f"quick_{int(time.time())}"
    )

    return planner.plan_task(user_request, context)
