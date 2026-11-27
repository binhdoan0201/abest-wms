# Báo cáo kiểm định độc lập khung dự án ABEST WMS (ag9-verify)

**Mã bước:** `ag9-verify`  
**Vai trò:** Người kiểm tra độc lập (Independent QA Verifier)  
**Môi trường thử nghiệm:** Bản clone sạch từ nhánh `develop` tại `D:\temp-verify\abest-wms`  
**Thời gian kiểm định:** 2026-11-21  
**Quy tắc tuân thủ:** Làm theo `README.md` từng bước và kiểm thử độc lập toàn diện.

---

## 1. Ghi nhận các điểm sai hoặc thiếu sót trong `README.md` (Đã khắc phục)

Quá trình dựng môi trường từ thư mục clone sạch hoàn toàn theo `README.md` ghi nhận các điểm thiếu sót và sai khác trên thực tế (đã được sửa và cập nhật hoàn tất):

| STT | Vị trí trong README | Nội dung ban đầu trong README | Vấn đề thực tế khi chạy | Mức độ | Tình trạng khắc phục |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | **Mục 2 - Bước 2:** Khởi tạo môi trường ảo | Hướng dẫn: `make install` | Trên Windows PowerShell, lệnh `make` không được nhận diện mặc định (`CommandNotFoundException: The term 'make' is not recognized`). | **Medium** | **ĐÃ SỬA:** Bổ sung hướng dẫn cho Windows PowerShell / cmd: `.\make.bat install`. |
| 2 | **Mục 3.1 & 5.1:** Lệnh chạy script kiểm thử CSDL | Hướng dẫn: `make db-test (hoặc: bash scripts/run_db_tests.sh)` | Trên Windows có kích hoạt tính năng WSL nhưng chưa cài đặt Linux distro hoàn chỉnh, lệnh `bash` trỏ vào `C:\WINDOWS\system32\bash.exe`, gây lỗi: `<3>WSL ERROR: execvpe(/bin/bash) failed: No such file or directory`. | **High** | **ĐÃ SỬA:** Hướng dẫn rõ trên Windows sử dụng `.\make.bat db-test` và `.\make.bat db-reset`. |
| 3 | **Mục 2 - Bước 3:** Cấu hình biến môi trường | Hướng dẫn: `cp .env.example .env` | Lệnh `cp` chỉ hoạt động trên Linux/macOS và PowerShell (dưới dạng alias). Trên Command Prompt (cmd.exe) cổ điển lệnh này báo `is not recognized`. | **Low** | **ĐÃ SỬA:** Bổ sung chú thích cho Windows cmd: `copy .env.example .env`. |
| 4 | **Mục 1 & Mục 3.1:** Docker Compose | Hướng dẫn: `docker compose up -d` | Cần lưu ý yêu cầu Docker Compose V2 cú pháp `docker compose` (dấu cách) thay vì cú pháp cũ `docker-compose` (gạch nối). | **Trivial** | Đã xác nhận hoạt động bình thường trên Docker Desktop V2. |

---

## 2. Bảng tổng hợp kiểm định Checklist bàn giao

