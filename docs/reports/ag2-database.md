# Báo cáo AG2: Cơ sở dữ liệu, Hạt giống (Seeds) và Kiểm thử CSDL

## 1. Mục tiêu
- Cấu hình dịch vụ CSDL PostgreSQL 16 trong `docker-compose.yml` có volume bền vững, healthcheck và nạp cấu hình từ `.env`.
- Viết kịch bản `scripts/reset_db.sh` chạy được độc lập, tự động DROP và CREATE database, nạp theo đúng thứ tự: `database/schema.sql`, `database/patch_v4_2_1.sql` và các file `database/seeds/*.sql`.
- Viết kịch bản `scripts/run_db_tests.sh` tạo DB tạm riêng biệt, nạp schema và patch, chạy `wms_smoke_test_v4_2_1.sql`, chạy patch lần 2 để kiểm tra tính idempotent, chạy `test_seed.sql` trên DB chính và xóa DB tạm.
- Tạo dữ liệu hạt giống (seeds) chuẩn xác, chạy lại được (idempotent):
  - `01_roles_permissions.sql`: 9 vai trò chuẩn, permissions và role_permissions theo ma trận phân quyền Mục 5.3 Đặc tả và slide phân rã v3.
  - `02_master_demo.sql`: 1 kho, warehouse_configs chuẩn, 3 khu vực (STORAGE, RECEIVING_DOCK, STAGING), 30 vị trí có barcode, 10 SKU (2 SKU có hạn dùng & theo dõi lô), 3 loại thùng, 3 khách hàng, 3 nhà cung cấp, reason codes.
  - `03_users_demo.sql`: 9 tài khoản demo cho 9 vai trò, mật khẩu `Demo@123456`, hash bcrypt sinh bằng script.
- Viết `database/tests/test_seed.sql` kiểm tra tự động 6 tiêu chuẩn dữ liệu seed.

## 2. Đã làm (Danh sách file)
- **Cấu hình Docker:**
  - `docker-compose.yml`: Dịch vụ PostgreSQL 16 Alpine, container `abest-wms-postgres`, port 5432, volume `pgdata`, healthcheck `pg_isready`.
- **Dữ liệu hạt giống CSDL (`database/seeds/`):**
  - `database/seeds/01_roles_permissions.sql`: 9 vai trò, 14 permissions, 46 bản ghi phân quyền role_permissions.
  - `database/seeds/02_master_demo.sql`: Kho WH01, 3 zone, 30 location, 10 SKU + 10 barcode, 3 box type, 3 customer, 3 supplier, 6 reason code.
  - `database/seeds/03_users_demo.sql`: 9 tài khoản người dùng demo ứng với 9 vai trò.
- **Kịch bản vận hành & Kiểm thử (`scripts/`):**
  - `scripts/make_password_hash.py`: Script Python sinh hash bcrypt an toàn.
  - `scripts/reset_db.sh`: Bash script reset và nạp tuần tự CSDL chính.
  - `scripts/run_db_tests.sh`: Bash script tự động chạy smoke test, idempotent patch và test_seed.
  - `database/tests/test_seed.sql`: Khối PL/pgSQL DO kiểm tra 6 tiêu chuẩn nghiệp vụ.
- **Tài liệu & Make:**
  - `Makefile`: Cập nhật thêm target `db-reset` và `db-test`.
  - `README.md`: Bổ sung bảng thông tin 9 tài khoản demo, mật khẩu và hướng dẫn chạy CSDL.

## 3. Cách chạy lại
```bash
# 1. Khởi động PostgreSQL qua Docker Compose
docker compose up -d

# 2. Reset và seed CSDL
make db-reset
# Hoặc: bash scripts/reset_db.sh

# 3. Chạy toàn bộ kiểm thử CSDL (smoke test + idempotent patch + test_seed)
make db-test
# Hoặc: bash scripts/run_db_tests.sh

# 4. Kiểm tra chất lượng mã nguồn
make ci
```

## 4. Kết quả test (Lệnh và kết quả thật)

