from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.task import TaskStatus
from backend.schemas.task import TaskCreate, TaskUpdate, TaskOut, TaskOutWithHistory, TaskFilter
from backend.services import task_service
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _can_modify_task(task, current_user: User) -> bool:
    if current_user.role in (UserRole.admin, UserRole.manager):
        return True
    return task.owner_id == current_user.id


@router.post("/", response_model=TaskOut)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.member:
        raise HTTPException(status_code=403, detail="Member không thể tạo task cho người khác")
    return task_service.create_task(db, data, created_by=current_user)


@router.get("/", response_model=List[TaskOut])
def list_tasks(
    status: Optional[TaskStatus] = None,
    owner_id: Optional[int] = None,
    owner_name: Optional[str] = None,
    project: Optional[str] = None,
    deadline_before: Optional[date] = None,
    deadline_after: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filters = TaskFilter(
        status=status,
        owner_id=owner_id,
        owner_name=owner_name,
        project=project,
        deadline_before=deadline_before,
        deadline_after=deadline_after,
        search=search,
    )
    # Members only see their own tasks
    if current_user.role == UserRole.member:
        filters.owner_id = current_user.id
    return task_service.list_tasks(db, filters, current_user)


@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return task_service.get_summary(db)


@router.get("/{task_id}", response_model=TaskOutWithHistory)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    if current_user.role == UserRole.member and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Không có quyền xem task này")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    if not _can_modify_task(task, current_user):
        raise HTTPException(status_code=403, detail="Không có quyền cập nhật task này")
    # Members can only update status and notes on their own tasks
    if current_user.role == UserRole.member:
        allowed = {"status", "notes"}
        disallowed = set(data.model_dump(exclude_unset=True).keys()) - allowed
        if disallowed:
            raise HTTPException(status_code=403, detail=f"Member không thể thay đổi: {disallowed}")
    return task_service.update_task(db, task_id, data, changed_by=current_user)


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = task_service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    if current_user.role not in (UserRole.admin, UserRole.manager):
        raise HTTPException(status_code=403, detail="Chỉ admin/manager mới có thể xóa task")
    task_service.delete_task(db, task_id, deleted_by=current_user)
