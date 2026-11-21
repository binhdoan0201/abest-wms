# Báo cáo thực hiện bước U6a: Thêm thành viên dự án

**Mã bước:** `u6a-members`  
**Vai trò:** Trợ lý DevOps  
**Thời gian thực hiện:** 2026-11-21  

---

## 1. Mục tiêu
Xác nhận username GitHub chính xác của 3 thành viên phát triển B, C, D và thêm vào kho lưu trữ `binhdoan0201/abest-wms` với quyền Write (push) thông qua GitHub REST API.

---

## 2. Đã làm
1. Tiếp nhận danh sách username GitHub chính thức từ Leader:
   - **Thành viên B (Phước):** `HuuPhuoc1235`
   - **Thành viên C (Cường):** `quoccuong1108`
   - **Thành viên D (Hiếu):** `hieunguyen201104`
2. Thực thi lệnh GitHub CLI (`gh api`) thêm từng thành viên vào repo với quyền `push` (Write).
3. Xác minh lời mời và danh sách collaborator qua `gh api /repos/binhdoan0201/abest-wms/collaborators` và `/invitations`.

---

## 3. Lệnh đã chạy và kết quả thật

### Lệnh 1: Thêm thành viên B (`HuuPhuoc1235`)
```bash
gh api --method PUT /repos/binhdoan0201/abest-wms/collaborators/HuuPhuoc1235 -f permission=push
```
- **Kết quả:** HTTP 201 Created (Invitation ID: `345273183`, `permissions: write`).

### Lệnh 2: Thêm thành viên C (`quoccuong1108`)
```bash
gh api --method PUT /repos/binhdoan0201/abest-wms/collaborators/quoccuong1108 -f permission=push
```
- **Kết quả:** HTTP 204 No Content (Thành viên đã xác nhận quyền collaborator trên repo).

### Lệnh 3: Thêm thành viên D (`hieunguyen201104`)
```bash
gh api --method PUT /repos/binhdoan0201/abest-wms/collaborators/hieunguyen201104 -f permission=push
```
- **Kết quả:** HTTP 201 Created (Invitation ID: `345335199`, `permissions: write`).

### Lệnh 4: Kiểm tra danh sách collaborator và lời mời
```bash
gh api /repos/binhdoan0201/abest-wms/collaborators --jq ".[].login"
gh api /repos/binhdoan0201/abest-wms/invitations --jq ".[].invitee.login"
```
- **Kết quả thật:**
  ```text
  binhdoan0201
  quoccuong1108
  HuuPhuoc1235
  hieunguyen201104
  ```

---

## 4. Kết luận
**ĐẠT**

---

## 5. Việc cần làm tiếp
1. Chuyển sang bước **U6b: Khởi tạo và đẩy 10 nhánh tính năng** (`feature/*`) lên remote.