| STT | Hạng mục kiểm tra | Tiêu chuẩn đánh giá | Lệnh / Bằng chứng thực tế | Kết quả |
| :--- | :--- | :--- | :--- | :---: |
| 1 | **Cây thư mục theo Mục 3 Đặc tả** | Khung thư mục và các file bắt buộc khớp 100% | Chạy `python scripts/check_structure.py` trả về mã thoát `0`. Đã kiểm tra 32 thư mục, 17 file bắt buộc tồn tại. | **ĐẠT** |
| 2 | **Cài đặt thư viện (`make install`)** | Virtualenv sạch tạo thành công, cài đủ dependencies | Chạy `.\make.bat install`: Cài đặt thành công 100% gói từ `server/requirements.txt` và `client/requirements.txt`. | **ĐẠT** |
| 3 | **Khởi tạo và Seed CSDL (`make db-reset`)** | Reset sạch CSDL, nạp schema, patch, seed mẫu | Chạy `.\make.bat db-reset`: Nạp schema.sql, patch_v4_2_1.sql, 3 file seeds (9 vai trò, 9 user, 1 kho, 30 vị trí, 10 SKU). | **ĐẠT** |
| 4 | **Kiểm thử CSDL (`run_db_tests.sh`)** | CSDL tạm, smoke test, idempotent patch, test seed | Chạy `.\make.bat db-test`: CSDL tạm `abest_wms_test_temp` chạy đạt toàn bộ smoke test, patch lần 2 idempotent, `test_seed.sql` đạt 100%. | **ĐẠT** |
| 5 | **Local CI (`make ci`)** | Black, Ruff, MyPy, DB Tests, Pytest | Chạy `.\make.bat ci`: Black 0 thay đổi, Ruff 0 lỗi, MyPy 152 files sạch, DB tests đạt, Pytest 63/63 tests passed. | **ĐẠT** |
| 6 | **Khởi chạy Server & Client** | Port 8000 (Backend) và Port 3000 (Client) hoạt động | Backend Uvicorn port 8000 trả HTTP 200 `/health`. Client Uvicorn port 3000 trả HTTP 200 `/health`. | **ĐẠT** |
| 7 | **Đăng nhập 9 tài khoản seed** | Cả 9 tài khoản đăng nhập thành công vào Client | Đăng nhập thành công 9/9 tài khoản seed với mật khẩu `Demo@123456`, sinh cookie phiên hợp lệ. | **ĐẠT** |
| 8 | **Menu Client theo quyền (RBAC)** | Menu hiển thị đúng theo phân quyền từng vai trò | Ghi nhận menu chính xác cho cả 9 vai trò: kiểm kê chỉ thấy kiểm kê/task; admin chỉ thấy dữ liệu nguồn; kho thấy nghiệp vụ tương ứng. | **ĐẠT** |
| 9 | **Thử phá luật 1: Phân quyền API** | `nv-nhan` gọi endpoint của `thukho` phải bị 403 | `nv-nhan` gọi `GET /api/v1/approvals` trả HTTP 403 (`FORBIDDEN`); gọi `POST /api/v1/cycle-counts` trả HTTP 403 (`FORBIDDEN`). `thukho` gọi qua được (501). | **ĐẠT** |
| 10 | **Thử phá luật 2: Token giả mạo/hỏng** | Gửi token hỏng phải bị 401 | `GET /api/v1/auth/me` với token hỏng trả HTTP 401 (`AUTH_INVALID_TOKEN`); với header sai cú pháp trả HTTP 401. | **ĐẠT** |
| 11 | **Thử phá luật 3: Khóa lạc quan (version_no)** | 2 request ghi cùng `version_no`, chỉ 1 thành công | Tạo task (ver 1): Giao task req 1 (ver 1) -> HTTP 200 (ver lên 2); req 2 cùng gửi (ver 1) -> HTTP 409 (`VERSION_CONFLICT`). | **ĐẠT** |
| 12 | **Thử phá luật 4: Trừ tồn kho quá mức** | Chặn trừ âm tồn kho | Gọi `apply_movement` với `delta_available = -9999999.000` -> Ném `BusinessError` mã `INVENTORY_INSUFFICIENT_QTY`, HTTP 409. | **ĐẠT** |
| 13 | **Giao diện hàm `tasks`** | Vòng đời nhiệm vụ hoạt động đúng chuẩn | Chạy chuỗi hàm `create_task` -> `assign_task` -> `accept_task` -> `complete_task`: Trạng thái và `version_no` cập nhật từ 1 đến 4. | **ĐẠT** |
| 14 | **Giao diện `apply_movement` & `transfer_inventory`** | Tác vụ kho và bảo toàn bucket | `apply_movement` ghi nhận biến động và version; `transfer_inventory` chuyển vị trí bảo toàn đúng bucket (`ALLOCATED`/`AVAILABLE`). | **ĐẠT** |
| 15 | **Hợp đồng OpenAPI khớp Đặc tả** | Đủ endpoint theo Mục 4 Chuẩn API | Kiểm thử kiến trúc `test_openapi_matches_docs.py` đối chiếu 100% endpoint giữa tài liệu đặc tả và FastAPI OpenAPI schema: Passed. | **ĐẠT** |
| 16 | **ENUM Python khớp CSDL PostgreSQL** | Toàn bộ enum Python đồng bộ với Postgres DB | Kiểm thử kiến trúc `test_enums_match_db.py` đối chiếu giá trị Enum: Passed 100%. | **ĐẠT** |
| 17 | **Pipeline CI trên GitHub Actions** | Workflow GitHub Actions chạy tự động và xanh | Chạy `gh run list --limit 3`: Run ID `44873097010` trên nhánh `develop` đạt **SUCCESS (XANH 100%)** trong 1m37s. | **ĐẠT** |

---

## 3. Bằng chứng thực tế chi tiết

### 3.1. Menu hiển thị trên Client cho 9 vai trò seed

Kiểm tra bằng cách gửi yêu cầu đăng nhập thực tế tới `POST http://127.0.0.1:3000/login`, đọc cookie phiên và trích xuất danh sách liên kết menu điều hướng trong giao diện HTML:

