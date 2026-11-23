# Báo cáo thực hiện bước U6.0: Tài liệu phân công nhóm và quyền sở hữu mã nguồn

**Mã bước:** `u6-team-docs`  
**Nhánh:** `chore/u6-team-docs`  
**Vai trò:** Kỹ sư tài liệu  
**Thời gian thực hiện:** 2026-11-23  

---

## 1. Mục tiêu
Thiết lập toàn bộ tài liệu phân công nhóm, quy chế phối hợp và cấu hình quyền sở hữu mã nguồn (`CODEOWNERS`) trên nhánh `chore/u6-team-docs` tách từ `develop`:
1. Tạo tài liệu phân công chi tiết `docs/PHAN_CONG.md` từ mục 7 và mục 8 của đặc tả dự án, ánh xạ chữ cái A..D sang danh tính thành viên có thật.
2. Cập nhật `README.md` bổ sung bảng phân công và hướng dẫn bắt đầu nhanh cho thành viên (chỉ dùng các lệnh Make có thật).
3. Cập nhật `.github/CODEOWNERS` thay toàn bộ placeholder bằng GitHub username thật.
4. Cập nhật `CONTRIBUTING.md` để đồng bộ tên thành viên, phân bổ nhánh và quy định review.
5. Viết công cụ kiểm tra tự động `scripts/check_assignments.py` để khẳng định đầy đủ 35 mã công việc.
6. Soạn thảo thông điệp khởi động gán tên thật v2 tại `docs/reports/u7-kickoff-message-v2.md` (giữ nguyên file v1, bổ sung hướng dẫn đồng bộ `develop`).
7. Đối chiếu nhánh `feature/*` từ remote với đặc tả và kiểm tra trạng thái bảo vệ của nhánh `develop`.
8. Chạy kiểm tra chất lượng mã nguồn (`make ci`: lint, typecheck, DB test, pytest) đảm bảo 100% xanh.

---

## 2. Đã làm
1. **Tiếp nhận danh sách thành viên từ `_inbox/members.txt`:**
   - **A (Leader):** Đoàn Duy Bình - GitHub: `@binhdoan0201`
   - **B:** Mai Hữu Phước - GitHub: `@HuuPhuoc1235`
   - **C:** Hồ Quốc Cường - GitHub: `@quoccuong1108`
   - **D:** Nguyễn Đức Hiếu - GitHub: `@hieunguyen201104`

2. **Đồng bộ file đặc tả `docs/spec/dac-ta-du-an.md`:**
   - Cập nhật từ `_inbox/Đặc tả dự án ABEST WMS hệ thống quản lý kho.md` (đã được người dùng duyệt tại lượt trước), bảo đảm giữ nguyên chữ cái A, B, C, D gốc và cấu trúc 35 mã công việc sau tái cân bằng. Không sửa bất kỳ file `.sql` nào.

3. **Tạo tài liệu `docs/PHAN_CONG.md`:**
   - Đầu file: Bảng thành viên với chữ cái A..D, họ tên, GitHub username, vai trò.
   - Mục 1: Bảng tóm tắt từ Mục 8.1 của đặc tả, cột Thành viên ghi «Họ tên (A)».
   - Mục 2: Bảng nhánh Git từ Mục 7.1, ghi bằng tên thật của thành viên.
   - Mục 3: Bảng công việc chi tiết từ Mục 8.2 đến 8.5 cho từng thành viên, sao chép đúng nguyên văn mã việc, công việc, nhánh, mức ưu tiên, các ghi chú chuyển việc, bổ sung 2 cột: `Trạng thái` (mặc định «Chưa làm») và `PR`.
   - Mục 4: Mô tả mối quan hệ phụ thuộc dịch vụ giữa các thành viên: B và C gọi `inventory` (A) và `tasks` (D); B gọi `approvals` (D); `dashboard` (A) đọc số liệu tổng hợp từ mọi module.
   - Cuối file: Ghi rõ nguồn trích dẫn từ đặc tả.

4. **Cập nhật `README.md`:**
   - Thêm mục «Nhóm và phân công» ngay sau phần giới thiệu, gồm bảng thành viên, vai trò, module, nhánh phụ trách, tài khoản GitHub và liên kết tới `docs/PHAN_CONG.md`.
   - Thêm mục «Bắt đầu nhanh cho thành viên»: Hướng dẫn clone, cấu hình `.env`, cài đặt, nạp DB, chuyển sang nhánh feature cá nhân, đọc hợp đồng API `docs/api/<module>.md`. Toàn bộ lệnh đều có trong `Makefile` và được xác minh bằng `make -n`.

5. **Cập nhật `.github/CODEOWNERS`:**
   - Thay thế toàn bộ placeholder `@A`, `@B`, `@C`, `@D` bằng `@binhdoan0201`, `@HuuPhuoc1235`, `@quoccuong1108`, `@hieunguyen201104`.
   - Ánh xạ đường dẫn `server/app/modules/<m>/`, `server/tests/*/<m>/`, `client/app/modules/<m>/`, `docs/api/<m>.md` theo đúng module phụ trách.
   - Leader Đoàn Duy Bình (`@binhdoan0201`) sở hữu các thành phần lõi: `server/app/core/`, `server/app/shared/`, `server/app/main.py`, `database/`, `docker-compose.yml`, `.github/`.

