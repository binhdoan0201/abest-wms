# Báo cáo kỹ thuật bước AG7: Khung 8 module (ag7-module-scaffold)

**Mã bước:** `ag7-module-scaffold`  
**Nhánh:** `chore/ag7-module-scaffold`  
**Người thực hiện:** AG7 (Antigravity Module Scaffold)  
**Ngày thực hiện:** 2026-11-21  
**Trạng thái:** HOÀN THÀNH - ĐẠT YÊU CẦU

---

## 1. Mục tiêu
Hoàn thành bước AG7 theo Mục 11 của `docs/spec/quy-trinh-dung-khung.md`, Mục 4, 5, 6, 7 của Chuẩn API (`docs/spec/chuan-api-cong-nghe.md`) và Mục 6.1 Đặc tả dự án (`docs/spec/dac-ta-du-an.md`):
1. **Dựng đủ cấu trúc cho toàn bộ các module còn lại:** `master_data`, `inbound`, `outbound`, `approvals`, `cycle_count`, `dashboard`, `integrations` (bên cạnh `auth`, `inventory`, `tasks` đã hoàn thiện ở các pha trước). Mỗi module trong `server/app/modules/<m>/` có đủ:
   - `models.py`: Định nghĩa ORM SQLAlchemy 2.0.
   - `schemas.py`: Khai báo Pydantic schemas cho dữ liệu vào/ra.
   - `repositories.py`: Đóng gói toàn bộ truy vấn dữ liệu và lời gọi hàm CSDL PostgreSQL.
   - `services.py`: Nghiệp vụ và điều phối logic.
   - `routers.py`: Khai báo toàn bộ endpoint theo Mục 4 Chuẩn API, trả về HTTP 501 `Not Implemented` kèm kiểm tra quyền bằng `require_permission(...)`.
   - `__init__.py`: Chỉ export các thành phần công khai (`Service` và `router`).
2. **Bao phủ toàn bộ 43 bảng CSDL theo Mục 6.1 đặc tả:** Sử dụng kiểu dữ liệu chính xác (SQLAlchemy `Numeric` cho các cột NUMERIC).
3. **Mẫu giao diện client:** Tạo `client/app/modules/<m>/templates/index.html` cho từng module.
4. **Hợp đồng API chi tiết:** Lập đầy đủ 10 file hợp đồng API tại `docs/api/<m>.md` theo mẫu chuẩn Mục 5.
5. **Kiểm thử kiến trúc bằng AST (`server/tests/architecture/test_layering.py`):**
   - `routers.py` không bao giờ import `sqlalchemy` hoặc `models`.
   - `services.py` chỉ import nội bộ module và giao tiếp chéo module thông qua `__init__`.
   - Lời gọi hàm DB `fn_*` chỉ xuất hiện trong `repositories.py` (và `fn_apply_inventory_movement`, `fn_transfer_inventory` chỉ thuộc `inventory`).
6. **Kiểm thử đối chiếu OpenAPI và Tài liệu (`server/tests/architecture/test_openapi_matches_docs.py`):**
   - Đảm bảo toàn bộ endpoint trong `docs/api/*.md` đều hiện diện chính xác trong OpenAPI schema của FastAPI.
7. **Kiểm thử bao phủ 43 bảng ORM (`server/tests/architecture/test_table_models_coverage.py`):**
   - Khẳng định đủ 43 bảng Mục 6.1 được đăng ký trong `Base.metadata.tables`.
8. **Script khởi tạo nhánh tính năng (`scripts/create_branches.sh`):**
   - Hỗ trợ cờ `--dry-run` in danh sách 10 nhánh tính năng dự kiến tạo từ `develop`.
9. **Bộ kiểm thử đơn vị & tích hợp:**
   - Mỗi module có `server/tests/unit/<m>/test_<m>.py` và `server/tests/integration/<m>/test_<m>.py`.
   - Toàn bộ 63 bài test trong hệ thống đều vượt qua (`make ci`).

---

## 2. Đã làm

