# Báo cáo kỹ thuật bước AG3: Lõi Server (Server Core)

**Mã bước:** `ag3-server-core`  
**Nhánh:** `chore/ag3-server-core`  
**Người thực hiện:** AG3 (Antigravity Core)  
**Ngày thực hiện:** 2026-11-21  
**Trạng thái:** HOÀN THÀNH - ĐẠT YÊU CẦU

---

## 1. Mục tiêu
Thiết lập toàn bộ khung lõi backend của máy chủ ABEST WMS theo Mục 1 đến Mục 3 của Chuẩn API (`docs/spec/chuan-api-cong-nghe.md`) và quy trình dựng khung (`docs/spec/quy-trinh-dung-khung.md`):
- Điểm khởi chạy `server/app/main.py`: Khởi tạo ứng dụng FastAPI với tiền tố `/api/v1`, cơ chế tự động nạp router của mọi module (`app/modules/*/routers.py`), endpoint `GET /health` kiểm tra kết nối DB.
- Cấu hình và kết nối CSDL: `core/config.py` (Pydantic Settings đọc `.env`), `core/database.py` (SQLAlchemy 2.x + Psycopg 3, session dependency với transaction tự động commit khi thành công và rollback khi gặp lỗi).
- Chuẩn hóa Envelope phản hồi API và Middleware: `core/responses.py` (`success_response`, `error_response`, `RequestIdMiddleware` quản lý `X-Request-ID` và `meta.request_id`).
- Xử lý ngoại lệ và ánh xạ lỗi CSDL: `core/exceptions.py` (`BusinessError`, `register_exception_handlers`, hàm `translate_db_error` ánh xạ các trigger và constraint của PostgreSQL sang mã lỗi chuẩn: `INTERNAL_IMMUTABLE_RECORD`, `ORDER_FROZEN`, `REAUTH_REQUIRED`, `SOD_VIOLATION`, `INVENTORY_INSUFFICIENT_QTY`).
- Đồng bộ ENUM tự động: `scripts/gen_enums.py` sinh `server/app/shared/enums.py` trực tiếp từ bảng hệ thống `pg_enum` của PostgreSQL (khớp 100%, không gõ tay, idempotent).
- Hệ thống Logging JSON có bảo mật dữ liệu nhạy cảm: `core/logging.py` (định dạng JSON cấu trúc kèm `request_id`, tích hợp bộ lọc che giấu hoàn toàn `authorization`, `password`, `token`, `cookie`, `secret`).
- Bộ kiểm thử kiến trúc và đơn vị đầy đủ, kiểm tra trực tiếp trên PostgreSQL Docker thật.

---

## 2. Đã làm
1. **Cấu hình ứng dụng (`server/app/core/config.py`):**
   - Sử dụng `pydantic-settings` đọc các biến môi trường từ file `.env`.
   - Quản lý cấu hình CSDL, JWT, Server API với singleton `get_settings()`.
2. **Quản trị kết nối và Transaction CSDL (`server/app/core/database.py`):**
   - Khởi tạo SQLAlchemy 2.x engine với driver `postgresql+psycopg`.
   - Dependency `get_db()`: một transaction mỗi request, commit tự động khi response thành công, rollback toàn bộ khi phát sinh lỗi, bảo đảm giải phóng kết nối trong `finally`.
3. **Chuẩn hóa phản hồi API và Middleware (`server/app/core/responses.py`):**
   - `success_response()`: tạo envelope `{"data": ..., "meta": {"request_id": "...", ...}}`.
   - `error_response()`: tạo envelope `{"error": {"code": "...", "message": "...", "details": ...}}`.
   - `RequestIdMiddleware`: tự động đọc header `X-Request-ID` từ client hoặc sinh UUID mới, gắn vào context (`request_id_ctx`) và gán vào header phản hồi.