6. **Cập nhật `CONTRIBUTING.md`:**
   - Thay `@A` thành `Đoàn Duy Bình (Leader @binhdoan0201)`.
   - Cập nhật bảng phân công nhánh và quy tắc review tương ứng với 4 thành viên.

7. **Xây dựng `scripts/check_assignments.py`:**
   - Script tự động đọc `docs/spec/dac-ta-du-an.md`, lọc các dòng `| <mã việc> |`, khẳng định cả 35 mã việc (A-01 đến A-13, B-03 đến B-10, C-01 đến C-08, D-01 đến D-05, D-08) xuất hiện đúng 1 lần trong `docs/PHAN_CONG.md`.

8. **Soạn thông điệp khởi động v2 (`docs/reports/u7-kickoff-message-v2.md`):**
   - Giữ nguyên `docs/reports/u7-kickoff-message.md`.
   - Soạn thảo bản mới v2 với họ tên thật, cập nhật phân bổ module và bổ sung quy trình chuẩn `git fetch` và `git merge origin/develop`. Không gửi tin nhắn này ra ngoài.

9. **Đối chiếu nhánh Git và kiểm tra cấu hình bảo vệ nhánh `develop`:**
   - Kiểm tra `git branch -r` đối chiếu 10 nhánh tính năng dài hạn.
   - Dùng `gh api` kiểm tra chính sách bảo vệ trên `develop`.

---

## 3. Lệnh và Kết quả Thật

### 3.1. Chạy công cụ kiểm tra phân công `scripts/check_assignments.py`
```text
$ python scripts/check_assignments.py
Đang kiểm tra phân công công việc...
- File đặc tả: D:\abest-wms\docs\spec\dac-ta-du-an.md
- File phân công: D:\abest-wms\docs\PHAN_CONG.md
-> Tìm thấy 35 mã công việc trong dac-ta-du-an.md.
-> Tìm thấy 35 mã công việc trong PHAN_CONG.md.
THÀNH CÔNG: Toàn bộ 35 mã việc xuất hiện đúng 1 lần trong PHAN_CONG.md!
```

### 3.2. Kiểm tra chuỗi định danh / placeholder còn sót (Grep)
- Kiểm tra các file làm việc và cấu hình (`.github/CODEOWNERS`, `docs/PHAN_CONG.md`, `README.md`, `CONTRIBUTING.md`, toàn bộ thư mục `server/`, `client/`, `scripts/`):
  -> **0 chuỗi `@A`, `@B`, `@C`, `@D`, `ten-github`, hay `Họ tên của`** tồn tại trong các file làm việc trên.
- Các file tài liệu lịch sử hoặc nguyên bản được bảo lưu theo chỉ thị:
  - `docs/reports/u7-kickoff-message.md` (giữ nguyên theo yêu cầu tại Việc 5).
  - `docs/reports/ag1-skeleton.md` (báo cáo lịch sử bước AG1).
  - `docs/spec/quy-trinh-dung-khung.md` (tài liệu mẫu hướng dẫn ban đầu).

### 3.3. Kiểm tra liên kết trong `README.md`
Kiểm tra toàn bộ 17 liên kết markdown trong `README.md`:
```text
Total markdown links in README.md: 17
[URL] ![CI Pipeline -> https://github.com/binhdoan0201/abest-wms/actions/workflows/ci.yml/badge.svg
[True] docs/PHAN_CONG.md -> docs/PHAN_CONG.md
[True] docs/api/inbound.md -> docs/api/inbound.md
[True] docs/api/cycle_count.md -> docs/api/cycle_count.md
[True] docs/api/outbound.md -> docs/api/outbound.md
[True] docs/api/tasks.md -> docs/api/tasks.md
[True] docs/api/approvals.md -> docs/api/approvals.md
[True] docs/api/auth.md -> docs/api/auth.md
[True] docs/api/inventory.md -> docs/api/inventory.md
[True] docs/api/master_data.md -> docs/api/master_data.md
[True] docs/api/dashboard.md -> docs/api/dashboard.md
[True] docs/api/integrations.md -> docs/api/integrations.md
[True] .github/workflows/ci.yml -> .github/workflows/ci.yml
[True] docs/spec/dac-ta-du-an.md -> docs/spec/dac-ta-du-an.md
[True] docs/spec/chuan-api-cong-nghe.md -> docs/spec/chuan-api-cong-nghe.md
[True] docs/adr/0001-cong-nghe.md -> docs/adr/0001-cong-nghe.md
[True] CONTRIBUTING.md -> CONTRIBUTING.md
=> 100% liên kết trỏ tới file có thật trên đĩa!
```

