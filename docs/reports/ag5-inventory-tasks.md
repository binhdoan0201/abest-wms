# Báo cáo kỹ thuật bước AG5: Dịch vụ & Router Inventory & Tasks (ag5-inventory-tasks)

**Mã bước:** `ag5-inventory-tasks`  
**Nhánh:** `chore/ag5-inventory-tasks`  
**Người thực hiện:** AG5 (Antigravity Inventory & Tasks)  
**Ngày thực hiện:** 2026-11-21  
**Trạng thái:** HOÀN THÀNH - ĐẠT YÊU CẦU

---

## 1. Mục tiêu
Xây dựng phân hệ Quản lý Tồn kho (`inventory`) và Quản lý Nhiệm vụ (`tasks`) theo Mục 9 của `docs/spec/quy-trinh-dung-khung.md`, Mục 4.1 và Mục 9.3 của Chuẩn API (`docs/spec/chuan-api-cong-nghe.md`):
- **Phân hệ Tồn kho (`server/app/modules/inventory/`):**
  - Bọc lời gọi hàm CSDL qua SQLAlchemy: `fn_apply_inventory_movement` và `fn_transfer_inventory`. Không viết lại logic kho bằng Python; dùng hàm DB, bắt exception từ PostgreSQL, translate thành lỗi nghiệp vụ rõ ràng (HTTP 409).
  - Export của `server/app/modules/inventory/__init__.py` chỉ để lộ đúng 2 hàm: `apply_movement` và `transfer_inventory`. Các hàm nội bộ không export ra ngoài.
  - Router REST cơ bản:
    - `GET /inventory/balances`: chỉ user có quyền `QL-1.1` (kiểm thử 403 khi dùng token `nv-kiemke`).
    - Các endpoint tra cứu tồn kho, giao dịch, lô hàng, pallet, vị trí.
- **Phân hệ Nhiệm vụ (`server/app/modules/tasks/`):**
  - Bảng `tasks`: ORM model + mapping (dựa trên bảng đã tạo từ AG2).
  - Dịch vụ quản lý vòng đời: tạo task (`create_task`), giao task (`assign_task`), nhận task (`accept_task`), từ chối kèm lý do (`reject_task`), hoàn thành (`complete_task`), cập nhật tiến độ; optimistic locking qua `version_no`.
  - Bọc TODOs rõ ràng cho các tính năng pha sau: tính SLA tự động, auto-dispatch bằng thuật toán, reassign khi timeout.
  - Router REST cơ bản:
    - `GET /tasks`: nhân viên kho chỉ xem task được giao cho mình hoặc task chưa gán thuộc khu vực của mình; các vai trò quản lý (`thukho`, `quanly`, `bgd`) xem được toàn bộ danh sách trong kho.
- **Bộ kiểm thử tự động toàn diện:** `server/tests/unit/test_inventory_tasks.py` kiểm thử đầy đủ các yêu cầu trên.

---

## 2. Đã làm

1. **Phân hệ Tồn kho (`server/app/modules/inventory/`):**
   - `models.py`: Định nghĩa ORM models `InventoryBalance`, `InventoryTransaction`, `Lot`, `Pallet` (sử dụng PostgreSQL ENUM `PalletStatusType`).
   - `schemas.py`: Các schema Pydantic `BalanceItem`, `TransactionItem`, `LotItem`, `PalletItem`, `LocationStockItem`.
   - `repositories.py`: Lớp `InventoryRepository` thực thi các hàm SQL PL/pgSQL qua `text("SELECT * FROM fn_apply_inventory_movement(...)")` và `text("SELECT * FROM fn_transfer_inventory(...)")`, kèm các hàm truy vấn số dư, giao dịch, lô hàng, pallet, tồn vị trí.
   - `services.py`: Cung cấp hàm `apply_movement` và `transfer_inventory` với cơ chế bọc lỗi `translate_db_error` (chuyển đổi lỗi PostgreSQL trigger/exception thành `BusinessError` HTTP 409), cùng lớp `InventoryService` phục vụ các API tra cứu.
   - `routers.py`: Cung cấp router `/inventory` với các endpoint:
     - `GET /inventory/balances`: Yêu cầu quyền `QL-1.1` qua `require_permission("QL-1.1")`.
     - `GET /inventory/transactions`: Lịch sử biến động kho.
     - `GET /inventory/lots`: Danh sách lô hàng.
     - `GET /inventory/pallets` và `GET /inventory/pallets/{id}`: Danh sách và chi tiết pallet.
     - `GET /inventory/locations/{id}/stock`: Tồn kho theo vị trí.
   - `__init__.py`: Giới hạn `__all__ = ["apply_movement", "transfer_inventory"]`, che giấu toàn bộ hàm nội bộ.

