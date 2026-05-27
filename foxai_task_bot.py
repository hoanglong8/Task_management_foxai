#!/usr/bin/env python3
"""
FOXAI Task Manager - Telegram Bot with Claude AI NLP
Version: 3.0 - Claude Haiku NLP (tiếng Việt tự nhiên)
"""

import logging
import json
import sys
import re
import asyncio
import atexit
from datetime import datetime, date, timedelta
import pytz
from pathlib import Path
from dotenv import load_dotenv
import os
from openai import OpenAI

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Load .env bằng đường dẫn tuyệt đối để tránh vấn đề child process
_ENV_FILE = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_FILE, override=True)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_ID = int(os.getenv("TELEGRAM_ALLOWED_USER_ID"))
TASKS_FILE = os.getenv("TASKS_FILE", "tasks.json")
REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "0"))
TZ = pytz.timezone(os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============= TASK MANAGER =============

class TaskManager:
    def __init__(self):
        self.tasks_file = Path(TASKS_FILE)
        self.tasks_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        for candidate in (self.tasks_file, Path(str(self.tasks_file) + ".bak")):
            if not candidate.exists():
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.data = data if isinstance(data, dict) else {"tasks": [], "last_id": 0}
                if self.data.get("tasks"):
                    self.data["last_id"] = max(t.get("id", 0) for t in self.data["tasks"])
                if candidate != self.tasks_file:
                    logger.warning("tasks.json hỏng — đã khôi phục từ backup")
                return
            except Exception as e:
                logger.error(f"{candidate.name} không đọc được: {e}")
        self.data = {"tasks": [], "last_id": 0}

    def _save(self):
        import shutil
        # Backup file hiện tại
        if self.tasks_file.exists():
            shutil.copy2(self.tasks_file, str(self.tasks_file) + ".bak")
        # Atomic write: ghi ra .tmp rồi rename (tránh truncate khi crash giữa chừng)
        tmp = self.tasks_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.tasks_file)

    def create(self, title, owner, deadline):
        self._load()
        self.data["last_id"] += 1
        task = {
            "id": self.data["last_id"],
            "title": title,
            "owner": owner.strip("@"),
            "deadline": deadline,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "notes": "",
        }
        self.data["tasks"].append(task)
        self._save()
        return task

    def get(self, task_id):
        self._load()
        for t in self.data["tasks"]:
            if t["id"] == task_id:
                return t
        return None

    def update(self, task_id, **kwargs):
        self._load()
        task = self.get(task_id)
        if task:
            task.update(kwargs)
            self._save()
            return task
        return None

    def delete(self, task_id: int):
        """Xóa task theo ID. Trả về task đã xóa hoặc None nếu không tìm thấy."""
        self._load()
        task = self.get(task_id)
        if task:
            self.data["tasks"] = [t for t in self.data["tasks"] if t["id"] != task_id]
            self._save()
            return task
        return None

    def list(self, filter_by=None):
        self._load()
        tasks = self.data["tasks"]
        if filter_by == "today":
            today = datetime.now().strftime("%Y-%m-%d")
            tasks = [t for t in tasks if t["deadline"] == today]
        elif filter_by == "pending":
            tasks = [t for t in tasks if t["status"] == "pending"]
        elif filter_by == "in_progress":
            tasks = [t for t in tasks if t["status"] == "in_progress"]
        elif filter_by == "active":
            tasks = [t for t in tasks if t["status"] != "completed"]
        elif filter_by and filter_by.startswith("@"):
            owner = filter_by.strip("@").lower()
            tasks = [t for t in tasks if t["owner"].lower() == owner]
        return sorted(tasks, key=lambda x: x["id"], reverse=True)

    def summary(self):
        self._load()
        tasks = self.data["tasks"]
        return {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t["status"] == "pending"),
            "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
            "completed": sum(1 for t in tasks if t["status"] == "completed"),
        }

    def search(self, keyword: str) -> list:
        """Tìm task active theo keyword trong title."""
        self._load()
        kw = keyword.lower().strip()
        results = [
            t for t in self.data["tasks"]
            if t["status"] != "completed" and kw in t["title"].lower()
        ]
        return sorted(results, key=lambda x: x["id"], reverse=True)


# ============= REGEX FALLBACK NLP =============

