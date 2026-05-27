"""Report Service — standup, weekly, deadline reminders."""
from datetime import date, timedelta
from sqlalchemy.orm import Session
from backend.models.task import Task, TaskStatus


def standup_report(db: Session) -> str:
    today = date.today()
    tasks = db.query(Task).filter(Task.status != TaskStatus.completed).order_by(Task.deadline).all()
    overdue = [t for t in tasks if t.deadline and t.deadline < today]
    due_today = [t for t in tasks if t.deadline == today]
    due_soon = [t for t in tasks if t.deadline and today < t.deadline <= today + timedelta(days=3)]
    in_progress = [t for t in tasks if t.status == TaskStatus.in_progress]

    lines = [f"🌅 STANDUP - {today.strftime('%d/%m/%Y')}"]

    if overdue:
        lines.append(f"\n🔴 QUÁ HẠN ({len(overdue)} tasks)")
        for t in overdue:
            days = (today - t.deadline).days
            lines.append(f"  #{t.id} {t.title} | @{t.owner_name or '?'} | Trễ {days} ngày")

    if due_today:
        lines.append(f"\n🟡 HÔM NAY ({len(due_today)} tasks)")
        for t in due_today:
            lines.append(f"  #{t.id} {t.title} | @{t.owner_name or '?'} | [{t.status.value}]")

    if due_soon:
        lines.append(f"\n🟠 3 NGÀY TỚI ({len(due_soon)} tasks)")
        for t in due_soon:
            days_left = (t.deadline - today).days
            lines.append(f"  #{t.id} {t.title} | @{t.owner_name or '?'} | còn {days_left} ngày")

    if in_progress:
        lines.append(f"\n🔵 ĐANG THỰC HIỆN ({len(in_progress)} tasks)")
        for t in in_progress:
            deadline_str = t.deadline.strftime('%d/%m') if t.deadline else 'N/A'
            lines.append(f"  #{t.id} {t.title} | @{t.owner_name or '?'} | Deadline: {deadline_str}")

    if not overdue and not due_today and not due_soon and not in_progress:
        lines.append("\n✅ Không có task nào cần chú ý hôm nay!")

    return "\n".join(lines)


def weekly_report(db: Session) -> str:
    today = date.today()
    week_end = today + timedelta(days=7)
    tasks = (
        db.query(Task)
        .filter(Task.deadline >= today, Task.deadline <= week_end, Task.status != TaskStatus.completed)
        .order_by(Task.deadline)
        .all()
    )
    by_day: dict[date, list] = {}
    for t in tasks:
        by_day.setdefault(t.deadline, []).append(t)

    lines = [f"📅 KẾ HOẠCH TUẦN - {today.strftime('%d/%m')} → {week_end.strftime('%d/%m/%Y')}"]
    if not by_day:
        lines.append("\n✅ Không có deadline nào trong tuần tới!")
    else:
        for d in sorted(by_day.keys()):
            day_tasks = by_day[d]
            lines.append(f"\n📌 {d.strftime('%A %d/%m')} ({len(day_tasks)} tasks):")
            for t in day_tasks:
                lines.append(f"  #{t.id} [{t.status.value}] {t.title} | @{t.owner_name or '?'}")
    return "\n".join(lines)


def deadline_reminder(db: Session) -> str:
    today = date.today()
    tasks = db.query(Task).filter(Task.status != TaskStatus.completed).all()
    overdue = [t for t in tasks if t.deadline and t.deadline < today]
    due_today = [t for t in tasks if t.deadline == today]
    due_tomorrow = [t for t in tasks if t.deadline == today + timedelta(days=1)]

    if not overdue and not due_today and not due_tomorrow:
        return ""

    lines = [f"⏰ NHẮC DEADLINE - {today.strftime('%d/%m/%Y')}"]
    if overdue:
        lines.append(f"\n🔴 Quá hạn: {len(overdue)} task")
        for t in overdue:
            lines.append(f"  #{t.id} {t.title} (@{t.owner_name or '?'})")
    if due_today:
        lines.append(f"\n🟡 Hôm nay: {len(due_today)} task")
        for t in due_today:
            lines.append(f"  #{t.id} {t.title} (@{t.owner_name or '?'})")
    if due_tomorrow:
        lines.append(f"\n🟠 Ngày mai: {len(due_tomorrow)} task")
        for t in due_tomorrow:
            lines.append(f"  #{t.id} {t.title} (@{t.owner_name or '?'})")
    return "\n".join(lines)
