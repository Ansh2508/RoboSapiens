"""
Decision Validation and Safety Framework

Comprehensive safety validation system for AI-driven robot decisions with
safety constraints, human-in-the-loop approval, and emergency override mechanisms.

Features:
- AI decision verification against safety constraints
- Physical limitation validation
- Human-in-the-loop approval systems
- Confidence scoring and uncertainty quantification
- Comprehensive audit trails
- Emergency override mechanisms
"""

import time
import json
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging

from llm.output_parser import RobotCommand, TaskPlan, SafetyValidation, CommandType
from utils.logger import get_logger

logger = get_logger(__name__)


class SafetyLevel(Enum):
    """Safety levels for operations."""
    MINIMAL = "minimal"
    STANDARD = "standard"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalStatus(Enum):
    """Human approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


class SafetyError(Exception):
    """Exception raised for safety violations."""
    pass


@dataclass
class SafetyConstraint:
    """Individual safety constraint definition."""
    constraint_id: str
    name: str
    description: str
    constraint_type: str  # "position", "speed", "force", "workspace", etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    severity: SafetyLevel = SafetyLevel.STANDARD
    enabled: bool = True
    
    def validate(self, command: RobotCommand) -> Tuple[bool, str]:
        """
        Validate command against this constraint.
        
        Args:
            command: Robot command to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # This is a base implementation - specific constraints would override
        return True, ""


@dataclass
class WorkspaceConstraint(SafetyConstraint):
    """Workspace boundary constraint."""
    
    def __post_init__(self):
        self.constraint_type = "workspace"
        if not self.parameters:
            # Default workspace limits for Niryo Ned2
            self.parameters = {
                'x_min': -800, 'x_max': 800,
                'y_min': -800, 'y_max': 800,
                'z_min': -100, 'z_max': 400
            }
    
    def validate(self, command: RobotCommand) -> Tuple[bool, str]:
        """Validate position is within workspace."""
        if not command.position:
            return True, ""
        
        pos = command.position
        params = self.parameters
        
        if pos.x < params['x_min'] or pos.x > params['x_max']:
            return False, f"X position {pos.x} outside workspace [{params['x_min']}, {params['x_max']}]"
        
        if pos.y < params['y_min'] or pos.y > params['y_max']:
            return False, f"Y position {pos.y} outside workspace [{params['y_min']}, {params['y_max']}]"
        
        if pos.z < params['z_min'] or pos.z > params['z_max']:
            return False, f"Z position {pos.z} outside workspace [{params['z_min']}, {params['z_max']}]"
        
        return True, ""


@dataclass
class SpeedConstraint(SafetyConstraint):
    """Speed limit constraint."""
    
    def __post_init__(self):
        self.constraint_type = "speed"
        if not self.parameters:
            self.parameters = {
                'max_speed': 80.0,  # Maximum safe speed percentage
                'warning_speed': 60.0  # Speed that triggers warning
            }
    
    def validate(self, command: RobotCommand) -> Tuple[bool, str]:
        """Validate speed is within safe limits."""
        speed = command.speed
        max_speed = self.parameters['max_speed']
        
        if speed > max_speed:
            return False, f"Speed {speed}% exceeds maximum safe speed {max_speed}%"
        
        return True, ""


@dataclass
class CollisionConstraint(SafetyConstraint):
    """Collision avoidance constraint."""
    
    def __post_init__(self):
        self.constraint_type = "collision"
        if not self.parameters:
            self.parameters = {
                'safety_margin': 50.0,  # Safety margin in mm
                'check_conveyor': True,
                'check_workspace_objects': True
            }
    
    def validate(self, command: RobotCommand) -> Tuple[bool, str]:
        """Validate command won't cause collisions."""
        # This would integrate with collision detection system
        # For now, basic validation
        
        if command.position and command.position.z < 0:
            margin = self.parameters['safety_margin']
            if command.position.z < -margin:
                return False, f"Position too close to table surface (Z={command.position.z})"
        
        return True, ""


@dataclass
class ApprovalRequest:
    """Human approval request."""
    request_id: str
    command_or_plan: Any  # RobotCommand or TaskPlan
    safety_issues: List[str]
    confidence: float
    requested_at: datetime = field(default_factory=datetime.now)
    timeout: float = 60.0  # Timeout in seconds
    
    # Approval details
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        return datetime.now() > self.requested_at + timedelta(seconds=self.timeout)


