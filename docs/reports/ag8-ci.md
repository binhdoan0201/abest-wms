# Báo cáo kỹ thuật bước AG8: CI và Kiểm thử tự động (ag8-ci)

**Mã bước:** `ag8-ci`  
**Nhánh:** `chore/ag8-ci`  
**Người thực hiện:** AG8 (Antigravity CI Engineer)  
**Ngày thực hiện:** 2026-11-21  
**Trạng thái:** HOÀN THÀNH - ĐẠT YÊU CẦU

---

## 1. Mục tiêu
Hoàn thành bước AG8 theo Mục 12 của `docs/spec/quy-trinh-dung-khung.md`:
1. **Thiết lập GitHub Actions Workflow (`.github/workflows/ci.yml`):**
   - Tự động chạy khi có Pull Request mở vào hoặc commit đẩy lên `develop` hoặc `main`.
   - Chạy các bước kiểm tra chất lượng mã nguồn: Black formatting (`black --check .`), Ruff linter (`ruff check .`), MyPy static type checking (`mypy server client scripts`).
   - Khởi tạo service container PostgreSQL 16 (`postgres:16-alpine`), tự động kiểm tra health check.
   - Cài đặt công cụ PostgreSQL client, nạp schema và seed dữ liệu bằng `scripts/reset_db.sh`.
   - Thực thi toàn bộ kiểm thử CSDL qua `scripts/run_db_tests.sh` (smoke test, idempotent patch lần 2, test seed).
   - Chạy bộ kiểm thử tự động toàn diện qua Pytest (unit tests, integration tests, architecture AST layering tests, OpenAPI contract match tests, table coverage tests).
   - Bật cache pip để tăng tốc các lần chạy sau.
2. **Đồng bộ hóa lệnh `make ci` (`make.bat ci` trên Windows):**
   - Đảm bảo môi trường phát triển cục bộ chạy đúng chuỗi lệnh kiểm tra tiêu chuẩn giống hệt pipeline CI trên GitHub.
3. **Cập nhật tài liệu `README.md`:**
   - Thêm huy hiệu (badge) trạng thái workflow GitHub Actions.
   - Hướng dẫn chi tiết cách chạy Local CI và quy trình CI trên GitHub Actions.

---

## 2. Đã làm

1. **Tạo file cấu hình workflow `.github/workflows/ci.yml`:**
   - Thiết lập các triggers `push` và `pull_request` cho 2 nhánh bảo vệ `develop` và `main`.
   - Khởi tạo service container PostgreSQL 16 với biến môi trường chuẩn của dự án (`wms_admin`, `wms_secret_pass`, `abest_wms`).
   - Cấu hình 10 bước thực thi rõ ràng, minh bạch với đầy đủ biến môi trường.
   - Kiểm tra cú pháp YAML bằng thư viện chuẩn `yaml.safe_load`.

2. **Cập nhật `Makefile`:**
   - Cấu hình biến `BASH` thông minh hỗ trợ Git Bash trên môi trường Windows.
   - Mở rộng mục tiêu `ci` thành: `ci: lint typecheck db-test test`.
   - Đảm bảo `make ci` và `make.bat ci` chạy mượt mà trên cả Linux/macOS và Windows.

3. **Cập nhật `README.md`:**
   - Thêm badge trạng thái `CI Pipeline` ngay dưới tiêu đề dự án.
   - Mở rộng Mục 5 giải thích chi tiết quy trình Local CI và GitHub Actions CI.

---

## 3. Cách chạy lại

### Kích hoạt môi trường và cập nhật PATH
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
```

### Kiểm tra cú pháp file Workflow YAML
```powershell
.venv\Scripts\python -c "import yaml; data = yaml.safe_load(open('.github/workflows/ci.yml', encoding='utf-8')); print('YAML Valid. Steps:', len(data['jobs']['ci']['steps']))"
```

### Chạy toàn bộ quy trình CI cục bộ (`make ci` / `make.bat ci`)
```powershell
.\make.bat ci
```

---

## 4. Kết quả kiểm thử thực tế

### 4.1. Kết quả kiểm tra cú pháp file Workflow YAML
```text
YAML Valid. Steps: 10
Keys in YAML: ['name', 'on', 'jobs']
Triggers: ['push', 'pull_request']
Workflow Name: ABEST WMS CI Pipeline
```

### 4.2. Kết quả chạy `make.bat ci` trên máy cục bộ
```text
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
152 files would be left unchanged.

.venv/Scripts/ruff.exe check .
All checks passed!

.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 152 source files