4. **Xử lý ngoại lệ và dịch lỗi CSDL (`server/app/core/exceptions.py`):**
   - Định nghĩa lớp `BusinessError(code, message, http_status, details)`.
   - Hàm `translate_db_error(exc)`: phân tích chi tiết ngoại lệ PostgreSQL để chuyển hóa thành `BusinessError`:
     - `BAN_GHI_BAT_BIEN` -> `INTERNAL_IMMUTABLE_RECORD` (HTTP 500)
     - `DON_BI_DONG_BANG` -> `ORDER_FROZEN` (HTTP 409)
     - `THIEU_XAC_THUC_LAI` -> `REAUTH_REQUIRED` (HTTP 403)
     - `VI_PHAM_TACH_QUYEN_SOD` hoặc `chk_sod_no_self_approval` -> `SOD_VIOLATION` (HTTP 403)
     - Check constraint `qty_available` -> `INVENTORY_INSUFFICIENT_QTY` (HTTP 409)
   - `register_exception_handlers()`: bắt `BusinessError`, `RequestValidationError` (HTTP 422 `VALIDATION_ERROR`), và `Exception` chưa biết (HTTP 500 `INTERNAL_SERVER_ERROR`).
5. **Sinh ENUM tự động (`scripts/gen_enums.py` & `server/app/shared/enums.py`):**
   - Truy vấn trực tiếp từ `pg_type` và `pg_enum` trong cơ sở dữ liệu `abest_wms`.
   - Đã sinh 20 lớp Enum Python (114 nhãn giá trị) kế thừa `(str, Enum)`.
6. **Logging JSON và Mặt nạ bảo mật (`server/app/core/logging.py`):**
   - `JSONFormatter`: xuất bản ghi log định dạng JSON với `timestamp` (ISO 8601 UTC), `level`, `logger`, `message`, `request_id`.
   - `SensitiveDataFilter` & `mask_sensitive_value`: che giấu giá trị nhạy cảm thành `***` đối với cả văn bản và đối tượng từ điển lồng nhau.
7. **Entrypoint máy chủ (`server/app/main.py`):**
   - Tạo instance FastAPI với tiền tố `/api/v1`.
   - Gắn `RequestIdMiddleware`, đăng ký `register_exception_handlers()`.
   - Tự động quét và nạp `router` từ thư mục `server/app/modules/*/routers.py`.
   - Endpoint `GET /health` kiểm tra kết nối CSDL bằng truy vấn `SELECT 1`.
8. **Bộ kiểm thử toàn diện:**
   - `server/tests/architecture/test_enums_match_db.py`: Kiểm thử kiến trúc đối chiếu 100% ENUM Python với `pg_enum` trong DB.
   - `server/tests/unit/test_health_and_envelope.py`: Kiểm thử endpoint `/health`, chuẩn hóa envelope và mã lỗi.
   - `server/tests/unit/test_db_error_translation.py`: Kiểm thử 5 lỗi CSDL với SQL thật trên PostgreSQL.
   - `server/tests/unit/test_logging_mask.py`: Kiểm thử mặt nạ bảo mật che giấu `authorization`, `password`, `token`, `cookie`.
   - `server/tests/unit/test_transaction_rollback.py`: Kiểm thử cơ chế transaction 2 bước rollback sạch sẽ khi có lỗi.

---

## 3. Cách chạy lại

### Kích hoạt môi trường và cập nhật PATH
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
```

### Sinh lại ENUM từ CSDL đang chạy
```powershell
.venv\Scripts\python scripts/gen_enums.py
```

### Chạy toàn bộ kiểm thử
```powershell
.venv\Scripts\pytest -v
```

### Chạy toàn bộ pipeline kiểm tra chất lượng (CI)
```powershell
.\make.bat ci
```

---

## 4. Kết quả test thực tế

### 4.1 Kết quả chạy sinh ENUM (`scripts/gen_enums.py`)
```text
============================================================
ABEST WMS: Đang sinh server/app/shared/enums.py từ DB...
============================================================
Đã đọc được 20 loại ENUM từ PostgreSQL:
  - actor_group_type (4 giá trị)
  - approval_object_type (5 giá trị)
  - approval_status_type (8 giá trị)
  - approval_tier_type (4 giá trị)
  - auth_provider_type (2 giá trị)
  - gi_doc_type (4 giá trị)
  - grn_status_type (9 giá trị)
  - location_status_type (6 giá trị)
  - order_status_type (13 giá trị)
  - pallet_status_type (8 giá trị)
  - pick_mode_type (3 giá trị)
  - picking_rule_type (2 giá trị)
  - po_status_type (6 giá trị)
  - post_approval_exec_status (7 giá trị)
  - sync_error_category (3 giá trị)
  - task_priority_type (3 giá trị)
  - task_status_type (7 giá trị)
  - task_type (10 giá trị)
  - user_status_type (4 giá trị)
  - work_stage_type (6 giá trị)

