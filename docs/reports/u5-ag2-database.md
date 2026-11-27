# Báo cáo U5: Nghiệm thu bước AG2 (ag2-database)

## 1. Thông tin nghiệm thu
- **Bước nghiệm thu:** AG2 (`ag2-database`)
- **Nhánh:** `chore/ag2-database`
- **Pull Request:** [#2 - feat(ag2-database): CSDL PostgreSQL 16, dữ liệu seeds và kiểm thử CSDL](https://github.com/binhdoan0201/abest-wms/pull/2)
- **Người thực hiện nghiệm thu:** DevOps Assistant (vai trò kiểm tra độc lập, không sửa code)

---

## 2. Kiểm tra tính đầy đủ của báo cáo AG2
- Đã đọc và kiểm tra báo cáo kỹ thuật `docs/reports/ag2-database.md`.
- Báo cáo tuân thủ đầy đủ 7 mục theo mẫu quy chuẩn:
  1. Mục tiêu (Đầy đủ)
  2. Đã làm - danh sách file (Đầy đủ)
  3. Cách chạy lại (Đầy đủ)
  4. Kết quả test thật (Đầy đủ)
  5. Giả định đã đặt (Đầy đủ)
  6. Chưa làm hoặc rủi ro (Đầy đủ)
  7. Đề xuất bước tiếp (Đầy đủ)

---

## 3. Chạy lại kiểm thử đối chiếu (Kết quả thật)

### 3.1. Lệnh nghiệm thu riêng AG2: `scripts/reset_db.sh && scripts/run_db_tests.sh`
- **Lệnh:**
  ```bash
  bash scripts/reset_db.sh && bash scripts/run_db_tests.sh
  ```
- **Kết quả thật:**
  - `reset_db.sh`: DROP & CREATE CSDL `abest_wms`, nạp `schema.sql`, `patch_v4_2_1.sql` và 3 file `seeds/*.sql` thành công.
  - `run_db_tests.sh`:
    - Tạo CSDL tạm `abest_wms_test_temp`.
    - Chạy `wms_smoke_test_v4_2_1.sql`: Đạt toàn bộ test T1–T5, F1–F21, in thông báo `TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test v4.2.1)`.
    - Nạp `patch_v4_2_1.sql` lần 2: Thành công (chứng minh tính idempotent).
    - Chạy `test_seed.sql` trên CSDL chính `abest_wms`:
      ```text
      NOTICE:  ============================================================
      NOTICE:  TẤT CẢ KIỂM THỬ TEST_SEED THÀNH CÔNG!
      NOTICE:   - Vai trò: 9/9
      NOTICE:   - User active theo vai trò: 1/1 cho 9 vai trò
      NOTICE:   - Quyền theo vai trò: 100% các vai trò có ít nhất 1 quyền
      NOTICE:   - Kho: 1/1
      NOTICE:   - Vị trí: 30 (kỳ vọng >= 30)
      NOTICE:   - SKU: 10 (kỳ vọng >= 10)
      NOTICE:  ============================================================
      ```
    - In thông điệp kết luận: `[THÀNH CÔNG] TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test, patch lần 2, test_seed)`.
    - Dọn dẹp CSDL tạm thành công.
- **Trạng thái:** Thoát mã 0 (ĐẠT).

### 3.2. Chạy bộ kiểm tra CI: `make ci`
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

  ============================== 1 passed in 0.08s ==============================
  ```
- **Trạng thái:** Thoát mã 0 (ĐẠT).

---

## 4. Kiểm tra các file CSDL đóng băng (Frozen Database Files)
- **Lệnh:**
  ```powershell
  git diff develop -- database/schema.sql database/patch_v4_2_1.sql database/tests/smoke_test.sql
  ```
- **Kết quả thật:** Đầu ra hoàn toàn rỗng.
- **Trạng thái:** ĐẠT (Tính bất biến của 3 file CSDL đóng băng được tuân thủ nghiêm ngặt 100%).

---

## 5. Đánh giá Giả định & Rủi ro
- **Giả định:** Mật khẩu mặc định `Demo@123456` với hash bcrypt chuẩn được lưu trữ và ghi nhận rõ ràng tại `README.md`. Scripts bash hỗ trợ chạy linh hoạt qua Docker Compose hoặc psql cục bộ.
- **Chưa làm hoặc rủi ro:** Module backend FastAPI sẽ kết nối tới CSDL ở bước AG3. Hiện tại không có rủi ro kỹ thuật nào.

---

## 6. Kết luận

- **Kết luận:** **NÊN MERGE**.
- **Lý do:**
  1. Đáp ứng toàn diện các tiêu chuẩn kỹ thuật của bước AG2 và Mục 5 Đặc tả.
  2. Các bài test CSDL (smoke test, idempotent patch, test_seed) và bộ kiểm tra CI đều pass 100%.
  3. Giữ nguyên vẹn các file CSDL đóng băng.
  4. Báo cáo kỹ thuật trung thực, khớp với kết quả kiểm tra lại thực tế.

> **Ghi chú:** Tuân thủ quy tắc nghiệm thu, hệ thống **KHÔNG tự động merge**. Khi bạn (Leader) xác nhận «merge», lệnh `gh pr merge --squash` sẽ được xin duyệt và thực thi.
