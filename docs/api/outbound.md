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
- Mục đích: Cấp phát tồn kho theo FEFO/FIFO, ghi `inventory_allocations` và giữ tồn `ALLOCATED`; loại bỏ các lô đã hết hạn (`expiry_date < CURRENT_DATE`) hoặc có hạn dùng nhỏ hơn ngày giao (`expiry_date < cutoff_time.date()`) khi có `cutoff_time`
- Vai trò: `thukho` (quyền `SO-1`, mức `G`; `quanly` chỉ có mức `V` nên bị từ chối 403)
- Phản hồi 200: Kết quả cấp phát tồn kho cho đơn
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_INSUFFICIENT_ALLOCATABLE_STOCK` 409

### POST /api/v1/pick-sessions
- Mục đích: Tạo phiên soạn hàng từ một hoặc nhiều đơn xuất đã cấp phát
- Vai trò: `thukho` (quyền `SO-1`, mức `G`)
- Phản hồi 201: Phiên soạn hàng mới kèm danh sách dòng soạn `lines`
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_INVALID_PICKER` 422

### GET /api/v1/pick-sessions/{pick_session_id}
- Mục đích: Xem chi tiết phiên soạn hàng và các dòng soạn
- Vai trò: `nv-soan`, `thukho`, `quanly` (quyền `SO-1`)
- Phản hồi 200: Chi tiết phiên soạn và danh sách `lines`
- Lỗi: `NOT_FOUND` 404

### POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm
- Mục đích: Xác nhận soạn một dòng hàng, chuyển tồn `ALLOCATED` sang khu tập kết `STAGING`
- Vai trò: `nv-soan` (quyền `SO-1`, mức `X_OWN`)
- Phản hồi 200: Dòng soạn đã cập nhật và trạng thái phiên/đơn
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_PICK_QTY_EXCEEDED` 409, `OUTBOUND_PARTIAL_PICK_REQUIRES_EXCEPTION` 409, `OUTBOUND_INVALID_ACTUAL_LOT` 409

### POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception
- Mục đích: Báo cáo ngoại lệ khi lấy hàng (thiếu, hư hỏng, sai lô), **giải phóng và trả lại toàn bộ số lượng cần soạn (`qty_to_pick`)** về tồn khả dụng (`AVAILABLE`), chuyển phân bổ sang `RELEASED` và đưa đơn sang `ON_HOLD` (không giữ lại phần lẻ)
- Vai trò: `nv-soan` (quyền `SO-1`, mức `X_OWN`)
- Phản hồi 200: Dòng soạn đã ghi nhận ngoại lệ và đưa phiên sang `ON_HOLD_SHORTAGE`
- Lỗi: `NOT_FOUND` 404, `INVALID_STATE` 409, `OUTBOUND_INVALID_REASON_CODE` 422

### POST /api/v1/outbound-orders/{order_id}/packages
- Mục đích: Đóng gói tạo kiện hàng và ghi nhận các dòng hàng trong kiện
- Vai trò: `nv-dongoi` (quyền `DG-1`, mức `X`)
- Phản hồi 201: Thông tin kiện hàng vừa tạo
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_EXCEED_PICKED_QTY` 409