class RegexNLP:
    """Phân tích tiếng Việt bằng keyword/regex — không cần API."""

    _EMPTY = {
        "intent": "unknown", "task_id": None, "task_ids": None, "deadline_groups": None,
        "keyword": None, "title": None, "owner": None, "deadline": None,
        "status": None, "filter": None, "notes": None,
    }

    def _deadline(self, text):
        m = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', text)
        if m:
            return m.group(1)
        m = re.search(r'\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b', text)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3) or 2026)
            try:
                return f"{y:04d}-{mo:02d}-{d:02d}"
            except Exception:
                pass
        m = re.search(r'(\d{1,2})\s*th[aá]ng\s*(\d{1,2})(?:\s+(\d{4}))?', text, re.IGNORECASE)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3) or 2026)
            try:
                return f"{y:04d}-{mo:02d}-{d:02d}"
            except Exception:
                pass
        return None

    def _task_id(self, text):
        m = re.search(r'\b(?:task\s*#?|#)(\d+)\b', text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _task_ids(self, text):
        """Trích xuất nhiều task ID: range 'từ 1 đến 5' / '1-5', hoặc list '#1 #2 #3' / '1 2 3'."""
        t = text.lower()
        # Range: "từ #1 đến #5", "#1 đến #5", "1-5"
        # Loại trừ "3 đến 31/5" (đó là task 3 + date 31/5, không phải range)
        m = re.search(r'(?:từ\s+)?(?:task\s+)?#?(\d+)\s*(?:đến|-)\s*#?(\d+)\b(?!\s*/)', t)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            return list(range(min(start, end), max(start, end) + 1))
        # List bằng #: "#1 #2 #3"
        ids = re.findall(r'#(\d+)', text)
        if len(ids) >= 2:
            return [int(i) for i in ids]
        # List số đứng sau từ khoá "task": "task 1 2 3"
        m2 = re.search(r'\btask[s]?\s+((?:\d+[\s,]+){1,}\d+)\b', t)
        if m2:
            ids2 = re.findall(r'\d+', m2.group(1))
            if len(ids2) >= 2:
                return [int(i) for i in ids2]
        return []

    def _owner(self, text):
        m = re.search(
            r'(?:cho|giao\s+cho)\s+([A-ZÀ-Ỹa-zà-ỹ][a-zà-ỹ]*(?:\s+[A-ZÀ-Ỹa-zà-ỹ][a-zà-ỹ]*)*)',
            text
        )
        if m:
            owner = m.group(1).strip()
            owner = re.sub(r'\s+(ngày|hạn|deadline|từ|vào|trước|sau).*$', '', owner, flags=re.IGNORECASE)
            return owner
        m = re.search(r'@(\w+)', text)
        return m.group(1) if m else None

    def _status(self, text):
        t = text.lower()
        if any(w in t for w in ['đang làm', 'in_progress', 'in progress', 'bắt đầu', 'đang thực hiện', 'triển khai']):
            return 'in_progress'
        # "xong/done/completed" không bị phủ định bởi "chưa"
        for w in ['xong', 'done', 'completed', 'finished', 'kết thúc']:
            if w in t:
                return 'completed'
        # "hoàn thành" phải kiểm tra phủ định: "chưa hoàn thành" ≠ completed
        if 'hoàn thành' in t:
            pos = t.find('hoàn thành')
            prefix = t[max(0, pos - 8):pos]
            if 'chưa ' not in prefix and 'không ' not in prefix:
                return 'completed'
        if any(w in t for w in ['chờ', 'pending', 'chưa làm', 'chưa bắt đầu']):
            return 'pending'
        return None

    def _parse_deadline_groups(self, text: str) -> list:
        """
        Tách nhiều nhóm (task_ids, deadline) khi mỗi nhóm có deadline khác nhau.
        Ví dụ: "#5 #8 deadline 25/05, #14 deadline 30/05"
        → [([5, 8], "2026-05-25"), ([14], "2026-05-30")]
        Trả về [] nếu chỉ có 1 nhóm hoặc không đủ dữ liệu.
        """
        # Tìm tất cả cặp (vị trí, ngày) trong text
        date_iter = list(re.finditer(
            r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{4}))?\b', text
        ))
        if len(date_iter) < 2:
            return []
        dates = []
        for m in date_iter:
            dl = self._deadline(m.group(0))
            if dl:
                dates.append((m.start(), dl))
        # Nếu tất cả deadline giống nhau → để phần bulk đơn giản xử lý
        if len(set(d for _, d in dates)) < 2:
            return []
        # Tìm tất cả #ID và vị trí của chúng
        id_iter = list(re.finditer(r'#(\d+)', text))
        if not id_iter:
            return []
        # Gán mỗi #ID cho nhóm deadline gần nhất ở SAU nó
        groups: dict[str, list] = {}
        for id_m in id_iter:
            best_dl = None
            best_dist = float('inf')
            for pos, dl in dates:
                if pos > id_m.start():
                    dist = pos - id_m.start()
                    if dist < best_dist:
                        best_dist, best_dl = dist, dl
            if best_dl:
                groups.setdefault(best_dl, []).append(int(id_m.group(1)))
        result = [(ids, dl) for dl, ids in groups.items() if ids]
        return result if len(result) >= 2 else []

    @staticmethod
    def _is_id_ref(kw: str) -> bool:
        """Trả về True nếu keyword trông như ID/range, không phải tên dự án."""
        # Xoá số, #, khoảng trắng, dấu phẩy, rồi xoá separator "đến/to/sang"
        cleaned = re.sub(r'[#\d\s,\-]', '', kw)
        cleaned = re.sub(r'\b(?:đến|to|sang|tới|và|and)\b', '', cleaned, flags=re.I).strip()
        return len(cleaned) < 2  # chỉ còn ký tự không có nghĩa → là ID ref

    def _keyword_update(self, text: str) -> dict | None:
        """
        Phát hiện update theo tên dự án/task (không theo ID).
        Ví dụ: "thay đổi deadline dự án ACB sang 25/05"
                "giao dự án KMS cho Quốc Anh"
        Trả về dict {keyword, deadline/owner/notes} hoặc None.
        """
        dl = self._deadline(text)
        owner = self._owner(text)

        # --- DEADLINE update ---
        if dl:
            m = re.search(
                r'(?:thay đổi|đổi|cập nhật|dời|lùi|điều chỉnh|gia hạn|thay)\s+'
                r'(?:deadline|hạn)?\s*'
                r'(?:(?:dự án|project|task|của)\s+)?'
                r'(.+?)'
                r'\s+(?:sang|đến|tới|thành)(?:\s+ngày)?'
                r'\s+\d',
                text, re.IGNORECASE
            )
            if m:
                kw = m.group(1).strip()
                kw = re.sub(r'^(dự án|project|task)\s+', '', kw, flags=re.I).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw):
                    return {"keyword": kw, "deadline": dl}

            # "gia hạn [dự án] KEYWORD [đến] DATE"
            m = re.search(
                r'gia hạn\s+(?:(?:dự án|project|task)\s+)?'
                r'(.+?)\s+(?:đến|sang|tới)\s+\d',
                text, re.IGNORECASE
            )
            if m:
                kw = m.group(1).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw):
                    return {"keyword": kw, "deadline": dl}

        # --- OWNER update ---
        # Chỉ bắt "giao lại / chuyển / assign" (KHÔNG bắt "giao task [tên]" vì đó là CREATE)
        # Và "giao dự án" (project marker rõ ràng)
        if owner:
            m = re.search(
                r'(?:giao lại|chuyển|assign)\s+'
                r'(?:(?:dự án|project|task)\s+)?'
                r'(.+?)\s+(?:cho|sang|thành)\s+',
                text, re.IGNORECASE
            )
            if not m:
                m = re.search(
                    r'giao\s+(?:dự án|project)\s+'
                    r'(.+?)\s+(?:cho|sang|thành)\s+',
                    text, re.IGNORECASE
                )
            if m:
                kw = m.group(1).strip()
                kw = re.sub(r'^(dự án|project|task)\s+', '', kw, flags=re.I).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw) and kw.lower() != owner.lower():
                    return {"keyword": kw, "owner": owner}

        # --- NOTES update ---
        # "ghi chú [cho/vào] [dự án] KEYWORD: NOTES"
        m = re.search(
            r'(?:ghi chú|thêm ghi chú|note)\s+(?:cho|vào)?\s*'
            r'(?:(?:dự án|project|task)\s+)?'
            r'(.+?)\s*[:\-]\s*(.+)$',
            text, re.IGNORECASE
        )
        if m:
            kw = m.group(1).strip()
            notes = m.group(2).strip()
            if kw and not re.search(r'^\d+$', kw) and notes:  # kw không phải số (đó là task_id)
                return {"keyword": kw, "notes": notes}

        return None

    def parse(self, text: str) -> dict:
        r = dict(self._EMPTY)
        t = text.lower().strip()

        # STANDUP
        if any(w in t for w in ['standup', 'stand up', 'sáng nay', 'hôm nay làm gì', 'hôm nay có gì', 'buổi sáng', 'công việc hôm nay']):
            r['intent'] = 'standup'
            return r

        # STATUS — chỉ aggregate/stats, không bắt câu hỏi về dự án cụ thể
        if any(w in t for w in ['tóm tắt', 'bao nhiêu task', 'báo cáo', 'tổng quan', 'overview', 'thống kê']):
            r['intent'] = 'status'
            return r

        # UPDATE THEO TÊN DỰ ÁN (không cần task_id)
        kw_update = self._keyword_update(text)
        if kw_update:
            r['intent'] = 'update'
            r.update(kw_update)
            return r

        task_id = self._task_id(text)
        task_ids = self._task_ids(text)
        status = self._status(text)

        # COMPLETE — bulk hoặc single
        if status == 'completed' and (task_ids or task_id):
            r['intent'] = 'complete'
            if task_ids:
                r['task_ids'] = task_ids
            else:
                r['task_id'] = task_id
                m = re.search(r'(?:xong|hoàn thành|done)\s+task\s*#?\d+\s*(.*)', text, re.IGNORECASE)
                if m and m.group(1).strip():
                    r['notes'] = m.group(1).strip()
            return r

        # UPDATE BULK — nhiều ID + field cần update
        if task_ids:
            dl = self._deadline(text)
            owner = self._owner(text)

            # Nếu có nhiều nhóm deadline khác nhau → multi-group
            groups = self._parse_deadline_groups(text)
            if groups:
                r['intent'] = 'update'
                r['deadline_groups'] = groups   # list of (task_ids, deadline)
                return r

            fields = {}
            # Deadline: có 'deadline' hoặc 'hạn' trong text kèm ngày
            if dl and ('deadline' in t or 'hạn' in t):
                fields['deadline'] = dl
            # Owner: "giao/chuyển/assign" + "cho" trong text (không có "deadline/hạn")
            if owner and re.search(r'\b(?:giao|chuyển|assign)\b', t) and re.search(r'\bcho\b', t) \
                    and 'deadline' not in t and 'hạn' not in t:
                fields['owner'] = owner
            if status is not None and status != 'completed':
                fields['status'] = status

            if fields:
                r['intent'] = 'update'
                r['task_ids'] = task_ids
                r.update(fields)
                return r

        if task_id:
            # UPDATE DEADLINE
            deadline_kw = ['đổi deadline', 'thay deadline', 'gia hạn', 'dời deadline', 'dời task',
                           'deadline mới', 'hạn mới', 'đổi hạn', 'lùi deadline', 'lùi hạn']
            if any(kw in t for kw in deadline_kw):
                dl = self._deadline(text)
                if dl:
                    r['intent'] = 'update'
                    r['task_id'] = task_id
                    r['deadline'] = dl
                    return r

            # UPDATE OWNER
            owner_kw = ['giao lại', 'giao task', 'chuyển cho', 'chuyển task', 'đổi người', 'assign cho', 'reassign']
            _has_cho = re.search(r'\bcho\b', t)
            _has_giao = re.search(r'\b(?:giao|chuyển|assign)\b', t)
            if (any(kw in t for kw in owner_kw) or (_has_giao and _has_cho)):
                owner = self._owner(text)
                if owner:
                    r['intent'] = 'update'
                    r['task_id'] = task_id
                    r['owner'] = owner
                    return r

            # UPDATE NOTES
            notes_kw = ['ghi chú', 'ghi chu', 'note:', 'notes:', 'thêm ghi chú', 'cập nhật ghi chú', 'bổ sung']
            for kw in notes_kw:
                if kw in t:
                    m = re.search(
                        r'(?:ghi ch[úu]|note[s]?|thêm ghi ch[úu]|cập nhật ghi ch[úu]|bổ sung)'
                        r'[:\s]+(?:task\s*#?\d+\s*[:\-]?\s*)?(.+)',
                        text, re.IGNORECASE
                    )
                    if not m:
                        m = re.search(r'task\s*#?\d+\s+(?:ghi ch[úu]|note[s]?)[:\s]+(.+)', text, re.IGNORECASE)
                    if m and m.group(1).strip():
                        r['intent'] = 'update'
                        r['task_id'] = task_id
                        r['notes'] = m.group(1).strip()
                        return r

            # UPDATE TITLE
            title_kw = ['đổi tên', 'sửa tên', 'đổi nội dung', 'sửa nội dung', 'rename']
            for kw in title_kw:
                if kw in t:
                    m = re.search(
                        r'(?:đổi tên|sửa tên|đổi nội dung|sửa nội dung|rename)\s+task\s*#?\d+\s*(?:thành|sang|:)?\s*(.+)',
                        text, re.IGNORECASE
                    )
                    if not m:
                        m = re.search(
                            r'task\s*#?\d+\s+(?:đổi tên|sửa tên)\s*(?:thành|sang|:)?\s*(.+)',
                            text, re.IGNORECASE
                        )
                    if m and m.group(1).strip():
                        r['intent'] = 'update'
                        r['task_id'] = task_id
                        r['title'] = m.group(1).strip()
                        return r

            # UPDATE STATUS (existing)
            if status:
                r['intent'] = 'update'
                r['task_id'] = task_id
                r['status'] = status
                return r

        # DELETE
        delete_kw = ['xóa task', 'xóa việc', 'xóa công việc', 'xóa các task', 'delete task', 'bỏ task', 'xoá task', 'xoá các task']
        if any(kw in t for kw in delete_kw) or (('xóa' in t or 'xoá' in t) and re.search(r'#?\d+', t)):
            r['intent'] = 'delete'
            # Dải số: "từ #28 đến #33" hoặc "#28 đến #33"
            m = re.search(r'(?:từ\s+)?#?(\d+)\s+đến\s+#?(\d+)', t)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                r['task_ids'] = list(range(min(start, end), max(start, end) + 1))
            else:
                # Nhiều ID rời: "#28 #29 #30" hoặc "28, 29, 30"
                ids = re.findall(r'#?(\d+)', t)
                if ids:
                    r['task_ids'] = [int(i) for i in ids]
            return r

        # CREATE
        create_kw = ['tạo task', 'tạo công việc', 'tạo việc', 'giao task', 'giao việc', 'thêm task', 'thêm việc', 'tạo mới']
        if any(kw in t for kw in create_kw):
            r['intent'] = 'create'
            m = re.search(
                r'(?:tạo task|tạo công việc|tạo việc|giao task|giao việc|thêm task|thêm việc|tạo mới)\s+'
                r'(.*?)(?:\s+cho\s|\s+@|\s+ngày\s|\s+hạn\s|$)',
                text, re.IGNORECASE
            )
            r['title'] = m.group(1).strip() if m else None
            r['owner'] = self._owner(text)
            r['deadline'] = self._deadline(text)
            return r

        # WEEKLY VIEW
        _weekly_kw = ['lịch tuần', 'xem lịch', 'kế hoạch tuần', 'lịch làm việc',
                      'work schedule', 'weekly', 'xem tuần', 'tuần này']
        if any(w in t for w in _weekly_kw):
            r['intent'] = 'weekly'
            return r

        # LIST
        _active_kw = ['chưa hoàn thành', 'chưa xong', 'còn lại', 'chưa done']
        _list_kw   = ['danh sách', 'liệt kê', 'xem task', 'xem các task', 'list task',
                      'có task gì', 'task gì', 'tất cả task', 'xem việc']
        # "cập nhật" hoặc "xem" khi đi kèm từ filter → hiểu là "show me"
        _list_trigger = (
            any(w in t for w in _list_kw) or
            ('cập nhật' in t and any(w in t for w in _active_kw + ['chưa làm', 'đang làm', 'hôm nay'])) or
            (('xem' in t) and any(w in t for w in _active_kw + ['chưa làm', 'đang làm', 'hôm nay']))
        )
        if _list_trigger:
            r['intent'] = 'list'
            if 'hôm nay' in t or 'today' in t:
                r['filter'] = 'today'
            elif 'đang làm' in t or 'in_progress' in t:
                r['filter'] = 'in_progress'
            elif 'chưa làm' in t or 'pending' in t:
                r['filter'] = 'pending'
            elif any(w in t for w in _active_kw):
                r['filter'] = 'active'
            return r

        # QUERY — câu hỏi mở cần LLM trả lời từ context dữ liệu
        query_kw = [
            'tình hình', 'đến đâu', 'như thế nào', 'thế nào', 'ra sao',
            'bao giờ xong', 'còn bao lâu', 'ai đang', 'ai phụ trách',
            'ưu tiên', 'rủi ro', 'nguy hiểm', 'quan trọng nhất',
            'tiến độ', 'làm gì', 'phụ trách gì', 'đảm nhận',
            'dự án nào', 'project nào', 'có gì cần',
        ]
        if any(kw in t for kw in query_kw) or text.strip().endswith('?'):
            r['intent'] = 'query'
            return r

        return r


