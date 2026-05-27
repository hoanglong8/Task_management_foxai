from pydantic import BaseModel, EmailStr
from datetime import datetime
from backend.models.user import UserRole
from typing import Optional


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.member
    department: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    department: Optional[str] = None
    telegram_id: Optional[str] = None
    zalo_id: Optional[str] = None
    facebook_id: Optional[str] = None
    whatsapp_phone: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: UserRole
    department: Optional[str]
    telegram_id: Optional[str]
    zalo_id: Optional[str]
    facebook_id: Optional[str]
    whatsapp_phone: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
