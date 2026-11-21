# Hợp đồng API Module: Xuất kho (Outbound)

- **Chủ module:** Thành viên C
- **Nhánh phụ trách:** `feature/outbound`
- **Mã module:** M5 (`outbound`)

---

## Danh mục Endpoint

### 1. GET /api/v1/outbound-orders
- **Mục đích:** Xem danh sách đơn xuất kho (`?status=`).
- **Vai trò:** `thukho`, `quanly`, `nv-soan`.
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/outbound-orders/{id}
- **Mục đích:** Xem chi tiết đơn xuất kho và danh sách dòng đơn (`outbound_order_lines`).
- **Vai trò:** `thukho`, `quanly`, `nv-soan`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. POST /api/v1/outbound-orders/{id}/allocate
- **Mục đích:** Cấp phát tồn kho FEFO/FIFO cho đơn, ghi `inventory_allocations`.
- **Vai trò:** `thukho`, `quanly`.
- **Phản hồi 200:** Kết quả cấp phát tồn kho.
- **Lỗi:** NOT_FOUND 404, INVENTORY_INSUFFICIENT_QTY 409, ORDER_FROZEN 409.

### 4. POST /api/v1/pick-sessions
- **Mục đích:** Tạo phiên soạn hàng từ một hoặc nhiều đơn.
- **Vai trò:** `thukho`.
- **Phản hồi 201:** `pick_session_id`, `status = ASSIGNED`.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 5. GET /api/v1/pick-sessions/{id}
- **Mục đích:** Xem chi tiết phiên soạn và các dòng soạn hàng (`pick_lines`).
- **Vai trò:** `nv-soan`, `thukho`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 6. POST /api/v1/pick-sessions/{id}/lines/{line_id}/confirm
- **Mục đích:** Xác nhận soạn thành công một dòng hàng.
- **Vai trò:** `nv-soan`.
- **Phản hồi 200:** Cập nhật dòng sang PICKED.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 7. POST /api/v1/pick-sessions/{id}/lines/{line_id}/exception
- **Mục đích:** Báo cáo ngoại lệ khi soạn hàng (thiếu hàng, hư hỏng, sai lô).
- **Vai trò:** `nv-soan`.
- **Phản hồi 200:** Ghi nhận ngoại lệ.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 8. POST /api/v1/outbound-orders/{id}/packages
- **Mục đích:** Đóng gói: tạo kiện và danh sách dòng kiện (`packages`, `package_lines`).
- **Vai trò:** `nv-dongoi`.
- **Phản hồi 201:** `package_id`, `package_barcode`.
- **Lỗi:** VALIDATION_ERROR 422, NOT_FOUND 404.

### 9. POST /api/v1/goods-issues
- **Mục đích:** Lập phiếu xuất kho GI, gán xe và tài xế vận chuyển.
- **Vai trò:** `nv-dongoi`.
- **Phản hồi 201:** `gi_id`, `gi_number`, `status = PENDING`.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 10. POST /api/v1/goods-issues/{id}/confirm
- **Mục đích:** Xác nhận giao hàng, đơn SHIPPED, trừ tồn khả dụng trong cùng transaction.
- **Vai trò:** `nv-dongoi`.
- **Phản hồi 200:** GI chuyển sang SHIPPED, đơn hàng hoàn tất.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409.

### 11. POST /api/v1/order-changes/{id}/decide
- **Mục đích:** Quản lý chốt yêu cầu đổi/hủy của ERP (gọi `fn_decide_order_change`).
- **Vai trò:** `quanly`.
- **Request body:** `decision` (`ACCEPT` hoặc `REJECT`), `reject_reason_code`, `reject_note`.
- **Phản hồi 200:** Kết quả xử lý yêu cầu thay đổi đơn hàng.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, INVALID_STATE 409.
