# Hợp đồng API Module: Kiểm kê (Cycle Count)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/cycle-count`
- **Mã module:** M8 (`cycle_count`)

---

## Danh mục Endpoint

### 1. POST /api/v1/cycle-counts
- **Mục đích:** Tạo phiếu kiểm kê định kỳ / đột xuất, tự động khóa vị trí kiểm kê.
- **Vai trò:** `thukho` (TK-1.1).
- **Request body:** `count_type`, `due_at`, `location_ids`.
- **Phản hồi 201/200:** Thông tin phiếu kiểm kê được tạo cùng danh sách dòng kiểm kê.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 2. GET /api/v1/cycle-counts
- **Mục đích:** Xem danh sách phiếu kiểm kê trong kho.
- **Vai trò:** `thukho`, `nv-kiemke` (KK-1).
- **Phản hồi 200:** Danh sách phiếu kiểm kê.
- **Lỗi:** FORBIDDEN 403.

### 3. GET /api/v1/cycle-counts/{id}
- **Mục đích:** Xem chi tiết phiếu kiểm kê. Trường hợp đếm mù (blind count) thì ẩn tồn kho hệ thống đối với nhân viên kiểm kê.
- **Vai trò:** `thukho`, `nv-kiemke` (KK-1).
- **Phản hồi 200:** Chi tiết phiếu và các dòng kiểm kê.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 4. POST /api/v1/cycle-counts/{id}/lines/{line_id}/count
- **Mục đích:** Ghi nhận số lượng đếm mù lần 1 cho dòng kiểm kê.
- **Vai trò:** `nv-kiemke` (KK-1).
- **Request body:** `blind_counted_qty`, `same_counter_override_reason`.
- **Phản hồi 200:** Ghi nhận lượt đếm thành công.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 5. POST /api/v1/cycle-counts/{id}/lines/{line_id}/recount
- **Mục đích:** Đếm lại dòng kiểm kê có phát hiện chênh lệch (bắt buộc khác người đếm lần trước, trừ khi có lý do ghi đè).
- **Vai trò:** `nv-kiemke` (KK-1).
- **Request body:** `blind_counted_qty`, `same_counter_override_reason`.
- **Phản hồi 200:** Ghi nhận lượt đếm lại thành công.
- **Lỗi:** NOT_FOUND 404, SAME_COUNTER_FORBIDDEN 400.

### 6. POST /api/v1/cycle-counts/{id}/close
- **Mục đích:** Đóng phiếu kiểm kê, tổng hợp kết quả chênh lệch và mở khóa các vị trí kiểm kê.
- **Vai trò:** `thukho` (TK-1.1).
- **Phản hồi 200:** Trạng thái phiếu kiểm kê chuyển sang CLOSED.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.
