"""
Automation Engine Module (Phase 6.1, 6.2, 6.3)
Task-based workflow automation for orders, sales, and inventory.
"""
from .service import AutomationService
from .order_triggers import OrderAutomationTriggers
from .sales_triggers import SalesAutomationTriggers
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
    "SalesAutomationTriggers",
    "TaskCreate",
    "TaskResponse",
    "TaskListResponse",
    "AssignmentCreate",
    "AssignmentResponse",
    "AssignmentComplete",
    "TaskEventResponse",
]