"C:/Program Files/Git/bin/bash.exe" scripts/run_db_tests.sh
============================================================
ABEST WMS: Chạy kiểm thử CSDL (run_db_tests.sh)
============================================================
1. Tạo CSDL tạm riêng: abest_wms_test_temp
2. Nạp schema.sql và patch_v4_2_1.sql vào abest_wms_test_temp
--> Đang chạy: database/schema.sql trên CSDL abest_wms_test_temp
--> Đang chạy: database/patch_v4_2_1.sql trên CSDL abest_wms_test_temp
3. Chạy wms_smoke_test_v4_2_1.sql
--> Đang chạy: database/tests/smoke_test.sql trên CSDL abest_wms_test_temp
4. Chạy patch_v4_2_1.sql lần 2 để kiểm tra idempotent
--> Đang chạy: database/patch_v4_2_1.sql trên CSDL abest_wms_test_temp
5. Chạy test_seed.sql trên CSDL chính (abest_wms)
--> Đang chạy: database/tests/test_seed.sql trên CSDL abest_wms
NOTICE:  ============================================================
NOTICE:  TẤT CẢ KIỂM THỬ TEST_SEED THÀNH CÔNG!
NOTICE:   - Vai trò: 9/9
NOTICE:   - User active theo vai trò: 1/1 cho 9 vai trò
NOTICE:   - Quyền theo vai trò: 100% các vai trò có ít nhất 1 quyền
NOTICE:   - Kho: 1/1
NOTICE:   - Vị trí: 30 (kỳ vọng >= 30)
NOTICE:   - SKU: 10 (kỳ vọng >= 10)
NOTICE:  ============================================================
============================================================
[THÀNH CÔNG] TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test, patch lần 2, test_seed)
============================================================

.venv/Scripts/pytest.exe server/tests
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 63 items

server\tests\architecture\test_enums_match_db.py .                       [  1%]
server\tests\architecture\test_layering.py ...                           [  6%]
server\tests\architecture\test_openapi_matches_docs.py .                 [  7%]
server\tests\architecture\test_structure.py .                            [  9%]
server\tests\architecture\test_table_models_coverage.py .                [ 11%]
server\tests\integration\approvals\test_approvals.py .                   [ 12%]
server\tests\integration\cycle_count\test_cycle_count.py .               [ 14%]
server\tests\integration\dashboard\test_dashboard.py .                   [ 15%]
server\tests\integration\inbound\test_inbound.py .                       [ 17%]
server\tests\integration\integrations\test_integrations.py .             [ 19%]
server\tests\integration\master_data\test_master_data.py .               [ 20%]
server\tests\integration\outbound\test_outbound.py .                     [ 22%]
server\tests\unit\approvals\test_approvals.py .                          [ 23%]
server\tests\unit\cycle_count\test_cycle_count.py .                      [ 25%]
server\tests\unit\dashboard\test_dashboard.py .                          [ 26%]
server\tests\unit\inbound\test_inbound.py .                              [ 28%]
server\tests\unit\integrations\test_integrations.py .                    [ 30%]
server\tests\unit\master_data\test_master_data.py .                      [ 31%]
server\tests\unit\outbound\test_outbound.py .                            [ 33%]
server\tests\unit\test_auth_rbac.py .......                              [ 44%]
server\tests\unit\test_client.py ..............                          [ 66%]
server\tests\unit\test_db_error_translation.py .....                     [ 74%]
server\tests\unit\test_health_and_envelope.py ........                   [ 87%]
server\tests\unit\test_inventory_tasks.py .....                          [ 95%]
server\tests\unit\test_logging_mask.py .                                 [ 96%]
server\tests\unit\test_transaction_rollback.py ..                        [100%]

======================= 63 passed, 5 warnings in 18.45s =======================
```

---

## 5. Hướng dẫn xem kết quả CI đầu tiên trên GitHub (Yêu cầu bắt buộc)

Sau khi nhánh `chore/ag8-ci` được đẩy lên và tạo Pull Request vào `develop`:
1. Mở trình duyệt và truy cập vào trang Pull Request trên GitHub:  
   `https://github.com/binhdoan0201/abest-wms/pulls`
2. Hoặc truy cập trực tiếp vào tab **Actions** của repository:  
   `https://github.com/binhdoan0201/abest-wms/actions`
3. Nhấp vào lần chạy mới nhất có tên commit hoặc tiêu đề PR (ví dụ: `feat(ci): configure github actions ci workflow and update make ci (ag8)`).
4. Quan sát danh sách các bước thực thi trong job `CI Pipeline (Lint, Typecheck, DB Tests, Pytest)`:
   - `Checkout repository`
   - `Set up Python 3.12`
   - `Install dependencies`
   - `Check code formatting (Black)`
   - `Lint code (Ruff)`
   - `Static type checking (MyPy)`
   - `Install PostgreSQL client utilities`
   - `Reset and seed test database`
   - `Run database tests (Smoke test, Idempotent patch, Test seed)`
   - `Run Pytest test suite (Unit, Integration, Architecture)`
5. Khi tất cả các bước đạt màu xanh lá cây (**Passed**), hệ thống đã sẵn sàng cho bước nghiệm thu U5 và merge vào `develop`.

---

## 6. Đề xuất bước tiếp theo
1. Lập báo cáo nghiệm thu độc lập U5 (`docs/reports/u5-ag8-ci.md`).
2. Trình người dùng phê duyệt commit và tạo Pull Request vào nhánh `develop`.
3. Nhận lệnh «merge» từ người dùng, thực hiện squash-merge PR vào `develop`.
4. Chuẩn bị bước **AG9: Kiểm tra độc lập (ag9-verify)** theo Mục 13 của đặc tả.