2. **Phân hệ Nhiệm vụ (`server/app/modules/tasks/`):**
   - `models.py`: Định nghĩa ORM model `Task` ánh xạ bảng `tasks`, tích hợp chính xác 4 PostgreSQL enum: `task_type`, `work_stage_type`, `task_priority_type`, `task_status_type`.
   - `schemas.py`: Pydantic models `CreateTaskRequest`, `AssignTaskRequest`, `AcceptTaskRequest`, `RejectTaskRequest`, `CompleteTaskRequest`, `TaskResponse`.
   - `repositories.py`: Lớp `TaskRepository` tạo mới, truy vấn theo ID và truy vấn danh sách lọc theo nhân viên / khu vực.
   - `services.py`: Lớp `TaskService` xử lý trọn vẹn vòng đời nhiệm vụ:
     - `create_task`: Khởi tạo nhiệm vụ mới (`PENDING`), ghi nhật ký `create_audit_log`.
     - `assign_task`: Phân công nhân viên, chuyển trạng thái `ASSIGNED`, kiểm tra khóa lạc quan `version_no`.
     - `accept_task`: Nhân viên nhận nhiệm vụ, chuyển trạng thái `IN_PROGRESS`, cập nhật `started_at`, tăng `version_no`.
     - `reject_task`: Nhân viên từ chối, ghi nhận `rejection_reason`, chuyển trạng thái `REJECTED`, tăng `version_no`.
     - `complete_task`: Hoàn tất nhiệm vụ, chuyển `COMPLETED`, cập nhật tiến độ 100%, ghi nhận `completed_qty`, tăng `version_no`.
     - Đặt rõ các khối TODOs cho pha sau: tính SLA tự động, auto-dispatch bằng thuật toán, reassign khi timeout.
   - `routers.py`: Endpoint `/tasks` với bộ lọc phân quyền thông minh: nhân viên kho chỉ xem task gán cho mình hoặc task chưa gán thuộc khu vực của mình.
   - `__init__.py`: Export các hàm dịch vụ và khai báo TODOs cho các tính năng tự động hóa pha sau.

3. **Cập nhật Exception và Translation (`server/app/core/exceptions.py`):**
   - Bổ sung ánh xạ lỗi PL/pgSQL `TON_KHO_KHONG_TON_TAI` và vi phạm check constraint tồn kho sang mã lỗi `INVENTORY_INSUFFICIENT_QTY` (HTTP 409).

4. **Tích hợp vào Ứng dụng chính (`server/app/main.py`):**
   - Đăng ký `inventory_router` tại prefix `/api/v1`.
   - Đăng ký `tasks_router` tại prefix `/api/v1`.

5. **Bộ kiểm thử toàn diện (`server/tests/unit/test_inventory_tasks.py`):**
   - `test_inventory_exports_only_movement_and_transfer`: Xác minh `inventory.__init__.__all__` chỉ có đúng 2 hàm.
   - `test_apply_movement_db_wrapper_and_error_translation`: Xác minh gọi hàm DB `fn_apply_inventory_movement` thành công cộng dồn tồn kho và khi trừ quá số lượng tồn bị translate thành HTTP 409 `INVENTORY_INSUFFICIENT_QTY`.
   - `test_inventory_balances_permission_ql11_and_forbidden_for_kiemke`: Xác minh tài khoản có quyền `QL-1.1` (`thukho`, `nv-nhan`) truy cập thành công HTTP 200, trong khi `nv-kiemke` và `admin` bị chặn HTTP 403 `FORBIDDEN`.
   - `test_task_lifecycle_and_optimistic_locking`: Xác minh trọn vẹn chu trình `create` -> `assign` -> `accept` -> `complete`, kiểm tra `version_no` xung đột ném HTTP 409 `VERSION_CONFLICT`, và xác minh từ chối nhiệm vụ (`reject`).
   - `test_tasks_filtering_for_worker`: Xác minh nhân viên kho chỉ nhìn thấy task của mình và task chưa gán cùng zone, không nhìn thấy task của nhân viên khác.

---

## 3. Cách chạy lại

### Chạy riêng bộ kiểm thử Inventory & Tasks
```powershell
.venv\Scripts\pytest server/tests/unit/test_inventory_tasks.py -v
```

### Chạy toàn bộ kiểm thử hệ thống (30 bài test)
```powershell
.venv\Scripts\pytest -v
```

### Chạy toàn bộ kiểm tra CI chuẩn (`make.bat ci`)
```powershell
.\make.bat ci
```

---

