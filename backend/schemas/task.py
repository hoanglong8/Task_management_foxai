from pydantic import BaseModel
from datetime import date, datetime
from backend.models.task import TaskStatus
from typing import Optional, List


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    deadline: Optional[date] = None
    project: Optional[str] = None
    notes: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    deadline: Optional[date] = None
    status: Optional[TaskStatus] = None
    project: Optional[str] = None
    notes: Optional[str] = None


class TaskHistoryOut(BaseModel):
    id: int
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    changed_by_name: Optional[str]
    changed_at: datetime

    model_config = {"from_attributes": True}


class TaskOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    project: Optional[str]
    notes: Optional[str]
    owner_id: Optional[int]
    owner_name: Optional[str]
    created_by: Optional[int]
    deadline: Optional[date]
    status: TaskStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskOutWithHistory(TaskOut):
    history: List[TaskHistoryOut] = []


class TaskFilter(BaseModel):
    status: Optional[TaskStatus] = None
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None
    project: Optional[str] = None
    deadline_before: Optional[date] = None
    deadline_after: Optional[date] = None
    search: Optional[str] = None
