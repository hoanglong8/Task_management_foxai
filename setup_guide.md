# FOXAI Task Manager Bot — Setup Guide

**Version:** 4.0 | **Cập nhật:** 2026-05-22  
**Bot:** `@Long_foxai_bot` | **Platform:** Windows 11, Python 3.11

---

## Mục lục

1. [Yêu cầu hệ thống](#1-yêu-cầu-hệ-thống)
2. [Tạo Telegram Bot](#2-tạo-telegram-bot)
3. [Cài đặt môi trường](#3-cài-đặt-môi-trường)
4. [Cấu hình `.env`](#4-cấu-hình-env)
5. [Chạy bot](#5-chạy-bot)
6. [Kiến trúc hệ thống](#6-kiến-trúc-hệ-thống)
7. [Tất cả tính năng](#7-tất-cả-tính-năng)
8. [Chạy liên tục (Production)](#8-chạy-liên-tục-production)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Yêu cầu hệ thống

- Windows 10/11 (hoặc Linux/macOS)
- Python 3.11+
- Kết nối Internet (để nhận lệnh Telegram)
- Tài khoản Telegram

**Dependencies (cài tự động):**
```
python-telegram-bot[job-queue]>=21.0
python-dotenv==1.0.0
openai>=1.0.0
apscheduler==3.10.4
pytz>=2024.1
```

---

## 2. Tạo Telegram Bot

### 2.1 Tạo bot qua BotFather

1. Mở Telegram → tìm `@BotFather`
2. Gửi `/newbot`
3. Đặt tên hiển thị: `FOXAI Task Manager`
4. Đặt username: `foxai_taskmanager_bot` (phải unique, kết thúc `_bot`)
5. BotFather trả về **Bot Token**: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`
6. Lưu token này — cần cho bước cấu hình

### 2.2 Lấy Telegram User ID của bạn

1. Tìm `@userinfobot` trên Telegram
2. Gửi bất kỳ tin nhắn
3. Bot trả về `Id: XXXXXXXXX` — đây là **User ID** của bạn

---

## 3. Cài đặt môi trường

```powershell
# Di chuyển vào thư mục bot
cd "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot"

# Tạo virtual environment (chỉ làm 1 lần)
python -m venv venv

# Kích hoạt venv
.\venv\Scripts\Activate.ps1

# Cài dependencies
pip install -r requirements.txt
```

**Kiểm tra cài đặt:**
```powershell
python -c "import telegram; print('telegram OK:', telegram.__version__)"
python -c "import apscheduler; print('scheduler OK:', apscheduler.__version__)"
python -c "import openai; print('openai OK')"
```

---

## 4. Cấu hình `.env`

Tạo file `.env` trong thư mục `telegram_bot/`:

```env
# ============================================
# FOXAI Task Manager Bot - Configuration
# ============================================

# --- Telegram ---
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_ALLOWED_USER_ID=5614500730
TELEGRAM_ALLOWED_USER_NAME=your_telegram_username

# --- AI / NLP ---
# OpenAI (primary NLP engine)
OPENAI_API_KEY=sk-proj-xxxxxxxxxx
# Claude (backup - optional)
CLAUDE_API_KEY=sk-ant-xxxxxxxxxx

# --- Storage ---
TASKS_FILE=D:\FoxAI\FOXAI_PRM project_resource_management\daily\tasks.json
STANDUP_DIR=D:\FoxAI\FOXAI_PRM project_resource_management\daily

# --- Scheduler ---
REMINDER_HOUR=9
REMINDER_MINUTE=0
TIMEZONE=Asia/Ho_Chi_Minh

# --- Team Members ---
TEAM_MEMBERS=Nguyễn Hoàng Long,Nguyễn Quốc Anh,Nguyễn Xuân Tiến,Lê Hải Sơn,Lê Ngọc Thắng,Nguyễn Việt Hoàng,Phạm Văn Tụ,Ngô Đức Kiên,Trần Thị Bích Hoài
```

> **Bảo mật:** File `.env` đã được thêm vào `.gitignore`. KHÔNG commit file này.

---

## 5. Chạy bot

### Cách 1: Script khởi động (khuyến nghị)
```powershell
.\start_bot.ps1
```
Script tự động kill instance cũ nếu có, sau đó start bot mới.

### Cách 2: Chạy trực tiếp
```powershell
.\venv\Scripts\python.exe foxai_task_bot.py
```

### Cách 3: Chạy trong background (PowerShell)
```powershell
Start-Process -FilePath ".\venv\Scripts\python.exe" `
    -ArgumentList "foxai_task_bot.py" `
    -WindowStyle Hidden
```

**Startup output khi thành công:**
```
=======================================================
🤖 FOXAI Task Manager Bot v4.0
=======================================================
✅ Token: 886022886...
✅ User ID: 5614500730
✅ Tasks: D:\FoxAI\...\tasks.json
✅ NLP: GPT-4o-mini ✅ (fallback: Regex)
✅ Q&A: GPT-4o-mini ✅ (fallback: local search)
✅ Reminder: 09:00 (Asia/Ho_Chi_Minh)

⏳ Polling...
```

---

## 6. Kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────┐
│              NGƯỜI DÙNG (Telegram)                  │
└──────────────────────┬──────────────────────────────┘
                       │ tin nhắn / lệnh
                       ▼
┌─────────────────────────────────────────────────────┐
│              Telegram Bot API (Polling)             │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                 AUTH LAYER                          │
│            (TELEGRAM_ALLOWED_USER_ID)               │
└──────────────────────┬──────────────────────────────┘
                       │
            ┌──────────┴──────────┐
            │ Slash Command?       │ Text tự nhiên?
            ▼                     ▼
    Command Handler         Hybrid NLP Engine
    (/create, /list,        ┌──────────────┐
     /update, /ask...)      │ OpenAI       │ primary
                            │ GPT-4o-mini  │
                            └──────┬───────┘
                                   │ lỗi
                            ┌──────▼───────┐
                            │ RegexNLP     │ fallback
                            │ (luôn hoạt)  │
                            └──────┬───────┘
                                   │
                       ┌───────────▼───────────┐
                       │   Intent Routing      │
                       │ create / list /       │
                       │ update / complete /   │
                       │ status / standup /    │
                       │ query                 │
                       └───────────┬───────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
               TaskManager   QueryEngine    Scheduler
               (CRUD JSON)   (Q&A + LLM)   (Reminder)
                    │
                    ▼
              tasks.json
```

### Luồng xử lý update theo tên dự án
```
"thay đổi deadline dự án ACB sang 25/5"
    │
    ▼ NLP → intent=update, keyword="ACB", deadline="2026-05-25"
    │
    ▼ TaskManager.search("ACB")
    │
    ├── 0 kết quả → báo lỗi
    ├── 1 kết quả → cập nhật + hiện kết quả
    └── N kết quả → hiện danh sách, yêu cầu chọn ID
```

---

## 7. Tất cả tính năng

### 7.1 Slash Commands

| Lệnh | Cú pháp | Ví dụ |
|------|---------|-------|
| `/start` | `/start` | Khởi động |
| `/help` | `/help` | Xem hướng dẫn |
| `/create` | `/create [title] @owner [YYYY-MM-DD]` | `/create Build API @Hoàng 2026-05-30` |
| `/list` | `/list [today\|pending\|in_progress\|@owner]` | `/list today` |
| `/update` | `/update [id] field=value ...` | `/update 3 deadline=2026-05-30 owner=Hoàng` |
| `/complete` | `/complete [id] [notes]` | `/complete 5 Đã test OK, deploy thành công` |
| `/remind` | `/remind` | Xem task sắp đến hạn |
| `/ask` | `/ask [câu hỏi]` | `/ask tình hình dự án ACB?` |
| `/status` | `/status` | Tóm tắt pending/in_progress/completed |
| `/standup` | `/standup` | Task deadline hôm nay |

**Fields cho `/update`:**
- `status` = `pending` | `in_progress` | `completed`
- `deadline` = `YYYY-MM-DD`
- `owner` = Tên người phụ trách
- `notes` = Nội dung ghi chú
- `title` = Tên task mới

### 7.2 Chat ngôn ngữ tự nhiên — Nhận diện intent

**CREATE — Tạo task**
```
Tạo task [tên] cho [người] ngày [dd/mm]
Giao việc [tên] cho [người], hạn [dd/mm]
Thêm task [tên] @[người] [dd/mm]
```

**LIST — Xem danh sách**
```
Danh sách task hôm nay
Xem task đang làm
Có task gì chưa làm?
Tất cả task
```

**UPDATE theo ID — Cập nhật task**
```
Task 3 đang làm
Xong task 5 rồi
Đổi deadline task 3 sang 30/5
Giao lại task 7 cho Quốc Anh
Ghi chú task 2: [nội dung]
Đổi tên task 4 thành [tên mới]
```

**UPDATE theo tên dự án — Không cần biết ID**
```
Thay đổi deadline dự án [tên] sang ngày [dd/mm]
Gia hạn [tên] đến [dd/mm]
Giao [tên dự án] cho [người]
Ghi chú [tên dự án]: [nội dung]
```

**COMPLETE — Hoàn thành**
```
Xong task 3 rồi
Hoàn thành task 5, test OK
Done task 7
```

**STATUS — Tóm tắt số liệu**
```
Tóm tắt công việc
Bao nhiêu task
Tổng quan
Báo cáo
```

**STANDUP — Task hôm nay**
```
Standup
Hôm nay làm gì?
Công việc hôm nay
```

**QUERY — Hỏi đáp thông minh**
```
Tình hình dự án ACB đến đâu rồi?
Hoàng đang phụ trách gì?
Deadline nào nguy hiểm nhất?
Ai đang làm gì liên quan đến KMS?
[Bất kỳ câu kết thúc bằng dấu ?]
```

### 7.3 Nhắc deadline tự động

Bot tự động gửi tin nhắn mỗi ngày lúc 09:00 (cấu hình qua `REMINDER_HOUR`):

```
⏰ Nhắc deadline — 22/05/2026

🔴 Quá hạn:
  • #5 Task A — @Hoàng (quá 3 ngày)
  • #8 Task B — @Tiến (quá 1 ngày)

🟠 Hôm nay:
  • #12 Task C — @Quốc Anh

🟡 Ngày mai:
  • #15 Task D — @Long

🟢 Trong 3 ngày:
  • #18 Task E — @Việt Hoàng (còn 2 ngày)
```

Chỉ hiện nếu có ít nhất 1 task trong các nhóm trên. Task đã `completed` không được nhắc.

---

## 8. Chạy liên tục (Production)

### 8.1 Windows Task Scheduler (cách đơn giản nhất)

1. Mở **Task Scheduler** (tìm trong Start menu)
2. **Create Basic Task** → đặt tên `FOXAI Bot`
3. Trigger: **At startup**
4. Action: **Start a program**
   - Program: `D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot\venv\Scripts\python.exe`
   - Arguments: `foxai_task_bot.py`
   - Start in: `D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot`
5. **Finish** → chuột phải → **Run** để test ngay

### 8.2 NSSM Windows Service (khuyến nghị cho server)

Download NSSM từ https://nssm.cc, sau đó:

```powershell
# Cài đặt service
nssm install FoxaiBot "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot\venv\Scripts\python.exe"
nssm set FoxaiBot AppParameters "foxai_task_bot.py"
nssm set FoxaiBot AppDirectory "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot"
nssm set FoxaiBot AppStdout "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot\logs\bot.log"
nssm set FoxaiBot AppStderr "D:\FoxAI\FOXAI_PRM project_resource_management\telegram_bot\logs\bot-error.log"
nssm set FoxaiBot Start SERVICE_AUTO_START

# Khởi động
nssm start FoxaiBot

# Kiểm tra
nssm status FoxaiBot
```

### 8.3 Kiểm tra bot có đang chạy không

```powershell
# Đọc PID từ file
$storedPid = [int](Get-Content ".\bot.pid")
$proc = Get-Process -Id $storedPid -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "Bot RUNNING — PID $storedPid, RAM $([math]::Round($proc.WorkingSet64/1MB,1))MB"
} else {
    Write-Host "Bot NOT running"
}
```

---

## 9. Troubleshooting

### Bot không start

**Lỗi:** `TELEGRAM_BOT_TOKEN chưa cấu hình`
```powershell
# Kiểm tra .env có tồn tại không
Test-Path ".\telegram_bot\.env"
# Xem nội dung (ẩn key)
Get-Content ".\telegram_bot\.env" | Where-Object { $_ -notmatch "KEY|TOKEN" }
```

**Lỗi:** `ModuleNotFoundError`
```powershell
.\venv\Scripts\pip.exe install -r requirements.txt
```

**Lỗi:** `Bot đã chạy rồi (PID XXXXX)`
```powershell
.\start_bot.ps1  # Script tự động kill instance cũ
```

### Bot không phản hồi

1. Kiểm tra bot có đang chạy: xem PID file hoặc Task Manager
2. Kiểm tra User ID trong `.env` khớp với Telegram ID của bạn
3. Thử gõ `/start` — nếu không có phản hồi → bot chết

### NLP trả về "Tôi chưa hiểu"

**Nguyên nhân:** OpenAI API lỗi + Regex không match pattern

**Debug:**
```powershell
$venvPython = ".\venv\Scripts\python.exe"
& $venvPython -c @"
import os; from dotenv import load_dotenv; load_dotenv('.env')
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
r = client.chat.completions.create(model='gpt-4o-mini', max_tokens=10,
    messages=[{'role':'user','content':'test'}])
print('API OK')
"@
```

**Nếu API lỗi 429 (quota):** Nạp thêm credits tại platform.openai.com/billing

**Nếu API OK nhưng vẫn "không hiểu":** Thử cách diễn đạt khác hoặc dùng slash command.

### Không tìm thấy task theo tên

**Vấn đề:** `❌ Không tìm thấy task nào liên quan đến 'ACB'`

**Giải pháp:**
1. Dùng `/list` xem đúng tên task
2. Thử keyword ngắn hơn (vd: "ACB" thay vì "dự án ACB 2026")
3. Kiểm tra task chưa bị mark `completed`

### Reminder không tới

1. Kiểm tra bot đang chạy lúc `REMINDER_HOUR:REMINDER_MINUTE`
2. Kiểm tra `TIMEZONE=Asia/Ho_Chi_Minh` trong `.env`
3. Dùng `/remind` để test thủ công

---

## Cấu trúc file

```
telegram_bot/
├── foxai_task_bot.py       ← Main bot (v4.0)
├── .env                    ← Cấu hình (không commit Git)
├── .env.example            ← Template cấu hình
├── requirements.txt        ← Python dependencies
├── start_bot.ps1           ← Script khởi động
├── bot.pid                 ← PID file (tự động tạo khi chạy)
├── setup_guide.md          ← File này
├── QUICK_START.md          ← Hướng dẫn nhanh
├── SETUP_NLP.md            ← Chi tiết về NLP
├── CHANGELOG.md            ← Lịch sử thay đổi
└── venv/                   ← Virtual environment
```

**Data storage:**
```
daily/
└── tasks.json              ← Toàn bộ task data
```

---

**Maintained by:** FOXAI Delivery Center R&D Team  
**Last Updated:** 2026-05-22
