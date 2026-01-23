"""
Pydantic schemas for the automation engine.
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field

from app.db.enums import AutomationTaskType, AutomationTaskStatus, AssignmentStatus, TaskEventType


# ---------------------- Task Schemas ----------------------

class TaskCreate(BaseModel):
    """Schema for creating a new task"""
    task_type: AutomationTaskType
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    related_order_id: Optional[int] = None
    metadata: Optional[dict[str, Any]] = None
    required_role: Optional[str] = None


class TaskResponse(BaseModel):
    """Schema for task response"""
    id: int
    task_type: AutomationTaskType
    status: AutomationTaskStatus
    title: str
    description: Optional[str]
    created_by_id: int
    related_order_id: Optional[int]
    metadata: Optional[dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]
    assignments: list["AssignmentResponse"] = []
    
    class Config:
        from_attributes = True


class TaskListResponse(BaseModel):
    """Schema for listing tasks (wrapper with pagination)"""
    tasks: list["TaskResponse"] = []
    total: int = 0
    
    class Config:
        from_attributes = True


# ---------------------- Assignment Schemas ----------------------

class AssignmentCreate(BaseModel):
    """Schema for creating a task assignment"""
    user_id: int
    role_hint: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class AssignmentResponse(BaseModel):
    """Schema for assignment response"""
    id: int
    task_id: int
    user_id: int
    role_hint: Optional[str]
    status: AssignmentStatus
    notes: Optional[str]
    assigned_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AssignmentComplete(BaseModel):
    """Schema for completing an assignment"""
    notes: Optional[str] = None


# ---------------------- Event Schemas ----------------------

class TaskEventResponse(BaseModel):
    """Schema for task event response"""
    id: int
    task_id: int
    user_id: Optional[int]
    event_type: TaskEventType
    metadata: Optional[dict[str, Any]]
    created_at: datetime
    
    class Config:
        from_attributes = True


class ClaimRequest(BaseModel):
    """Schema for claim endpoint"""
    override: bool = False


# Update forward references
TaskResponse.model_rebuild()