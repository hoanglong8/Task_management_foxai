"""Telegram Adapter — multi-user version của foxai_task_bot.py."""
import logging
import sys
import asyncio
from datetime import datetime, date, timedelta
import pytz
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from backend.config import settings
from backend.database import SessionLocal
from backend.services.auth_service import get_user_by_telegram_id
from backend.services import task_service, nlp_service, report_service
from backend.schemas.task import TaskCreate, TaskUpdate, TaskFilter
from backend.models.task import TaskStatus

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logger = logging.getLogger(__name__)
TZ = pytz.timezone(settings.timezone)

HELP_TEXT = """
🤖 <b>FOXAI Task Manager</b>

<b>Lệnh nhanh:</b>
/start — Bắt đầu / xem hướng dẫn
/standup — Standup buổi sáng
/list — Xem danh sách task của bạn
/status — Thống kê tổng quan
/weekly — Kế hoạch tuần
/help — Xem hướng dẫn

<b>Nhắn tự nhiên (tiếng Việt):</b>
• "tạo task [tên] cho [người] ngày [ngày]"
• "task #3 đang làm"
• "xong task #5"
• "xem task của tôi"
• "tình hình dự án ACB?"
"""


def _get_db():
    return SessionLocal()


def _get_user_from_telegram(telegram_id: str):
    db = _get_db()
    try:
        return get_user_by_telegram_id(db, telegram_id), db
    except Exception:
        db.close()
        return None, None


async def _auth(update: Update) -> tuple:
    """Lấy (user, db) từ telegram_id. Nếu chưa liên kết tài khoản, hướng dẫn đăng ký."""
    tid = str(update.effective_user.id)
    db = _get_db()
    user = get_user_by_telegram_id(db, tid)
    if not user:
        await update.message.reply_text(
            "⚠️ Tài khoản Telegram của bạn chưa được liên kết.\n"
            "Liên hệ admin để được cấp quyền truy cập hệ thống FOXAI."
        )
        db.close()
        return None, None
    return user, db


def _fmt_task(t) -> str:
    status_emoji = {"pending": "⏳", "in_progress": "🔵", "completed": "✅"}
    emoji = status_emoji.get(t.status.value if hasattr(t.status, 'value') else t.status, "📌")
    deadline_str = t.deadline.strftime('%d/%m/%Y') if t.deadline else 'N/A'
    return f"{emoji} #{t.id} {t.title} | @{t.owner_name or '?'} | {deadline_str}"


# ── Handlers ─────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP_TEXT)


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_html(HELP_TEXT)


async def standup_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user, db = await _auth(update)
    if not user:
        return
    try:
        report = report_service.standup_report(db)
        await update.message.reply_text(report)
    finally:
        db.close()


async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user, db = await _auth(update)
    if not user:
        return
    try:
        from backend.models.user import UserRole
        args = " ".join(ctx.args).lower() if ctx.args else ""
        filters = TaskFilter()
        if "hôm nay" in args or "today" in args:
            filters.deadline_after = date.today()
            filters.deadline_before = date.today()
        elif "in_progress" in args or "đang làm" in args:
            filters.status = TaskStatus.in_progress
        elif "pending" in args or "chưa làm" in args:
            filters.status = TaskStatus.pending
        # Members only see their own tasks (enforced in task_service)
        if user.role == UserRole.member:
            filters.owner_id = user.id
        tasks = task_service.list_tasks(db, filters, user)
        if not tasks:
            await update.message.reply_text("✅ Không có task nào.")
            return
        lines = [f"📋 Danh sách ({len(tasks)} tasks):"]
        lines.extend(_fmt_task(t) for t in tasks[:20])
        if len(tasks) > 20:
            lines.append(f"... và {len(tasks) - 20} task khác")
        await update.message.reply_text("\n".join(lines))
    finally:
        db.close()


async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user, db = await _auth(update)
    if not user:
        return
    try:
        s = task_service.get_summary(db)
        msg = (
            f"📊 Tổng quan:\n"
            f"📌 Tổng: {s['total']}\n"
            f"⏳ Chờ: {s['pending']}\n"
            f"🔵 Đang làm: {s['in_progress']}\n"
            f"✅ Xong: {s['completed']}\n"
            f"🔴 Quá hạn: {s['overdue']}"
        )
        await update.message.reply_text(msg)
    finally:
        db.close()


