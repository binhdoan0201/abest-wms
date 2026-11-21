# Hợp đồng API Module: Nhập kho (Inbound)

- **Chủ module:** Thành viên B
- **Nhánh phụ trách:** `feature/inbound`
- **Mã module:** M4 (`inbound`)

---

## Danh mục Endpoint

### 1. GET /api/v1/purchase-orders
- **Mục đích:** Xem danh sách PO và trạng thái nhận hàng.
- **Vai trò:** `nv-nhan`, `thukho`, `quanly`.
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/purchase-orders/{id}
- **Mục đích:** Xem chi tiết đơn mua hàng PO và các dòng hàng (po_lines).
- **Vai trò:** `nv-nhan`, `thukho`, `quanly`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. GET /api/v1/asns
- **Mục đích:** Xem danh sách thông báo giao hàng trước ASN.
- **Vai trò:** `nv-nhan`, `thukho`, `quanly`.
- **Lỗi:** FORBIDDEN 403.

### 4. POST /api/v1/grns
- **Mục đích:** Tạo mới phiếu nhập kho GRN từ PO hoặc ASN.
- **Vai trò:** `nv-nhan`.
- **Request body:** `po_id` (uuid, tùy chọn), `asn_id` (uuid, tùy chọn), `is_blind_receipt` (boolean).
- **Phản hồi 201:** `grn_id`, `grn_number`, `warehouse_id`, `status`.
- **Lỗi:** VALIDATION_ERROR 422, NOT_FOUND 404, FORBIDDEN 403.

### 5. GET /api/v1/grns
- **Mục đích:** Xem danh sách phiếu nhập kho GRN.
- **Vai trò:** `nv-nhan`, `thukho`, `quanly`.
- **Lỗi:** FORBIDDEN 403.

### 6. GET /api/v1/grns/{id}
- **Mục đích:** Xem chi tiết GRN và các dòng đếm (nếu `is_blind_receipt = true` thì ẩn `qty_expected` đối với `nv-nhan`).
- **Vai trò:** `nv-nhan`, `thukho`, `quanly`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 7. POST /api/v1/grns/{id}/lines
- **Mục đích:** Ghi một dòng kiểm đếm cho GRN đang ở trạng thái COUNTING.
- **Vai trò:** `nv-nhan`.
- **Request body:** `sku_id`, `lot_id`, `uom_code`, `qty_actual`, `qty_damaged`, `version_no`.
- **Phản hồi 201:** Dòng kiểm đếm được ghi nhận.
- **Lỗi:** VALIDATION_ERROR 422, NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409.

### 8. POST /api/v1/grns/{id}/submit
- **Mục đích:** Chốt đếm, gọi hàm CSDL `fn_resolve_approval_tier` tự ghi nhận hoặc tạo yêu cầu duyệt chênh lệch.
- **Vai trò:** `nv-nhan`.
- **Phản hồi 200:** Trạng thái GRN sau chốt (APPROVED hoặc PENDING_D1/D2/D3).
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409.

### 9. POST /api/v1/grns/{id}/recount
- **Mục đích:** Yêu cầu đếm lại khi bị cấp quản lý trả lời hoặc yêu cầu kiểm tra lại.
- **Vai trò:** `nv-nhan`.
- **Phản hồi 200:** Trạng thái chuyển sang RECOUNTING.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 10. POST /api/v1/grns/{id}/complete
- **Mục đích:** Hoàn tất phiếu nhập: tạo pallet, trạng thái STAGED, sinh task PUTAWAY.
- **Vai trò:** `nv-nhan`.
- **Phản hồi 200:** GRN chuyển sang CLOSED, danh sách pallet và task sinh ra.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409.

### 11. POST /api/v1/putaway/suggest
- **Mục đích:** Gợi ý vị trí cất hàng tối ưu cho pallet.
- **Vai trò:** `nv-cat`.
- **Request body:** `pallet_id` (uuid).
- **Phản hồi 200:** `suggested_location_id`, `location_code`, `zone_code`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 12. POST /api/v1/pallets/{id}/putaway
- **Mục đích:** Xác nhận cất pallet vào vị trí lưu kho, pallet chuyển sang STORED, tăng tồn kho.
- **Vai trò:** `nv-cat`.
- **Request body:** `location_id` (uuid), `version_no` (int).
- **Phản hồi 200:** Trạng thái cập nhật thành công.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409.
