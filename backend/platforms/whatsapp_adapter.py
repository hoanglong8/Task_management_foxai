"""WhatsApp Business API Adapter."""
import hashlib
import hmac
import logging
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.services import task_service, nlp_service, report_service
from backend.models.user import User

router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])
logger = logging.getLogger(__name__)


def _verify_signature(body: bytes, signature: str) -> bool:
    secret = settings.facebook_app_secret  # WhatsApp uses Facebook App Secret
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _send_reply(phone: str, message: str) -> None:
    token = settings.whatsapp_access_token
    phone_id = settings.whatsapp_phone_number_id
    if not token or not phone_id:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "text",
                    "text": {"body": message[:4096]},
                },
            )
    except Exception as e:
        logger.error(f"WhatsApp reply error: {e}")


@router.get("/")
async def wa_verify(request: Request):
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == settings.whatsapp_verify_token
    ):
        return int(params.get("hub.challenge", 0))
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/")
async def wa_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, sig):
        raise HTTPException(status_code=403, detail="Invalid signature")

    data = await request.json()
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                phone = msg.get("from", "")
                text = msg.get("text", {}).get("body", "").strip()
                if not phone or not text:
                    continue

                user = db.query(User).filter(User.whatsapp_phone == phone).first()
                if not user:
                    await _send_reply(phone, "⚠️ Số điện thoại của bạn chưa được liên kết với FOXAI. Liên hệ admin.")
                    continue

                parsed = nlp_service.nlp.parse(text)
                intent = parsed.get("intent", "unknown")
                from backend.platforms.zalo_adapter import _dispatch
                reply = _dispatch(db, user, parsed, intent)
                await _send_reply(phone, reply)

    return {"status": "ok"}
