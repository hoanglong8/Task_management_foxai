# FOXAI Task Manager Bot — Quick Start

**Bot:** `@Long_foxai_bot` | **Version:** 4.0 | **Cập nhật:** 2026-05-22

---

## Khởi động bot

```powershell
cd "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot"
.\start_bot.ps1
```

Thấy `Bot running — PID XXXXX` là OK.

---

## Các lệnh có sẵn

| Lệnh | Mô tả |
|------|-------|
| `/start` | Khởi động bot |
| `/help` | Hiện tất cả lệnh |
| `/create [title] @owner [deadline]` | Tạo task |
| `/list [today\|pending\|in_progress\|@owner]` | Liệt kê task |
| `/update [id] field=value ...` | Cập nhật task |
| `/complete [id] [notes]` | Đánh dấu hoàn thành |
| `/remind` | Xem task sắp đến hạn |
| `/ask [câu hỏi]` | Hỏi đáp về dự án & nhân sự |
| `/status` | Tóm tắt số liệu |
| `/standup` | Task hôm nay |

---

## Chat tiếng Việt tự nhiên — Ví dụ thực tế

### Tạo task
```
Tạo task hoàn thiện tài liệu BA cho Quốc Anh ngày 30/5
Giao việc review code cho Việt Hoàng, hạn 25/5
Thêm task họp khách hàng ACB cho Long ngày 28/5
```

### Cập nhật theo ID
```
Task 3 đang làm
Xong task 5 rồi, test OK
Đổi deadline task 3 sang 30/5
Giao lại task 7 cho Quốc Anh
Ghi chú task 2: đã liên hệ khách hàng, chờ phản hồi
Đổi tên task 4 thành Hoàn thiện thiết kế database
```

### Cập nhật theo tên dự án (không cần ID)
```
Thay đổi deadline dự án ACB sang ngày 25/05
Gia hạn KMS đến 31/5
Giao dự án IOC cho Quốc Anh
Ghi chú ACB: đã demo xong, chờ feedback khách hàng
```

### Xem danh sách
```
Danh sách task hôm nay
Xem task đang làm
Có task gì chưa làm?
Liệt kê tất cả task
```

### Hỏi đáp về dự án
```
Tình hình dự án ACB đến đâu rồi?
Hoàng đang phụ trách những gì?
Deadline nào đang nguy hiểm nhất?
Ai đang làm gì liên quan đến KMS?
```

### Lệnh `/update` nâng cao
```
/update 3 status=in_progress
/update 3 deadline=2026-05-30
/update 5 owner=Quốc Anh
/update 3 notes=Đã liên hệ KH, chờ phản hồi
/update 3 status=in_progress deadline=2026-05-30 owner=Hoàng
```

---

## Cấu hình `.env`

```env
# Bắt buộc
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_ALLOWED_USER_ID=your_user_id

# NLP (nếu không có → dùng Regex fallback)
OPENAI_API_KEY=sk-proj-xxxxx

# Lưu trữ
TASKS_FILE=D:\FoxAI\FOXAI_PRM project_resource_management\daily\tasks.json

# Nhắc deadline tự động (mặc định 09:00 VN)
REMINDER_HOUR=9
REMINDER_MINUTE=0
TIMEZONE=Asia/Ho_Chi_Minh
```

---

## Troubleshooting

| Vấn đề | Nguyên nhân | Giải pháp |
|--------|------------|-----------|
| Bot không phản hồi | Process chết | Chạy lại `.\start_bot.ps1` |
| "Tôi chưa hiểu..." | NLP không nhận | Thử cách diễn đạt khác hoặc dùng slash command |
| NLP trả lời chậm | OpenAI API | Bình thường ~1-2s; nếu >5s → check internet |
| Không tìm thấy task | Keyword sai | Dùng `/list` xem đúng tên rồi search lại |
| Reminder không tới | Bot chưa chạy lúc 9h | Đảm bảo bot chạy liên tục (xem phần 8 setup_guide) |

---

## Kiến trúc NLP

```
Tin nhắn tiếng Việt
        │
        ▼
   OpenAI GPT-4o-mini  ──lỗi──▶  RegexNLP Fallback
        │                              │
        └──────────────┬───────────────┘
                       ▼
              Intent Classification
              ┌─────────────────┐
              │ create          │ → Tạo task mới
              │ list            │ → Liệt kê task
              │ update          │ → Cập nhật (by ID hoặc keyword)
              │ complete        │ → Đánh dấu xong
              │ status          │ → Tóm tắt số liệu
              │ standup         │ → Task hôm nay
              │ query           │ → Q&A qua QueryEngine
              └─────────────────┘
```

---

**Hỗ trợ:** Liên hệ R&D Team — FOXAI Delivery Center