# ============= OPENAI GPT NLP =============

_regex_nlp = RegexNLP()


class OpenAINLP:
    """
    Phân tích tin nhắn tiếng Việt bằng GPT-4o-mini.
    Hiểu ngôn ngữ tự nhiên linh hoạt, không bị giới hạn bởi regex.
    """

    SYSTEM_PROMPT = """Bạn là module phân tích tin nhắn quản lý công việc cho FOXAI.

Nhận tin nhắn tiếng Việt từ Giám đốc Delivery Center, trả về JSON với cấu trúc CHÍNH XÁC:
{
  "intent": "<một trong: create|list|update|complete|delete|status|standup|query|unknown>",
  "task_id": <số nguyên hoặc null>,
  "task_ids": <mảng số nguyên hoặc null — dùng cho delete nhiều task>,
  "keyword": "<tên dự án/task để tìm kiếm, dùng khi không có task_id cụ thể — null nếu có task_id>",
  "title": "<tên công việc hoặc null>",
  "owner": "<tên người phụ trách hoặc null, KHÔNG kèm từ 'cập nhật/deadline/hạn'>",
  "deadline": "<YYYY-MM-DD hoặc null>",
  "status": "<một trong: pending|in_progress|completed hoặc null>",
  "filter": "<một trong: today|pending|in_progress|active hoặc null>",
  "notes": "<ghi chú bổ sung hoặc null>"
}

KEYWORD — trích xuất tên dự án/task khi update không có ID:
- "thay đổi deadline dự án ACB sang 25/5" → keyword="ACB", deadline="2026-05-25", task_id=null
- "gia hạn KMS đến 31/5" → keyword="KMS", deadline="2026-05-31", task_id=null
- "giao dự án IOC cho Quốc Anh" → keyword="IOC", owner="Quốc Anh", task_id=null
- "ghi chú ACB: đã liên hệ khách hàng" → keyword="ACB", notes="đã liên hệ khách hàng"
- "task 3 deadline 25/5" → task_id=3, keyword=null (có ID thì KHÔNG dùng keyword)

INTENT — phân biệt cẩn thận:
- create: tạo/thêm/giao task mới ("tạo task", "giao việc", "thêm công việc")
- list: xem/liệt kê danh sách task. Dùng khi KHÔNG có task_id cụ thể và không có giá trị thay đổi rõ ràng:
  + "danh sách", "có task gì", "xem task", "liệt kê task", "task của ai"
  + "hãy cập nhật các task chưa hoàn thành" → list, filter=active  ← "cập nhật" ở đây = "cho tôi xem"
  + "cập nhật tình hình task đang làm" → list, filter=in_progress
  + "xem các task chưa xong" → list, filter=active
  + "task hôm nay" → list, filter=today
  LƯU Ý: "cập nhật" + từ khóa filter (chưa hoàn thành/đang làm/hôm nay) mà KHÔNG có task_id = intent=list
- update: cập nhật task — BẮT BUỘC phải có task_id hoặc keyword (tên dự án), VÀ có giá trị thay đổi cụ thể:
  + status: "task 3 đang làm", "bắt đầu task 2", "chuyển task 5 sang in_progress"
  + deadline: "đổi deadline task 3 sang 25/5", "gia hạn task 4 đến 30/5", "dời task 3 sang tuần sau"
  + owner: "giao lại task 5 cho Hoàng", "chuyển task 3 cho Quốc Anh", "task 2 assign cho Tiến"
  + notes: "ghi chú task 2: đã liên hệ KH", "thêm note task 3: đang chờ feedback", "bổ sung task 1: cần review lại"
  + title: "đổi tên task 1 thành Hoàn thiện BA document", "sửa tên task 4: Cập nhật thiết kế DB"
- complete: đánh dấu hoàn thành task có ID ("xong task X", "hoàn thành task X", "done task X")
- delete: xóa task vĩnh viễn ("xóa task #5", "xóa các task từ #28 đến #33", "bỏ task 3 4 5")
  + task_ids: mảng ID cần xóa (ví dụ [28,29,30,31,32,33] cho "từ #28 đến #33")
- status: tóm tắt/thống kê TỔNG QUAN không có ID cụ thể ("tóm tắt", "tình hình", "bao nhiêu task", "báo cáo", "tổng quan", "overview")
- weekly: xem lịch làm việc theo tuần ("lịch tuần", "xem lịch", "kế hoạch tuần", "lịch làm việc tuần")
- standup: standup buổi sáng ("standup", "hôm nay làm gì", "công việc hôm nay")
- query: câu hỏi mở về dự án, nhân sự, tiến độ cần tra cứu dữ liệu ("tình hình dự án ACB?", "Hoàng đang làm gì?", "deadline nào nguy hiểm nhất?", "ai phụ trách KMS?", "tiến độ như thế nào?")
- unknown: không rõ ý định

DEADLINE — chuyển về YYYY-MM-DD, năm mặc định là 2026:
- "15/5" hoặc "ngày 15/5" → "2026-05-15"
- "20 tháng 5" → "2026-05-20"
- "25/5/2026" → "2026-05-25"
- "2026-05-25" → giữ nguyên

STATUS:
- "đang làm / bắt đầu / in progress" → "in_progress"
- "xong / hoàn thành / done / finished" → "completed"
- "chờ / pending / chưa làm" → "pending"

FILTER (dùng cho intent=list):
- "hôm nay / today" → "today"
- "chưa làm / pending" → "pending"
- "đang làm / in progress" → "in_progress"
- "chưa hoàn thành / chưa xong / còn lại" → "active"
- không có filter rõ → null

OWNER — chỉ lấy tên người, KHÔNG lấy động từ/trạng thái đi kèm:
- "giao cho Hoàng cập nhật" → owner = "Hoàng"
- "cho Quốc Anh làm" → owner = "Quốc Anh"

CHỈ trả về JSON thuần túy, không giải thích, không markdown."""

    _EMPTY = {
        "intent": "unknown",
        "task_id": None,
        "task_ids": None,
        "deadline_groups": None,
        "keyword": None,
        "title": None,
        "owner": None,
        "deadline": None,
        "status": None,
        "filter": None,
        "notes": None,
    }

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("OPENAI_API_KEY không có — NLP bị tắt")
            self._client = None
        else:
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://api.openai.com/v1",  # override OPENAI_BASE_URL env var
            )

    def parse(self, text: str) -> dict:
        if not self._client:
            return _regex_nlp.parse(text)

        try:
            response = self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=300,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user",   "content": text},
                ],
            )
            raw = response.choices[0].message.content.strip()
            result = json.loads(raw)
            merged = {**self._EMPTY, **result}
            if merged["task_id"] is not None:
                merged["task_id"] = int(merged["task_id"])
            logger.info(
                f"GPT NLP: intent={merged['intent']}, "
                f"id={merged['task_id']}, owner={merged['owner']}, "
                f"deadline={merged['deadline']}"
            )
            return merged
        except Exception as e:
            logger.warning(f"GPT NLP lỗi ({type(e).__name__}) — dùng RegexNLP fallback")
            return _regex_nlp.parse(text)


