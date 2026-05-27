from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base


class PlatformNotification(Base):
    __tablename__ = "platform_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    platform: Mapped[str] = mapped_column(String(20))  # telegram|zalo|facebook|whatsapp|web
    message_type: Mapped[str] = mapped_column(String(50))  # deadline_reminder|task_assigned|task_updated
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent|failed|read
