"""NLP Service — port của RegexNLP + OpenAINLP từ foxai_task_bot.py."""
import re
import json
import logging
from openai import OpenAI
from backend.config import settings

logger = logging.getLogger(__name__)

_EMPTY = {
    "intent": "unknown", "task_id": None, "task_ids": None, "deadline_groups": None,
    "keyword": None, "title": None, "owner": None, "deadline": None,
    "status": None, "filter": None, "notes": None,
}


class RegexNLP:
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
        t = text.lower()
        m = re.search(r'(?:từ\s+)?(?:task\s+)?#?(\d+)\s*(?:đến|-)\s*#?(\d+)\b(?!\s*/)', t)
        if m:
            start, end = int(m.group(1)), int(m.group(2))
            return list(range(min(start, end), max(start, end) + 1))
        ids = re.findall(r'#(\d+)', text)
        if len(ids) >= 2:
            return [int(i) for i in ids]
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
        for w in ['xong', 'done', 'completed', 'finished', 'kết thúc']:
            if w in t:
                return 'completed'
        if 'hoàn thành' in t:
            pos = t.find('hoàn thành')
            prefix = t[max(0, pos - 8):pos]
            if 'chưa ' not in prefix and 'không ' not in prefix:
                return 'completed'
        if any(w in t for w in ['chờ', 'pending', 'chưa làm', 'chưa bắt đầu']):
            return 'pending'
        return None

    def _parse_deadline_groups(self, text: str) -> list:
        date_iter = list(re.finditer(r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{4}))?\b', text))
        if len(date_iter) < 2:
            return []
        dates = []
        for m in date_iter:
            dl = self._deadline(m.group(0))
            if dl:
                dates.append((m.start(), dl))
        if len(set(d for _, d in dates)) < 2:
            return []
        id_iter = list(re.finditer(r'#(\d+)', text))
        if not id_iter:
            return []
        groups: dict = {}
        for id_m in id_iter:
            best_dl, best_dist = None, float('inf')
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
        cleaned = re.sub(r'[#\d\s,\-]', '', kw)
        cleaned = re.sub(r'\b(?:đến|to|sang|tới|và|and)\b', '', cleaned, flags=re.I).strip()
        return len(cleaned) < 2

    def _keyword_update(self, text: str) -> dict | None:
        dl = self._deadline(text)
        owner = self._owner(text)
        if dl:
            m = re.search(
                r'(?:thay đổi|đổi|cập nhật|dời|lùi|điều chỉnh|gia hạn|thay)\s+'
                r'(?:deadline|hạn)?\s*(?:(?:dự án|project|task|của)\s+)?(.+?)'
                r'\s+(?:sang|đến|tới|thành)(?:\s+ngày)?\s+\d',
                text, re.IGNORECASE
            )
            if m:
                kw = re.sub(r'^(dự án|project|task)\s+', '', m.group(1).strip(), flags=re.I).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw):
                    return {"keyword": kw, "deadline": dl}
            m = re.search(
                r'gia hạn\s+(?:(?:dự án|project|task)\s+)?(.+?)\s+(?:đến|sang|tới)\s+\d',
                text, re.IGNORECASE
            )
            if m:
                kw = m.group(1).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw):
                    return {"keyword": kw, "deadline": dl}
        if owner:
            m = re.search(
                r'(?:giao lại|chuyển|assign)\s+(?:(?:dự án|project|task)\s+)?(.+?)\s+(?:cho|sang|thành)\s+',
                text, re.IGNORECASE
            )
            if not m:
                m = re.search(
                    r'giao\s+(?:dự án|project)\s+(.+?)\s+(?:cho|sang|thành)\s+',
                    text, re.IGNORECASE
                )
            if m:
                kw = re.sub(r'^(dự án|project|task)\s+', '', m.group(1).strip(), flags=re.I).strip()
                if kw and len(kw) > 1 and not self._is_id_ref(kw) and kw.lower() != owner.lower():
                    return {"keyword": kw, "owner": owner}
        m = re.search(
            r'(?:ghi chú|thêm ghi chú|note)\s+(?:cho|vào)?\s*'
            r'(?:(?:dự án|project|task)\s+)?(.+?)\s*[:\-]\s*(.+)$',
            text, re.IGNORECASE
        )
        if m:
            kw, notes = m.group(1).strip(), m.group(2).strip()
            if kw and not re.search(r'^\d+$', kw) and notes:
                return {"keyword": kw, "notes": notes}
        return None

    def parse(self, text: str) -> dict:
        r = dict(_EMPTY)
        t = text.lower().strip()

        if any(w in t for w in ['standup', 'stand up', 'sáng nay', 'hôm nay làm gì', 'hôm nay có gì', 'buổi sáng', 'công việc hôm nay']):
            r['intent'] = 'standup'; return r

        if any(w in t for w in ['tóm tắt', 'bao nhiêu task', 'báo cáo', 'tổng quan', 'overview', 'thống kê']):
            r['intent'] = 'status'; return r

        kw_update = self._keyword_update(text)
        if kw_update:
            r['intent'] = 'update'; r.update(kw_update); return r

        task_id = self._task_id(text)
        task_ids = self._task_ids(text)
        status = self._status(text)

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

        if task_ids:
            dl = self._deadline(text)
            owner = self._owner(text)
            groups = self._parse_deadline_groups(text)
            if groups:
                r['intent'] = 'update'; r['deadline_groups'] = groups; return r
            fields = {}
            if dl and ('deadline' in t or 'hạn' in t):
                fields['deadline'] = dl
            if owner and re.search(r'\b(?:giao|chuyển|assign)\b', t) and re.search(r'\bcho\b', t) \
                    and 'deadline' not in t and 'hạn' not in t:
                fields['owner'] = owner
            if status is not None and status != 'completed':
                fields['status'] = status
            if fields:
                r['intent'] = 'update'; r['task_ids'] = task_ids; r.update(fields); return r

        if task_id:
            dl = self._deadline(text)
            deadline_kw = ['đổi deadline', 'thay deadline', 'gia hạn', 'dời deadline', 'deadline mới', 'đổi hạn', 'lùi deadline']
            if any(kw in t for kw in deadline_kw) and dl:
                r['intent'] = 'update'; r['task_id'] = task_id; r['deadline'] = dl; return r
            _has_cho = re.search(r'\bcho\b', t)
            _has_giao = re.search(r'\b(?:giao|chuyển|assign)\b', t)
            if _has_giao and _has_cho:
                owner = self._owner(text)
                if owner:
                    r['intent'] = 'update'; r['task_id'] = task_id; r['owner'] = owner; return r
            notes_kw = ['ghi chú', 'ghi chu', 'note:', 'thêm ghi chú', 'bổ sung']
            for kw in notes_kw:
                if kw in t:
                    m = re.search(
                        r'(?:ghi ch[úu]|note[s]?|thêm ghi ch[úu]|bổ sung)[:\s]+'
                        r'(?:task\s*#?\d+\s*[:\-]?\s*)?(.+)',
                        text, re.IGNORECASE
                    )
                    if m and m.group(1).strip():
                        r['intent'] = 'update'; r['task_id'] = task_id; r['notes'] = m.group(1).strip(); return r
            if status:
                r['intent'] = 'update'; r['task_id'] = task_id; r['status'] = status; return r

        if any(kw in t for kw in ['xóa task', 'xóa việc', 'delete task', 'bỏ task', 'xoá task']) or \
                (('xóa' in t or 'xoá' in t) and re.search(r'#?\d+', t)):
            r['intent'] = 'delete'
            m = re.search(r'(?:từ\s+)?#?(\d+)\s+đến\s+#?(\d+)', t)
            if m:
                start, end = int(m.group(1)), int(m.group(2))
                r['task_ids'] = list(range(min(start, end), max(start, end) + 1))
            else:
                ids = re.findall(r'#?(\d+)', t)
                if ids:
                    r['task_ids'] = [int(i) for i in ids]
            return r

        if any(kw in t for kw in ['tạo task', 'tạo công việc', 'tạo việc', 'giao task', 'giao việc', 'thêm task']):
            r['intent'] = 'create'
            m = re.search(
                r'(?:tạo task|tạo công việc|tạo việc|giao task|giao việc|thêm task)\s+'
                r'(.*?)(?:\s+cho\s|\s+@|\s+ngày\s|\s+hạn\s|$)',
                text, re.IGNORECASE
            )
            r['title'] = m.group(1).strip() if m else None
            r['owner'] = self._owner(text)
            r['deadline'] = self._deadline(text)
            return r

        if any(w in t for w in ['lịch tuần', 'kế hoạch tuần', 'weekly', 'tuần này']):
            r['intent'] = 'weekly'; return r

        if any(w in t for w in ['danh sách', 'liệt kê', 'xem task', 'list task', 'có task gì', 'tất cả task']):
            r['intent'] = 'list'
            if 'hôm nay' in t:
                r['filter'] = 'today'
            elif 'đang làm' in t or 'in_progress' in t:
                r['filter'] = 'in_progress'
            elif 'chưa làm' in t or 'pending' in t:
                r['filter'] = 'pending'
            elif any(w in t for w in ['chưa hoàn thành', 'chưa xong', 'còn lại']):
                r['filter'] = 'active'
            return r

        query_kw = ['tình hình', 'đến đâu', 'như thế nào', 'bao giờ xong', 'ai đang', 'ai phụ trách',
                    'ưu tiên', 'rủi ro', 'tiến độ', 'dự án nào']
        if any(kw in t for kw in query_kw) or text.strip().endswith('?'):
            r['intent'] = 'query'; return r

        return r


OPENAI_SYSTEM_PROMPT = """Bạn là module phân tích tin nhắn quản lý công việc cho FOXAI.
Nhận tin nhắn tiếng Việt, trả về JSON:
{"intent":"create|list|update|complete|delete|status|standup|weekly|query|unknown","task_id":null,"task_ids":null,"keyword":null,"title":null,"owner":null,"deadline":null,"status":null,"filter":null,"notes":null}
DEADLINE → YYYY-MM-DD, năm mặc định 2026. Chỉ trả JSON thuần túy."""

_regex_nlp = RegexNLP()


class OpenAINLP:
    def __init__(self):
        api_key = settings.openai_api_key
        self._client = OpenAI(api_key=api_key, base_url="https://api.openai.com/v1") if api_key else None

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
                    {"role": "system", "content": OPENAI_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            )
            result = json.loads(response.choices[0].message.content.strip())
            merged = {**_EMPTY, **result}
            if merged["task_id"] is not None:
                merged["task_id"] = int(merged["task_id"])
            return merged
        except Exception as e:
            logger.warning(f"OpenAI NLP error: {e} — fallback to RegexNLP")
            return _regex_nlp.parse(text)


nlp = OpenAINLP()