class SafetyValidator:
    """
    Comprehensive safety validation system for AI-driven robot decisions
    with human-in-the-loop approval and emergency override capabilities.
    """
    
    def __init__(self):
        """Initialize safety validator."""
        # Safety constraints
        self.constraints: List[SafetyConstraint] = []
        self._initialize_default_constraints()
        
        # Approval system
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_callback: Optional[Callable] = None
        
        # Statistics
        self.validation_stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'failed_validations': 0,
            'approvals_requested': 0,
            'approvals_granted': 0,
            'approvals_rejected': 0,
            'emergency_stops': 0
        }
        
        # Emergency state
        self.emergency_stop_active = False
        self.emergency_stop_reason = ""
        
        logger.info("Safety validator initialized")
    
    def _initialize_default_constraints(self) -> None:
        """Initialize default safety constraints."""
        # Workspace constraint
        self.constraints.append(WorkspaceConstraint(
            constraint_id="workspace_001",
            name="Primary Workspace",
            description="Main robot workspace boundaries"
        ))
        
        # Speed constraint
        self.constraints.append(SpeedConstraint(
            constraint_id="speed_001",
            name="Maximum Speed",
            description="Maximum safe movement speed"
        ))
        
        # Collision constraint
        self.constraints.append(CollisionConstraint(
            constraint_id="collision_001",
            name="Collision Avoidance",
            description="Basic collision avoidance"
        ))
        
        logger.info(f"Initialized {len(self.constraints)} default safety constraints")
    
    def add_constraint(self, constraint: SafetyConstraint) -> None:
        """Add a safety constraint."""
        self.constraints.append(constraint)
        logger.info(f"Added safety constraint: {constraint.name}")
    
    def remove_constraint(self, constraint_id: str) -> bool:
        """Remove a safety constraint."""
        for i, constraint in enumerate(self.constraints):
            if constraint.constraint_id == constraint_id:
                removed = self.constraints.pop(i)
                logger.info(f"Removed safety constraint: {removed.name}")
                return True
        return False
    
    def validate_command(self, command: RobotCommand, require_approval: bool = False) -> SafetyValidation:
        """
        Validate a robot command against all safety constraints.
        
        Args:
            command: Robot command to validate
            require_approval: Force human approval requirement
            
        Returns:
            Safety validation result
        """
        self.validation_stats['total_validations'] += 1
        
        if self.emergency_stop_active:
            return SafetyValidation(
                is_safe=False,
                confidence=1.0,
                errors=[f"Emergency stop active: {self.emergency_stop_reason}"],
                requires_approval=True
            )
        
        checks_performed = []
        warnings = []
        errors = []
        
        # Run all enabled constraints
        for constraint in self.constraints:
            if not constraint.enabled:
                continue
            
            try:
                is_valid, error_msg = constraint.validate(command)
                checks_performed.append(f"{constraint.constraint_type}_{constraint.constraint_id}")
                
                if not is_valid:
                    if constraint.severity in [SafetyLevel.CRITICAL, SafetyLevel.HIGH]:
                        errors.append(f"{constraint.name}: {error_msg}")
                    else:
                        warnings.append(f"{constraint.name}: {error_msg}")
                
            except Exception as e:
                logger.error(f"Error validating constraint {constraint.constraint_id}: {e}")
                errors.append(f"Constraint validation error: {constraint.name}")
        
        # Calculate confidence
        confidence = 1.0 - (len(errors) * 0.4 + len(warnings) * 0.1)
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine if safe
        is_safe = len(errors) == 0
        
        # Determine if approval required
        requires_approval = (
            require_approval or
            len(errors) > 0 or
            len(warnings) > 2 or
            confidence < 0.7 or
            command.command_type in [CommandType.CONVEYOR_START, CommandType.WORKFLOW_EXECUTE]
        )
        
        if is_safe:
            self.validation_stats['passed_validations'] += 1
        else:
            self.validation_stats['failed_validations'] += 1
        
        return SafetyValidation(
            is_safe=is_safe,
            confidence=confidence,
            checks_performed=checks_performed,
            warnings=warnings,
            errors=errors,
            requires_approval=requires_approval
        )
    
    def validate_task_plan(self, task_plan: TaskPlan, require_approval: bool = False) -> SafetyValidation:
        """
        Validate a complete task plan.
        
        Args:
            task_plan: Task plan to validate
            require_approval: Force human approval requirement
            
        Returns:
            Safety validation result
        """
        self.validation_stats['total_validations'] += 1
        
        if self.emergency_stop_active:
            return SafetyValidation(
                is_safe=False,
                confidence=1.0,
                errors=[f"Emergency stop active: {self.emergency_stop_reason}"],
                requires_approval=True
            )
        
        all_checks = []
        all_warnings = []
        all_errors = []
        min_confidence = 1.0
        
        # Validate each step
        for step in task_plan.steps:
            step_validation = self.validate_command(step.command, require_approval=False)
            
            all_checks.extend(step_validation.checks_performed)
            all_warnings.extend([f"Step {step.step_id}: {w}" for w in step_validation.warnings])
            all_errors.extend([f"Step {step.step_id}: {e}" for e in step_validation.errors])
            min_confidence = min(min_confidence, step_validation.confidence)
        
        # Additional plan-level validations
        all_checks.append("task_plan_structure")
        
        # Check for dangerous sequences
        if self._has_dangerous_sequence(task_plan):
            all_warnings.append("Task plan contains potentially dangerous command sequence")
            min_confidence *= 0.8
        
        # Determine overall safety
        is_safe = len(all_errors) == 0
        
        # Determine if approval required
        requires_approval = (
            require_approval or
            len(all_errors) > 0 or
            len(all_warnings) > 3 or
            min_confidence < 0.6 or
            task_plan.priority in ["high", "critical"]
        )
        
        if is_safe:
            self.validation_stats['passed_validations'] += 1
        else:
            self.validation_stats['failed_validations'] += 1
        
        return SafetyValidation(
            is_safe=is_safe,
            confidence=min_confidence,
            checks_performed=list(set(all_checks)),
            warnings=all_warnings,
            errors=all_errors,
            requires_approval=requires_approval
        )
    
    def _has_dangerous_sequence(self, task_plan: TaskPlan) -> bool:
        """Check for dangerous command sequences."""
        commands = [step.command.command_type for step in task_plan.steps]
        
        # Check for rapid direction changes
        direction_changes = 0
        for i in range(1, len(commands)):
            if commands[i] == CommandType.MOVE and commands[i-1] == CommandType.MOVE:
                direction_changes += 1
        
        if direction_changes > 5:
            return True
        
        # Check for conveyor operations without proper stops
        for i, cmd in enumerate(commands):
            if cmd == CommandType.CONVEYOR_START:
                # Look for corresponding stop within reasonable distance
                stop_found = False
                for j in range(i+1, min(i+10, len(commands))):
                    if commands[j] == CommandType.CONVEYOR_STOP:
                        stop_found = True
                        break
                if not stop_found:
                    return True
        
        return False

    def request_approval(self, command_or_plan: Any, safety_validation: SafetyValidation,
                        timeout: float = 60.0) -> str:
        """
        Request human approval for a command or plan.

        Args:
            command_or_plan: Command or plan requiring approval
            safety_validation: Safety validation result
            timeout: Approval timeout in seconds

        Returns:
            Approval request ID
        """
        request_id = f"approval_{int(time.time() * 1000)}"

        approval_request = ApprovalRequest(
            request_id=request_id,
            command_or_plan=command_or_plan,
            safety_issues=safety_validation.errors + safety_validation.warnings,
            confidence=safety_validation.confidence,
            timeout=timeout
        )

        self.pending_approvals[request_id] = approval_request
        self.validation_stats['approvals_requested'] += 1

        # Trigger approval callback if set
        if self.approval_callback:
            try:
                self.approval_callback(approval_request)
            except Exception as e:
                logger.error(f"Approval callback failed: {e}")

        logger.info(f"Approval requested: {request_id} (timeout: {timeout}s)")
        return request_id

    def check_approval_status(self, request_id: str) -> ApprovalStatus:
        """
        Check status of an approval request.

        Args:
            request_id: Approval request ID

        Returns:
            Current approval status
        """
        if request_id not in self.pending_approvals:
            return ApprovalStatus.TIMEOUT

        request = self.pending_approvals[request_id]

        # Check for timeout
        if request.is_expired() and request.status == ApprovalStatus.PENDING:
            request.status = ApprovalStatus.TIMEOUT
            logger.warning(f"Approval request {request_id} timed out")

        return request.status

    def approve_request(self, request_id: str, approved_by: str) -> bool:
        """
        Approve a pending request.

        Args:
            request_id: Approval request ID
            approved_by: Identifier of approver

        Returns:
            True if approval successful
        """
        if request_id not in self.pending_approvals:
            logger.error(f"Approval request {request_id} not found")
            return False

        request = self.pending_approvals[request_id]

        if request.status != ApprovalStatus.PENDING:
            logger.error(f"Approval request {request_id} not pending (status: {request.status})")
            return False

        if request.is_expired():
            request.status = ApprovalStatus.TIMEOUT
            logger.error(f"Approval request {request_id} has expired")
            return False

        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.now()

        self.validation_stats['approvals_granted'] += 1
        logger.info(f"Approval granted for request {request_id} by {approved_by}")

        return True

    def reject_request(self, request_id: str, rejected_by: str, reason: str) -> bool:
        """
        Reject a pending request.

        Args:
            request_id: Approval request ID
            rejected_by: Identifier of rejector
            reason: Rejection reason

        Returns:
            True if rejection successful
        """
        if request_id not in self.pending_approvals:
            logger.error(f"Approval request {request_id} not found")
            return False

        request = self.pending_approvals[request_id]

        if request.status != ApprovalStatus.PENDING:
            logger.error(f"Approval request {request_id} not pending (status: {request.status})")
            return False

        request.status = ApprovalStatus.REJECTED
        request.approved_by = rejected_by
        request.approved_at = datetime.now()
        request.rejection_reason = reason

        self.validation_stats['approvals_rejected'] += 1
        logger.info(f"Approval rejected for request {request_id} by {rejected_by}: {reason}")

        return True

    def emergency_stop(self, reason: str = "Manual emergency stop") -> None:
        """
        Activate emergency stop.

        Args:
            reason: Reason for emergency stop
        """
        self.emergency_stop_active = True
        self.emergency_stop_reason = reason
        self.validation_stats['emergency_stops'] += 1

        # Reject all pending approvals
        for request_id, request in self.pending_approvals.items():
            if request.status == ApprovalStatus.PENDING:
                request.status = ApprovalStatus.REJECTED
                request.rejection_reason = f"Emergency stop: {reason}"

        logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")

    def reset_emergency_stop(self, reset_by: str) -> bool:
        """
        Reset emergency stop state.

        Args:
            reset_by: Identifier of person resetting

        Returns:
            True if reset successful
        """
        if not self.emergency_stop_active:
            logger.warning("Emergency stop not active")
            return False

        self.emergency_stop_active = False
        old_reason = self.emergency_stop_reason
        self.emergency_stop_reason = ""

        logger.info(f"Emergency stop reset by {reset_by} (was: {old_reason})")
        return True

    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        stats = self.validation_stats.copy()

        # Calculate rates
        total = stats['total_validations']
        if total > 0:
            stats['pass_rate'] = stats['passed_validations'] / total
            stats['fail_rate'] = stats['failed_validations'] / total
        else:
            stats['pass_rate'] = 0.0
            stats['fail_rate'] = 0.0

        # Add current state
        stats['emergency_stop_active'] = self.emergency_stop_active
        stats['pending_approvals'] = len([req for req in self.pending_approvals.values()
                                         if req.status == ApprovalStatus.PENDING])
        stats['total_constraints'] = len(self.constraints)
        stats['enabled_constraints'] = len([c for c in self.constraints if c.enabled])

        return stats


# Convenience functions
def create_safety_validator() -> SafetyValidator:
    """Create and initialize safety validator."""
    return SafetyValidator()


def validate_command_safety(command: RobotCommand) -> SafetyValidation:
    """Quick command safety validation."""
    validator = SafetyValidator()
    return validator.validate_command(command)


def validate_plan_safety(task_plan: TaskPlan) -> SafetyValidation:
    """Quick plan safety validation."""
    validator = SafetyValidator()
    return validator.validate_task_plan(task_plan)