### (a) `scripts/reset_db.sh` chạy 2 lần liên tiếp đều thành công
- **Lệnh (lần 1 & lần 2):**
  ```bash
  bash scripts/reset_db.sh
  ```
- **Kết quả thật:**
  ```text
  ============================================================
  ABEST WMS: Reset & Seed CSDL (abest_wms)
  ============================================================
  1. Đang kiểm tra kết nối Postgres...
  Postgres đã sẵn sàng!
  2. Khởi tạo lại CSDL: abest_wms
  DROP DATABASE
  CREATE DATABASE
  3. Nạp database/schema.sql
  --> Đang nạp: database/schema.sql
  CREATE EXTENSION ... CREATE TABLE ... CREATE FUNCTION ...
  4. Nạp database/patch_v4_2_1.sql
  --> Đang nạp: database/patch_v4_2_1.sql
  COMMIT
  5. Nạp các file database/seeds/*.sql
  --> Đang nạp: database/seeds/01_roles_permissions.sql
  INSERT 0 9
  INSERT 0 14
  DELETE 0
  INSERT 0 46
  --> Đang nạp: database/seeds/02_master_demo.sql
  INSERT 0 1 ... INSERT 0 30 ... INSERT 0 10 ...
  --> Đang nạp: database/seeds/03_users_demo.sql
  INSERT 0 9
  ============================================================
  [THÀNH CÔNG] Đã reset và seed dữ liệu CSDL abest_wms thành công!
  ============================================================
  ```
- **Mã thoát:** `0` cho cả 2 lần chạy liên tiếp (ĐẠT).

### (b) `scripts/run_db_tests.sh` in dòng "TẤT CẢ BÀI KIỂM THỬ ĐẠT", patch lần 2 không lỗi, test_seed.sql pass
- **Lệnh:**
  ```bash
  bash scripts/run_db_tests.sh
  ```
- **Kết quả thật:**
  ```text
  ============================================================
  ABEST WMS: Chạy kiểm thử CSDL (run_db_tests.sh)
  ============================================================
  1. Tạo CSDL tạm riêng: abest_wms_test_temp
  CREATE DATABASE
  2. Nạp schema.sql và patch_v4_2_1.sql vào abest_wms_test_temp
  --> Đang chạy: database/schema.sql trên CSDL abest_wms_test_temp
  --> Đang chạy: database/patch_v4_2_1.sql trên CSDL abest_wms_test_temp
  3. Chạy wms_smoke_test_v4_2_1.sql
  --> Đang chạy: database/tests/smoke_test.sql trên CSDL abest_wms_test_temp
  NOTICE:  PASS T1-T2, F2 (tồn kho, chuyển hàng, phần trăm đầy với hàng không pallet)
  NOTICE:  PASS T3, F2 (kiểm tra phần trăm đầy với hàng trên pallet)
  NOTICE:  PASS T4, F1, F3, F4 (cấp phát, soạn hàng, đóng gói, xuất kho)
  NOTICE:  PASS T5 (SoD - phân tách nhiệm vụ: tự duyệt bị chặn)
  NOTICE:  PASS F5 (lệnh đổi ERP đơn sang CANCELLED và đóng băng)
  NOTICE:  PASS F6 (bất biến sổ cái: UPDATE/DELETE inventory_transactions bị chặn)
  NOTICE:  PASS F7 (bất biến audit log: UPDATE/DELETE audit_logs bị chặn)
  NOTICE:  PASS F8 (quy tắc phân tầng phê duyệt fn_resolve_approval_tier)
  NOTICE:  PASS F9 (lấy quyền user fn_get_user_effective_permissions)
  NOTICE:  PASS F10 (không trừ âm tồn khả dụng)
  NOTICE:  PASS F11 (bắt buộc xác thực lại khi duyệt giá trị lớn)
  NOTICE:  PASS F12 (không cho phép người bị ủy quyền tự ủy quyền tiếp)
  NOTICE:  PASS F13 (chuyển hàng hư sang khu vực DAMAGED và trừ tồn khả dụng)
  NOTICE:  PASS F14 (khóa vị trí khi kiểm kê counting_location_tx_policy = BLOCK)
  NOTICE:  PASS F15 (cấm tự hủy task khi đang IN_PROGRESS)
  NOTICE:  PASS F16 (xóa đơn hàng DRAFT không để lại rác ở bảng con)
  NOTICE:  PASS F17 (đếm lại kiểm kê: quá max_recount_attempts bắt buộc chuyển cấp trên)
  NOTICE:  PASS F18 (chuyển đổi đơn vị tính UOM tự động khi quét mã vạch)
  NOTICE:  PASS F19 (tự động mở khóa tài khoản sau thời gian lockout_duration_minutes)
  NOTICE:  PASS F20 (không cho phép xóa vị trí đang có tồn kho)
  NOTICE:  PASS F21 (đổi mật khẩu lần đầu: xóa cờ must_change_password)
  NOTICE:  ============================================================
  NOTICE:  TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test v4.2.1)
  NOTICE:  ============================================================
  4. Chạy patch_v4_2_1.sql lần 2 để kiểm tra idempotent
  --> Đang chạy: database/patch_v4_2_1.sql trên CSDL abest_wms_test_temp
  COMMIT
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
  DO
  ============================================================
  [THÀNH CÔNG] TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test, patch lần 2, test_seed)
  ============================================================
  Dọn dẹp CSDL tạm: abest_wms_test_temp...
  DROP DATABASE
  ```
