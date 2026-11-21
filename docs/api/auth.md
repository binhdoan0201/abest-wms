# Hợp đồng API Module: Xác thực & Phân quyền (Auth)

- **Chủ module:** Thành viên A
- **Nhánh phụ trách:** `feature/core-auth`
- **Mã module:** M0 (`core` + `auth`)

---

## Danh mục Endpoint

### 1. POST /api/v1/auth/login
- **Mục đích:** Xác thực danh tính người dùng bằng tên tài khoản và mật khẩu, trả về JWT access token.
- **Vai trò:** Công khai (không yêu cầu token).
- **Request body:** `username` (chuỗi), `password` (chuỗi).
- **Phản hồi 200:** `access_token`, `token_type`, `user` (thông tin người dùng và vai trò).
- **Lỗi:** AUTH_INVALID_CREDENTIALS 401, ACCOUNT_LOCKED 403, VALIDATION_ERROR 422.

### 2. GET /api/v1/auth/me
- **Mục đích:** Lấy thông tin tài khoản đang đăng nhập, thông tin vai trò, kho công tác và danh sách mã quyền.
- **Vai trò:** Mọi vai trò đã đăng nhập hợp lệ.
- **Phản hồi 200:** `user_id`, `username`, `full_name`, `role_code`, `warehouse_id`, `permissions`.
- **Lỗi:** AUTH_REQUIRED 401, AUTH_INVALID_TOKEN 401.

### 3. POST /api/v1/auth/change-password
- **Mục đích:** Đổi mật khẩu cá nhân (bắt buộc khi đăng nhập lần đầu nếu cờ `must_change_password` bật).
- **Vai trò:** Mọi vai trò đã đăng nhập.
- **Request body:** `old_password` (chuỗi), `new_password` (chuỗi).
- **Phản hồi 200:** Cập nhật mật khẩu thành công.
- **Lỗi:** AUTH_INVALID_CREDENTIALS 401, VALIDATION_ERROR 422.