## 4. Kết quả test thực tế

### 4.1 Kết quả kiểm thử bộ Inventory & Tasks (`server/tests/unit/test_inventory_tasks.py`)
```text
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0 -- D:\abest-wms\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collecting ... collected 5 items

server/tests/unit/test_inventory_tasks.py::test_inventory_exports_only_movement_and_transfer PASSED [ 20%]
server/tests/unit/test_inventory_tasks.py::test_apply_movement_db_wrapper_and_error_translation PASSED [ 40%]
server/tests/unit/test_inventory_tasks.py::test_inventory_balances_permission_ql11_and_forbidden_for_kiemke PASSED [ 60%]
server/tests/unit/test_inventory_tasks.py::test_task_lifecycle_and_optimistic_locking PASSED [ 80%]
server/tests/unit/test_inventory_tasks.py::test_tasks_filtering_for_worker PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\starlette\testclient.py:40
  D:\abest-wms\.venv\Lib\site-packages\starlette\testclient.py:40: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = typing.Callable[[], typing.ContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 5 passed, 1 warning in 3.65s =========================
```

### 4.2 Kết quả chạy CI đầy đủ (`make.bat ci`)
```text
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
59 files would be left unchanged.
.venv/Scripts/ruff.exe check .
All checks passed!
.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 59 source files
.venv/Scripts/pytest.exe server/tests
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
rootdir: D:\abest-wms
configfile: pyproject.toml
plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
collected 30 items

server\tests\architecture\test_enums_match_db.py .                       [  3%]
server\tests\architecture\test_structure.py .                            [  6%]
server\tests\unit\test_auth_rbac.py .......                              [ 30%]
server\tests\unit\test_db_error_translation.py .....                     [ 46%]
server\tests\unit\test_health_and_envelope.py ........                   [ 73%]
server\tests\unit\test_inventory_tasks.py .....                          [ 90%]
server\tests\unit\test_logging_mask.py .                                 [ 93%]
server\tests\unit\test_transaction_rollback.py ..                        [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\starlette\testclient.py:40
  D:\abest-wms\.venv\Lib\site-packages\starlette\testclient.py:40: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = typing.Callable[[], typing.ContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================= 30 passed, 1 warning in 12.48s ========================
```

---

## 5. Giả định (Assumptions)
1. CSDL PostgreSQL đã được khởi tạo và chạy ổn định từ bước AG2 với schema v4.1, bản vá v4.2.1 và dữ liệu mẫu (seeds).
2. Các bảng chưa có ORM model ở pha này (`warehouses`, `locations`, `skus`, `zones`) không khai báo `ForeignKey` trong ORM class của Python để tránh lỗi `NoReferencedTableError`, trong khi tính toàn vẹn khóa ngoại vẫn được CSDL PostgreSQL bảo đảm nghiêm ngặt.
3. Trong hạt giống phân quyền (`database/patch_v4_2_1.sql`), quyền `QL-1.1` được cấp cho 7 vai trò (`nv-nhan`, `nv-cat`, `nv-soan`, `nv-dongoi`, `thukho`, `quanly`, `bgd`) và không cấp cho `nv-kiemke` cũng như `admin`.

---

## 6. Rủi ro và biện pháp xử lý
- **Rủi ro xung đột dữ liệu đồng thời trên Nhiệm vụ:** Nhiều nhân viên hoặc quản lý cùng thao tác trên 1 nhiệm vụ.
  - *Biện pháp:* Sử dụng optimistic locking thông qua trường `version_no`. Bất kỳ thao tác chuyển trạng thái nào nếu gửi sai `version_no` đều bị từ chối với HTTP 409 `VERSION_CONFLICT`.
- **Rủi ro rò rỉ logic nghiệp vụ kho trên tầng Python:** Nhân viên code vô tình viết lại logic tính tồn hoặc âm kho trên Python.
  - *Biện pháp:* Đóng gói triệt để qua hàm CSDL `fn_apply_inventory_movement` và `fn_transfer_inventory`; `modules/inventory/__init__.py` chỉ để lộ đúng 2 hàm này.

---

## 7. Đề xuất bước tiếp theo
1. Tiến hành kiểm tra và lập biên bản nghiệm thu độc lập U5 cho bước AG5 (`docs/reports/u5-ag5-inventory-tasks.md`).
2. Trình người dùng phê duyệt commit và tạo Pull Request vào nhánh `develop`.
3. Sau khi người dùng duyệt `merge`, thực hiện squash-merge PR vào nhánh `develop`.
4. Chuyển sang bước AG6: Khung Client (FastAPI + Jinja2 + HTMX + Tailwind CDN).