# ============= QUERY ENGINE =============

class QueryEngine:
    """Trả lời câu hỏi mở bằng LLM + toàn bộ context dữ liệu dự án."""

    SYSTEM_PROMPT = """\
Bạn là trợ lý quản lý dự án thông minh cho FOXAI Delivery Center.
Trả lời câu hỏi bằng tiếng Việt, ngắn gọn, súc tích (tối đa 300 từ).
Chỉ dùng thông tin từ context được cung cấp.
Nếu không đủ thông tin, nói rõ: "Tôi không tìm thấy thông tin về [X] trong dữ liệu hiện có."
Ưu tiên dữ liệu task thực tế hơn tài liệu chung. Dùng bullet point khi liệt kê.

=== DỮ LIỆU HIỆN TẠI ===
{context}"""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY", "")
        self._client = (
            OpenAI(api_key=api_key, base_url="https://api.openai.com/v1")
            if api_key else None
        )

    def _build_context(self) -> str:
        parts = []
        today = datetime.now(TZ).date()
        base_dir = Path(TASKS_FILE).parent.parent

        # 1. Tasks active — compact format với trạng thái deadline
        tasks = tm.list()
        active = [t for t in tasks if t["status"] != "completed"]
        lines = []
        for t in active:
            try:
                diff = (date.fromisoformat(t["deadline"]) - today).days
                tag = f"QUÁ HẠN {abs(diff)}N" if diff < 0 else f"còn {diff}N"
            except Exception:
                tag = t["deadline"]
            note = f" | ghi chú: {t['notes']}" if t.get("notes") else ""
            lines.append(
                f"- #{t['id']} [{t['status'].upper()}] {t['title']}"
                f" | @{t['owner']} | {t['deadline']} ({tag}){note}"
            )
        parts.append(f"## TASKS ĐANG ACTIVE ({len(active)} tasks, ngày {today})\n" + "\n".join(lines))

        # 2. Danh sách nhân sự
        roster = base_dir / "Danh_sach_nhan_su_FOXAI.md"
        if roster.exists():
            parts.append("## NHÂN SỰ FOXAI\n" + roster.read_text(encoding="utf-8")[:2500])

        # 3. Project memory files
        memory_dir = base_dir / "memory"
        if memory_dir.exists():
            for f in sorted(memory_dir.glob("*.md")):
                if f.name == "MEMORY.md":
                    continue
                try:
                    content = f.read_text(encoding="utf-8")
                    parts.append(f"## {f.stem.upper()}\n{content[:1500]}")
                except Exception:
                    pass

        # 4. Báo cáo công việc gần nhất
        reports = sorted(base_dir.glob("Bao_cao*.md"), reverse=True)
        if reports:
            parts.append(
                "## BÁO CÁO CÔNG VIỆC GẦN NHẤT\n"
                + reports[0].read_text(encoding="utf-8")[:3000]
            )

        return "\n\n---\n\n".join(parts)

    def answer(self, question: str) -> str:
        if not self._client:
            return self._fallback(question)
        try:
            context = self._build_context()
            resp = self._client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=600,
                temperature=0.3,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT.format(context=context)},
                    {"role": "user",   "content": question},
                ],
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(f"QueryEngine API lỗi: {e} — dùng fallback")
            return self._fallback(question)

    def _fallback(self, question: str) -> str:
        """Trả lời cơ bản bằng dữ liệu local khi không có API."""
        q = question.lower()
        tasks = tm.list()
        active = [t for t in tasks if t["status"] != "completed"]
        today = datetime.now(TZ).date()

        # Câu hỏi về task quá hạn
        if any(w in q for w in ['quá hạn', 'trễ', 'trễ hạn', 'overdue']):
            overdue = [t for t in active if date.fromisoformat(t["deadline"]) < today]
            if not overdue:
                return "✅ Không có task nào quá hạn."
            lines = [f"• #{t['id']} {t['title']} (@{t['owner']}, hạn {t['deadline']})" for t in overdue[:8]]
            return f"🔴 Có {len(overdue)} task quá hạn:\n" + "\n".join(lines)

        # Câu hỏi về người cụ thể — tìm theo tên trong task
        for t in active:
            owner_parts = t["owner"].lower().split()
            if any(part in q for part in owner_parts if len(part) > 2):
                owner_tasks = [x for x in active if x["owner"].lower() == t["owner"].lower()]
                lines = [
                    f"• #{x['id']} [{x['status']}] {x['title']} (deadline {x['deadline']})"
                    for x in owner_tasks
                ]
                return f"📋 Tasks của @{t['owner']} ({len(owner_tasks)} task):\n" + "\n".join(lines)

        # Câu hỏi về dự án — tìm keyword trong title task
        words = [w for w in re.findall(r'\w+', q) if len(w) > 3]
        matched = [t for t in active if any(w in t["title"].lower() for w in words)]
        if matched:
            lines = [
                f"• #{t['id']} [{t['status']}] {t['title']} (@{t['owner']}, hạn {t['deadline']})"
                for t in matched[:6]
            ]
            return f"🔍 Tìm thấy {len(matched)} task liên quan:\n" + "\n".join(lines)

        # Mặc định: tóm tắt
        s = tm.summary()
        return (
            f"📊 Tổng quan công việc:\n"
            f"• Đang làm: {s['in_progress']} task\n"
            f"• Chờ xử lý: {s['pending']} task\n"
            f"• Hoàn thành: {s['completed']} task\n\n"
            f"💡 Thêm API key để hỏi chi tiết hơn."
        )


