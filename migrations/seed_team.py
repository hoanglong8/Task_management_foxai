"""Seed FOXAI team members from CLAUDE.md team reference."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import SessionLocal, init_db
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password

TEAM = [
    # (full_name, email, role, department)
    ("Nguyễn Hoàng Long", "hoanglong208@gmail.com", UserRole.admin, "Management"),
    # Delivery
    ("Nguyễn Quốc Anh", "quocanh@foxai.vn", UserRole.manager, "Delivery"),
    ("Trần Thị Bích Hoài", "bichoai@foxai.vn", UserRole.manager, "Delivery"),
    ("Ngô Đức Kiên", "ductien@foxai.vn", UserRole.manager, "Delivery"),
    ("Nguyễn Thị Linh", "thiLinh@foxai.vn", UserRole.member, "Delivery"),
    ("Nguyễn Khánh Huy", "khanhhuy@foxai.vn", UserRole.member, "Delivery"),
    ("Nguyễn Hương Trà", "huongtra@foxai.vn", UserRole.member, "Delivery"),
    ("Nguyễn Việt Hoàng", "viethoang@foxai.vn", UserRole.member, "Delivery"),
    ("Lê Định", "ledinh@foxai.vn", UserRole.member, "Delivery"),
    ("Đinh Thị Quế", "thique@foxai.vn", UserRole.member, "Delivery"),
    ("Nguyễn Mạnh Toàn", "manhtoan@foxai.vn", UserRole.member, "Delivery"),
    # R&D
    ("Vi Anh Tuấn", "anhtuan@foxai.vn", UserRole.manager, "R&D"),
    ("Hà Thanh Hào", "thanhhao@foxai.vn", UserRole.member, "R&D"),
    ("Lê Hải Sơn", "haison@foxai.vn", UserRole.member, "R&D"),
    ("An Ngọc Phúc", "ngocphuc@foxai.vn", UserRole.member, "R&D"),
    ("Phan Trung Hiếu", "trunghieu@foxai.vn", UserRole.member, "R&D"),
    ("Phạm Văn Tụ", "vantu@foxai.vn", UserRole.member, "R&D"),
    ("Nguyễn Văn Nghĩa", "vannghia@foxai.vn", UserRole.member, "R&D"),
    ("Lê Ngọc Thắng", "ngocthang@foxai.vn", UserRole.member, "R&D"),
    ("Phan Lưu Chí", "luuchi@foxai.vn", UserRole.member, "R&D"),
    # Sales
    ("Trần Quốc Vương", "quocvuong@foxai.vn", UserRole.manager, "Sales"),
    ("Lê Viết Trường", "viettruong@foxai.vn", UserRole.member, "Sales"),
    ("Hà Quốc Thạch", "quocthach@foxai.vn", UserRole.member, "Sales"),
    ("Bùi Mạnh Hùng", "manhhung@foxai.vn", UserRole.member, "Sales"),
    ("Hà Thị Mỹ Hằng", "myhang@foxai.vn", UserRole.member, "Sales"),
    ("Lê Duy Minh", "duyminh@foxai.vn", UserRole.member, "Sales"),
    ("Nguyễn Trà My", "tramy@foxai.vn", UserRole.member, "Sales"),
    ("Nguyễn Văn Mạnh", "vanmanh@foxai.vn", UserRole.member, "Sales"),
    # Marketing
    ("Đoàn Tự Hào", "tuhao@foxai.vn", UserRole.member, "Marketing"),
    ("Nguyễn Quốc Bảo", "quocbao@foxai.vn", UserRole.member, "Marketing"),
    # Back-office
    ("Lê Thu Thủy", "thuthuy@foxai.vn", UserRole.member, "Back-office"),
    ("Nguyễn Thị Vân Anh", "vananh@foxai.vn", UserRole.member, "Back-office"),
    ("Đặng Quang Dũng", "quangdung@foxai.vn", UserRole.member, "Back-office"),
    ("Ngô Thị Bích Lợi", "bichloi@foxai.vn", UserRole.member, "Back-office"),
]

DEFAULT_PASSWORD = "foxai2026!"  # Users should change on first login


def seed():
    init_db()
    db = SessionLocal()
    added = 0
    try:
        for full_name, email, role, dept in TEAM:
            if not db.query(User).filter(User.email == email).first():
                db.add(User(
                    full_name=full_name,
                    email=email,
                    hashed_password=hash_password(DEFAULT_PASSWORD),
                    role=role,
                    department=dept,
                ))
                added += 1
        db.commit()
        print(f"Seeded {added} team members. Default password: {DEFAULT_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