| STT | Username | Vai trò (`role_code`) | Trạng thái đăng nhập | Menu điều hướng hiển thị thực tế |
| :--- | :--- | :--- | :---: | :--- |
| 1 | `nv_nhan` | `nv-nhan` | Thành công (200) | `['Tồn kho', 'Nhập kho', 'Nhiệm vụ']` |
| 2 | `nv_cat` | `nv-cat` | Thành công (200) | `['Tồn kho', 'Nhập kho', 'Nhiệm vụ']` |
| 3 | `nv_soan` | `nv-soan` | Thành công (200) | `['Tồn kho', 'Xuất kho', 'Nhiệm vụ']` |
| 4 | `nv_dongoi` | `nv-dongoi` | Thành công (200) | `['Tồn kho', 'Xuất kho', 'Nhiệm vụ']` |
| 5 | `nv_kiemke` | `nv-kiemke` | Thành công (200)* | `['Nhiệm vụ', 'Kiểm kê']` |
| 6 | `thukho` | `thukho` | Thành công (200) | `['Tổng quan', 'Tồn kho', 'Nhập kho', 'Xuất kho', 'Nhiệm vụ', 'Kiểm kê', 'Phê duyệt']` |
| 7 | `quanly` | `quanly` | Thành công (200) | `['Tổng quan', 'Tồn kho', 'Nhập kho', 'Xuất kho', 'Nhiệm vụ', 'Kiểm kê', 'Phê duyệt']` |
| 8 | `bgd` | `bgd` | Thành công (200) | `['Tổng quan', 'Tồn kho', 'Phê duyệt']` |
| 9 | `admin` | `admin` | Thành công (200)* | `['Dữ liệu nguồn']` |

*\*Ghi chú:* Với `nv_kiemke` và `admin`, do không có quyền `QL-1.1` (Xem tồn kho), khi client chuyển hướng mặc định vào `/inventory`, hệ thống render trang lỗi 403 Forbidden chuẩn UX kèm theo đúng thanh điều hướng cho phép các vai trò này truy cập vào đúng phân hệ được cấp phép (`['Nhiệm vụ', 'Kiểm kê']` cho `nv_kiemke` và `['Dữ liệu nguồn']` cho `admin`).

---

### 3.2. Bằng chứng 4 bài kiểm thử phá luật (Break-the-rules Tests)

#### Thử nghiệm 1: `nv_nhan` gọi endpoint của `thukho`
- **Lệnh thực hiện:** Gọi `GET http://127.0.0.1:8000/api/v1/approvals` (yêu cầu quyền `TK-3.2`) bằng token của `nv_nhan`.
- **Kết quả thật:**
  - HTTP Status: **403 Forbidden**
  - Payload trả về:
    ```json
    {
      "error": {
        "code": "FORBIDDEN",
        "message": "Tài khoản không có quyền `TK-3.2` để thực hiện hành động này",
        "details": {
          "permission_codes": ["TK-3.2"],
          "role_code": "nv-nhan"
        }
      }
    }
    ```
- **Đối chứng với `thukho`:** Cùng gọi `GET /api/v1/approvals` với token của `thukho`, vượt qua kiểm tra RBAC và trả về HTTP 501 `NOT_IMPLEMENTED` (khung scaffold cho module D).

#### Thử nghiệm 2: Đưa token hỏng / giả mạo
- **Lệnh thực hiện:** Gọi `GET http://127.0.0.1:8000/api/v1/auth/me` với Header `Authorization: Bearer this_is_a_broken_token`.
- **Kết quả thật:**
  - HTTP Status: **401 Unauthorized**
  - Payload trả về:
    ```json
    {
      "error": {
        "code": "AUTH_INVALID_TOKEN",
        "message": "Token xác thực không hợp lệ",
        "details": {}
      }
    }
    ```

#### Thử nghiệm 3: Gửi 2 request ghi cùng `version_no` (Optimistic Locking)
- **Kịch bản:** Tạo một nhiệm vụ kho mới (`task_id: d11872b3-04b4-4640-bedf-227f56a9fba0`, trạng thái `UNASSIGNED`, `version_no: 1`).
- **Request 1:** Gọi `POST /api/v1/tasks/{id}/assign` với `version_no: 1`.
  - HTTP Status: **200 OK**
  - Trạng thái cập nhật: `ASSIGNED`, `version_no` tăng lên `2`.
- **Request 2:** Gửi lại yêu cầu gán nhiệm vụ với cùng `version_no: 1` cũ.
  - HTTP Status: **409 Conflict**
  - Payload trả về:
    ```json
    {
      "error": {
        "code": "VERSION_CONFLICT",
        "message": "Nhiệm vụ đã được cập nhật bởi thao tác khác",
        "details": {
          "current_version_no": 2
        }
      }
    }
    ```

