# Changelog - FOXAI Task Manager Bot

---

## Version 4.0 (2026-05-22) — NLP theo tên dự án

### Tính năng mới

#### Cập nhật task theo tên dự án (không cần ID)
Bot có thể tìm task theo từ khóa tên dự án và cập nhật trực tiếp:

```
"thay đổi deadline dự án ACB sang ngày 25/05"
"gia hạn KMS đến 31/5"
"giao dự án IOC cho Quốc Anh"
"ghi chú ACB: đã liên hệ khách hàng"
```

**Logic xử lý:**
- **1 kết quả khớp** → cập nhật ngay, hiện thông báo tự động tìm
- **Nhiều kết quả** → liệt kê danh sách, yêu cầu chọn bằng ID
- **0 kết quả** → thông báo lỗi + gợi ý `/list`

#### TaskManager.search()
Phương thức tìm kiếm task active theo keyword trong title.

### Thay đổi kỹ thuật
- Thêm field `keyword` vào NLP schema (RegexNLP + OpenAINLP)
- Thêm method `_keyword_update()` trong `RegexNLP`
- Thêm method `search(keyword)` trong `TaskManager`
- Cập nhật `handle_message` update handler để xử lý 3 trường hợp (0/1/nhiều kết quả)
- Cập nhật OpenAI system prompt với hướng dẫn trích xuất `keyword`

---

## Version 3.1 (2026-05-22) — Q&A ngôn ngữ tự nhiên

### Tính năng mới

#### QueryEngine — Hỏi đáp thông minh
Cho phép hỏi bất kỳ câu hỏi mở về dự án, nhân sự, tiến độ:

```
"Tình hình dự án ACB đến đâu rồi?"
"Hoàng đang phụ trách những gì?"
"Deadline nào đang nguy hiểm nhất?"
"Ai phụ trách dự án KMS?"
```

**Nguồn dữ liệu bot tra cứu:**
- Toàn bộ task đang active (status, owner, deadline, ghi chú)
- Danh sách nhân sự FOXAI (`Danh_sach_nhan_su_FOXAI.md`)
- Project memory files (`memory/*.md`)
- Báo cáo công việc gần nhất (`Bao_cao*.md`)

**Fallback khi không có API:**
- Câu hỏi về quá hạn → lọc task trong `tasks.json`
- Câu hỏi về người cụ thể → filter theo owner name
- Câu hỏi về dự án → tìm keyword trong task title

#### Lệnh `/ask`
```
/ask tình hình dự án ACB đến đâu rồi?
/ask Hoàng đang phụ trách gì?
/ask deadline nào nguy hiểm nhất?
```

### Thay đổi kỹ thuật
- Thêm class `QueryEngine` với method `answer()` và `_fallback()`
- Thêm intent `query` vào RegexNLP và OpenAINLP prompt
- Tách `"tình hình"` khỏi STATUS keywords (nhường cho query)
- Thêm `ChatAction.TYPING` indicator khi xử lý Q&A
- Import `from telegram.constants import ChatAction`

---

## Version 3.0 (2026-05-21) — Cập nhật nội dung task qua NLP

### Tính năng mới

#### Cập nhật đa trường qua chat tự nhiên
Không chỉ status, giờ có thể cập nhật mọi trường của task:

```
"Đổi deadline task 3 sang 30/5"
"Giao lại task 5 cho Quốc Anh"
"Ghi chú task 3: đã liên hệ KH, chờ phản hồi"
"Đổi tên task 1 thành Hoàn thiện tài liệu BA"
```

#### Lệnh `/update` mở rộng
Cú pháp mới hỗ trợ `field=value`:
```
/update 3 deadline=2026-05-30
/update 5 owner=Hoàng
/update 3 status=in_progress deadline=2026-05-30
/update 2 notes=Đã liên hệ KH
/update 1 title=Hoàn thiện tài liệu BA
```
Backward compatible — cú pháp cũ `/update 3 in_progress` vẫn hoạt động.

#### Hiển thị ghi chú trong `fmt()`
Task display giờ hiện thêm dòng `📝 [notes]` nếu có ghi chú.

### Thay đổi kỹ thuật
- Mở rộng `RegexNLP`: thêm pattern nhận diện update deadline/owner/notes/title
- Mở rộng OpenAI prompt: update intent bao gồm tất cả trường
- Rewrite `update_cmd()` để parse `field=value` pairs
- Rewrite `handle_message` update handler để apply nhiều trường cùng lúc

---

## Version 2.1 (2026-05-21) — Deadline Reminder tự động

### Tính năng mới

#### Nhắc deadline tự động hàng ngày
Bot tự động gửi thông báo mỗi sáng theo giờ cấu hình:

```
⏰ Nhắc deadline — 22/05/2026

🔴 Quá hạn:
  • #5 Task A — @Hoàng (quá 3 ngày)

🟠 Hôm nay:
  • #8 Task B — @Quốc Anh

🟡 Ngày mai:
  • #12 Task C — @Tiến

🟢 Trong 3 ngày:
  • #15 Task D — @Long (còn 2 ngày)
```

#### Lệnh `/remind` (trigger thủ công)
Xem ngay danh sách task sắp đến hạn bất cứ lúc nào.

#### Cấu hình giờ nhắc
Trong `.env`:
```
REMINDER_HOUR=9
REMINDER_MINUTE=0
TIMEZONE=Asia/Ho_Chi_Minh
```

### Thay đổi kỹ thuật
- Cài thêm `apscheduler==3.10.4` và `pytz`
- Thêm hàm `_build_reminder_message()` phân loại task theo deadline
- Thêm job `deadline_reminder` chạy daily qua `app.job_queue.run_daily()`
- Đổi requirements sang `python-telegram-bot[job-queue]>=21.0`

---

## Version 2.0 (2026-05-21) — Hybrid NLP (API + Regex Fallback)

### Tính năng mới

#### Regex Fallback NLP
Khi OpenAI API lỗi (hết quota, mất mạng), bot tự động chuyển sang Regex NLP:
- Không bị downtime khi API không khả dụng
- Xử lý ~85% use case thông dụng mà không cần API
- Transparent với người dùng — phản hồi y hệt

#### Luồng Hybrid
```
Tin nhắn → OpenAI GPT-4o-mini (primary)
                ↓ lỗi
           RegexNLP (fallback, luôn hoạt động)
```

### Thay đổi kỹ thuật
- Thêm class `RegexNLP` với đầy đủ parser tiếng Việt
- Sửa `OpenAINLP.parse()` để gọi `_regex_nlp.parse()` khi exception
- Sửa trường hợp `_client = None` (thiếu API key) cũng dùng regex
- Thêm instance `_regex_nlp = RegexNLP()` làm singleton

---

## Version 1.1 (2026-05-15) — Claude AI NLP

### Tính năng mới
- Chat tiếng Việt tự nhiên (không cần `/` command)
- Tích hợp Claude API để phân tích intent
- Typing indicator khi xử lý
- Phản hồi bằng emoji và Markdown

---

## Version 1.0 (2026-05-14) — Initial Release

### Tính năng
- Telegram Bot với slash commands
- `/create` — Tạo task
- `/list [filter]` — Liệt kê task (today/pending/in_progress/@owner)
- `/update [id] [status]` — Cập nhật trạng thái
- `/complete [id] [notes]` — Đánh dấu hoàn thành
- `/status` — Tóm tắt tổng quan
- `/standup` — Danh sách task hôm nay
- JSON storage cho tasks
- User ID authentication

---

**Bot:** `@Long_foxai_bot`  
**Maintained by:** FOXAI Delivery Center
