# Báo cáo nghiệm thu U5: Bước AG4 (Xác thực và Phân quyền - Auth & RBAC)

**Mã nghiệm thu:** `u5-ag4-auth-rbac`  
**PR liên quan:** [#4 - feat(auth): implement authentication and rbac infrastructure (ag4)](https://github.com/binhdoan0201/abest-wms/pull/4)  
**Nhánh kiểm tra:** `chore/ag4-auth-rbac`  
**Người thực hiện nghiệm thu:** Antigravity Independent Auditor (U5)  
**Ngày nghiệm thu:** 2026-11-21  
**Trạng thái:** ĐẠT - NÊN MERGE

---

## 1. Mục tiêu nghiệm thu
Thực hiện nghiệm thu độc lập cho bước AG4 theo quy chuẩn Mục 13 của `docs/spec/quy-trinh-dung-khung.md`:
1. Kiểm tra tính bất biến của thư mục CSDL `database/`: tuyệt đối không có diff so với nhánh `develop`.
2. Kiểm tra bộ test bắt buộc cho Auth & RBAC (8 yêu cầu).
3. Kiểm tra toàn bộ quy trình CI (`make.bat ci`: Black, Ruff, Mypy, Pytest).
4. Kiểm tra trạng thái PR trên GitHub.

---

## 2. Các hạng mục kiểm tra độc lập và Kết quả thực tế

### 2.1. Kiểm tra tính toàn vẹn thư mục CSDL (`git diff origin/develop database/`)
- **Lệnh thực hiện:**
  ```powershell
  git diff origin/develop database/
  ```
- **Kết quả thực tế:**
  Rỗng hoàn toàn (0 dòng thay đổi). Các file CSDL đóng băng (`schema.sql`, `patch_v4_2_1.sql`, `smoke_test.sql`) được bảo toàn nguyên vẹn 100%.

### 2.2. Kiểm tra bộ kiểm thử bắt buộc AG4 (`server/tests/unit/test_auth_rbac.py`)
- **Lệnh thực hiện:**
  ```powershell
  .venv\Scripts\pytest server/tests/unit/test_auth_rbac.py -v
  ```
- **Kết quả thực tế:**
  ```text
  collected 7 items

  server/tests/unit/test_auth_rbac.py::test_all_9_seed_accounts_login_and_me PASSED [ 14%]
  server/tests/unit/test_auth_rbac.py::test_parameterized_role_permissions_matrix PASSED [ 28%]
  server/tests/unit/test_auth_rbac.py::test_invalid_credentials_and_token_errors PASSED [ 42%]
  server/tests/unit/test_warehouse_scope_isolation PASSED [ 57%]
  server/tests/unit/test_auth_rbac.py::test_audit_logs_recorded PASSED     [ 71%]
  server/tests/unit/test_auth_rbac.py::test_change_password_and_login_with_new_password PASSED [ 85%]
  server/tests/unit/test_login_logging_masks_all_credentials PASSED [100%]

  ======================== 7 passed, 1 warning in 8.66s =========================
  ```

- **Đối chiếu 8 tiêu chí nghiệm thu của AG4:**
  1. *(a) 9 tài khoản seed đều đăng nhập được; `/auth/me` trả đúng role và danh sách quyền khác nhau giữa các vai trò:* **ĐẠT** (`test_all_9_seed_accounts_login_and_me`).
  2. *(b) Test tham số hóa theo từng cặp (vai trò, quyền): endpoint thử trả 200 nếu có quyền và 403 nếu không; riêng admin bị chặn mọi quyền nghiệp vụ kho:* **ĐẠT** (`test_parameterized_role_permissions_matrix`).
  3. *(c) Sai mật khẩu (`AUTH_INVALID_CREDENTIALS`), token hỏng (`AUTH_INVALID_TOKEN`), token hết hạn (`AUTH_TOKEN_EXPIRED`) đều trả đúng mã lỗi và HTTP 401:* **ĐẠT** (`test_invalid_credentials_and_token_errors`).
  4. *(d) Phạm vi kho: tạo kho thứ hai WH02 trong test, tài khoản kho này không thấy dữ liệu kho kia (HTTP 404 `NOT_FOUND`):* **ĐẠT** (`test_warehouse_scope_isolation`).
  5. *(e) `audit_logs` có dòng mới sau hành động ghi:* **ĐẠT** (`test_audit_logs_recorded`).
  6. *(f) Đổi mật khẩu rồi đăng nhập bằng mật khẩu mới thành công, mật khẩu cũ bị từ chối:* **ĐẠT** (`test_change_password_and_login_with_new_password`).
  7. *(g) `make ci` xanh toàn bộ:* **ĐẠT** (xem mục 2.3).
  8. *(h) Đăng nhập thành công và thất bại rồi đọc toàn bộ log: mặt nạ log che giấu 100% token, mật khẩu hay header Authorization:* **ĐẠT** (`test_login_logging_masks_all_credentials`).

### 2.3. Kiểm tra toàn bộ quy trình CI (`make.bat ci`)
- **Lệnh thực hiện:**
  ```powershell
  .\make.bat ci
  ```
- **Kết quả thực tế:**
  ```text
  .venv/Scripts/black.exe --check .
  All done! ✨ 🍰 ✨
  48 files would be left unchanged.
  .venv/Scripts/ruff.exe check .
  All checks passed!
  .venv/Scripts/mypy.exe server client scripts
  Success: no issues found in 48 source files
  .venv/Scripts/pytest.exe server/tests
  ======================== 25 passed, 1 warning in 10.04s ========================
  ```

---

## 3. Kết luận nghiệm thu
- **Kết luận:** **ĐẠT**
- **Đánh giá khuyến nghị:** **NÊN MERGE**
- **Pull Request:** [PR #4](https://github.com/binhdoan0201/abest-wms/pull/4) đã sẵn sàng để squash merge vào `develop`.

---

## 4. Việc tôi cần làm tiếp
1. Chờ người giữ kho (User) ra lệnh xác nhận «merge».
2. Thực hiện lệnh `gh pr merge 4 --squash --delete-branch`.
3. Chuyển sang nhánh `develop`, kéo cập nhật mới nhất từ `origin/develop`.
4. Bắt đầu bước tiếp theo: **AG5: Giao diện hàm inventory và tasks (ag5-inventory-tasks)** (có thể làm song song với AG6).
