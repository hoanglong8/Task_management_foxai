# FOXAI Task Management Platform

Nền tảng quản lý công việc nội bộ cho **FOXAI Delivery Center** — hỗ trợ 37 nhân viên qua nhiều kênh giao tiếp.

## Tính năng

- **Multi-user**: 37 nhân viên với 3 cấp quyền (admin / manager / member)
- **Multi-platform**: Telegram, Zalo OA, Facebook Messenger, WhatsApp, Web Dashboard, Portal nhúng
- **NLP tiếng Việt**: Nhắn tin tự nhiên (OpenAI GPT-4o-mini + RegexNLP fallback)
- **REST API**: FastAPI với Swagger docs tại `/docs`
- **Audit trail**: Lịch sử thay đổi mọi task
- **Báo cáo**: Standup sáng, kế hoạch tuần, nhắc deadline

## Cài đặt nhanh

### 1. Clone & cấu hình

```bash
git clone https://github.com/hoanglong8/Task_management_foxai.git
cd Task_management_foxai
cp .env.example .env
# Chỉnh sửa .env với các API keys của bạn
```

### 2. Chạy với Docker (khuyến nghị)

```bash
docker-compose up -d
```

Truy cập: `http://localhost:8000`

### 3. Chạy thủ công (dev)

```bash
# Tạo virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Cài dependencies
pip install -r requirements.txt

# Chạy server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# (Tùy chọn) Seed 37 nhân viên FOXAI
python migrations/seed_team.py
```

### 4. Chạy tests

```bash
python -m pytest tests/ -v
```

## Cấu trúc thư mục

```
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings từ .env
│   ├── database.py          # SQLAlchemy setup
│   ├── models/              # Database models (User, Task, Notification)
│   ├── schemas/             # Pydantic schemas
│   ├── services/            # Business logic (task, auth, nlp, report, notification)
│   ├── routers/             # API endpoints (/auth, /tasks, /users, /reports)
│   └── platforms/           # Platform adapters (Telegram, Zalo, Facebook, WhatsApp)
├── frontend/                # Web dashboard (HTML/CSS/JS)
├── embed/                   # Embeddable portal widget
├── migrations/              # SQL schema + team seed script
├── tests/                   # pytest test suite
├── foxai_task_bot.py        # Bot Telegram cũ (single-user, vẫn chạy được)
├── docker-compose.yml
├── Dockerfile
└── .env.example
```

## API Endpoints

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/auth/login` | Đăng nhập, nhận JWT token |
| GET | `/auth/me` | Thông tin user hiện tại |
| GET | `/tasks` | Danh sách task (có filters) |
| POST | `/tasks` | Tạo task mới |
| PATCH | `/tasks/{id}` | Cập nhật task |
| DELETE | `/tasks/{id}` | Xóa task |
| GET | `/tasks/summary` | Thống kê tổng quan |
| GET | `/reports/standup` | Báo cáo standup |
| GET | `/reports/weekly` | Kế hoạch tuần |
| GET | `/users` | Danh sách users (admin) |
| POST | `/webhooks/zalo` | Zalo OA webhook |
| POST | `/webhooks/facebook` | Facebook Messenger webhook |
| POST | `/webhooks/whatsapp` | WhatsApp Business webhook |

Swagger UI: `http://localhost:8000/docs`

## Nhúng vào Portal

```html
<!-- Option 1: Widget script -->
<div id="foxai-tasks"></div>
<script src="https://your-server/embed/widget.js"
        data-api="https://your-server"
        data-token="JWT_TOKEN"
        data-container="#foxai-tasks"></script>

<!-- Option 2: iFrame -->
<iframe src="https://your-server/app?embed=1" width="100%" height="500px" frameborder="0"></iframe>
```

## Phân quyền

| Role | Quyền |
|------|-------|
| `admin` | Toàn quyền |
| `manager` | Tạo/sửa task, xem báo cáo team |
| `member` | Xem task của mình, cập nhật status/notes |

## Liên kết tài khoản Platform

Để nhận nhắc nhở qua Telegram/Zalo/WhatsApp, admin cần liên kết platform ID cho từng user:

```bash
PATCH /users/{id}
{"telegram_id": "123456789", "zalo_id": "abc123"}
```

---

**Version 2.0** — Multi-user, Multi-platform  
**FOXAI Delivery Center** — Nguyễn Hoàng Long
