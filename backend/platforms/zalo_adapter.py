"""Zalo OA Adapter — webhook nhận tin nhắn từ Zalo Official Account."""
import hashlib
import hmac
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.services.auth_service import get_user_by_zalo_id
from backend.services import task_service, nlp_service, report_service
from backend.schemas.task import TaskCreate, TaskUpdate

router = APIRouter(prefix="/webhooks/zalo", tags=["zalo"])
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = settings.zalo_webhook_secret
    if not secret:
        return True  # dev mode: skip verification
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _send_reply(zalo_user_id: str, message: str) -> None:
    token = settings.zalo_oa_access_token
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "https://openapi.zalo.me/v3.0/oa/message/cs",
                headers={"access_token": token},
                json={"recipient": {"user_id": zalo_user_id}, "message": {"text": message}},
            )
    except Exception as e:
        logger.error(f"Zalo reply error: {e}")


@router.get("/")
async def zalo_verify(request: Request):
    """Zalo OA webhook verification."""
    params = dict(request.query_params)
    challenge = params.get("challenge", "")
    return {"challenge": challenge}


@router.post("/")
async def zalo_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("X-ZEvent-Signature", "")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    event_type = data.get("event_name", "")

    if event_type != "user_send_text":
        return {"status": "ignored"}

    sender_id = data.get("sender", {}).get("id", "")
    message_text = data.get("message", {}).get("text", "").strip()
    if not sender_id or not message_text:
        return {"status": "ok"}

    user = get_user_by_zalo_id(db, sender_id)
    if not user:
        await _send_reply(sender_id, "⚠️ Tài khoản Zalo của bạn chưa được liên kết với hệ thống FOXAI. Liên hệ admin.")
        return {"status": "ok"}

    parsed = nlp_service.nlp.parse(message_text)
    intent = parsed.get("intent", "unknown")
    reply = _dispatch(db, user, parsed, intent)
    await _send_reply(sender_id, reply)
    return {"status": "ok"}


def _dispatch(db, user, parsed: dict, intent: str) -> str:
    try:
        if intent == "standup":
            return report_service.standup_report(db)
        elif intent == "weekly":
            return report_service.weekly_report(db)
        elif intent == "status":
            s = task_service.get_summary(db)
            return f"Tổng: {s['total']} | Chờ: {s['pending']} | Đang: {s['in_progress']} | Xong: {s['completed']}"
        elif intent == "list":
            from backend.schemas.task import TaskFilter
            from backend.models.user import UserRole
            filters = TaskFilter()
            if user.role == UserRole.member:
                filters.owner_id = user.id
            tasks = task_service.list_tasks(db, filters, user)
            if not tasks:
                return "✅ Không có task nào."
            lines = [f"#{t.id} {t.title} | @{t.owner_name} | {t.deadline}" for t in tasks[:10]]
            return "\n".join(lines)
        elif intent == "create":
            from backend.models.user import UserRole
            if user.role == UserRole.member:
                return "⚠️ Bạn cần quyền manager/admin để tạo task."
            if not parsed.get("title") or not parsed.get("owner") or not parsed.get("deadline"):
                return "⚠️ Cần đủ: tên task, người phụ trách, deadline."
            data = TaskCreate(title=parsed["title"], owner_name=parsed["owner"], deadline=parsed["deadline"])
            task = task_service.create_task(db, data, created_by=user)
            return f"✅ Tạo task #{task.id}: {task.title} | @{task.owner_name} | {task.deadline}"
        elif intent in ("update", "complete"):
            task_id = parsed.get("task_id")
            if task_id:
                upd = TaskUpdate()
                if intent == "complete":
                    upd.status = "completed"
                elif parsed.get("status"):
                    upd.status = parsed["status"]
                if parsed.get("deadline"):
                    upd.deadline = parsed["deadline"]
                task = task_service.update_task(db, task_id, upd, changed_by=user)
                return f"✅ Cập nhật task #{task_id}" if task else f"⚠️ Không tìm thấy task #{task_id}"
            return "⚠️ Vui lòng chỉ định task ID."
        else:
            return "🤔 Tôi chưa hiểu. Thử: 'danh sách task', 'standup', 'tạo task...'"
    except Exception as e:
        logger.error(f"Zalo dispatch error: {e}")
        return "⚠️ Có lỗi xảy ra, vui lòng thử lại."
