"""
Automation Engine Module (Phase 6.1 & 6.2)
Task-based workflow automation for orders and sales.
"""
from .service import AutomationService
from .order_triggers import OrderAutomationTriggers
from .schemas import (
    TaskCreate,
    TaskResponse,
    TaskListResponse,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentComplete,
    TaskEventResponse,
)

__all__ = [
    "AutomationService",
    "OrderAutomationTriggers",
    "TaskCreate",
    "TaskResponse",
    "TaskListResponse",
    "AssignmentCreate",
    "AssignmentResponse",
    "AssignmentComplete",
    "TaskEventResponse",
]
