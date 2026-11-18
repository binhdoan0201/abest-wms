# ABEST WMS - Hệ thống Quản lý Kho Hàng

ABEST WMS (Warehouse Management System) là hệ thống quản lý kho được xây dựng trên kiến trúc Client–Server kết hợp MVC, đáp ứng các tiêu chuẩn nghiệp vụ kho bãi hiện đại (Inbound, Outbound, Tồn kho đa vị trí, Phân quyền RBAC, Quản lý công việc và Luồng phê duyệt đa cấp).

---

## 1. Yêu cầu hệ thống
- **Hệ điều hành:** Linux, macOS, hoặc Windows
- **Python:** Phiên bản 3.11 trở lên (khuyến nghị 3.12)
- **Docker & Docker Desktop:** Để chạy CSDL PostgreSQL
- **Git** và **GitHub CLI (`gh`)**

---

## 2. Hướng dẫn cài đặt

### Bước 1: Clone kho lưu trữ và chuyển nhánh
```bash
git clone https://github.com/binhdoan0201/abest-wms.git
cd abest-wms
git checkout develop
```

### Bước 2: Khởi tạo môi trường ảo và cài đặt thư viện
```bash
# Cách 1: Dùng Makefile
make install

# Cách 2: Thủ công qua Python
python -m venv .venv

# Kích hoạt môi trường:
# Trên Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Trên Linux/macOS:
source .venv/bin/activate

# Cài đặt dependencies:
pip install --upgrade pip
pip install -r server/requirements.txt
pip install -r client/requirements.txt
```

### Bước 3: Cấu hình biến môi trường
```bash
cp .env.example .env
# Chỉnh sửa .env nếu cần thay đổi thông tin kết nối CSDL
```

---

## 3. Khởi chạy CSDL và Hệ thống

### 3.1. Chạy CSDL PostgreSQL (Docker)
```bash
docker-compose up -d
```

### 3.2. Chạy Server Backend (FastAPI API)
```bash
# Bằng Makefile:
make run-server

# Hoặc bằng lệnh trực tiếp:
uvicorn server.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Docs (Swagger UI): `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

### 3.3. Chạy Client Frontend (FastAPI + Jinja2 + HTMX)
```bash
# Bằng Makefile:
make run-client

# Hoặc bằng lệnh trực tiếp:
uvicorn client.app.main:app --host 0.0.0.0 --port 3000 --reload
```
- Truy cập giao diện: `http://localhost:3000`

---

## 4. Chạy kiểm thử và Kiểm tra chất lượng mã nguồn

```bash
# Kiểm tra định dạng (Black & Ruff)
make lint

# Kiểm tra kiểu tĩnh (MyPy)
make typecheck

# Chạy toàn bộ bài kiểm thử (Pytest)
make test

# Chạy trọn gói kiểm tra CI (Lint + Typecheck + Test)
make ci
```

---

## 5. Quy ước và Tài liệu tham chiếu

Tất cả các thành viên tham gia phát triển dự án bắt buộc phải đọc và tuân thủ các tài liệu đặc tả:
- **Đặc tả dự án:** [docs/spec/dac-ta-du-an.md](docs/spec/dac-ta-du-an.md) (Kiến trúc, cấu trúc thư mục, quy cách đặt tên, phân quyền RBAC và kịch bản demo).
- **Chuẩn công nghệ và Hợp đồng API:** [docs/spec/chuan-api-cong-nghe.md](docs/spec/chuan-api-cong-nghe.md) (Quy ước endpoint, envelope, mã lỗi chung và danh mục API).
- **Quyết định kiến trúc (ADR):** [docs/adr/0001-cong-nghe.md](docs/adr/0001-cong-nghe.md).
- **Quy trình Git & Đóng góp:** [CONTRIBUTING.md](CONTRIBUTING.md).
