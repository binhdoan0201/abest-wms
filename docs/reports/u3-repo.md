# Báo cáo U3: Khởi tạo và thiết lập kho lưu trữ GitHub

## 1. Mục tiêu
- Khởi tạo Git repository trên máy cục bộ với nhánh mặc định `main`.
- Tạo file `.gitignore` tối thiểu chứa các mục: `_inbox/`, `.env`, `__pycache__/`, `.venv/`.
- Tạo commit đầu tiên chỉ bao gồm `.gitignore`.
- Tạo repository private trên GitHub với tên `abest-wms` từ thư mục hiện tại và đẩy nhánh `main` lên remote `origin`.
- Tạo nhánh `develop` từ nhánh `main` và đẩy lên GitHub.
- Xác nhận trạng thái repo bằng `gh repo view` và `git branch -a`.

## 2. Đã làm
- Khởi tạo Git repo nhánh `main` bằng `git init -b main`.
- Tạo file `.gitignore` với các dòng chỉ định.
- Stage duy nhất `.gitignore` và commit với thông điệp: `chore: initial commit with .gitignore`.
- Xin phê duyệt từ người dùng theo Quy tắc 1 trước khi chạy các lệnh tương tác với GitHub.
- Sau khi được người dùng duyệt, chạy lệnh `gh repo create abest-wms --private --source=. --remote=origin --push` thành công.
- Tạo nhánh `develop` và push lên remote `origin` với tracking `origin/develop`.
- Chạy `gh repo view` và `git branch -a` để xác nhận kết quả.

## 3. Lệnh đã chạy và kết quả thật

### 3.1. Khởi tạo Git repo
- **Lệnh:**
  ```powershell
  git init -b main
  ```
- **Kết quả thật:**
  ```text
  Initialized empty Git repository in D:/abest-wms/.git/
  ```

### 3.2. Tạo file `.gitignore` và commit đầu tiên
- **Lệnh:**
  ```powershell
  git add .gitignore
  git commit -m "chore: initial commit with .gitignore"
  git log -n 1 --stat
  ```
- **Kết quả thật:**
  ```text
  [main (root-commit) 5afe04b] chore: initial commit with .gitignore
   1 file changed, 4 insertions(+)
   create mode 100644 .gitignore

  commit 5afe04b199cc0355e72f12f4d72b38e84c677ebb
  Author: binhdoan0201 <nhutan321@gmail.com>
  Date:   Tue Nov 17 18:36:10 2026 +0700

      chore: initial commit with .gitignore

   .gitignore | 4 ++++
   1 file changed, 4 insertions(+)
  ```

### 3.3. Tạo repository GitHub và đẩy nhánh `main`
- **Lệnh:**
  ```powershell
  gh repo create abest-wms --private --source=. --remote=origin --push
  ```
- **Kết quả thật:**
  ```text
  https://github.com/binhdoan0201/abest-wms
  branch 'main' set up to track 'origin/main'.
  To https://github.com/binhdoan0201/abest-wms.git
   * [new branch]      HEAD -> main
  ```

### 3.4. Tạo nhánh `develop` và đẩy lên GitHub
- **Lệnh:**
  ```powershell
  git checkout -b develop
  git push -u origin develop
  ```
- **Kết quả thật:**
  ```text
  Switched to a new branch 'develop'
  branch 'develop' set up to track 'origin/develop'.
  To https://github.com/binhdoan0201/abest-wms.git
   * [new branch]      develop -> develop
  ```

### 3.5. Xác nhận trạng thái repo và danh sách nhánh
- **Lệnh:**
  ```powershell
  gh repo view
  git branch -a
  ```
- **Kết quả thật:**
  ```text
  name:	binhdoan0201/abest-wms
  description:	
  * develop
    main
    remotes/origin/develop
    remotes/origin/main
  ```

---

## 4. Kết luận
- **Kết luận:** **ĐẠT**.
- Repository `binhdoan0201/abest-wms` ở chế độ `private` đã được tạo thành công trên GitHub.
- Cả hai nhánh `main` và `develop` đã được khởi tạo và đẩy lên GitHub đồng bộ.

---

## 5. Việc tôi cần làm tiếp
- Chuyển sang thực hiện **U4. Gom file nguồn**:
  - Thực hiện trên nhánh `develop`.
  - Di chuyển/sao chép các file từ `_inbox/` vào các thư mục cấu trúc của repo (`database/`, `docs/source/`, `docs/spec/`).
  - Đưa `docs/adr/0001-cong-nghe.md` và các báo cáo `docs/reports/` (từ u1 đến u3) vào cùng commit.
  - Kiểm tra tính toàn vẹn SHA-256 của các file SQL.
  - Xin phê duyệt của người dùng trước khi push nhánh `develop` lên GitHub theo Quy tắc 1.