[THÀNH CÔNG] Đã ghi file: server\app\shared\enums.py
```

### 4.2 Kết quả chạy kiểm thử Pytest (18/18 tests passed)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 18 items

server\tests\architecture\test_enums_match_db.py .                       [  5%]
server\tests\architecture\test_structure.py .                            [ 11%]
server\tests\unit\test_db_error_translation.py .....                     [ 38%]
server\tests\unit\test_health_and_envelope.py ........                   [ 83%]
server\tests\unit\test_logging_mask.py .                                 [ 88%]
server\tests\unit\test_transaction_rollback.py ..                        [100%]

======================== 18 passed, 1 warning in 1.02s ========================
```

### 4.3 Kết quả chạy CI hoàn chỉnh (`make ci`)
```text
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
39 files would be left unchanged.
.venv/Scripts/ruff.exe check .
All checks passed!
.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 39 source files
.venv/Scripts/pytest.exe server/tests
======================== 18 passed, 1 warning in 1.02s ========================
```

---

## 5. Giả định đã đặt
1. **Quy tắc đặt tên Enum Class trong Python:**
   - Chuyển `typname` dạng snake_case của PostgreSQL sang PascalCase (ví dụ: `actor_group_type` -> `ActorGroupType`).
   - Giữ nguyên nhãn giá trị ENUM dạng chuỗi hoa gạch dưới (ví dụ: `THUC_THI = "THUC_THI"`).
2. **Khóa đồng thời và Rollback:**
   - Dependency `get_db()` quản lý session ở mức request: toàn bộ các thao tác ghi trong cùng một request chia sẻ chung một transaction; chỉ khi request kết thúc mà không phát sinh exception thì transaction mới được commit.
3. **Mặt nạ bảo mật:**
   - Che giấu toàn bộ các trường mang từ khóa `authorization`, `password`, `token`, `cookie`, `secret`, `credentials` xuất hiện ở dạng key trong JSON/dict hoặc chuỗi văn bản (Bearer token, Cookie header, v.v.).

---

## 6. Chưa làm hoặc rủi ro
1. **Chưa làm:**
   - Các router nghiệp vụ cụ thể của 8 modules sẽ được triển khai ở các bước tiếp theo (AG4 cho Auth/RBAC, AG5 cho Inventory/Tasks, AG7 cho 8 module tổng quát).
   - Chưa tích hợp cơ chế rate-limiting ở tầng gateway/core (không bắt buộc trong phạm vi demo).
2. **Rủi ro & Biện pháp giảm thiểu:**
   - *Rủi ro:* CSDL thêm mới enum kiểu dữ liệu trong tương lai khiến mã Python lệch.
   - *Biện pháp:* Đã có test kiến trúc `test_enums_match_db.py` chạy trong CI; nếu CSDL thay đổi mà chưa chạy lại `python scripts/gen_enums.py` thì CI sẽ lập tức báo đỏ ngăn chặn commit/merge.

---

## 7. Đề xuất bước tiếp theo
1. Tiến hành nghiệm thu U5 độc lập cho bước AG3.
2. Tạo Pull Request cho nhánh `chore/ag3-server-core` vào `develop`.
3. Sau khi PR được duyệt và merge, chuyển sang bước **AG4: Xác thực và phân quyền (ag4-auth-rbac)**.