- **Mã thoát:** `0` (ĐẠT).

### (c) `make ci` vẫn xanh
- **Lệnh:**
  ```powershell
  mingw32-make ci
  ```
- **Kết quả thật:**
  ```text
  .venv/Scripts/black.exe --check .
  All done! ✨ 🍰 ✨
  27 files would be left unchanged.
  .venv/Scripts/ruff.exe check .
  All checks passed!
  .venv/Scripts/mypy.exe server client scripts
  Success: no issues found in 27 source files
  .venv/Scripts/pytest.exe server/tests
  ============================= test session starts =============================
  platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
  rootdir: D:\abest-wms
  configfile: pyproject.toml
  plugins: anyio-4.16.0, platformdirs-4.14.7, asyncio-0.25.0
  asyncio: mode=Mode.AUTO, asyncio_default_fixture_loop_scope=function
  collected 1 item

  server\tests\architecture\test_structure.py .                            [100%]

  ============================== 1 passed in 0.12s ==============================
  ```
- **Mã thoát:** `0` (ĐẠT).

## 5. Giả định đã đặt
- Sử dụng mật khẩu mặc định `Demo@123456` cho cả 9 tài khoản demo, đã được hash chuẩn xác bằng thuật toán `bcrypt` và cập nhật thông tin minh bạch trong `README.md`.
- Các scripts bash (`reset_db.sh`, `run_db_tests.sh`) được thiết kế linh hoạt: ưu tiên thực thi thông qua `docker compose exec` nếu container Docker `db` đang chạy, hoặc sử dụng `psql` cục bộ nếu có, đảm bảo chạy trơn tru trên cả môi trường Windows (Git Bash) lẫn Linux/CI.
- Các file CSDL đóng băng (`database/schema.sql`, `database/patch_v4_2_1.sql`, `database/tests/smoke_test.sql`) được giữ nguyên tuyệt đối 100% (git diff rỗng).

## 6. Chưa làm hoặc rủi ro
- Các module Python FastAPI hiện tại chưa kết nối trực tiếp đến PostgreSQL (sẽ thực hiện ở AG3: dựng lõi server, engine SQLAlchemy và session dependency).

## 7. Đề xuất bước tiếp
- Leader thực hiện nghiệm thu U5 cho bước AG2 (`make ci`, kiểm tra CSDL và báo cáo) rồi merge PR `chore/ag2-database` vào `develop`.
- Tiến hành bước **AG3: Lõi server** (`chore/ag3-server-core`).
