# Hợp đồng API Phân hệ Xuất kho (Outbound)

## 1. Danh sách Endpoint

### GET /api/v1/outbound-orders
- Mục đích: Xem danh sách đơn xuất kho theo kho hiện tại (`?status=&page=1&page_size=20`)
- Vai trò: `thukho`, `quanly` (quyền `QL-2.1`)
- Phản hồi 200: Danh sách đơn xuất kèm `meta` phân trang

### GET /api/v1/outbound-orders/{order_id}
- Mục đích: Xem chi tiết đơn xuất kho, các dòng hàng, phân bổ tồn và kiện hàng
- Vai trò: `thukho`, `quanly` (quyền `QL-2.1`)
- Phản hồi 200: Chi tiết đơn xuất kho
- Lỗi: `NOT_FOUND` 404

### POST /api/v1/outbound-orders/{order_id}/allocate
- Mục đích: Cấp phát tồn kho theo FEFO/FIFO, ghi `inventory_allocations` và giữ tồn `ALLOCATED`
- Vai trò: `thukho`, `quanly` (quyền `QL-2.1`)
- Phản hồi 200: Kết quả cấp phát tồn kho cho đơn
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_INSUFFICIENT_ALLOCATABLE_STOCK` 409

### POST /api/v1/pick-sessions
- Mục đích: Tạo phiên soạn hàng từ một hoặc nhiều đơn xuất đã cấp phát
- Vai trò: `thukho` (quyền `SO-1`)
- Phản hồi 201: Phiên soạn hàng mới kèm danh sách dòng soạn `pick_lines`
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `ORDER_FROZEN` 409

### GET /api/v1/pick-sessions/{pick_session_id}
- Mục đích: Xem chi tiết phiên soạn hàng và các dòng soạn
- Vai trò: `nv-soan`, `thukho`, `quanly` (quyền `SO-1`)
- Phản hồi 200: Chi tiết phiên soạn và danh sách `pick_lines`
- Lỗi: `NOT_FOUND` 404

### POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm
- Mục đích: Xác nhận soạn một dòng hàng, chuyển tồn `ALLOCATED` sang khu tập kết `STAGING`
- Vai trò: `nv-soan` (quyền `SO-1`)
- Phản hồi 200: Dòng soạn đã cập nhật và trạng thái phiên/đơn
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409

### POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception
- Mục đích: Báo cáo ngoại lệ khi lấy hàng (thiếu, hư hỏng, sai lô)
- Vai trò: `nv-soan` (quyền `SO-1`)
- Phản hồi 200: Dòng soạn đã ghi nhận ngoại lệ và đưa phiên sang `ON_HOLD_SHORTAGE`
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `OUTBOUND_INVALID_REASON_CODE` 400

### POST /api/v1/outbound-orders/{order_id}/packages
- Mục đích: Đóng gói tạo kiện hàng và ghi nhận các dòng hàng trong kiện
- Vai trò: `nv-dongoi` (quyền `DG-1`)
- Phản hồi 201: Thông tin kiện hàng vừa tạo
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_EXCEED_PICKED_QTY` 409

### POST /api/v1/goods-issues
- Mục đích: Lập phiếu xuất kho (GI), gắn các kiện hàng của đơn và phương tiện vận chuyển
- Vai trò: `nv-dongoi` (quyền `DG-1`)
- Phản hồi 201: Phiếu xuất kho GI vừa khởi tạo
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_NO_PACKAGES` 409

### POST /api/v1/goods-issues/{gi_id}/confirm
- Mục đích: Xác nhận bàn giao vận chuyển, trừ tồn kho `ALLOCATED` và chuyển đơn sang `SHIPPED`
- Vai trò: `nv-dongoi` (quyền `DG-1`)
- Phản hồi 200: Phiếu xuất kho đã xác nhận `GI_CONFIRMED`
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_DRIVER_SIGNATURE_REQUIRED` 409

### POST /api/v1/order-changes/{request_id}/decide
- Mục đích: Quản lý chốt yêu cầu đổi/hủy đơn từ ERP (`ACCEPT` hoặc `REJECT`)
- Vai trò: `quanly` (quyền `QL-5.3`)
- Phản hồi 200: Kết quả xử lý yêu cầu đổi/hủy đơn
- Lỗi: `NOT_FOUND` 404, `FORBIDDEN` 403, `INVALID_STATE` 409, `OUTBOUND_REJECT_NOTE_REQUIRED` 400