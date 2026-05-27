from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.services.report_service import standup_report, weekly_report, deadline_reminder
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/standup")
def standup(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"report": standup_report(db)}


@router.get("/weekly")
def weekly(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"report": weekly_report(db)}


@router.get("/reminder")
def reminder(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"report": deadline_reminder(db)}
