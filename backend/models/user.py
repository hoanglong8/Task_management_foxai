from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from backend.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    manager = "manager"
    member = "member"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.member)

    # Platform identifiers (nullable — user links accounts gradually)
    telegram_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    zalo_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    facebook_id: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)

    department: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
