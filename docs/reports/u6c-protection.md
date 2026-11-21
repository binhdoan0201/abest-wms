# Báo cáo thực hiện bước U6c: Cấu hình bảo vệ nhánh (Branch Protection)

**Mã bước:** `u6c-protection`  
**Vai trò:** Trợ lý DevOps  
**Thời gian thực hiện:** 2026-11-21  

---

## 1. Mục tiêu
Kiểm tra khả năng hiển thị của repo (Public/Private), cấu hình quy tắc bảo vệ nhánh cho cả `main` và `develop`: bắt buộc tạo Pull Request, bắt buộc ít nhất 1 người duyệt (review), bắt buộc kiểm tra trạng thái CI xanh (`CI Pipeline (Lint, Typecheck, DB Tests, Pytest)`), chặn push trực tiếp và cấm force push.

---

## 2. Đã làm
1. Kiểm tra trạng thái kho lưu trữ: `gh repo view --json isPrivate,visibility` -> Kho lưu trữ ở trạng thái `PUBLIC` (hỗ trợ đầy đủ tính năng Branch Protection miễn phí).
2. Xây dựng payload cấu hình bảo vệ nhánh chuẩn:
   - `required_status_checks.strict: true` (nhánh phải cập nhật với base trước khi merge).
   - `required_status_checks.contexts: ["CI Pipeline (Lint, Typecheck, DB Tests, Pytest)"]` (CI phải xanh).
   - `required_pull_request_reviews.required_approving_review_count: 1` (ít nhất 1 người duyệt).
   - `allow_force_pushes: false`, `allow_deletions: false`.
3. Áp dụng quy tắc bảo vệ cho nhánh `main` qua GitHub API.
4. Áp dụng quy tắc bảo vệ cho nhánh `develop` qua GitHub API.
5. Xác minh kết quả trả về từ GitHub REST API.

---

## 3. Lệnh đã chạy và kết quả thật

### Lệnh 1: Kiểm tra tính khả kiến của repo
```bash
gh repo view --json isPrivate,visibility
```
- **Kết quả:** `{"isPrivate": false, "visibility": "PUBLIC"}`

### Lệnh 2: Cấu hình bảo vệ nhánh `main`
```bash
gh api --method PUT /repos/binhdoan0201/abest-wms/branches/main/protection --input payload.json
```
- **Kết quả:** HTTP 200 OK
  - Contexts: `["CI Pipeline (Lint, Typecheck, DB Tests, Pytest)"]`
  - Required review count: `1`
  - Strict: `true`

### Lệnh 3: Cấu hình bảo vệ nhánh `develop`
```bash
gh api --method PUT /repos/binhdoan0201/abest-wms/branches/develop/protection --input payload.json
```
- **Kết quả:** HTTP 200 OK
  - Contexts: `["CI Pipeline (Lint, Typecheck, DB Tests, Pytest)"]`
  - Required review count: `1`
  - Strict: `true`

---

## 4. Kết luận
**ĐẠT**

---

## 5. Việc cần làm tiếp
1. Chuyển sang bước **U6d: Kiểm tra CI và gắn tag release `v0.0-skeleton`**.
