"""Tests for TaskService and NLP."""
import pytest
from datetime import date

from backend.services.nlp_service import RegexNLP

nlp = RegexNLP()


class TestRegexNLP:
    def test_create(self):
        r = nlp.parse("tạo task Hoàn thiện BA document cho Quốc Anh ngày 25/5")
        assert r["intent"] == "create"
        assert r["title"] == "Hoàn thiện BA document"
        assert r["owner"] == "Quốc Anh"
        assert r["deadline"] == "2026-05-25"

    def test_list_all(self):
        r = nlp.parse("danh sách task")
        assert r["intent"] == "list"

    def test_list_in_progress(self):
        r = nlp.parse("xem task đang làm")
        assert r["intent"] == "list"
        assert r["filter"] == "in_progress"

    def test_update_status(self):
        r = nlp.parse("task #3 đang làm")
        assert r["intent"] == "update"
        assert r["task_id"] == 3
        assert r["status"] == "in_progress"

    def test_update_deadline(self):
        r = nlp.parse("đổi deadline task #5 sang 30/6")
        assert r["intent"] == "update"
        assert r["task_id"] == 5
        assert r["deadline"] == "2026-06-30"

    def test_complete_single(self):
        r = nlp.parse("xong task #2")
        assert r["intent"] == "complete"
        assert r["task_id"] == 2

    def test_complete_bulk(self):
        r = nlp.parse("hoàn thành #1 #2 #3")
        assert r["intent"] == "complete"
        assert r["task_ids"] == [1, 2, 3]

    def test_delete(self):
        r = nlp.parse("xóa task #7")
        assert r["intent"] == "delete"

    def test_delete_range(self):
        r = nlp.parse("xóa task từ #1 đến #5")
        assert r["intent"] == "delete"
        assert r["task_ids"] == [1, 2, 3, 4, 5]

    def test_standup(self):
        r = nlp.parse("standup")
        assert r["intent"] == "standup"

    def test_status_aggregate(self):
        r = nlp.parse("bao nhiêu task")
        assert r["intent"] == "status"

    def test_keyword_update_deadline(self):
        r = nlp.parse("thay đổi deadline dự án ACB sang 25/5")
        assert r["intent"] == "update"
        assert r["keyword"] == "ACB"
        assert r["deadline"] == "2026-05-25"

    def test_no_false_positive_chua_hoan_thanh(self):
        r = nlp.parse("xem task chưa hoàn thành")
        assert r["intent"] == "list"
        assert r["filter"] == "active"


class TestDeadlineParsing:
    def test_iso(self):
        r = nlp._deadline("2026-05-25")
        assert r == "2026-05-25"

    def test_slash(self):
        r = nlp._deadline("15/5")
        assert r == "2026-05-15"

    def test_slash_full(self):
        r = nlp._deadline("25/5/2026")
        assert r == "2026-05-25"

    def test_thang(self):
        r = nlp._deadline("20 tháng 6")
        assert r == "2026-06-20"
