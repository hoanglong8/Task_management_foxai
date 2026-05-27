# FOXAI Bot — Chi tiết về NLP Engine

**Cập nhật:** 2026-05-22 | **Version:** 4.0

---

## Tổng quan kiến trúc NLP

Bot sử dụng chiến lược **Hybrid NLP** — hai tầng phân tích xếp tầng:

```
Tin nhắn tiếng Việt
        │
        ▼
┌───────────────────┐
│  OpenAI           │  primary — GPT-4o-mini
│  GPT-4o-mini      │  ~1-2 giây, cần internet + API key
└────────┬──────────┘
         │ lỗi (quota, timeout, mất mạng)
         ▼
┌───────────────────┐
│  RegexNLP         │  fallback — luôn hoạt động
│  Fallback         │  <1ms, không cần API
└────────┬──────────┘
         │
         ▼
    Intent + Entities
```

**Lý do dùng Hybrid:**
- OpenAI API hết quota → bot không bị downtime
- RegexNLP cover ~85% use case thông dụng
- Người dùng không biết tầng nào đang xử lý

---

## Danh sách Intent

| Intent | Kích hoạt khi | Dữ liệu trích xuất |
|--------|--------------|-------------------|
| `create` | Tạo/giao/thêm task mới | title, owner, deadline |
| `list` | Xem/liệt kê task | filter (today/pending/in_progress) |
| `update` | Cập nhật task (theo ID hoặc tên) | task_id **hoặc** keyword, + fields |
| `complete` | Đánh dấu hoàn thành | task_id, notes |
| `status` | Tóm tắt thống kê tổng hợp | — |
| `standup` | Standup/task hôm nay | — |
| `query` | Hỏi đáp mở về dự án/nhân sự | — (full text gửi QueryEngine) |
| `unknown` | Không nhận diện được | — |

---

## Schema NLP (JSON output)

```json
{
  "intent":   "create | list | update | complete | status | standup | query | unknown",
  "task_id":  123,
  "keyword":  "ACB",
  "title":    "Tên task",
  "owner":    "Nguyễn Quốc Anh",
  "deadline": "2026-05-25",
  "status":   "pending | in_progress | completed",
  "filter":   "today | pending | in_progress",
  "notes":    "Ghi chú bổ sung"
}
```

**Quy tắc `task_id` vs `keyword`:**
- Nếu tin nhắn có số ID cụ thể ("task 3") → `task_id=3`, `keyword=null`
- Nếu tin nhắn có tên dự án ("dự án ACB") → `task_id=null`, `keyword="ACB"`
- Không bao giờ có cả hai cùng lúc

---

## OpenAI NLP (Primary)

### Cấu hình
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxx
```

### Model
- **GPT-4o-mini** — cân bằng tốc độ/chất lượng/chi phí
- `temperature=0` — output ổn định, không sáng tạo
- `max_tokens=300` — giới hạn response để tiết kiệm chi phí
- `response_format={"type": "json_object"}` — đảm bảo output là JSON hợp lệ

### Chi phí ước tính
- ~50 tin nhắn/ngày × 30 ngày = 1,500 API calls
- Mỗi call ~200 tokens → 300,000 tokens/tháng
- Chi phí: ~**$0.05/tháng** (GPT-4o-mini = $0.15/1M input tokens)

### Khi API lỗi
Các lỗi được bắt và fallback sang RegexNLP:
- `RateLimitError` (429) — hết quota
- `AuthenticationError` (401) — API key sai
- `APIConnectionError` — mất mạng
- `Timeout` — API chậm
- Mọi exception khác

---

## RegexNLP Fallback

Hoạt động hoàn toàn offline, không cần API key.

### Từ khóa nhận diện intent

**STANDUP** (ưu tiên cao nhất):
```python
['standup', 'stand up', 'sáng nay', 'hôm nay làm gì',
 'hôm nay có gì', 'buổi sáng', 'công việc hôm nay']
```

**STATUS** (aggregate stats):
```python
['tóm tắt', 'bao nhiêu task', 'báo cáo',
 'tổng quan', 'overview', 'thống kê']
```
> Lưu ý: "tình hình" KHÔNG thuộc status (→ query), để tránh nuốt câu như "tình hình dự án ACB"

**UPDATE theo tên dự án** (keyword-based):
- Deadline: `thay đổi deadline`, `đổi deadline`, `gia hạn`, `dời deadline`, `lùi deadline`
- Owner: `giao lại`, `giao`, `chuyển`, `assign`
- Notes: `ghi chú`, `thêm ghi chú`, `note`

**UPDATE theo ID**:
- Pattern: `task #?(\d+)` → trích xuất task_id
- Status keywords: `đang làm`, `bắt đầu`, `xong`, `hoàn thành`, `chờ`, `pending`
- Field keywords: `deadline`, `owner`, `ghi chú`, `tên task`, `rename`

**CREATE**:
```python
['tạo task', 'tạo công việc', 'giao task', 'giao việc',
 'thêm task', 'thêm việc', 'tạo mới']
```

**LIST**:
```python
['danh sách', 'liệt kê', 'xem task', 'list task',
 'có task gì', 'tất cả task', 'xem việc']
```