### POST /api/v1/goods-issues
- Mục đích: Lập phiếu xuất kho (GI), gắn các kiện hàng của đơn, phương tiện vận chuyển và gọi TMS xin vận đơn (`request_waybill`; nếu TMS lỗi trả `None` thì chuyển đơn sang `WAITING_WAYBILL`)
- Vai trò: `nv-dongoi` (quyền `DG-1`, mức `X`)
- Phản hồi 201: Phiếu xuất kho GI vừa khởi tạo
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_NO_PACKAGES` 409

### POST /api/v1/goods-issues/{gi_id}/confirm
- Mục đích: Xác nhận bàn giao vận chuyển, trừ tồn kho `ALLOCATED`, chuyển đơn sang `SHIPPED` và xếp phiếu xuất `GI` vào hàng đợi gửi ERP (`enqueue_to_erp`)
- Vai trò: `nv-dongoi` (quyền `DG-1`, mức `X`)
- Phản hồi 200: Phiếu xuất kho đã xác nhận `GI_CONFIRMED`
- Lỗi: `NOT_FOUND` 404, `VERSION_CONFLICT` 409, `INVALID_STATE` 409, `ORDER_FROZEN` 409, `OUTBOUND_DRIVER_SIGNATURE_REQUIRED` 409

### POST /api/v1/order-changes/{request_id}/decide
- Mục đích: Quản lý chốt yêu cầu đổi/hủy đơn từ ERP (`ACCEPT` hoặc `REJECT`)
- Vai trò: `quanly` (quyền `QL-5.3`, mức `X`)
- Phản hồi 200: Kết quả xử lý yêu cầu đổi/hủy đơn
- Lỗi: `NOT_FOUND` 404, `FORBIDDEN` 403, `INVALID_STATE` 409, `OUTBOUND_REJECT_NOTE_REQUIRED` 422

## 2. Ví dụ Payload Request

- **Allocate (`POST /api/v1/outbound-orders/{order_id}/allocate`):** `{"strategy": "FEFO", "version_no": 1}`
- **Pick Session (`POST /api/v1/pick-sessions`):** `{"order_ids": ["2c8d1f30-7a9b-4e11-9c2d-111111111111"], "pick_mode": "SINGLE_ORDER", "picker_user_id": "7b3c6e85-0000-0000-0000-000000000002"}`
- **Confirm Pick Line (`POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm`):** `{"qty_picked": "10.000", "target_tote_barcode": "TOTE-001", "version_no": 1}`
- **Pick Exception (`POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception`):** `{"exception_type": "EXCEPTION_SHORT", "exception_reason": "DISCREPANCY_SHORT", "qty_actual": "2.000", "version_no": 1}`
- **Package (`POST /api/v1/outbound-orders/{order_id}/packages`):** `{"weight_kg": "3.500", "length_cm": "40.00", "width_cm": "30.00", "height_cm": "25.00", "items": [{"order_line_id": "3d9e2a41-0000-0000-0000-000000000001", "sku_id": "4e0f3b52-0000-0000-0000-000000000001", "qty": "10.000"}], "version_no": 3}`
- **Create GI (`POST /api/v1/goods-issues`):** `{"order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "vehicle_id": "9f1a2b3c-0000-0000-0000-000000000009", "tms_waybill_code": "WB-2026-0001", "version_no": 4}`
- **Confirm GI (`POST /api/v1/goods-issues/{gi_id}/confirm`):** `{"driver_signature_data": "data:image/png;base64,SIGN_OK", "handover_photo_urls": ["https://cdn.example.com/gi/01.jpg"], "version_no": 1}`
- **Decide Change (`POST /api/v1/order-changes/{request_id}/decide`):** `{"decision": "REJECT", "reject_note": "Đơn hàng đã hoàn tất đóng gói"}`

## 3. Ví dụ Phản hồi (Response)

- **GET /api/v1/outbound-orders (200):**
```json
{"data": [{"order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "erp_order_number": "SO-2026-0001", "order_type": "SO", "status": "NEW", "version_no": 1}], "meta": {"page": 1, "page_size": 20, "total": 1, "request_id": "8a1b2c3d-0000-0000-0000-000000000001"}}
```
- **GET /api/v1/outbound-orders/{order_id} (200):**
```json
{"data": {"order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "erp_order_number": "SO-2026-0001", "status": "NEW", "version_no": 2, "lines": [{"order_line_id": "3d9e2a41-0000-0000-0000-000000000001", "sku_id": "4e0f3b52-0000-0000-0000-000000000001", "qty_ordered": "10.000", "qty_allocated": "10.000", "qty_picked": "0.000", "qty_packed": "0.000"}], "allocations": [{"allocation_id": "5f1a4c63-0000-0000-0000-000000000001", "qty_allocated": "10.000", "status": "ACTIVE"}], "packages": []}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000002"}}
```
- **POST /api/v1/outbound-orders/{order_id}/allocate (200):**
```json
{"data": {"order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "status": "NEW", "has_shortage": false, "version_no": 2, "allocations": [{"allocation_id": "5f1a4c63-0000-0000-0000-000000000001", "qty_allocated": "10.000"}]}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000003"}}
```
- **POST /api/v1/pick-sessions (201):**
```json
{"data": {"pick_session_id": "8c4d7f96-0000-0000-0000-000000000001", "pick_mode": "SINGLE_ORDER", "status": "OPEN", "version_no": 1, "lines": [{"pick_line_id": "9d5e8a07-0000-0000-0000-000000000001", "qty_to_pick": "10.000", "status": "PENDING"}]}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000004"}}
```
- **GET /api/v1/pick-sessions/{pick_session_id} (200):**
```json
{"data": {"pick_session_id": "8c4d7f96-0000-0000-0000-000000000001", "pick_mode": "SINGLE_ORDER", "status": "IN_PROGRESS", "version_no": 2, "lines": [{"pick_line_id": "9d5e8a07-0000-0000-0000-000000000001", "qty_to_pick": "10.000", "qty_picked": "10.000", "status": "PICKED"}]}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000005"}}
```
- **POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/confirm (200):**
```json
{"data": {"pick_line_id": "9d5e8a07-0000-0000-0000-000000000001", "pick_session_id": "8c4d7f96-0000-0000-0000-000000000001", "status": "PICKED", "qty_picked": "10.000", "session_status": "COMPLETED", "session_version_no": 2}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000006"}}
```
- **POST /api/v1/pick-sessions/{pick_session_id}/lines/{pick_line_id}/exception (200):**
```json
{"data": {"pick_line_id": "9d5e8a07-0000-0000-0000-000000000001", "pick_session_id": "8c4d7f96-0000-0000-0000-000000000001", "status": "EXCEPTION_SHORT", "exception_reason": "DISCREPANCY_SHORT", "qty_actual": "2.000", "session_status": "ON_HOLD_SHORTAGE"}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000007"}}
```
- **POST /api/v1/outbound-orders/{order_id}/packages (201):**
```json
{"data": {"package_id": "2b3c4d5e-0000-0000-0000-000000000001", "package_barcode": "PKG-A1B2C3D4E5", "order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "weight_kg": "3.500", "order_status": "READY_TO_SHIP", "lines": []}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000008"}}
```
- **POST /api/v1/goods-issues (201):**
```json
{"data": {"gi_id": "4d5e6f7a-0000-0000-0000-000000000001", "gi_number": "GI-2026-0001", "gi_type": "SO_SHIPMENT", "order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "vehicle_id": "9f1a2b3c-0000-0000-0000-000000000009", "tms_waybill_code": "WB-2026-0001", "total_packages": 1, "status": "WAITING_WAYBILL", "version_no": 1}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000009"}}
```
- **POST /api/v1/goods-issues/{gi_id}/confirm (200):**
```json
{"data": {"gi_id": "4d5e6f7a-0000-0000-0000-000000000001", "gi_number": "GI-2026-0001", "order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "status": "GI_CONFIRMED", "order_status": "SHIPPED", "total_packages": 1, "version_no": 2}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000010"}}
```
- **POST /api/v1/order-changes/{request_id}/decide (200):**
```json
{"data": {"request_id": "5e6f7a8b-0000-0000-0000-000000000001", "order_id": "2c8d1f30-7a9b-4e11-9c2d-111111111111", "decision": "REJECT", "request_status": "REJECTED", "order_status": "READY_TO_SHIP", "erp_change_pending": false}, "meta": {"request_id": "8a1b2c3d-0000-0000-0000-000000000011"}}
```
