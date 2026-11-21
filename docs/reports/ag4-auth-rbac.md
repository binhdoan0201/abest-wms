# Báo cáo kỹ thuật bước AG4: Xác thực và Phân quyền (Auth & RBAC)

**Mã bước:** `ag4-auth-rbac`  
**Nhánh:** `chore/ag4-auth-rbac`  
**Người thực hiện:** AG4 (Antigravity Auth & RBAC)  
**Ngày thực hiện:** 2026-11-21  
**Trạng thái:** HOÀN THÀNH - ĐẠT YÊU CẦU

---

## 1. Mục tiêu
Xây dựng phân hệ xác thực, cấp quyền và quản trị truy cập cho ABEST WMS theo Mục 8 của `docs/spec/quy-trinh-dung-khung.md`, Mục 4.1 và Mục 8, 9.3 của Chuẩn API (`docs/spec/chuan-api-cong-nghe.md`):
- Phân hệ xác thực `server/app/modules/auth/` đủ 5 file (`models.py`, `schemas.py`, `repositories.py`, `services.py`, `routers.py`) và `__init__.py`.
- Các endpoint: `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/change-password`.
- JWT HS256 hết hạn sau 8 giờ, mang các claim: `sub`, `role_code`, `warehouse_id`, `username`; mật khẩu băm bảo mật bằng Bcrypt.
- Hạ tầng phân quyền `core/rbac.py`: dependency `require_permission(permission_code)` trả về `access_type`; helper `enforce_warehouse_scope`; helper cho `X_OWN` và `V_OWN`.
- Quy tắc bảo mật đặc thù: Vai trò `admin` bị CHẶN tuyệt đối khỏi mọi quyền nghiệp vụ kho (chỉ được cấp `AD-1`).
- Hạ tầng ghi nhật ký kiểm toán `core/audit.py`: ghi nhận vào bảng bất biến `audit_logs` cho các thao tác đăng nhập, đổi mật khẩu và các chứng từ.
- Router thử nghiệm trong thư mục test và bộ test bắt buộc toàn diện 8 mục.

---

## 2. Đã làm
1. **Hạ tầng mật khẩu và JWT (`server/app/core/security.py`):**
   - Hàm `verify_password(plain, hashed)` và `hash_password(plain)` sử dụng Bcrypt (salt round = 12).
   - Hàm `create_access_token(data, expires_delta)` sinh JWT mã hóa HS256 với thời hạn 8 giờ (`ACCESS_TOKEN_EXPIRE_HOURS = 8`).
   - Hàm `decode_access_token(token)` giải mã, ném `AUTH_TOKEN_EXPIRED` (HTTP 401) nếu token quá hạn, ném `AUTH_INVALID_TOKEN` (HTTP 401) nếu token không hợp lệ hoặc sai chữ ký.
2. **Hạ tầng Audit Log bất biến (`server/app/core/audit.py`):**
   - Hàm `create_audit_log(db, action_code, entity_name, ...)` ghi nhận bản ghi nhật ký kiểm toán vào bảng `audit_logs`.
   - Đáp ứng đầy đủ quy định Mục 9.3 Chuẩn API (ghi nhận `LOGIN`, `LOGIN_FAILED`, `CHANGE_PASSWORD`, v.v.).
3. **Hạ tầng RBAC và Kiểm soát phạm vi (`server/app/core/rbac.py`):**
   - Lớp dữ liệu `UserContext(user_id, username, role_code, warehouse_id, permissions)`.
   - Dependency `get_current_user`: trích xuất Bearer token từ header `Authorization`, nạp vai trò và danh mục quyền của người dùng trực tiếp từ CSDL.
   - Dependency factory `require_permission(code)`:
     - Kiểm tra và chặn vai trò `admin` với mã lỗi `FORBIDDEN` (HTTP 403) nếu cố truy cập quyền nghiệp vụ kho.
     - Kiểm tra tài khoản có quyền `code` hay không; nếu không trả `FORBIDDEN` (HTTP 403).
     - Trả về `access_type` (`V`, `X`, `V_OWN`, `X_OWN`).
   - Helper `enforce_warehouse_scope(user, resource_warehouse_id)`: chặn tài khoản kho này truy cập dữ liệu kho khác bằng HTTP 404 `NOT_FOUND` (bảo mật tránh suy đoán ID).
   - Helper `enforce_owner_scope(access_type, user, owner_user_id)`: bảo vệ phạm vi sở hữu `X_OWN`/`V_OWN`, trả HTTP 403 nếu cố truy cập dữ liệu của người khác.