#### Thử nghiệm 4: Trừ tồn vượt mức khả dụng (Negative Inventory Check)
- **Lệnh thực hiện:** Gọi hàm dịch vụ `apply_movement` với `delta_available = Decimal("-999999999.000")` vượt quá tồn khả dụng hiện tại (0).
- **Kết quả thật:**
  - Ném ngoại lệ `BusinessError`:
    - `code`: `INVENTORY_INSUFFICIENT_QTY`
    - `message`: `"Số lượng tồn khả dụng không đủ để thực hiện giao dịch"`
    - `http_status`: **409**

---

### 3.3. Bằng chứng Pipeline CI trên GitHub Actions chạy XANH

- **Lệnh kiểm tra:** `gh run list --limit 3`
- **Kết quả thật:**
  ```text
  completed  success  fix(ci): sua health-cmd trong github actions ci va cap nhat readme ch…  ABEST WMS CI Pipeline  develop  push  44873097010  1m37s  2026-11-21T05:55:20Z
  completed  success  fix(ci): sua health-cmd trong github actions ci va cap nhat readme (ag9)  ABEST WMS CI Pipeline  fix/ci-healthcheck-and-readme  pull_request  44872952236  1m38s  2026-11-21T05:53:22Z
  ```
- **Các bước trong Job CI trên GitHub Actions đều hoàn thành với mã thoát 0:**
  - `✓ Set up job`
  - `✓ Initialize containers` (Postgres 16 Alpine với `--health-cmd pg_isready`)
  - `✓ Checkout repository`
  - `✓ Set up Python 3.12`
  - `✓ Install dependencies` (Server & Client requirements)
  - `✓ Check code formatting (Black)` (152 files unchanged)
  - `✓ Lint code (Ruff)` (All checks passed)
  - `✓ Static type checking (MyPy)` (Success: 0 issues in 152 files)
  - `✓ Install PostgreSQL client utilities`
  - `✓ Reset and seed test database` (`scripts/reset_db.sh`)
  - `✓ Run database tests` (`scripts/run_db_tests.sh`: smoke test, patch idempotent, test_seed)
  - `✓ Run Pytest test suite` (63 passed in 18.84s)
  - `✓ Complete job`

---

## 4. Danh sách lỗi và trạng thái khắc phục

1. **[CRITICAL - ĐÃ KHẮC PHỤC] Lỗi cú pháp cấu hình service container trong `.github/workflows/ci.yml`:**
   - Đã sửa dòng 28 thành `--health-cmd pg_isready`.
   - Pipeline GitHub Actions trên nhánh `develop` đã chạy thành công 100% (Run ID `44873097010`).

2. **[HIGH - ĐÃ KHẮC PHỤC] Lệnh chạy script CSDL xung đột với WSL trên Windows:**
   - Đã cập nhật `README.md` hướng dẫn rõ ràng việc sử dụng `.\make.bat db-reset` và `.\make.bat db-test` trên Windows.

3. **[MEDIUM - ĐÃ KHẮC PHỤC] Thiếu cú pháp lệnh Windows PowerShell trong `README.md`:**
   - Đã cập nhật `README.md` bổ sung `.\make.bat install`.

4. **[LOW - ĐÃ KHẮC PHỤC] Lệnh `cp` không tương thích cmd.exe cổ điển:**
   - Đã bổ sung ghi chú `copy .env.example .env` cho Windows Command Prompt.

---

## 5. Kết luận kiểm định

**KẾT LUẬN:** **SẴN SÀNG GIAO MODULE**

### Lý do:
1. **Kiến trúc & Cấu trúc thư mục:** Hoàn thành 100% khớp Mục 3 Đặc tả (32 thư mục, 17 file bắt buộc, phân tầng AST sạch).
2. **Hợp đồng OpenAPI & ENUM:** 100% endpoint của 8 module scaffold khớp Mục 4 Chuẩn API; toàn bộ Python Enum khớp CSDL PostgreSQL.
3. **Phân quyền RBAC & Giao diện:** Cả 9 vai trò demo đăng nhập trơn tru; menu điều hướng lọc chính xác theo quyền hạn; bảo mật token và phân quyền 403 hoạt động nghiêm ngặt.
4. **Dịch vụ Lõi & Tính toàn vẹn Dữ liệu:** `apply_movement` và `transfer_inventory` bảo toàn đúng các bucket tồn kho; khóa lạc quan `version_no` ngăn chặn xung đột ghi đồng thời; chặn trừ âm tồn khả dụng.
5. **CI/CD Tự động hóa:** Cả kiểm thử cục bộ (`.\make.bat ci`) và pipeline GitHub Actions trên nhánh `develop` đều **XANH HOÀN TOÀN** (63/63 Pytest passed, Black, Ruff, MyPy, DB Tests).
6. Dự án hoàn toàn đủ điều kiện chuyển sang bước **U6 (Gắn tag phát hành `v0.0-skeleton`)** và **U7 (Mời các thành viên B, C, D nhận nhánh phát triển module)** theo quy trình dựng khung.
