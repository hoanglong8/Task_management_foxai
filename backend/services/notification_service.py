"""Notification Service — gửi nhắc nhở qua đúng platform của từng user."""
import logging
import httpx
from typing import Optional
from sqlalchemy.orm import Session
from backend.config import settings
from backend.models.user import User
from backend.models.notification import PlatformNotification

logger = logging.getLogger(__name__)


async def send_to_user(
    user: User,
    message: str,
    db: Optional[Session] = None,
    task_id: Optional[int] = None,
    message_type: str = "notification",
) -> bool:
    """Send message to user via their preferred platform (first available)."""
    sent = False

    if user.telegram_id:
        sent = await _send_telegram(user.telegram_id, message)
        if sent and db:
            _log_notification(db, user.id, task_id, "telegram", message_type)

    if not sent and user.zalo_id:
        sent = await _send_zalo(user.zalo_id, message)
        if sent and db:
            _log_notification(db, user.id, task_id, "zalo", message_type)

    if not sent and user.whatsapp_phone:
        sent = await _send_whatsapp(user.whatsapp_phone, message)
        if sent and db:
            _log_notification(db, user.id, task_id, "whatsapp", message_type)

    return sent


async def _send_telegram(chat_id: str, message: str) -> bool:
    token = settings.telegram_bot_token
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": message, "parse_mode": "HTML"},
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def _send_zalo(zalo_id: str, message: str) -> bool:
    token = settings.zalo_oa_access_token
    if not token:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://openapi.zalo.me/v3.0/oa/message/cs",
                headers={"access_token": token},
                json={
                    "recipient": {"user_id": zalo_id},
                    "message": {"text": message},
                },
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"Zalo send error: {e}")
        return False


async def _send_whatsapp(phone: str, message: str) -> bool:
    token = settings.whatsapp_access_token
    phone_id = settings.whatsapp_phone_number_id
    if not token or not phone_id:
        return False
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://graph.facebook.com/v18.0/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "type": "text",
                    "text": {"body": message},
                },
            )
            return resp.status_code == 200
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        return False


def _log_notification(
    db: Session,
    user_id: int,
    task_id: Optional[int],
    platform: str,
    message_type: str,
) -> None:
    entry = PlatformNotification(
        user_id=user_id,
        task_id=task_id,
        platform=platform,
        message_type=message_type,
        status="sent",
    )
    db.add(entry)
    db.commit()
