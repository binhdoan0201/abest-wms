# Báo cáo nghiệm thu U5: Bước AG3 (Lõi Server - Server Core)

**Mã nghiệm thu:** `u5-ag3-server-core`  
**PR liên quan:** [#3 - chore(server): implement server core infrastructure (ag3)](https://github.com/binhdoan0201/abest-wms/pull/3)  
**Nhánh kiểm tra:** `chore/ag3-server-core`  
**Người thực hiện nghiệm thu:** Antigravity Independent Auditor (U5)  
**Ngày nghiệm thu:** 2026-11-21  
**Trạng thái:** ĐẠT - NÊN MERGE

---

## 1. Mục tiêu nghiệm thu
Thực hiện quy trình nghiệm thu độc lập cho bước AG3 theo quy chuẩn Mục 13 của `docs/spec/quy-trinh-dung-khung.md`:
1. Kiểm tra tính bất biến của thư mục CSDL `database/`: tuyệt đối không có diff so với nhánh `develop`.
2. Kiểm tra việc sinh tự động ENUM từ CSDL thật: chạy `scripts/gen_enums.py` và đối chiếu với `pg_enum`.
3. Kiểm tra toàn bộ bộ test bắt buộc của AG3 (7 bài test).
4. Kiểm tra toàn bộ quy trình CI (`make.bat ci`: Black, Ruff, Mypy, Pytest).
5. Kiểm tra trạng thái PR trên GitHub.

---

## 2. Các hạng mục kiểm tra độc lập và Kết quả thực tế

### 2.1. Kiểm tra tính toàn vẹn thư mục CSDL (`git diff origin/develop database/`)
- **Lệnh thực hiện:**
  ```powershell
  git diff origin/develop database/
  ```
- **Kết quả thực tế:**
  Rỗng hoàn toàn (0 dòng thay đổi). Các file CSDL đóng băng (`schema.sql`, `patch_v4_2_1.sql`, `smoke_test.sql`) được bảo toàn 100%.

### 2.2. Kiểm tra sinh tự động ENUM (`scripts/gen_enums.py`)
- **Lệnh thực hiện:**
  ```powershell
  .venv\Scripts\python scripts/gen_enums.py
  ```
- **Kết quả thực tế:**
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

### 2.3. Kiểm tra kiểm thử Pytest đầy đủ (18 tests)
- **Lệnh thực hiện:**
  ```powershell
  .venv\Scripts\pytest -v
  ```
- **Kết quả thực tế:**
  ```text
  collected 18 items

  server\tests\architecture\test_enums_match_db.py .                       [  5%]
  server\tests\architecture\test_structure.py .                            [ 11%]
  server\tests\unit\test_db_error_translation.py .....                     [ 38%]
  server\tests\unit\test_health_and_envelope.py ........                   [ 83%]
  server\tests\unit\test_logging_mask.py .                                 [ 88%]
  server\tests\unit\test_transaction_rollback.py ..                        [100%]

  ======================== 18 passed, 1 warning in 1.21s ========================
  ```

- **Đối chiếu 7 yêu cầu test bắt buộc của AG3:**
  1. *(a) `/health` trả 200 và DB ok:* ĐẠT (`test_health_endpoint_root`, `test_health_endpoint_api_v1`).
  2. *(b) Phản hồi thành công và lỗi đúng envelope mục 2 chuẩn API, có `request_id`:* ĐẠT (`test_success_response_envelope_single`, `test_success_response_envelope_list`, `test_business_error_response`, `test_validation_error_response`).
  3. *(c) Mỗi lỗi DB gây ra bằng SQL thật ra đúng mã và HTTP status:* ĐẠT (5 tests trong `test_db_error_translation.py`: `BAN_GHI_BAT_BIEN` -> 500, `qty_available` -> 409, `DON_BI_DONG_BANG` -> 409, `THIEU_XAC_THUC_LAI` -> 403, `VI_PHAM_TACH_QUYEN_SOD` -> 403).
  4. *(d) `test_enums_match_db.py` đối chiếu ENUM Python với `pg_enum`:* ĐẠT (khớp 20 class enum, 114 nhãn).
  5. *(e) `make ci` xanh:* ĐẠT (Black, Ruff, Mypy, Pytest đều pass 100%).
  6. *(f) Bộ lọc log che `authorization`, `password`, `token`, `cookie`:* ĐẠT (`test_logging_masks_sensitive_data_in_text_and_dict`).
  7. *(g) Transaction ghi 2 bước mà bước 2 lỗi thì bước 1 bị rollback sạch:* ĐẠT (`test_transaction_two_step_rollback_on_error`).

### 2.4. Kiểm tra toàn bộ quy trình CI (`make ci`)
- **Lệnh thực hiện:**
  ```powershell
  .\make.bat ci
  ```
- **Kết quả thực tế:**
  ```text
  .venv/Scripts/black.exe --check .
  All done! ✨ 🍰 ✨
  39 files would be left unchanged.
  .venv/Scripts/ruff.exe check .
  All checks passed!
  .venv/Scripts/mypy.exe server client scripts
  Success: no issues found in 39 source files
  .venv/Scripts/pytest.exe server/tests
  ======================== 18 passed, 1 warning in 1.21s ========================
  ```

---

## 3. Kết luận nghiệm thu
- **Kết luận:** **ĐẠT**
- **Đánh giá khuyến nghị:** **NÊN MERGE**
- **Pull Request:** [PR #3](https://github.com/binhdoan0201/abest-wms/pull/3) đã sẵn sàng để squash merge vào `develop`.

---

## 4. Việc tôi cần làm tiếp
1. Chờ người giữ kho (User) ra lệnh xác nhận «merge».
2. Thực hiện lệnh `gh pr merge 3 --squash --delete-branch`.
3. Chuyển sang nhánh `develop`, kéo cập nhật mới nhất từ `origin/develop`.
4. Bắt đầu bước tiếp theo: **AG4: Xác thực và phân quyền (ag4-auth-rbac)**.
