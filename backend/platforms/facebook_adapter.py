"""Facebook Messenger Adapter — webhook nhận tin nhắn từ Facebook Page."""
import hashlib
import hmac
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.services.auth_service import get_user_by_id
from backend.services import task_service, nlp_service, report_service
from backend.models.user import User

router = APIRouter(prefix="/webhooks/facebook", tags=["facebook"])
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = settings.facebook_app_secret
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _send_reply(recipient_id: str, message: str) -> None:
    token = settings.facebook_page_access_token
    if not token:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                "https://graph.facebook.com/v18.0/me/messages",
                params={"access_token": token},
                json={"recipient": {"id": recipient_id}, "message": {"text": message[:2000]}},
            )
    except Exception as e:
        logger.error(f"Facebook reply error: {e}")


@router.get("/")
async def fb_verify(request: Request):
    """Facebook webhook verification challenge."""
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.facebook_verify_token
    ):
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/")
async def fb_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    if data.get("object") != "page":
        return {"status": "ok"}

    for entry in data.get("entry", []):
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id", "")
            message = messaging.get("message", {})
            text = message.get("text", "").strip()
            if not sender_id or not text:
                continue

            # Find user by facebook_id
            user = db.query(User).filter(User.facebook_id == sender_id).first()
            if not user:
                await _send_reply(sender_id, "⚠️ Tài khoản Facebook của bạn chưa được liên kết. Liên hệ admin.")
                continue

            parsed = nlp_service.nlp.parse(text)
            intent = parsed.get("intent", "unknown")

            # Reuse Zalo dispatch logic
            from backend.platforms.zalo_adapter import _dispatch
            reply = _dispatch(db, user, parsed, intent)
            await _send_reply(sender_id, reply)

    return {"status": "ok"}
