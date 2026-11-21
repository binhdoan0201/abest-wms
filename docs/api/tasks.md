# Hợp đồng API Module: Quản lý Nhiệm vụ Kho (Tasks)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/tasks`
- **Mã module:** M6 (`tasks`)

---

## Danh mục Endpoint

### 1. GET /api/v1/tasks
- **Mục đích:** Danh sách nhiệm vụ kho (`?scope=mine` cho nhân viên thực thi, `?scope=queue` hoặc `?scope=all` cho quản lý).
- **Vai trò:** Nhân viên thực thi xem task của mình (`nv-*`); `thukho`, `quanly` xem toàn bộ.
- **Phản hồi 200:** Danh sách nhiệm vụ kho.
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/tasks/{id}
- **Mục đích:** Xem chi tiết một nhiệm vụ kho.
- **Vai trò:** Người được giao hoặc cấp quản lý.
- **Phản hồi 200:** Chi tiết nhiệm vụ (`task_id`, `task_type`, `priority`, `status`, `assigned_to`...).
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. POST /api/v1/tasks
- **Mục đích:** Tạo nhiệm vụ thủ công khi phát sinh nhu cầu đột xuất ngoài hệ thống.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `task_type`, `priority`, `source_location_id`, `dest_location_id`, `assigned_to`, `payload`.
- **Phản hồi 201:** Nhiệm vụ mới được khởi tạo.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 4. POST /api/v1/tasks/{id}/assign
- **Mục đích:** Giao hoặc phân công nhiệm vụ cho nhân viên thực thi.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `assigned_to_user_id`.
- **Phản hồi 200:** Cập nhật người phụ trách nhiệm vụ.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 5. POST /api/v1/tasks/{id}/accept
- **Mục đích:** Nhân viên xác nhận tiếp nhận nhiệm vụ.
- **Vai trò:** Nhân viên được phân công.
- **Phản hồi 200:** Chuyển trạng thái task sang IN_PROGRESS.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409, FORBIDDEN 403.

### 6. POST /api/v1/tasks/{id}/reject
- **Mục đích:** Nhân viên từ chối tiếp nhận nhiệm vụ kèm mã lý do.
- **Vai trò:** Nhân viên được phân công.
- **Request body:** `reason_code`, `note`.
- **Phản hồi 200:** Trả task về hàng chờ phân công.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 7. POST /api/v1/tasks/{id}/complete
- **Mục đích:** Hoàn tất nhiệm vụ kho.
- **Vai trò:** Nhân viên được phân công.
- **Phản hồi 200:** Chuyển trạng thái task sang COMPLETED.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 8. POST /api/v1/tasks/{id}/reassign
- **Mục đích:** Điều chuyển nhiệm vụ sang nhân viên khác.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `new_assigned_to_user_id`, `reason`.
- **Phản hồi 200:** Task được điều chuyển.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 9. POST /api/v1/tasks/{id}/cancel
- **Mục đích:** Hủy nhiệm vụ kho.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `cancel_reason`.
- **Phản hồi 200:** Task chuyển sang trạng thái CANCELLED.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.
