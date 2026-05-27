"""TaskService — port của TaskManager từ foxai_task_bot.py lên SQLAlchemy + multi-user."""
from datetime import date, datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from backend.models.task import Task, TaskHistory, TaskStatus
from backend.models.user import User
from backend.schemas.task import TaskCreate, TaskUpdate, TaskFilter


def _record_change(
    db: Session,
    task: Task,
    changed_by: Optional[User],
    field: str,
    old_val,
    new_val,
) -> None:
    if str(old_val) == str(new_val):
        return
    entry = TaskHistory(
        task_id=task.id,
        changed_by=changed_by.id if changed_by else None,
        changed_by_name=changed_by.full_name if changed_by else "system",
        field_name=field,
        old_value=str(old_val) if old_val is not None else None,
        new_value=str(new_val) if new_val is not None else None,
    )
    db.add(entry)


def create_task(db: Session, data: TaskCreate, created_by: Optional[User] = None) -> Task:
    task = Task(
        title=data.title,
        description=data.description,
        owner_id=data.owner_id,
        owner_name=data.owner_name,
        deadline=data.deadline,
        project=data.project,
        notes=data.notes,
        status=TaskStatus.pending,
        created_by=created_by.id if created_by else None,
    )
    db.add(task)
    db.flush()
    _record_change(db, task, created_by, "created", None, data.title)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: int) -> Optional[Task]:
    return db.query(Task).filter(Task.id == task_id).first()


def list_tasks(
    db: Session,
    filters: Optional[TaskFilter] = None,
    current_user: Optional[User] = None,
) -> List[Task]:
    q = db.query(Task)

    if filters:
        if filters.status:
            q = q.filter(Task.status == filters.status)
        if filters.owner_id:
            q = q.filter(Task.owner_id == filters.owner_id)
        if filters.owner_name:
            q = q.filter(Task.owner_name.ilike(f"%{filters.owner_name}%"))
        if filters.project:
            q = q.filter(Task.project.ilike(f"%{filters.project}%"))
        if filters.deadline_before:
            q = q.filter(Task.deadline <= filters.deadline_before)
        if filters.deadline_after:
            q = q.filter(Task.deadline >= filters.deadline_after)
        if filters.search:
            q = q.filter(
                or_(
                    Task.title.ilike(f"%{filters.search}%"),
                    Task.project.ilike(f"%{filters.search}%"),
                )
            )

    return q.order_by(Task.id.desc()).all()


def update_task(
    db: Session,
    task_id: int,
    data: TaskUpdate,
    changed_by: Optional[User] = None,
) -> Optional[Task]:
    task = get_task(db, task_id)
    if not task:
        return None

    fields = data.model_dump(exclude_unset=True)
    for field, new_val in fields.items():
        old_val = getattr(task, field)
        _record_change(db, task, changed_by, field, old_val, new_val)
        setattr(task, field, new_val)

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id: int, deleted_by: Optional[User] = None) -> Optional[Task]:
    task = get_task(db, task_id)
    if not task:
        return None
    _record_change(db, task, deleted_by, "deleted", task.title, None)
    db.delete(task)
    db.commit()
    return task


def get_summary(db: Session) -> dict:
    tasks = db.query(Task).all()
    today = date.today()
    overdue = [t for t in tasks if t.deadline and t.deadline < today and t.status != TaskStatus.completed]
    return {
        "total": len(tasks),
        "pending": sum(1 for t in tasks if t.status == TaskStatus.pending),
        "in_progress": sum(1 for t in tasks if t.status == TaskStatus.in_progress),
        "completed": sum(1 for t in tasks if t.status == TaskStatus.completed),
        "overdue": len(overdue),
    }


def get_tasks_by_deadline_range(db: Session, start: date, end: date) -> List[Task]:
    return (
        db.query(Task)
        .filter(Task.deadline >= start, Task.deadline <= end, Task.status != TaskStatus.completed)
        .order_by(Task.deadline)
        .all()
    )


def update_tasks_by_keyword(
    db: Session,
    keyword: str,
    data: TaskUpdate,
    changed_by: Optional[User] = None,
) -> List[Task]:
    """Update all active tasks whose title contains keyword (used by NLP keyword-based updates)."""
    tasks = (
        db.query(Task)
        .filter(Task.title.ilike(f"%{keyword}%"), Task.status != TaskStatus.completed)
        .all()
    )
    updated = []
    for task in tasks:
        fields = data.model_dump(exclude_unset=True)
        for field, new_val in fields.items():
            old_val = getattr(task, field)
            _record_change(db, task, changed_by, field, old_val, new_val)
            setattr(task, field, new_val)
        task.updated_at = datetime.utcnow()
        updated.append(task)
    db.commit()
    return updated
