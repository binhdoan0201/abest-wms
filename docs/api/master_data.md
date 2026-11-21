# Hợp đồng API Module: Dữ liệu nguồn (Master Data)

- **Chủ module:** Thành viên B
- **Nhánh phụ trách:** `feature/master-data`
- **Mã module:** M3 (`master_data`)

---

## Danh mục Endpoint

### 1. GET /api/v1/{resource}
- **Mục đích:** Lấy danh sách bản ghi danh mục ({resource} thuộc: `warehouses`, `zones`, `locations`, `item-categories`, `skus`, `sku-barcodes`, `suppliers`, `customers`, `reason-codes`, `box-types`, `users`, `roles`).
- **Vai trò:** Mọi vai trò (riêng `users`, `roles` chỉ `admin`).
- **Query params:** `page`, `page_size`, `is_active` (TODO: B bổ sung).
- **Phản hồi 200:** Danh sách bản ghi theo chuẩn phong bì `{"data": [...], "meta": {...}}`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 2. GET /api/v1/{resource}/{id}
- **Mục đích:** Xem chi tiết một bản ghi danh mục.
- **Vai trò:** Mọi vai trò (riêng `users`, `roles` chỉ `admin`).
- **Phản hồi 200:** Chi tiết bản ghi.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. POST /api/v1/{resource}
- **Mục đích:** Tạo mới một bản ghi danh mục.
- **Vai trò:** `admin` (quyền `AD-1`).
- **Request body:** TODO: B hoàn thiện cấu trúc body chi tiết cho từng loại tài nguyên.
- **Phản hồi 201:** Bản ghi vừa tạo kèm ID và timestamps.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403.

### 4. PATCH /api/v1/{resource}/{id}
- **Mục đích:** Cập nhật thông tin bản ghi danh mục.
- **Vai trò:** `admin` (quyền `AD-1`).
- **Request body:** TODO: B hoàn thiện các trường cho phép cập nhật.
- **Phản hồi 200:** Bản ghi sau khi cập nhật.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VERSION_CONFLICT 409.

### 5. POST /api/v1/{resource}/{id}/deactivate
- **Mục đích:** Ngừng kích hoạt một bản ghi danh mục.
- **Vai trò:** `admin` (quyền `AD-1`).
- **Phản hồi 200:** Trạng thái `is_active = false`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.
