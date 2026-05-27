"""
Regression test cho RegexNLP.
Chạy: python test_nlp.py
Phải pass 100% trước khi restart bot.
"""
import sys
sys.path.insert(0, '.')
from foxai_task_bot import RegexNLP

nlp = RegexNLP()

CASES = [
    # fmt: (mô tả, câu input, intent mong đợi, các field mong đợi)

    # ── LIST ──────────────────────────────────────────────────────────────
    ("list all",            "danh sách task",                           "list",     {"filter": None}),
    ("list all 2",          "liệt kê tất cả task",                      "list",     {"filter": None}),
    ("list active",         "liệt kê các task chưa hoàn thành",         "list",     {"filter": "active"}),
    ("list active 2",       "hãy cập nhật các task chưa hoàn thành",    "list",     {"filter": "active"}),
    ("list active 3",       "xem các task chưa xong",                   "list",     {"filter": "active"}),
    ("list today",          "danh sách task hôm nay",                   "list",     {"filter": "today"}),
    ("list pending",        "có task gì chưa làm",                      "list",     {"filter": "pending"}),
    ("list in_progress",    "xem task đang làm",                        "list",     {"filter": "in_progress"}),

    # ── COMPLETE single ───────────────────────────────────────────────────
    ("complete single",     "xong task 3",                              "complete", {"task_id": 3}),
    ("complete single 2",   "hoàn thành task 5",                        "complete", {"task_id": 5}),

    # ── COMPLETE bulk ─────────────────────────────────────────────────────
    ("complete bulk space", "xong task 1 2 3",                          "complete", {"task_ids": [1, 2, 3]}),
    ("complete bulk #",     "hoàn thành #1 #2 #3",                      "complete", {"task_ids": [1, 2, 3]}),
    ("complete range",      "xong task #1 đến #5",                      "complete", {"task_ids": [1, 2, 3, 4, 5]}),

    # ── UPDATE single - deadline ──────────────────────────────────────────
    ("upd deadline id",     "đổi deadline task 3 sang 30/5",            "update",   {"task_id": 3, "deadline": "2026-05-30"}),
    ("upd deadline giahan", "gia hạn task 3 đến 31/5",                  "update",   {"task_id": 3, "deadline": "2026-05-31"}),

    # ── UPDATE single - owner ─────────────────────────────────────────────
    ("upd owner giao lai",  "giao lại task 3 cho Quốc Anh",             "update",   {"task_id": 3, "owner": "Quốc Anh"}),
    ("upd owner giao task", "giao task 3 cho Hoàng",                    "update",   {"task_id": 3}),

    # ── UPDATE single - status ────────────────────────────────────────────
    ("upd status ip",       "task 3 đang làm",                          "update",   {"task_id": 3, "status": "in_progress"}),
    ("upd status pending",  "task 3 chờ",                               "update",   {"task_id": 3, "status": "pending"}),

    # ── UPDATE bulk - deadline ────────────────────────────────────────────
    ("bulk dl same #",      "#5 và #8 chuyển deadline 25/05",           "update",   {"task_ids": [5, 8], "deadline": "2026-05-25"}),
    ("bulk dl same all",    "#5 và #8 chuyển deadline 25/05, #14 chuyển deadline sang 25/05",
                                                                         "update",   {"task_ids": [5, 8, 14], "deadline": "2026-05-25"}),
    ("bulk dl giahan",      "gia hạn task #1 đến #3 đến 30/5",         "update",   {"task_ids": [1, 2, 3], "deadline": "2026-05-30"}),

    # ── UPDATE bulk - multi-group deadline ────────────────────────────────
    ("multi dl groups",     "#5 #8 deadline 25/05, #14 deadline 30/05", "update",   {"deadline_groups": [([5, 8], "2026-05-25"), ([14], "2026-05-30")]}),

    # ── UPDATE bulk - owner ───────────────────────────────────────────────
    ("bulk owner #",        "giao task #1 #2 #3 cho Quốc Anh",         "update",   {"task_ids": [1, 2, 3]}),

    # ── UPDATE bulk - status ──────────────────────────────────────────────
    ("bulk status ip",      "chuyển task #1 #2 #3 sang đang làm",      "update",   {"task_ids": [1, 2, 3], "status": "in_progress"}),

    # ── UPDATE keyword (by name) ──────────────────────────────────────────
    ("kw deadline",         "thay đổi deadline dự án ACB sang 25/5",   "update",   {"keyword": "ACB", "deadline": "2026-05-25"}),
    ("kw giahan",           "gia hạn KMS đến 31/5",                     "update",   {"keyword": "KMS", "deadline": "2026-05-31"}),
    ("kw owner",            "giao dự án IOC cho Quốc Anh",              "update",   {"keyword": "IOC"}),

    # ── DELETE ────────────────────────────────────────────────────────────
    ("delete single",       "xóa task #5",                              "delete",   {"task_ids": [5]}),
    ("delete range",        "xóa các task từ #28 đến #33",              "delete",   {"task_ids": list(range(28, 34))}),
    ("delete multi",        "xóa task #1 #3 #5",                        "delete",   {"task_ids": [1, 3, 5]}),

    # ── CREATE ────────────────────────────────────────────────────────────
    ("create",              "tạo task họp khách hàng cho Long ngày 28/5","create",  {}),
    ("create 2",            "giao task review code cho Hoàng hạn 25/5", "create",   {}),

    # ── WEEKLY ────────────────────────────────────────────────────────────
    ("weekly",   "lịch tuần",                   "weekly", {}),
    ("weekly 2", "xem lịch làm việc tuần",      "weekly", {}),
    ("weekly 3", "kế hoạch tuần này",           "weekly", {}),

    # ── STATUS / STANDUP ──────────────────────────────────────────────────
    ("status",              "tóm tắt task",                             "status",   {}),
    ("standup",             "standup",                                  "standup",  {}),
    ("standup 2",           "hôm nay làm gì",                           "standup",  {}),

    # ── QUERY ─────────────────────────────────────────────────────────────
    ("query ?",             "tình hình dự án ACB đến đâu rồi?",         "query",    {}),
    ("query ai",            "Hoàng đang phụ trách gì?",                 "query",    {}),
]