1. **Khởi tạo và hoàn thiện các module nghiệp vụ:**
   - `master_data`: 11 bảng CSDL (`warehouses`, `warehouse_configs`, `zones`, `locations`, `item_categories`, `skus`, `sku_barcodes`, `suppliers`, `customers`, `reason_codes`, `box_types`), CRUD endpoints mẫu cho 10 danh mục chung và users/roles, template client, tests và tài liệu `docs/api/master_data.md`.
   - `inbound`: 6 bảng CSDL (`purchase_orders`, `po_lines`, `asns`, `grns`, `grn_lines`, `grn_count_attempts`), 12 endpoints theo Mục 4.5, template client, tests và tài liệu `docs/api/inbound.md`.
   - `outbound`: 8 bảng CSDL (`outbound_orders`, `outbound_order_lines`, `pick_sessions`, `pick_lines`, `packages`, `goods_issues`, `package_lines`, `order_change_requests`), bọc hàm `fn_receive_erp_order_change` & `fn_decide_order_change`, 11 endpoints theo Mục 4.6, template client, tests và tài liệu `docs/api/outbound.md`.
   - `approvals`: 3 bảng CSDL (`approval_requests`, `approval_histories`, `stock_adjustments`), bọc hàm `fn_resolve_approval_tier` & `fn_escalate_expired_approvals`, 6 endpoints theo Mục 4.8, template client, tests và tài liệu `docs/api/approvals.md`.
   - `cycle_count`: 3 bảng CSDL (`cycle_count_sheets`, `cycle_count_lines`, `cycle_count_attempts`), 6 endpoints theo Mục 4.9, template client, tests và tài liệu `docs/api/cycle_count.md`.
   - `dashboard`: Phân hệ chỉ đọc (0 bảng riêng, truy vấn tổng hợp trên tồn kho và nhiệm vụ), 3 endpoints theo Mục 4.10, template client, tests và tài liệu `docs/api/dashboard.md`.
   - `integrations`: 1 bảng CSDL (`integration_sync_logs`), 5 endpoints ERP mock & nhật ký theo Mục 4.4, template client, tests và tài liệu `docs/api/integrations.md`.
   - `auth`: Bổ sung model ORM `AuditLog` (`audit_logs`) hoàn tất đủ 5 bảng của M0.
   - `inventory`: Bổ sung model ORM `InventoryAllocation` (`inventory_allocations` từ patch v4.2.1) hoàn tất đủ 5 bảng của M1.
   - `tasks`: Bổ sung route `reassign` và `cancel` hoàn tất đủ 9 endpoints của M6.

2. **Tài liệu hợp đồng API (`docs/api/`):**
   - Đầy đủ 10 file tài liệu: `auth.md`, `inventory.md`, `tasks.md`, `master_data.md`, `inbound.md`, `outbound.md`, `approvals.md`, `cycle_count.md`, `dashboard.md`, `integrations.md`.

3. **Kiểm thử kiến trúc phân tầng AST (`server/tests/architecture/test_layering.py`):**
   - Sử dụng module chuẩn `ast` duyệt cây cú pháp:
     - Khẳng định 10 `routers.py` không import `sqlalchemy` hoặc `models`.
     - Khẳng định `services.py` không import sâu vào nội bộ module khác ngoài `__init__`.
     - Khẳng định lời gọi hàm CSDL `fn_*` chỉ nằm trong `repositories.py` (và `fn_apply_inventory_movement` / `fn_transfer_inventory` chỉ thuộc `inventory`).

4. **Kiểm thử đối chiếu hợp đồng (`test_openapi_matches_docs.py` & `test_table_models_coverage.py`):**
   - Đối chiếu 121 API endpoints trong tài liệu với OpenAPI của FastAPI (khớp 100%).
   - Đối chiếu 43 bảng CSDL của Mục 6.1 với `Base.metadata.tables` (khớp 100%).

5. **Script khởi tạo nhánh (`scripts/create_branches.sh`):**
   - Viết kịch bản bash an toàn với `set -euo pipefail` và hỗ trợ `--dry-run`.