### 3.4. Đối chiếu nhánh remote (`git branch -r`) với Mục 7.1 của Đặc tả
Kết quả chạy lệnh `git branch -r`:
- **10 nhánh tính năng theo Mục 7.1:**
  1. `feature/core-auth` -> `origin/feature/core-auth` (ĐÃ CÓ)
  2. `feature/inventory` -> `origin/feature/inventory` (ĐÃ CÓ)
  3. `feature/integrations-mock` -> `origin/feature/integrations-mock` (ĐÃ CÓ)
  4. `feature/master-data` -> `origin/feature/master-data` (ĐÃ CÓ)
  5. `feature/dashboard` -> `origin/feature/dashboard` (ĐÃ CÓ)
  6. `feature/inbound` -> `origin/feature/inbound` (ĐÃ CÓ)
  7. `feature/cycle-count` -> `origin/feature/cycle-count` (ĐÃ CÓ)
  8. `feature/outbound` -> `origin/feature/outbound` (ĐÃ CÓ)
  9. `feature/tasks` -> `origin/feature/tasks` (ĐÃ CÓ)
  10. `feature/approvals` -> `origin/feature/approvals` (ĐÃ CÓ)
- **Nhánh thiếu:** 0 (Không thiếu nhánh nào).
- **Nhánh tính năng thừa:** 0 (Không có nhánh feature nào ngoài danh mục).

### 3.5. Kiểm tra bảo vệ nhánh `develop` (`gh api`)
Lệnh kiểm tra:
```bash
gh api repos/binhdoan0201/abest-wms/branches/develop/protection
```
Kết quả:
- Trạng thái: **ĐANG BẬT** (Protection is enabled).
- `required_status_checks`: strict = `true`, context bắt buộc = `["CI Pipeline (Lint, Typecheck, DB Tests, Pytest)"]`.
- `required_pull_request_reviews`: yêu cầu tối thiểu `1 approving review`.
- **Người cần duyệt PR này:**
  Theo quy định Mục 7.2 của Đặc tả: *"PR của A do B review và duyệt"*. Vì nhánh `chore/u6-team-docs` do Leader A (**Đoàn Duy Bình** - `@binhdoan0201`) khởi tạo mở vào nhánh `develop`, PR này cần thành viên B (**Mai Hữu Phước** - `@HuuPhuoc1235`) duyệt.

### 3.6. Chạy bộ kiểm thử CI cục bộ (`make ci`)
```text
$ .\make.bat ci
.venv/Scripts/black.exe --check .
All done! ✨ 🍰 ✨
153 files would be left unchanged.

.venv/Scripts/ruff.exe check .
All checks passed!

.venv/Scripts/mypy.exe server client scripts
Success: no issues found in 153 source files

"C:/Program Files/Git/bin/bash.exe" scripts/run_db_tests.sh
============================================================
ABEST WMS: Chạy kiểm thử CSDL (run_db_tests.sh)
============================================================
1. Tạo CSDL tạm riêng: abest_wms_test_temp
CREATE DATABASE
2. Nạp schema.sql và patch_v4_2_1.sql vào abest_wms_test_temp
3. Chạy wms_smoke_test_v4_2_1.sql trên CSDL abest_wms_test_temp
[THÀNH CÔNG] Smoke test hoàn thành không có lỗi!
4. Kiểm tra tính lũy kế (idempotency): Chạy lại patch_v4_2_1.sql lần 2
[THÀNH CÔNG] Patch lần 2 an toàn (idempotent)!
5. Chạy test_seed.sql trên CSDL chính (abest_wms)
TẤT CẢ KIỂM THỬ TEST_SEED THÀNH CÔNG!
  - Vai trò: 9/9
  - User active theo vai trò: 1/1 cho 9 vai trò
  - Quyền theo vai trò: 100% các vai trò có ít nhất 1 quyền
  - Kho: 1/1
  - Vị trí: 30 (kỳ vọng >= 30)
  - SKU: 10 (kỳ vọng >= 10)
============================================================
[THÀNH CÔNG] TẤT CẢ BÀI KIỂM THỬ ĐẠT (smoke test, patch lần 2, test_seed)
============================================================

.venv/Scripts/pytest.exe server/tests
============================= test session starts =============================
platform win32 -- Python 3.12.8, pytest-8.3.4, pluggy-1.7.0
rootdir: D:\abest-wms
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

======================= 63 passed, 5 warnings in 19.31s =======================
```

---

## 4. Kết luận
**ĐẠT** - Toàn bộ các hạng mục công việc từ Việc 1 đến Việc 7 đều đã được triển khai hoàn chỉnh, xác thực tự động và vượt qua kiểm thử chất lượng mã nguồn 100%.

---

## 5. Việc cần làm tiếp
1. Xin ý kiến duyệt của Leader Đoàn Duy Bình trước khi thực hiện lệnh `git push` và mở Pull Request qua GitHub CLI (`gh`).
2. Mở Pull Request từ nhánh `chore/u6-team-docs` vào `develop`.
3. Chỉ định Reviewer: Mai Hữu Phước (`@HuuPhuoc1235`).
4. Theo dõi pipeline CI trên GitHub Actions và chờ duyệt trước khi gộp vào `develop`.