**QUERY** (câu hỏi mở):
```python
['tình hình', 'đến đâu', 'như thế nào', 'thế nào', 'ra sao',
 'bao giờ xong', 'còn bao lâu', 'ai đang', 'ai phụ trách',
 'ưu tiên', 'rủi ro', 'tiến độ', 'làm gì', 'phụ trách gì']
# Hoặc: câu kết thúc bằng dấu ?
```

### Xử lý ngày tháng tiếng Việt

| Định dạng | Ví dụ | Output |
|-----------|-------|--------|
| ISO | `2026-05-15` | `2026-05-15` |
| dd/mm | `15/5` | `2026-05-15` |
| dd/mm/yyyy | `15/5/2026` | `2026-05-15` |
| Chữ | `15 tháng 5` | `2026-05-15` |
| Chữ | `ngày 20 tháng 6` | `2026-06-20` |

Năm mặc định: **2026** khi không có năm.

### Trích xuất tên người (Owner)

Pattern 1 — từ "cho/giao cho":
```
"cho [TÊN]" | "giao cho [TÊN]"
→ Lấy tên, loại bỏ từ theo sau (ngày/hạn/deadline/từ/vào)
```

Pattern 2 — mention:
```
@[username]
```

### Trích xuất keyword (tên dự án)

Pattern deadline update:
```
"[action] [deadline?] [marker?] KEYWORD sang/đến DATE"
Lazy match (.+?) để lấy đúng keyword trước separator
```

Ví dụ parse:
```
"thay đổi deadline dự án ACB sang 25/5"
    action = "thay đổi"
    field  = "deadline"
    marker = "dự án"
    KEYWORD = "ACB"  ← group(1) của regex
    sep    = "sang"
    date   = "25/5" → "2026-05-25"
```

---

## QueryEngine — Q&A thông minh

Xử lý câu hỏi mở cần tra cứu context dữ liệu.

### Nguồn dữ liệu

```
1. tasks.json          ← Toàn bộ task active (status/owner/deadline/notes)
2. Danh_sach_nhan_su_FOXAI.md  ← Nhân sự, vai trò, bộ phận
3. memory/*.md         ← Project memory files (nếu có)
4. Bao_cao*.md         ← Báo cáo công việc gần nhất (nếu có)
```

### Context format gửi LLM

```
## TASKS ĐANG ACTIVE (N tasks, YYYY-MM-DD)
- #1 [IN_PROGRESS] Tên task | @owner | 2026-05-30 (còn 8N)
- #2 [PENDING] Tên task | @owner | 2026-05-20 (QUÁ HẠN 2N)

---

## NHÂN SỰ FOXAI
[nội dung Danh_sach_nhan_su_FOXAI.md, tối đa 2500 ký tự]

---

## BÁO CÁO CÔNG VIỆC GẦN NHẤT
[nội dung báo cáo, tối đa 3000 ký tự]
```

### Fallback khi không có API

| Câu hỏi chứa | Hành động |
|-------------|-----------|
| `quá hạn / trễ / overdue` | Lọc task deadline < hôm nay |
| Tên người (`Hoàng`, `Tiến`...) | Lọc task theo owner |
| Tên dự án (`ACB`, `KMS`...) | Tìm keyword trong task title |
| Mặc định | Trả về summary stats |

---

## Cấu hình và tùy chỉnh

### Thêm từ khóa vào RegexNLP

Mở `foxai_task_bot.py`, tìm `class RegexNLP` và bổ sung vào các list từ khóa:

```python
# Thêm từ đồng nghĩa vào CREATE
create_kw = ['tạo task', 'giao task', ..., 'assign task']  # thêm vào đây

# Thêm cách nói mới cho STATUS
status_kw = ['tóm tắt', 'thống kê', ..., 'summary']       # thêm vào đây

# Thêm trigger cho QUERY
query_kw = ['tình hình', 'đến đâu', ..., 'progress']      # thêm vào đây
```

Không cần restart bot để thêm từ khóa vào code — nhưng cần restart để apply.

### Cải thiện System Prompt

Nếu OpenAI trả về sai intent, chỉnh `SYSTEM_PROMPT` trong class `OpenAINLP`:

```python
# Thêm ví dụ vào phần INTENT
- update: ...
  + deadline: "thay deadline task 3", "push deadline ACB", ...  ← thêm ví dụ
```

### Theo dõi chất lượng NLP

Xem log để biết tầng nào đang xử lý:
```
INFO - GPT NLP: intent=update, id=None, owner=Quốc Anh, deadline=2026-05-30
WARN - GPT NLP lỗi (RateLimitError) — dùng RegexNLP fallback
```

Nếu Regex fallback xuất hiện nhiều → nạp thêm OpenAI credits hoặc tăng giới hạn.

---

## Đo lường và cải thiện

### Metrics cần theo dõi

| Metric | Mục tiêu | Cách đo |
|--------|---------|---------|
| Intent `unknown` rate | < 10% | Đếm log `intent=unknown` / tổng |
| API fallback rate | < 20% | Đếm log `RegexNLP fallback` / tổng |
| Response time | < 3 giây | Timestamp trong log |

### Quy trình cải thiện hàng tuần

1. Xem log: tìm các tin nhắn bị `unknown`
2. Phân tích: pattern nào bị miss?
3. Thêm vào RegexNLP keyword list nếu là pattern phổ biến
4. Cập nhật System Prompt nếu OpenAI parse sai
5. Test lại với các ví dụ mới

---

**Maintained by:** FOXAI Delivery Center R&D Team