---

## 3. Cách chạy lại

### Kích hoạt môi trường
```powershell
$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
```

### Chạy mô phỏng script tạo nhánh
```powershell
& "C:\Program Files\Git\bin\bash.exe" scripts/create_branches.sh --dry-run
```

### Chạy kiểm thử kiến trúc AST
```powershell
.venv\Scripts\pytest server/tests/architecture/ -v
```

### Chạy toàn bộ quy trình CI (`make.bat ci`)
```powershell
.\make.bat ci
```

---

## 4. Kết quả kiểm thử thực tế

### 4.1. Kết quả chạy `scripts/create_branches.sh --dry-run`
```text
==========================================================
ABEST WMS - Khởi tạo 10 nhánh tính năng từ 'develop'
==========================================================
[DRY-RUN] Chế độ mô phỏng - KHÔNG thực hiện thay đổi trên Git/Remote.
Danh sách 10 nhánh tính năng dự kiến tạo từ 'develop':
  - feature/core-auth -> git branch feature/core-auth develop && git push -u origin feature/core-auth
  - feature/inventory -> git branch feature/inventory develop && git push -u origin feature/inventory
  - feature/integrations-mock -> git branch feature/integrations-mock develop && git push -u origin feature/integrations-mock
  - feature/master-data -> git branch feature/master-data develop && git push -u origin feature/master-data
  - feature/inbound -> git branch feature/inbound develop && git push -u origin feature/inbound
  - feature/outbound -> git branch feature/outbound develop && git push -u origin feature/outbound
  - feature/tasks -> git branch feature/tasks develop && git push -u origin feature/tasks
  - feature/approvals -> git branch feature/approvals develop && git push -u origin feature/approvals
  - feature/cycle-count -> git branch feature/cycle-count develop && git push -u origin feature/cycle-count
  - feature/dashboard -> git branch feature/dashboard develop && git push -u origin feature/dashboard
[DRY-RUN] Hoàn tất mô phỏng kiểm tra danh sách nhánh.
```

### 4.2. Kết quả chạy CI (`make.bat ci`)
```text
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
152 files would be left unchanged.
.venv/Scripts/ruff.exe check .
All checks passed!
.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 152 source files
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

======================= 63 passed, 5 warnings in 18.89s =======================
```

---

## 5. Giả định (Assumptions)
1. Các router của 8 module scaffold trả về HTTP 501 `Not Implemented` cùng mã lỗi `NOT_IMPLEMENTED` để xác lập ranh giới giao kèo API mà không gây nhầm lẫn với lỗi máy chủ hoặc lỗi thiếu quyền.
2. Các chủ module (A, B, C, D) sẽ triển khai chi tiết mã nguồn nghiệp vụ thực thi trong các nhánh `feature/*` tương ứng sau khi bước AG7 được hợp nhất vào `develop`.

---

## 6. Rủi ro và biện pháp xử lý
- **Rủi ro vi phạm ranh giới phân tầng:** Lập trình viên có thể vô tình import models hoặc viết truy vấn DB trong router.
  - *Biện pháp:* Khóa chặn bằng `server/tests/architecture/test_layering.py` chạy qua AST trong mọi lần chạy CI.
- **Rủi ro sai lệch tài liệu API so với mã nguồn:**
  - *Biện pháp:* Khóa chặn bằng `server/tests/architecture/test_openapi_matches_docs.py` đối chiếu tự động.

---

## 7. Đề xuất bước tiếp theo
1. Lập báo cáo nghiệm thu độc lập U5 (`docs/reports/u5-ag7-module-scaffold.md`).
2. Trình người dùng phê duyệt commit và tạo Pull Request vào nhánh `develop`.
3. Nhận lệnh «merge» từ người dùng, thực hiện squash-merge PR vào `develop`.
4. Tiến hành bước tiếp theo trong quy trình dựng khung: **AG8 (Tài liệu tổng hợp khung) và U6 (Bật bảo vệ nhánh, chạy tạo nhánh thật)**.