# ============= HELPERS =============

tm = TaskManager()
nlp = OpenAINLP()
qe = QueryEngine()


def _esc(text: str) -> str:
    """Escape ký tự đặc biệt cho Telegram Markdown v1."""
    for ch in ['*', '_', '`', '[', ']']:
        text = text.replace(ch, '\\' + ch)
    return text


def fmt(task):
    emoji = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(task["status"], "❓")
    title = _esc(str(task.get("title") or ""))
    owner = _esc(str(task.get("owner") or ""))
    notes = _esc(str(task.get("notes") or ""))
    lines = [
        f"{emoji} *#{task['id']}* | {title}",
        f"   Owner: {owner} | Deadline: {task.get('deadline', '')}",
        f"   Status: {task['status']}",
    ]
    if notes:
        lines.append(f"   📝 {notes}")
    return "\n".join(lines)


def auth(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


# ============= COMMAND HANDLERS =============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    await update.message.reply_text(
        "🤖 *FOXAI Task Manager Bot*\n\n"
        "Chat tự nhiên bằng tiếng Việt hoặc gõ /help để xem lệnh.",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    await update.message.reply_text(
        "*📋 Lệnh có sẵn:*\n\n"
        "`/create [title] @owner [deadline]` — Tạo task\n"
        "`/list [today|pending|@owner]` — Liệt kê\n"
        "`/update [id] field=value ...` — Cập nhật\n"
        "   fields: `status` `deadline` `owner` `notes` `title`\n"
        "`/complete [id] [notes]` — Hoàn thành\n"
        "`/remind` — Xem task sắp đến hạn\n"
        "`/ask [câu hỏi]` — Hỏi đáp về dự án & nhân sự\n"
        "`/status` — Tóm tắt\n"
        "`/standup` — Standup hôm nay\n\n"
        "*💬 Chat tự nhiên (tiếng Việt):*\n"
        "\"Tạo task build dashboard cho Hoàng ngày 15/5\"\n"
        "\"Đổi deadline task 3 sang 30/5\"\n"
        "\"Giao lại task 5 cho Quốc Anh\"\n"
        "\"Ghi chú task 3: đã liên hệ KH\"\n"
        "\"Tình hình dự án ACB đến đâu rồi?\"\n"
        "\"Hoàng đang phụ trách những gì?\"",
        parse_mode="Markdown"
    )


async def create_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    args = context.args
    if not args or len(args) < 3:
        await update.message.reply_text(
            "❌ Format: /create [title] @owner [deadline]\n"
            "Ví dụ: /create Build dashboard @Hoàng 2026-05-15"
        )
        return
    title = " ".join(args[:-2])
    owner, deadline = args[-2], args[-1]
    task = tm.create(title, owner, deadline)
    await update.message.reply_text(
        f"✅ Tạo task #{task['id']} thành công!\n\n{fmt(task)}",
        parse_mode="Markdown"
    )


async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    f = context.args[0] if context.args else None
    tasks = tm.list(f)
    if not tasks:
        await update.message.reply_text("📭 Không có task nào.")
        return
    label = {"today": "hôm nay", "pending": "chưa làm", "in_progress": "đang làm", "active": "chưa hoàn thành"}
    header = f"📋 Tasks {label.get(f, 'tất cả')} ({len(tasks)} task)"
    lines = [fmt(t) for t in tasks]
    chunk, chunks = f"*{header}*\n\n", []
    for line in lines:
        if len(chunk) + len(line) + 2 > 4000:
            chunks.append(chunk.rstrip())
            chunk = line + "\n\n"
        else:
            chunk += line + "\n\n"
    if chunk.strip():
        chunks.append(chunk.rstrip())
    for i, part in enumerate(chunks):
        prefix = "" if i == 0 else f"_(tiếp — trang {i+1}/{len(chunks)})_\n\n"
        await update.message.reply_text(prefix + part, parse_mode="Markdown")


async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    args = context.args
    HELP = (
        "📝 *Cú pháp:* `/update [id] field=value ...`\n\n"
        "*Fields:*\n"
        "`status=` pending \\| in\\_progress \\| completed\n"
        "`deadline=` YYYY\\-MM\\-DD\n"
        "`owner=` Tên người phụ trách\n"
        "`notes=` Nội dung ghi chú\n"
        "`title=` Tên task mới\n\n"
        "*Ví dụ:*\n"
        "`/update 3 status=in_progress`\n"
        "`/update 3 deadline=2026-05-30`\n"
        "`/update 3 owner=Hoàng notes=Đã liên hệ KH`\n"
        "`/update 3 title=Hoàn thiện tài liệu BA`"
    )
    if not args:
        await update.message.reply_text(HELP, parse_mode="MarkdownV2")
        return
    try:
        task_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID task phải là số nguyên")
        return

    if len(args) < 2:
        await update.message.reply_text(HELP, parse_mode="MarkdownV2")
        return

    STATUSES = ("pending", "in_progress", "completed")
    FIELDS = {"status", "deadline", "owner", "notes", "title"}

    # Backward compat: /update 3 in_progress
    if args[1] in STATUSES:
        kwargs = {"status": args[1]}
    else:
        rest = " ".join(args[1:])
        kwargs = {}
        # Split on "key=" boundaries
        for m in re.finditer(r'(\w+)=(.+?)(?=\s+\w+=|$)', rest):
            key, val = m.group(1), m.group(2).strip()
            if key in FIELDS:
                kwargs[key] = val
        if not kwargs:
            await update.message.reply_text(HELP, parse_mode="MarkdownV2")
            return

    if "status" in kwargs and kwargs["status"] not in STATUSES:
        await update.message.reply_text("❌ Status phải là: pending, in\\_progress, completed", parse_mode="MarkdownV2")
        return

    task = tm.update(task_id, **kwargs)
    if task:
        updated = ", ".join(f"`{k}`" for k in kwargs)
        await update.message.reply_text(
            f"✅ Đã cập nhật task \\#{task_id} \\({updated}\\)\\!\n\n{fmt(task)}",
            parse_mode="MarkdownV2"
        )
    else:
        await update.message.reply_text(f"❌ Không tìm thấy task \\#{task_id}", parse_mode="MarkdownV2")


async def complete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    if not context.args:
        await update.message.reply_text("❌ Format: /complete [id] [notes]")
        return
    try:
        task_id = int(context.args[0])
        notes = " ".join(context.args[1:])
        task = tm.update(task_id, status="completed", notes=notes)
        if task:
            resp = f"✅ Hoàn thành task #{task_id}!\n\n{fmt(task)}"
            if notes:
                resp += f"\n📝 Notes: {notes}"
            await update.message.reply_text(resp, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Không tìm thấy task #{task_id}")
    except ValueError:
        await update.message.reply_text("❌ ID task phải là số nguyên")


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    s = tm.summary()
    await update.message.reply_text(
        f"*📊 Tóm tắt task*\n\n"
        f"⏳ Pending: {s['pending']}\n"
        f"🔄 In Progress: {s['in_progress']}\n"
        f"✅ Completed: {s['completed']}\n"
        f"📈 Total: {s['total']}",
        parse_mode="Markdown"
    )


async def standup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    today = datetime.now().strftime("%Y-%m-%d")
    tasks = tm.list("today")
    if not tasks:
        await update.message.reply_text(f"📭 Không có task nào hôm nay ({today})")
        return
    body = "\n\n".join(fmt(t) for t in tasks)
    await update.message.reply_text(
        f"*🌅 Standup - {today}*\n\n📋 {len(tasks)} task hôm nay:\n\n{body}",
        parse_mode="Markdown"
    )


# ============= DEADLINE REMINDER =============

def _build_reminder_message() -> str | None:
    today = datetime.now(TZ).date()
    tasks = [t for t in tm.list() if t["status"] != "completed"]

    overdue, due_today, due_tomorrow, due_soon = [], [], [], []
    for t in tasks:
        try:
            dl = date.fromisoformat(t["deadline"])
        except Exception:
            continue
        diff = (dl - today).days
        if diff < 0:
            overdue.append((t, diff))
        elif diff == 0:
            due_today.append(t)
        elif diff == 1:
            due_tomorrow.append(t)
        elif diff <= 3:
            due_soon.append((t, diff))

    if not any([overdue, due_today, due_tomorrow, due_soon]):
        return None

    lines = [f"⏰ *Nhắc deadline — {today.strftime('%d/%m/%Y')}*\n"]

    if overdue:
        lines.append("🔴 *Quá hạn:*")
        for t, diff in overdue:
            lines.append(f"  • #{t['id']} {t['title']} — @{t['owner']} _(quá {abs(diff)} ngày)_")

    if due_today:
        lines.append("\n🟠 *Hôm nay:*")
        for t in due_today:
            lines.append(f"  • #{t['id']} {t['title']} — @{t['owner']}")

    if due_tomorrow:
        lines.append("\n🟡 *Ngày mai:*")
        for t in due_tomorrow:
            lines.append(f"  • #{t['id']} {t['title']} — @{t['owner']}")

    if due_soon:
        lines.append("\n🟢 *Trong 3 ngày:*")
        for t, diff in due_soon:
            lines.append(f"  • #{t['id']} {t['title']} — @{t['owner']} _(còn {diff} ngày)_")

    return "\n".join(lines)


async def deadline_reminder(context: ContextTypes.DEFAULT_TYPE):
    msg = _build_reminder_message()
    if msg:
        await context.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=msg,
            parse_mode="Markdown",
        )


def _build_weekly_view() -> str:
    """Tạo lịch làm việc tuần — nhóm task theo ngày deadline."""
    today = datetime.now(TZ).date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    days_vi = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
    status_emoji = {"pending": "⏳", "in_progress": "🔄"}

    active = [t for t in tm.list() if t["status"] != "completed"]

    by_date: dict = {}
    overdue, later = [], []
    for t in active:
        try:
            dl = date.fromisoformat(str(t["deadline"]).split("T")[0])
        except Exception:
            later.append(t)
            continue
        if dl < monday:
            overdue.append((t, dl))
        elif dl > sunday:
            later.append(t)
        else:
            by_date.setdefault(dl, []).append(t)

    lines = [
        f"📅 *LỊCH TUẦN {monday.strftime('%d/%m')} – {sunday.strftime('%d/%m/%Y')}*",
        f"_(hôm nay: {today.strftime('%A %d/%m').replace('Monday','Thứ 2').replace('Tuesday','Thứ 3').replace('Wednesday','Thứ 4').replace('Thursday','Thứ 5').replace('Friday','Thứ 6').replace('Saturday','Thứ 7').replace('Sunday','CN')})_\n",
    ]

    for i in range(7):
        day = monday + timedelta(i)
        is_today = (day == today)
        marker = "▶" if is_today else "•"
        suffix = "  ← *hôm nay*" if is_today else ""
        lines.append(f"{marker} *{days_vi[i]} {day.strftime('%d/%m')}*{suffix}")

        day_tasks = by_date.get(day, [])
        if day_tasks:
            for t in day_tasks:
                em = status_emoji.get(t["status"], "❓")
                lines.append(f"   {em} \\#{t['id']} {_esc(t['title'][:40])} _({_esc(t['owner'])})_")
        else:
            lines.append("   _— trống —_")

    # Quá hạn
    if overdue:
        lines.append(f"\n🔴 *Quá hạn — {len(overdue)} task:*")
        for t, dl in sorted(overdue, key=lambda x: x[1]):
            diff = (today - dl).days
            lines.append(f"   \\#{t['id']} {_esc(t['title'][:40])} _({_esc(t['owner'])}, quá {diff}n)_")

    # Sau tuần này
    if later:
        lines.append(f"\n📆 *Sau tuần này — {len(later)} task:*")
        for t in sorted(later, key=lambda x: str(x.get("deadline", "9999"))):
            dl_str = str(t.get("deadline", "?")).split("T")[0]
            lines.append(f"   \\#{t['id']} {_esc(t['title'][:40])} _({dl_str})_")

    total = len(active)
    this_week = sum(len(v) for v in by_date.values())
    lines.append(f"\n📊 *Tổng: {total} task chưa xong | {this_week} task trong tuần*")
    return "\n".join(lines)


async def morning_checkin(context: ContextTypes.DEFAULT_TYPE):
    """8:00 — task deadline hôm nay chưa hoàn thành."""
    today = datetime.now(TZ).date()
    active = [t for t in tm.list() if t["status"] != "completed"]

    overdue, due_today = [], []
    for t in active:
        try:
            dl = date.fromisoformat(str(t["deadline"]).split("T")[0])
        except Exception:
            continue
        diff = (dl - today).days
        if diff < 0:
            overdue.append((t, abs(diff)))
        elif diff == 0:
            due_today.append(t)

    if not overdue and not due_today:
        await context.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=f"🌅 *Buổi sáng {today.strftime('%d/%m/%Y')}*\n\n✅ Không có task nào deadline hôm nay.",
            parse_mode="Markdown",
        )
        return

    lines = [f"🌅 *Buổi sáng {today.strftime('%d/%m/%Y')} — Task cần xử lý hôm nay:*\n"]
    if overdue:
        lines.append("🔴 *Quá hạn — cần giải quyết ngay:*")
        for t, days in overdue:
            lines.append(f"  • \\#{t['id']} {_esc(t['title'])} — {_esc(t['owner'])} _(quá {days} ngày)_")
    if due_today:
        lines.append("\n🟠 *Deadline hôm nay:*")
        for t in due_today:
            lines.append(f"  • \\#{t['id']} {_esc(t['title'])} — {_esc(t['owner'])}")

    await context.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


