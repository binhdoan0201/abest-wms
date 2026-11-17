# ADR 0001: Quyết định công nghệ cho dự án ABEST WMS

Trạng thái: Đã chốt bởi leader (2026-11-17)

## 1. Bối cảnh
Dự án ABEST WMS cần thống nhất nền tảng công nghệ, công cụ phát triển, quy chuẩn kiến trúc và kiểm thử để 4 thành viên cùng phát triển đồng bộ và hiệu quả trong thời gian ngắn hạn (15 ngày demo).

## 2. Bảng tổng hợp quyết định công nghệ

| Hạng mục | Quyết định | Lý do | Không dùng trong 15 ngày |
| :--- | :--- | :--- | :--- |
| **Ngôn ngữ** | Python 3.11 trở lên | Yêu cầu của nhóm | |
| **Server** | FastAPI + Uvicorn | Tự sinh OpenAPI, kiểm dữ liệu bằng Pydantic v2, dễ chia module | Django (ORM lệch với schema có sẵn) |
| **Truy cập DB** | SQLAlchemy 2.x, driver psycopg 3 | Vừa ORM vừa gọi được hàm `fn_*` của DB bằng `text("SELECT fn_...")` | |
| **CSDL** | PostgreSQL 15 trở lên (đã kiểm thử trên 16) | Schema v4.1 + patch v4.2.1 dùng ENUM, trigger, hàm PL/pgSQL | SQLite, MySQL |
| **Nạp schema** | `psql`: schema v4.1, patch v4.2.1, seed; Alembic chỉ cho thay đổi sau đó | ENUM thêm giá trị không chạy trong transaction của migration | |
| **Xác thực** | JWT một token, hạn 8 giờ (một ca), mật khẩu bcrypt | Đủ cho demo, bỏ refresh token | SSO, OAuth |
| **Client** | Ứng dụng web chạy riêng: FastAPI + Jinja2 + HTMX + Tailwind (CDN), gọi server bằng `httpx` | Cùng ngôn ngữ, dựng nhanh, chạy trên điện thoại hoặc máy PDA bằng trình duyệt | React/Vue SPA, app native |
| **Phiên đăng nhập phía client** | Token lưu trong cookie `httpOnly` của client; trình duyệt không bao giờ cầm token | Tránh lộ token ra JavaScript | |
| **Quét mã** | Máy quét kiểu bàn phím hoặc nhập tay | Không cần phần cứng thật | Quét bằng camera |
| **Kiểm thử** | `pytest`, `httpx.TestClient`, DB test trong Docker, cộng `wms_smoke_test_v4_2_1.sql` | Đã có bộ kiểm thử DB | |
| **Chất lượng code** | `ruff`, `black`, `mypy`, `pre-commit` | Đồng nhất code của 4 người | |
| **Môi trường** | `docker-compose` (Postgres), `.env` | Mọi người chạy giống nhau | Kubernetes |
| **Việc nền** | Không có tiến trình riêng: leo thang SLA gọi bằng endpoint `POST /approvals/escalate-expired` (bấm tay trong demo) | Bớt một thành phần phải dựng | Redis, Celery, message queue |