4. **Phân hệ Auth (`server/app/modules/auth/`):**
   - `models.py`: Định nghĩa ORM SQLAlchemy 2.0 cho các bảng `User`, `Role`, `Permission`, `RolePermission`.
   - `schemas.py`: Các Pydantic Schemas `LoginRequest`, `LoginResponseData`, `UserMeResponse`, `PermissionItem`, `ChangePasswordRequest`.
   - `repositories.py`: Lớp `AuthRepository` truy vấn người dùng theo username/id, lấy permissions theo role_id, cập nhật mật khẩu, ghi nhận login thành công/thất bại.
   - `services.py`: Lớp `AuthService` điều phối logic đăng nhập, xác thực mật khẩu, kiểm tra trạng thái hoạt động, ghi audit log, đổi mật khẩu và cấp JWT.
   - `routers.py`: Đăng ký các route `/auth/login`, `/auth/me`, `/auth/change-password` với chuẩn envelope `success_response`.
   - `__init__.py`: Export các lớp và router.
5. **Bộ kiểm thử độc lập (`server/tests/unit/test_auth_rbac.py`):**
   - Router thử nghiệm `dummy_rbac_router` đăng ký động toàn bộ 14 mã quyền và endpoint kiểm tra phạm vi kho.
   - 7 bài test đơn vị và tích hợp kiểm tra toàn bộ 8 yêu cầu bắt buộc của bước AG4.

---

## 3. Cách chạy lại

### Kích hoạt môi trường và cập nhật PATH
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
```

### Chạy riêng bộ kiểm thử Auth & RBAC
```powershell
.venv\Scripts\pytest server/tests/unit/test_auth_rbac.py -v
```

### Chạy toàn bộ kiểm thử dự án (25 tests)
```powershell
.venv\Scripts\pytest -v
```

### Chạy toàn bộ quy trình CI (`make.bat ci`)
```powershell
.\make.bat ci
```

---

## 4. Kết quả test thực tế

### 4.1 Kết quả kiểm thử bộ Auth & RBAC (`server/tests/unit/test_auth_rbac.py`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0 -- D:\abest-wms\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collecting ... collected 7 items

server/tests/unit/test_auth_rbac.py::test_all_9_seed_accounts_login_and_me PASSED [ 14%]
server/tests/unit/test_auth_rbac.py::test_parameterized_role_permissions_matrix PASSED [ 28%]
server/tests/unit/test_auth_rbac.py::test_invalid_credentials_and_token_errors PASSED [ 42%]
server/tests/unit/test_warehouse_scope_isolation PASSED [ 57%]
server/tests/unit/test_auth_rbac.py::test_audit_logs_recorded PASSED     [ 71%]
server/tests/unit/test_auth_rbac.py::test_change_password_and_login_with_new_password PASSED [ 85%]
server/tests/unit/test_auth_rbac.py::test_login_logging_masks_all_credentials PASSED [100%]

======================== 7 passed, 1 warning in 8.66s =========================
```

### 4.2 Kết quả chạy kiểm thử toàn dự án (25/25 tests passed)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0 -- D:\abest-wms\.venv\Scripts\python.exe
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 25 items