async def evening_review(context: ContextTypes.DEFAULT_TYPE):
    """21:00 — toàn bộ task chưa hoàn thành để lập kế hoạch."""
    today = datetime.now(TZ).date()
    active = [t for t in tm.list() if t["status"] != "completed"]

    if not active:
        await context.bot.send_message(
            chat_id=ALLOWED_USER_ID,
            text=f"🌙 *Tổng kết {today.strftime('%d/%m/%Y')}*\n\n✅ Tất cả task đã hoàn thành!",
            parse_mode="Markdown",
        )
        return

    pending     = [t for t in active if t["status"] == "pending"]
    in_progress = [t for t in active if t["status"] == "in_progress"]

    lines = [f"🌙 *Tổng kết {today.strftime('%d/%m/%Y')} — {len(active)} task chưa hoàn thành:*\n"]

    if in_progress:
        lines.append(f"🔄 *Đang làm ({len(in_progress)} task):*")
        for t in in_progress:
            try:
                dl = date.fromisoformat(str(t["deadline"]).split("T")[0])
                diff = (dl - today).days
                flag = " 🔴" if diff < 0 else (" 🟠" if diff == 0 else "")
            except Exception:
                flag = ""
            lines.append(f"  • \\#{t['id']} {_esc(t['title'])} — {_esc(t['owner'])} | {t['deadline']}{flag}")

    if pending:
        lines.append(f"\n⏳ *Chờ xử lý ({len(pending)} task):*")
        for t in pending:
            try:
                dl = date.fromisoformat(str(t["deadline"]).split("T")[0])
                diff = (dl - today).days
                flag = " 🔴" if diff < 0 else (" 🟠" if diff == 0 else "")
            except Exception:
                flag = ""
            lines.append(f"  • \\#{t['id']} {_esc(t['title'])} — {_esc(t['owner'])} | {t['deadline']}{flag}")

    lines.append("\n_🔴 quá hạn  🟠 hôm nay_")

    await context.bot.send_message(
        chat_id=ALLOWED_USER_ID,
        text="\n".join(lines),
        parse_mode="Markdown",
    )


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    msg = _build_reminder_message()
    if msg:
        await update.message.reply_text(msg, parse_mode="Markdown")
    else:
        await update.message.reply_text("✅ Không có task nào sắp đến hạn.")


async def week_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    await update.message.reply_text(_build_weekly_view(), parse_mode="Markdown")


