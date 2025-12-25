"""
Automation Engine Module (Phase 6.1)
Task-based workflow automation for orders and sales.
"""
from .service import AutomationService
from .schemas import (
    TaskCreate,
    TaskResponse,
    AssignmentCreate,
    AssignmentResponse,
    TaskEventResponse,
)

__all__ = [
    "AutomationService",
    "TaskCreate",
    "TaskResponse",
    "AssignmentCreate",
    "AssignmentResponse",
    "TaskEventResponse",
]