async def weekly_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user, db = await _auth(update)
    if not user:
        return
    try:
        report = report_service.weekly_report(db)
        await update.message.reply_text(report)
    finally:
        db.close()


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user, db = await _auth(update)
    if not user:
        return
    text = update.message.text.strip()
    try:
        parsed = nlp_service.nlp.parse(text)
        intent = parsed.get("intent", "unknown")

        if intent == "create":
            from backend.models.user import UserRole
            if user.role == UserRole.member:
                await update.message.reply_text("⚠️ Bạn cần quyền manager/admin để tạo task.")
                return
            if not parsed.get("title") or not parsed.get("owner") or not parsed.get("deadline"):
                await update.message.reply_text("⚠️ Cần đủ thông tin: tên task, người phụ trách, và deadline.")
                return
            data = TaskCreate(
                title=parsed["title"],
                owner_name=parsed["owner"],
                deadline=parsed["deadline"],
            )
            task = task_service.create_task(db, data, created_by=user)
            await update.message.reply_text(
                f"✅ Tạo task #{task.id}: {task.title}\n"
                f"👤 @{task.owner_name} | 📅 {task.deadline}"
            )

        elif intent == "list":
            filters = TaskFilter()
            from backend.models.user import UserRole
            if user.role == UserRole.member:
                filters.owner_id = user.id
            if parsed.get("filter") == "today":
                filters.deadline_after = date.today()
                filters.deadline_before = date.today()
            elif parsed.get("filter") == "in_progress":
                filters.status = TaskStatus.in_progress
            elif parsed.get("filter") == "pending":
                filters.status = TaskStatus.pending
            elif parsed.get("filter") == "active":
                pass  # no status filter = show all non-completed implicitly
            tasks = task_service.list_tasks(db, filters, user)
            if not tasks:
                await update.message.reply_text("✅ Không có task nào.")
            else:
                lines = [f"📋 {len(tasks)} tasks:"]
                lines.extend(_fmt_task(t) for t in tasks[:15])
                await update.message.reply_text("\n".join(lines))

        elif intent in ("update", "complete"):
            task_id = parsed.get("task_id")
            if task_id:
                upd = TaskUpdate()
                if parsed.get("status"):
                    upd.status = parsed["status"]
                elif intent == "complete":
                    upd.status = TaskStatus.completed
                if parsed.get("deadline"):
                    upd.deadline = parsed["deadline"]
                if parsed.get("owner"):
                    upd.owner_name = parsed["owner"]
                if parsed.get("notes"):
                    upd.notes = parsed["notes"]
                task = task_service.update_task(db, task_id, upd, changed_by=user)
                if task:
                    await update.message.reply_text(f"✅ Cập nhật task #{task.id}: {task.title}")
                else:
                    await update.message.reply_text(f"⚠️ Không tìm thấy task #{task_id}")
            elif parsed.get("keyword"):
                upd = TaskUpdate()
                if parsed.get("deadline"):
                    upd.deadline = parsed["deadline"]
                if parsed.get("owner"):
                    upd.owner_name = parsed["owner"]
                updated = task_service.update_tasks_by_keyword(db, parsed["keyword"], upd, changed_by=user)
                await update.message.reply_text(f"✅ Cập nhật {len(updated)} task liên quan đến '{parsed['keyword']}'")
            else:
                await update.message.reply_text("⚠️ Vui lòng chỉ định task ID hoặc tên dự án.")

        elif intent == "delete":
            from backend.models.user import UserRole
            if user.role not in (UserRole.admin, UserRole.manager):
                await update.message.reply_text("⚠️ Chỉ admin/manager mới có thể xóa task.")
                return
            ids = parsed.get("task_ids") or ([parsed["task_id"]] if parsed.get("task_id") else [])
            if not ids:
                await update.message.reply_text("⚠️ Không xác định được task cần xóa.")
                return
            deleted = []
            for tid in ids:
                if task_service.delete_task(db, tid, deleted_by=user):
                    deleted.append(tid)
            await update.message.reply_text(f"🗑️ Đã xóa {len(deleted)} task: {deleted}")

        elif intent == "status":
            s = task_service.get_summary(db)
            await update.message.reply_text(
                f"📊 Tổng: {s['total']} | Chờ: {s['pending']} | "
                f"Đang: {s['in_progress']} | Xong: {s['completed']} | Quá hạn: {s['overdue']}"
            )

        elif intent == "standup":
            await update.message.reply_text(report_service.standup_report(db))

        elif intent == "weekly":
            await update.message.reply_text(report_service.weekly_report(db))

        else:
            await update.message.reply_text(
                "🤔 Tôi chưa hiểu yêu cầu này.\n"
                "Gõ /help để xem hướng dẫn."
            )
    finally:
        db.close()


async def deadline_reminder_job(ctx: ContextTypes.DEFAULT_TYPE):
    db = _get_db()
    try:
        from backend.models.user import User as UserModel
        users = db.query(UserModel).filter(UserModel.telegram_id.isnot(None), UserModel.is_active == True).all()
        for u in users:
            reminder = report_service.deadline_reminder(db)
            if reminder and u.telegram_id:
                try:
                    await ctx.bot.send_message(chat_id=u.telegram_id, text=reminder)
                except Exception as e:
                    logger.error(f"Telegram reminder failed for {u.full_name}: {e}")
    finally:
        db.close()


def run_telegram_bot():
    token = settings.telegram_bot_token
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot not started")
        return

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("standup", standup_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("weekly", weekly_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Daily reminder
    job_queue = app.job_queue
    if job_queue:
        tz = pytz.timezone(settings.timezone)
        import datetime as dt
        remind_time = dt.time(hour=settings.reminder_hour, minute=settings.reminder_minute, tzinfo=tz)
        job_queue.run_daily(deadline_reminder_job, time=remind_time)

    logger.info("Telegram bot starting (multi-user mode)...")
    app.run_polling(drop_pending_updates=True)