async def bulk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /bulk field=value id1 id2 ... hoặc /bulk field=value id_start-id_end
    Ví dụ:
      /bulk status=completed 1 2 3 4 5
      /bulk status=in_progress 1-5
      /bulk owner=Hoàng 1 2 3
      /bulk deadline=2026-05-30 1-5
    """
    if not auth(update):
        return
    args = context.args
    HELP = (
        "📝 *Cú pháp:* `/bulk field=value [ids...]`\n\n"
        "*Fields:*\n"
        "`status=` pending \\| in\\_progress \\| completed\n"
        "`deadline=` YYYY\\-MM\\-DD\n"
        "`owner=` Tên người phụ trách\n\n"
        "*Ví dụ:*\n"
        "`/bulk status=completed 1 2 3 4 5`\n"
        "`/bulk status=in_progress 1-5`\n"
        "`/bulk owner=Hoàng 1 2 3`\n"
        "`/bulk deadline=2026-05-30 1-5`"
    )
    if not args:
        await update.message.reply_text(HELP, parse_mode="MarkdownV2")
        return

    # Parse field=value pairs và IDs
    fields, id_args = {}, []
    for arg in args:
        if "=" in arg:
            k, v = arg.split("=", 1)
            fields[k.strip()] = v.strip()
        else:
            id_args.append(arg)

    if not fields:
        await update.message.reply_text(HELP, parse_mode="MarkdownV2")
        return

    # Validate fields
    valid = {"status", "deadline", "owner", "notes"}
    bad = set(fields) - valid
    if bad:
        await update.message.reply_text(f"❌ Field không hợp lệ: {', '.join(bad)}\nChỉ dùng: status, deadline, owner, notes")
        return
    if "status" in fields and fields["status"] not in ("pending", "in_progress", "completed"):
        await update.message.reply_text("❌ status phải là: pending | in_progress | completed")
        return

    # Parse IDs
    task_ids = []
    for arg in id_args:
        m = re.match(r'^(\d+)-(\d+)$', arg)
        if m:
            s, e = int(m.group(1)), int(m.group(2))
            task_ids.extend(range(min(s, e), max(s, e) + 1))
        elif arg.isdigit():
            task_ids.append(int(arg))

    if not task_ids:
        await update.message.reply_text("❌ Chưa có ID task. Ví dụ: `/bulk status=completed 1 2 3`", parse_mode="Markdown")
        return

    ok, fail = [], []
    for tid in sorted(set(task_ids)):
        task = tm.update(tid, **fields)
        if task:
            ok.append(f"#{tid}")
        else:
            fail.append(f"#{tid}")

    field_desc = ", ".join(f"{k}={v}" for k, v in fields.items())
    lines = [f"✅ Bulk update ({field_desc}) — {len(ok)}/{len(set(task_ids))} task:"]
    lines.append("  " + "  ".join(ok) if ok else "  (không có)")
    if fail:
        lines.append(f"⚠️ Không tìm thấy: {' '.join(fail)}")
    await update.message.reply_text("\n".join(lines))


async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    args = context.args
    if not args:
        await update.message.reply_text(
            "📝 *Cú pháp:* `/delete [id1] [id2] ...` hoặc `/delete [start]-[end]`\n\n"
            "*Ví dụ:*\n"
            "`/delete 5` — xóa task #5\n"
            "`/delete 28 29 30` — xóa task #28, #29, #30\n"
            "`/delete 28-33` — xóa task từ #28 đến #33",
            parse_mode="Markdown"
        )
        return
    task_ids = []
    for arg in args:
        m = re.match(r'^(\d+)-(\d+)$', arg)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            task_ids.extend(range(min(start, end), max(start, end) + 1))
        elif arg.isdigit():
            task_ids.append(int(arg))
    if not task_ids:
        await update.message.reply_text("❌ Không nhận ra ID task. Ví dụ: `/delete 28-33`", parse_mode="Markdown")
        return
    deleted, not_found = [], []
    for tid in sorted(set(task_ids)):
        task = tm.delete(tid)
        if task:
            deleted.append(f"#{tid} {task['title']}")
        else:
            not_found.append(f"#{tid}")
    lines = []
    if deleted:
        lines.append(f"🗑 Đã xóa {len(deleted)} task:")
        lines.extend(f"  • {d}" for d in deleted)
    if not_found:
        lines.append(f"\n⚠️ Không tìm thấy: {', '.join(not_found)}")
    await update.message.reply_text("\n".join(lines))


async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text(
            "💬 *Hỏi gì đi:*\n\n"
            "`/ask tình hình dự án ACB đến đâu rồi?`\n"
            "`/ask Hoàng đang phụ trách những gì?`\n"
            "`/ask deadline nào đang nguy hiểm nhất?`\n\n"
            "Hoặc chat trực tiếp bằng tiếng Việt tự nhiên.",
            parse_mode="Markdown"
        )
        return
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    answer = qe.answer(question)
    await update.message.reply_text(f"🤖 {answer}")


# ============= NATURAL LANGUAGE HANDLER =============

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not auth(update):
        return

    text = update.message.text
    r = nlp.parse(text)
    intent = r["intent"]

    if intent == "create":
        title = r["title"] or text
        owner = r["owner"] or "Unassigned"
        deadline = r["deadline"] or datetime.now().strftime("%Y-%m-%d")
        task = tm.create(title, owner, deadline)
        await update.message.reply_text(
            f"✅ Tạo task #{task['id']} thành công!\n\n{fmt(task)}",
            parse_mode="Markdown"
        )

    elif intent == "list":
        f = r["filter"]
        tasks = tm.list(f)
        if not tasks:
            await update.message.reply_text("📭 Không có task nào.")
            return
        label = {"today": "hôm nay", "pending": "chưa làm", "in_progress": "đang làm", "active": "chưa hoàn thành"}
        header = f"📋 Tasks {label.get(f, 'tất cả')} ({len(tasks)} task)"
        lines = [fmt(t) for t in tasks]
        # Chia nhỏ nếu vượt giới hạn 4096 ký tự của Telegram
        chunk, chunks = f"*{header}*\n\n", []
        for line in lines:
            if len(chunk) + len(line) + 2 > 4000:
                chunks.append(chunk.rstrip())
                chunk = line + "\n\n"
            else:
                chunk += line + "\n\n"
        if chunk.strip():
            chunks.append(chunk.rstrip())
        for i, part in enumerate(chunks):
            prefix = "" if i == 0 else f"_(tiếp — trang {i+1}/{len(chunks)})_\n\n"
            await update.message.reply_text(prefix + part, parse_mode="Markdown")

    elif intent == "update":
        task_id = r.get("task_id")
        task_ids_bulk = r.get("task_ids")
        keyword = r.get("keyword")
        auto_found_title = None

        # MULTI-GROUP DEADLINE — mỗi nhóm task có deadline riêng
        deadline_groups = r.get("deadline_groups")
        if deadline_groups:
            all_lines = ["📅 Cập nhật deadline theo nhóm:"]
            for group_ids, dl in deadline_groups:
                ok, fail = [], []
                for tid in sorted(set(group_ids)):
                    task = tm.update(tid, deadline=dl)
                    if task:
                        ok.append(f"#{tid}")
                    else:
                        fail.append(f"#{tid}")
                line = f"  {dl}: " + " ".join(ok)
                if fail:
                    line += f" (không tìm thấy: {' '.join(fail)})"
                all_lines.append(line)
            total = sum(len(g[0]) for g in deadline_groups)
            all_lines.append(f"\n✅ Tổng cộng {total} task đã cập nhật.")
            await update.message.reply_text("\n".join(all_lines))
            return

        # BULK UPDATE — nhiều task cùng lúc, cùng field
        if task_ids_bulk:
            kwargs = {f: r[f] for f in ("status", "deadline", "owner", "notes") if r.get(f)}
            if not kwargs:
                await update.message.reply_text(
                    "❓ Bạn muốn cập nhật gì cho các task này?\n"
                    "Ví dụ: _Chuyển task 1 2 3 sang đang làm_\n"
                    "hoặc: `/bulk status=in_progress 1 2 3`",
                    parse_mode="Markdown"
                )
                return
            ok, fail = [], []
            for tid in sorted(set(task_ids_bulk)):
                task = tm.update(tid, **kwargs)
                if task:
                    ok.append(f"#{tid}")
                else:
                    fail.append(f"#{tid}")
            field_desc = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            lines = [f"✅ Đã cập nhật {len(ok)} task ({field_desc}):"]
            lines.append("  " + "  ".join(ok))
            if fail:
                lines.append(f"⚠️ Không tìm thấy: {' '.join(fail)}")
            await update.message.reply_text("\n".join(lines))
            return

        # Tìm task theo tên dự án nếu không có task_id
        if not task_id and keyword:
            matches = tm.search(keyword)
            if len(matches) == 0:
                await update.message.reply_text(
                    f"❌ Không tìm thấy task nào liên quan đến *{keyword}*\n\n"
                    f"Dùng `/list` để xem toàn bộ danh sách task.",
                    parse_mode="Markdown"
                )
                return
            elif len(matches) == 1:
                task_id = matches[0]["id"]
                auto_found_title = matches[0]["title"]
            else:
                # Nhiều kết quả → yêu cầu người dùng chọn
                kwargs = {f: r[f] for f in ("status", "deadline", "owner", "notes", "title") if r.get(f)}
                update_desc = ", ".join(f"`{k}={v}`" for k, v in kwargs.items()) if kwargs else "_chưa rõ_"
                lines = [f"• `#{t['id']}` {t['title']} — @{t['owner']}" for t in matches[:5]]
                more = f"\n_...và {len(matches)-5} task khác_" if len(matches) > 5 else ""
                await update.message.reply_text(
                    f"🔍 Tìm thấy *{len(matches)} task* liên quan đến '{keyword}':\n\n"
                    + "\n".join(lines) + more
                    + f"\n\nBạn muốn cập nhật {update_desc} cho task nào?\n"
                    + f"Nhắn: `\"task [số] [nội dung cập nhật]\"`",
                    parse_mode="Markdown"
                )
                return

        if not task_id:
            await update.message.reply_text(
                "❓ Bạn muốn cập nhật task nào?\n\n"
                "• Theo ID: \"task 3 đang làm\"\n"
                "• Theo tên: \"đổi deadline dự án ACB sang 25/5\"\n"
                "• Theo tên: \"giao KMS cho Quốc Anh\""
            )
            return

        kwargs = {f: r[f] for f in ("status", "deadline", "owner", "notes", "title") if r.get(f)}
        if not kwargs:
            await update.message.reply_text(
                "❓ Bạn muốn cập nhật gì?\n\n"
                "• Deadline: \"đổi deadline dự án ACB sang 25/5\"\n"
                "• Người làm: \"giao ACB cho Hoàng\"\n"
                "• Trạng thái: \"task 3 đang làm\"\n"
                "• Ghi chú: \"ghi chú task 3: đã liên hệ KH\""
            )
            return

        task = tm.update(task_id, **kwargs)
        if task:
            updated = ", ".join(kwargs.keys())
            found_note = f"\n_🔍 Tự động tìm: '{auto_found_title}'_" if auto_found_title else ""
            await update.message.reply_text(
                f"✅ Đã cập nhật task #{task_id} ({updated})!{found_note}\n\n{fmt(task)}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"❌ Không tìm thấy task #{task_id}")

    elif intent == "complete":
        task_ids_bulk = r.get("task_ids")
        task_id = r.get("task_id")

        # BULK complete
        if task_ids_bulk:
            ok, fail = [], []
            for tid in sorted(set(task_ids_bulk)):
                task = tm.update(tid, status="completed")
                if task:
                    ok.append(f"#{tid} {task['title']}")
                else:
                    fail.append(f"#{tid}")
            lines = [f"✅ Hoàn thành {len(ok)} task:"]
            lines.extend(f"  • {t}" for t in ok)
            if fail:
                lines.append(f"⚠️ Không tìm thấy: {' '.join(fail)}")
            await update.message.reply_text("\n".join(lines))
            return

        # Single complete
        if not task_id:
            await update.message.reply_text("❓ Task số mấy đã xong?")
            return
        notes = r["notes"] or ""
        task = tm.update(task_id, status="completed", notes=notes)
        if task:
            resp = f"✅ Hoàn thành task #{task_id}!\n\n{fmt(task)}"
            if notes:
                resp += f"\n📝 Notes: {notes}"
            await update.message.reply_text(resp, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"❌ Không tìm thấy task #{task_id}")

    elif intent == "delete":
        task_ids = r.get("task_ids") or []
        if not task_ids:
            await update.message.reply_text(
                "❓ Xóa task nào?\n"
                "Ví dụ: _Xóa task #5_ hoặc _Xóa các task từ #28 đến #33_",
                parse_mode="Markdown"
            )
            return
        deleted, not_found = [], []
        for tid in sorted(set(task_ids)):
            task = tm.delete(tid)
            if task:
                deleted.append(f"#{tid} {task['title']}")
            else:
                not_found.append(f"#{tid}")
        lines = []
        if deleted:
            lines.append(f"🗑 Đã xóa {len(deleted)} task:")
            lines.extend(f"  • {d}" for d in deleted)
        if not_found:
            lines.append(f"\n⚠️ Không tìm thấy: {', '.join(not_found)}")
        await update.message.reply_text("\n".join(lines))

    elif intent == "status":
        s = tm.summary()
        await update.message.reply_text(
            f"*📊 Tóm tắt task*\n\n"
            f"⏳ Pending: {s['pending']}\n"
            f"🔄 In Progress: {s['in_progress']}\n"
            f"✅ Completed: {s['completed']}\n"
            f"📈 Total: {s['total']}",
            parse_mode="Markdown"
        )

    elif intent == "standup":
        today = datetime.now().strftime("%Y-%m-%d")
        tasks = tm.list("today")
        if not tasks:
            await update.message.reply_text(f"📭 Không có task nào hôm nay ({today})")
            return
        body = "\n\n".join(fmt(t) for t in tasks)
        await update.message.reply_text(
            f"*🌅 Standup - {today}*\n\n📋 {len(tasks)} task hôm nay:\n\n{body}",
            parse_mode="Markdown"
        )

    elif intent == "weekly":
        await update.message.reply_text(_build_weekly_view(), parse_mode="Markdown")

    elif intent == "query":
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        answer = qe.answer(text)
        await update.message.reply_text(f"🤖 {answer}")

    else:
        await update.message.reply_text(
            "❓ Tôi chưa hiểu yêu cầu này.\n\n"
            "Thử các cách diễn đạt:\n"
            "• \"Tạo task [tên] cho [người] ngày [dd/mm]\"\n"
            "• \"Danh sách task hôm nay\"\n"
            "• \"Task 1 đang làm\" hoặc \"Xong task 2\"\n"
            "• \"Tình hình dự án ACB đến đâu rồi?\"\n\n"
            "Hoặc gõ /help để xem lệnh."
        )


# ============= PID LOCK =============

PID_FILE = Path(__file__).parent / "bot.pid"

def _is_running(pid: int) -> bool:
    """Kiểm tra process còn sống trên Windows/Linux."""
    try:
        if sys.platform == 'win32':
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x0400, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return exit_code.value == 259  # STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _acquire_lock():
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if _is_running(old_pid):
                print(f"\n❌ Bot đã chạy rồi (PID {old_pid})!")
                print(f"   Để dừng: Stop-Process -Id {old_pid} -Force")
                sys.exit(1)
        except (ValueError, OSError):
            pass
    PID_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: PID_FILE.unlink(missing_ok=True))

# ============= MAIN =============

def main():
    _acquire_lock()

    print("\n" + "=" * 55)
    print("🤖 FOXAI Task Manager Bot v3.0")
    print("   GPT-4o-mini NLP — tiếng Việt tự nhiên")
    print("=" * 55)

    if not TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN chưa cấu hình")
        return
    if not ALLOWED_USER_ID:
        print("❌ TELEGRAM_ALLOWED_USER_ID chưa cấu hình")
        return

    print(f"✅ Token: {TOKEN[:20]}...")
    print(f"✅ User ID: {ALLOWED_USER_ID}")
    print(f"✅ Tasks: {TASKS_FILE}")
    nlp_status = "GPT-4o-mini ✅ (fallback: Regex)" if nlp._client else "Regex-only (không có OPENAI_API_KEY)"
    print(f"✅ NLP: {nlp_status}")
    qa_status = "GPT-4o-mini ✅ (fallback: local search)" if qe._client else "Local search only"
    print(f"✅ Q&A: {qa_status}")
    print(f"✅ Reminder: {REMINDER_HOUR:02d}:{REMINDER_MINUTE:02d} ({TZ})")
    print()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("create", create_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("update", update_cmd))
    app.add_handler(CommandHandler("complete", complete_cmd))
    app.add_handler(CommandHandler("status", status_cmd))
    app.add_handler(CommandHandler("standup", standup_cmd))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("week", week_cmd))
    app.add_handler(CommandHandler("bulk", bulk_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler tự động
    import datetime as _dt
    # 08:00 — task deadline hôm nay (buổi sáng)
    app.job_queue.run_daily(morning_checkin, time=_dt.time(8, 0, tzinfo=TZ))
    # 21:00 — toàn bộ task chưa hoàn thành (lập kế hoạch tối)
    app.job_queue.run_daily(evening_review,  time=_dt.time(21, 0, tzinfo=TZ))

    print("⏳ Polling...\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