def check(r, intent, fields):
    if r["intent"] != intent:
        return False, f"intent={r['intent']} (expected {intent})"
    for k, v in fields.items():
        if k == "task_ids" and v is not None:
            actual = r.get(k)
            if sorted(actual or []) != sorted(v):
                return False, f"{k}={actual} (expected {v})"
        elif k == "deadline_groups" and v is not None:
            # Chỉ kiểm tra số lượng nhóm và các deadline
            actual = r.get(k)
            if not actual or len(actual) != len(v):
                return False, f"deadline_groups len={len(actual or [])} (expected {len(v)})"
        elif r.get(k) != v:
            return False, f"{k}={r.get(k)!r} (expected {v!r})"
    return True, ""


passed = failed = 0
for desc, text, exp_intent, exp_fields in CASES:
    r = nlp.parse(text)
    ok, reason = check(r, exp_intent, exp_fields)
    if ok:
        passed += 1
        print(f"  ✅  {desc}")
    else:
        failed += 1
        print(f"  ❌  {desc}")
        print(f"       input   : {text}")
        print(f"       mismatch: {reason}")
        snap = {k: r.get(k) for k in ["intent","task_id","task_ids","deadline","owner","status","filter","keyword","deadline_groups"]}
        print(f"       actual  : {snap}")

print(f"\n{'='*55}")
print(f"Kết quả: {passed}/{passed+failed} passed")
if failed:
    print(f"❌ {failed} FAILED — cần sửa trước khi restart bot!")
    sys.exit(1)
else:
    print("✅ All passed — an toàn để restart bot.")
