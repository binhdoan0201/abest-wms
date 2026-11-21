# ABEST WMS - Hệ thống Quản lý Kho Hàng

[![CI Pipeline](https://github.com/binhdoan0201/abest-wms/actions/workflows/ci.yml/badge.svg)](https://github.com/binhdoan0201/abest-wms/actions/workflows/ci.yml)

ABEST WMS (Warehouse Management System) là hệ thống quản lý kho được xây dựng trên kiến trúc Client–Server kết hợp MVC, đáp ứng các tiêu chuẩn nghiệp vụ kho bãi hiện đại (Inbound, Outbound, Tồn kho đa vị trí, Phân quyền RBAC, Quản lý công việc và Luồng phê duyệt đa cấp).

---

## 1. Yêu cầu hệ thống
- **Hệ điều hành:** Linux, macOS, hoặc Windows
- **Python:** Phiên bản 3.11 trở lên (khuyến nghị 3.12)
- **Docker & Docker Desktop:** Để chạy CSDL PostgreSQL 16
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

### 3.1. Chạy CSDL PostgreSQL (Docker Compose)
```bash
docker compose up -d

# Nạp schema, patch và dữ liệu mẫu:
make db-reset
# (hoặc: bash scripts/reset_db.sh)

# Chạy bài kiểm thử CSDL:
make db-test
# (hoặc: bash scripts/run_db_tests.sh)
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

## 4. Tài khoản người dùng Demo (Mục 5 Đặc tả)

Toàn bộ 9 tài khoản demo sử dụng mật khẩu mặc định: **`Demo@123456`**

| Username | Vai trò (`role_code`) | Họ và tên | Khâu làm việc (`primary_stage`) | Kênh truy cập |
| :--- | :--- | :--- | :--- | :--- |
| `nv_nhan` | `nv-nhan` | Trần Văn Nhận | `NHAN_HANG` | Mobile |
| `nv_cat` | `nv-cat` | Lê Văn Cất | `CAT_HANG` | Mobile |
| `nv_soan` | `nv-soan` | Phạm Văn Soạn | `SOAN_HANG` | Mobile |
| `nv_dongoi` | `nv-dongoi` | Hoàng Thị Gói | `DONG_GOI_XUAT` | Mobile |
| `nv_kiemke` | `nv-kiemke` | Võ Văn Kê | `KIEM_KE` | Mobile |
| `thukho` | `thukho` | Đỗ Thủ Kho | `QUAN_LY_CHUNG` | Mobile + Web |
| `quanly` | `quanly` | Nguyễn Văn Quản Lý | `QUAN_LY_CHUNG` | Mobile + Web |
| `bgd` | `bgd` | Phan Giám Đốc | `QUAN_LY_CHUNG` | Web |
| `admin` | `admin` | Quản Trị Viên Hệ Thống | `QUAN_LY_CHUNG` | Web |

---

## 5. Chạy kiểm thử và Tích hợp liên tục (CI)

### 5.1. Chạy CI tại môi trường cục bộ (Local CI)
Lệnh `make ci` (hoặc `.\make.bat ci` trên Windows) thực thi trọn vẹn chuỗi kiểm tra tiêu chuẩn trước khi tạo Pull Request:
```bash
# Chạy trọn gói kiểm tra CI cục bộ (Lint + Typecheck + DB Tests + Pytest)
make ci
```
Quy trình thực hiện tuần tự:
1. `make lint`: Kiểm tra định dạng chuẩn với Black và Ruff (`black --check .`, `ruff check .`).
2. `make typecheck`: Kiểm tra kiểu tĩnh với MyPy (`mypy server client scripts`).
3. `make db-test`: Kiểm thử CSDL với script `scripts/run_db_tests.sh` (CSDL tạm, smoke test, idempotent patch lần 2, test seed).
4. `make test`: Chạy toàn bộ 63 bài kiểm thử tự động với Pytest (kiểm thử đơn vị, kiểm thử tích hợp, kiểm thử kiến trúc AST).

Bạn cũng có thể chạy riêng lẻ từng bước:
```bash
make lint       # Định dạng mã nguồn
make typecheck  # Kiểu tĩnh MyPy
make db-test    # Kiểm thử CSDL
make test       # Kiểm thử Pytest (server/tests)
```

### 5.2. Pipeline Tích hợp liên tục trên GitHub Actions
Pipeline CI được thiết lập tại [.github/workflows/ci.yml](.github/workflows/ci.yml) và tự động kích hoạt mỗi khi:
- Có Pull Request mở vào nhánh `develop` hoặc `main`.
- Có commit mới được đẩy (push) lên nhánh `develop` hoặc `main`.

**Các bước thực thi trên GitHub Actions:**
1. Khởi tạo service container **PostgreSQL 16**.
2. Kiểm tra định dạng (Black) và lint mã nguồn (Ruff).
3. Kiểm tra kiểu tĩnh (MyPy).
4. Khởi tạo, nạp schema và seed dữ liệu CSDL (`scripts/reset_db.sh`).
5. Chạy toàn bộ các bài kiểm thử CSDL (`scripts/run_db_tests.sh`).
6. Chạy bộ kiểm thử tự động toàn diện Pytest (unit, integration, AST layering, OpenAPI contract, table coverage).

**Cách xem kết quả CI trên GitHub:**
1. Truy cập tab **Actions** tại kho lưu trữ GitHub: `https://github.com/binhdoan0201/abest-wms/actions`.
2. Chọn workflow run tương ứng với nhánh hoặc Pull Request cần theo dõi.
3. Khi tất cả các bước hiển thị dấu tích xanh (green checkmark), Pull Request đủ điều kiện để được xem xét nghiệm thu và merge.

---

## 6. Quy ước và Tài liệu tham chiếu

Tất cả các thành viên tham gia phát triển dự án bắt buộc phải đọc và tuân thủ các tài liệu đặc tả:
- **Đặc tả dự án:** [docs/spec/dac-ta-du-an.md](docs/spec/dac-ta-du-an.md) (Kiến trúc, cấu trúc thư mục, quy cách đặt tên, phân quyền RBAC và kịch bản demo).
- **Chuẩn công nghệ và Hợp đồng API:** [docs/spec/chuan-api-cong-nghe.md](docs/spec/chuan-api-cong-nghe.md) (Quy ước endpoint, envelope, mã lỗi chung và danh mục API).
- **Quyết định kiến trúc (ADR):** [docs/adr/0001-cong-nghe.md](docs/adr/0001-cong-nghe.md).
- **Quy trình Git & Đóng góp:** [CONTRIBUTING.md](CONTRIBUTING.md).
