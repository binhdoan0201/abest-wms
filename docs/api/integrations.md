# Hợp đồng API Module: Tích hợp hệ thống ngoài (Integrations)

- **Chủ module:** Thành viên A
- **Nhánh phụ trách:** `feature/integrations-mock`
- **Mã module:** M2 (`integrations`)

---

## Danh mục Endpoint

### 1. POST /api/v1/integrations/erp/purchase-orders
- **Mục đích:** ERP mock đẩy dữ liệu đơn đặt hàng mua (PO) vào ABEST WMS.
- **Vai trò:** `admin` (AD-1).
- **Request body:** `po_number`, `warehouse_id`, `supplier_id`, `expected_delivery_date`, `lines`.
- **Phản hồi 201:** Tạo PO thành công và trả về mã PO trong hệ thống WMS.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 2. POST /api/v1/integrations/erp/asns
- **Mục đích:** ERP mock đẩy dữ liệu thông báo giao hàng trước (ASN) vào ABEST WMS.
- **Vai trò:** `admin` (AD-1).
- **Request body:** `asn_number`, `warehouse_id`, `po_id`, `supplier_id`, `expected_arrival_time`, `lines`.
- **Phản hồi 201:** Tạo ASN thành công.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 3. POST /api/v1/integrations/erp/outbound-orders
- **Mục đích:** ERP mock đẩy dữ liệu đơn bán hàng (SO/Outbound Order) vào hệ thống để bắt đầu quy trình xuất kho.
- **Vai trò:** `admin` (AD-1).
- **Request body:** `order_number`, `warehouse_id`, `customer_id`, `order_type`, `lines`.
- **Phản hồi 201:** Tạo đơn xuất thành công.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 4. POST /api/v1/integrations/erp/outbound-orders/{order_id}/changes
- **Mục đích:** ERP mock gửi yêu cầu hủy đơn hoặc đổi số lượng đơn xuất (gọi hàm CSDL `fn_receive_erp_order_change`).
- **Vai trò:** `admin` (AD-1).
- **Request body:** `change_type`, `change_reason`, `payload`.
- **Phản hồi 200:** Trạng thái tiếp nhận yêu cầu thay đổi (ACCEPTED_AUTO, REJECTED, QUEUED).
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 5. GET /api/v1/integrations/sync-logs
- **Mục đích:** Xem nhật ký đồng bộ tích hợp với hệ thống ngoài (`?warehouse_id=&status=&limit=`).
- **Vai trò:** `quanly`, `admin` (AD-1, QL-2.1).
- **Phản hồi 200:** Danh sách nhật ký đồng bộ.
- **Lỗi:** FORBIDDEN 403.