server/tests/architecture/test_enums_match_db.py::test_enums_match_db_strictly PASSED [  4%]
server/tests/architecture/test_structure.py::test_project_structure_completeness PASSED [  8%]
server/tests/unit/test_auth_rbac.py::test_all_9_seed_accounts_login_and_me PASSED [ 12%]
server/tests/unit/test_auth_rbac.py::test_parameterized_role_permissions_matrix PASSED [ 16%]
server/tests/unit/test_auth_rbac.py::test_invalid_credentials_and_token_errors PASSED [ 20%]
server/tests/unit/test_auth_rbac.py::test_warehouse_scope_isolation PASSED [ 24%]
server/tests/unit/test_auth_rbac.py::test_audit_logs_recorded PASSED     [ 28%]
server/tests/unit/test_auth_rbac.py::test_change_password_and_login_with_new_password PASSED [ 32%]
server/tests/unit/test_auth_rbac.py::test_login_logging_masks_all_credentials PASSED [ 36%]
server/tests/unit/test_db_error_translation.py::test_error_immutable_inventory_transactions PASSED [ 40%]
server/tests/unit/test_db_error_translation.py::test_error_inventory_insufficient_qty PASSED [ 44%]
server/tests/unit/test_db_error_translation.py::test_error_order_frozen PASSED [ 48%]
server/tests/unit/test_db_error_translation.py::test_error_reauth_required PASSED [ 52%]
server/tests/unit/test_db_error_translation.py::test_error_sod_violation PASSED [ 56%]
server/tests/unit/test_health_and_envelope.py::test_health_endpoint_root PASSED [ 60%]
server/tests/unit/test_health_and_envelope.py::test_health_endpoint_api_v1 PASSED [ 64%]
server/tests/unit/test_health_and_envelope.py::test_request_id_custom_header_propagation PASSED [ 68%]
server/tests/unit/test_health_and_envelope.py::test_success_response_envelope_single PASSED [ 72%]
server/tests/unit/test_health_and_envelope.py::test_success_response_envelope_list PASSED [ 76%]
server/tests/unit/test_health_and_envelope.py::test_business_error_response PASSED [ 80%]
server/tests/unit/test_health_and_envelope.py::test_validation_error_response PASSED [ 84%]
server/tests/unit/test_health_and_envelope.py::test_unhandled_exception_response PASSED [ 88%]
server/tests/unit/test_logging_mask.py::test_logging_masks_sensitive_data_in_text_and_dict PASSED [ 92%]
server/tests/unit/test_transaction_rollback.py::test_transaction_two_step_rollback_on_error PASSED [ 96%]
server/tests/unit/test_transaction_rollback.py::test_transaction_commits_when_successful PASSED [100%]

======================== 25 passed, 1 warning in 8.87s ========================
```

### 4.3 Kết quả kiểm tra CI (`make ci`)
```text
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
48 files would be left unchanged.
.venv/Scripts/ruff.exe check .
All checks passed!
.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 48 source files
.venv/Scripts/pytest.exe server/tests
======================== 25 passed, 1 warning in 9.66s ========================
```

---

## 5. Giả định đã đặt
1. **Khóa tài khoản khi sai mật khẩu:**
   - Trong bảng `users` có cột `failed_login_attempts` ghi nhận số lần sai (được tăng khi sai và reset về 0 khi đăng nhập thành công).
   - Tuy nhiên, trong CSDL không có cột cấu hình ngưỡng khóa (ví dụ: `max_failed_logins` trong `warehouse_configs`). Do đó, theo đúng chỉ dẫn của đặc tả: *"Nếu schema có cột đếm lần sai và ngưỡng khóa thì khóa tài khoản theo đó; nếu không có thì bỏ qua và ghi vào báo cáo."*, hệ thống ghi nhận số lần sai vào CSDL và không tự tiện sinh thêm cột ngoài schema đóng băng.
2. **Quyền hạn của Quản trị viên (`admin`):**
   - Tài khoản `admin` có quyền hệ thống `AD-1`. Toàn bộ các quyền nghiệp vụ kho (`NH-1`, `TK-3.2`, `SO-1`, v.v.) bị `require_permission` chặn cứng bằng HTTP 403 `FORBIDDEN` nhằm bảo đảm nguyên tắc phân tách trách nhiệm và bảo mật dữ liệu nghiệp vụ.

---

## 6. Chưa làm hoặc rủi ro
1. **Chưa làm:**
   - Chưa tích hợp Refresh Token hoặc SSO/LDAP bên ngoài (đúng theo quyết định thiết kế ADR 0001: dùng 1 JWT 8 giờ cho bản demo 15 ngày).
   - Giao diện đăng nhập phía client (sẽ được hoàn thiện ở bước AG6).
2. **Rủi ro & Biện pháp giảm thiểu:**
   - *Rủi ro:* Lộ JWT bí mật nếu Secret Key bị lộ.
   - *Biện pháp:* Khóa bí mật `SECRET_KEY` được đọc từ `.env`, logging JSON áp dụng mặt nạ che giấu toàn diện mọi token và header Authorization.

---

## 7. Đề xuất bước tiếp theo
1. Tiến hành nghiệm thu độc lập U5 cho bước AG4.
2. Tạo Pull Request cho nhánh `chore/ag4-auth-rbac` vào `develop`.
3. Sau khi PR được merge, tiến hành bước **AG5 (Giao diện hàm inventory và tasks)** và **AG6 (Khung Client)** có thể thực hiện song song.
