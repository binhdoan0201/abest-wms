# Hợp đồng API Module: Quản lý Nhiệm vụ Kho (Tasks)

- **Chủ module:** Thành viên D (Nguyễn Đức Hiếu)
- **Nhánh phụ trách:** `feature/tasks`
- **Mã module:** M6 (`tasks`)

---

## Quy ước chung

- Mọi thao tác ghi trên một nhiệm vụ đã tồn tại (`assign`, `accept`, `reject`, `complete`, `reassign`, `cancel`) bắt buộc gửi `version_no` hiện tại của nhiệm vụ (khóa lạc quan, TK-1.1). Sai phiên bản trả `VERSION_CONFLICT` (409) kèm `details.current_version_no`.
- Khi giao hoặc điều chuyển, người nhận việc phải **đúng khâu làm việc** (`users.primary_stage` trùng `tasks.stage`) và **chưa đạt giới hạn task mở** (`warehouse_configs.max_open_tasks_per_user`, mặc định 3; task mở gồm `ASSIGNED` và `IN_PROGRESS`).
- Mọi thao tác ghi đều ghi `audit_logs` (`TASK_CREATE`, `TASK_ASSIGN`, `TASK_ACCEPT`, `TASK_REJECT`, `TASK_COMPLETE`, `TASK_REASSIGN`, `TASK_CANCEL`).

### Mã lỗi riêng của module

| Mã | HTTP | Khi nào |
| --- | --- | --- |
| `VERSION_CONFLICT` | 409 | `version_no` gửi lên khác phiên bản hiện tại của nhiệm vụ |
| `INVALID_STATE` | 409 | Trạng thái nhiệm vụ không cho phép thao tác (hoặc điều chuyển cho chính người đang giữ) |
| `TASKS_MAX_OPEN_EXCEEDED` | 409 | Người nhận việc đã đạt giới hạn số task mở theo cấu hình kho |
| `TASKS_STAGE_MISMATCH` | 409 | Người nhận việc không thuộc khâu làm việc của nhiệm vụ |

---

## Danh mục Endpoint

### 1. GET /api/v1/tasks
- **Mục đích:** Danh sách nhiệm vụ kho (`?scope=mine` cho nhân viên thực thi, `?scope=queue` hoặc `?scope=all` cho quản lý; lọc thêm `?status=`).
- **Vai trò:** Nhân viên thực thi xem task của mình (`nv-*`); `thukho`, `quanly` xem toàn bộ.
- **Phản hồi 200:** Danh sách nhiệm vụ kho.
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/tasks/{id}
- **Mục đích:** Xem chi tiết một nhiệm vụ kho.
- **Vai trò:** Người được giao hoặc cấp quản lý.
- **Phản hồi 200:** Chi tiết nhiệm vụ (`task_id`, `task_type`, `stage`, `priority`, `status`, `assigned_to`, `version_no`...).
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. POST /api/v1/tasks
- **Mục đích:** Tạo nhiệm vụ thủ công khi phát sinh nhu cầu đột xuất ngoài hệ thống.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `task_type`, `stage`, `ref_doc_type`, `ref_doc_id`, `zone_id` (tùy chọn), `priority` (mặc định `NORMAL`).
- **Phản hồi 200:** Nhiệm vụ mới ở trạng thái `UNASSIGNED`, `version_no = 1`.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 4. POST /api/v1/tasks/{id}/assign
- **Mục đích:** Giao nhiệm vụ cho nhân viên thực thi (chỉ khi `UNASSIGNED` hoặc `REJECTED`).
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `assigned_to_user_id`, `version_no`.
- **Phản hồi 200:** Nhiệm vụ chuyển sang `ASSIGNED`, `version_no` tăng 1.
- **Lỗi:** NOT_FOUND 404 (không có nhiệm vụ hoặc nhân viên), FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409, TASKS_STAGE_MISMATCH 409, TASKS_MAX_OPEN_EXCEEDED 409.

### 5. POST /api/v1/tasks/{id}/accept
- **Mục đích:** Nhân viên xác nhận tiếp nhận nhiệm vụ.
- **Vai trò:** Nhân viên được phân công.
- **Request body:** `version_no`.
- **Phản hồi 200:** Chuyển trạng thái task sang `IN_PROGRESS`, ghi `started_at`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409.

### 6. POST /api/v1/tasks/{id}/reject
- **Mục đích:** Nhân viên từ chối tiếp nhận nhiệm vụ kèm lý do.
- **Vai trò:** Nhân viên được phân công.
- **Request body:** `rejection_reason`, `version_no`.
- **Phản hồi 200:** Task chuyển sang `REJECTED` (trở lại hàng chờ phân công).
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409.

### 7. POST /api/v1/tasks/{id}/complete
- **Mục đích:** Hoàn tất nhiệm vụ kho.
- **Vai trò:** Nhân viên được phân công.
- **Request body:** `completed_qty` (tùy chọn), `version_no`.
- **Phản hồi 200:** Chuyển trạng thái task sang `COMPLETED`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409.

### 8. POST /api/v1/tasks/{id}/reassign
- **Mục đích:** Điều chuyển nhiệm vụ sang nhân viên khác (mọi trạng thái trừ `COMPLETED`, `CANCELLED`). Nhiệm vụ về `ASSIGNED`, xóa `started_at`; lý do được lưu trong `audit_logs`.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `new_assigned_to_user_id`, `reason` (tùy chọn), `version_no`.
- **Phản hồi 200:** Task được điều chuyển, `version_no` tăng 1.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409 (kể cả điều chuyển cho chính người đang giữ), TASKS_STAGE_MISMATCH 409, TASKS_MAX_OPEN_EXCEEDED 409.

### 9. POST /api/v1/tasks/{id}/cancel
- **Mục đích:** Hủy nhiệm vụ kho chưa hoàn tất. Lý do hủy chỉ lưu trong `audit_logs`, không ghi vào `rejection_reason`.
- **Vai trò:** `thukho`, `quanly` (TK-3.1).
- **Request body:** `cancel_reason` (tùy chọn), `version_no`.
- **Phản hồi 200:** Task chuyển sang trạng thái `CANCELLED`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409, INVALID_STATE 409.
