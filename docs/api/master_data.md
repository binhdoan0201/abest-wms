# API master_data (người B, B-01)

Tiền tố: `/api/v1`. Mọi response theo chuẩn `docs/api/_conventions.md`: `{"data": ...}`, danh sách có `meta` (`page`, `page_size`, `total`), lỗi dạng `{"error": {"code", "message", "details"}}`.
Số tiền, số lượng và kích thước (NUMERIC) trong JSON luôn là **chuỗi**, ví dụ `"100000.0000"`.

## 1. Khuôn chung cho mỗi danh mục

Mỗi tài nguyên `{res}` có đủ 5 endpoint:

| Phương thức và đường dẫn | Mục đích | Quyền |
|---|---|---|
| `GET /{res}` | Danh sách, phân trang, lọc, tìm kiếm | mọi vai trò đã đăng nhập |
| `GET /{res}/{id}` | Chi tiết | mọi vai trò đã đăng nhập |
| `POST /{res}` | Tạo (201) | mã quyền ghi của tài nguyên |
| `PATCH /{res}/{id}` | Sửa một phần: chỉ trường gửi lên mới đổi | mã quyền ghi |
| `POST /{res}/{id}/deactivate` | Vô hiệu hóa, không xóa | mã quyền ghi |

**Tham số danh sách**: `page` (mặc định 1), `page_size` (mặc định 20, tối đa 100), `sort` (tên cột, thêm `-` phía trước để giảm dần), `q` (tìm không phân biệt hoa thường trên các cột tìm kiếm), và lọc bằng tham số trùng tên cột trong bảng bên dưới. Lọc theo cột không được liệt kê trả `422 VALIDATION_ERROR`.

**Kho**: client **không gửi** `warehouse_id`; server lấy từ token. Gửi trường lạ (kể cả `warehouse_id`) trả `422`. Bản ghi của kho khác trả `404 NOT_FOUND`.

**Khóa lạc quan**: các bảng danh mục không có `version_no` nên không có `409 VERSION_CONFLICT`. Hai người sửa cùng lúc thì lần ghi sau thắng. Mọi thay đổi đều ghi `audit_logs`.

## 2. Tài nguyên

| `{res}` | Khóa | Phạm vi | Quyền ghi (đoán, cần đối chiếu seed) | Cột tìm kiếm `q` | Cột lọc | Duy nhất |
|---|---|---|---|---|---|---|
| `warehouses` | UUID | admin thấy mọi kho, vai khác chỉ kho mình | AD-8 | `erp_warehouse_code`, `warehouse_name` | `is_active` | `erp_warehouse_code` |
| `zones` | UUID | theo kho | AD-3 | `zone_code`, `zone_name` | `zone_type`, `is_active` | `zone_code` trong kho |
| `locations` | UUID | theo kho | AD-3 | `location_code`, `barcode` | `zone_id`, `status`, `is_active` | `location_code` và `barcode` trong kho |
| `item-categories` | UUID | toàn hệ thống | AD-5 | `category_code`, `category_name` | `shelf_life_violation_action` | `category_code` |
| `skus` | UUID | toàn hệ thống | AD-5 | `sku_code`, `sku_name` | `category_id`, `storage_requirement`, `is_active` | `sku_code` |
| `sku-barcodes` | UUID | toàn hệ thống | AD-5 | `barcode` | `sku_id` | `barcode` |
| `suppliers` | UUID | toàn hệ thống | ER-1 | `erp_supplier_code`, `supplier_name` | `is_active` | `erp_supplier_code` |
| `customers` | UUID | toàn hệ thống | ER-1 | `erp_customer_code`, `customer_name` | `is_active` | `erp_customer_code` |
| `reason-codes` | **chuỗi** (`reason_code`) | toàn hệ thống | AD-3 | `reason_code`, `description` | `reason_category`, `is_active` | `reason_code` |
| `box-types` | UUID | toàn hệ thống | AD-3 | `box_code`, `box_name` | (không) | `box_code` |

`item-categories`, `sku-barcodes`, `box-types` không có cột `is_active` trong schema, nên `deactivate` trả `409 MASTER_DATA_NOT_DEACTIVATABLE`.

### Ví dụ: tạo SKU

```
POST /api/v1/skus
{"sku_code":"SP001","sku_name":"Sữa tươi 1L","base_uom":"PCS","unit_cost":"18500","storage_requirement":"COLD"}
```
```
201 {"data":{"sku_id":"...","sku_code":"SP001","unit_cost":"18500.0000","is_lot_tracked":true,"is_expiry_tracked":true,"is_serial_tracked":false,"storage_requirement":"COLD","is_active":true, ...}}
```

### Giá trị hợp lệ

- `zone_type`: `STORAGE`, `RECEIVING_DOCK`, `PACKING`, `DAMAGED`, `QUARANTINE`, `STAGING`, `COLD`, `HAZMAT`.
- `storage_requirement`: `NORMAL`, `COLD`, `HAZMAT`.
- `shelf_life_violation_action`: `WARN`, `BLOCK`.

## 3. Cấu hình kho

| Phương thức và đường dẫn | Mục đích | Quyền |
|---|---|---|
| `GET /warehouses/{id}/config` | Đọc tham số vận hành | mọi vai trò đã đăng nhập (kho của mình; admin: mọi kho) |
| `PATCH /warehouses/{id}/config` | Sửa tham số, trường nào gửi mới đổi | AD-5 |

Tham số sửa được: `threshold_x_d1_amount`, `threshold_y_d2_amount`, `tolerance_z_mode` (`AMOUNT_ONLY`, `PERCENT_ONLY`, `BOTH_AND`), `tolerance_z_amount`, `tolerance_z_percent`, `reauth_min_amount`, `picking_rule` (`FEFO`, `FIFO`), `blind_receipt_policy` (`REJECT`, `WARN_HOLD_D1`), `missing_cert_policy`, `counting_location_tx_policy`, `task_sla_minutes`, `approval_sla_hours`, `max_open_tasks_per_user`, `max_recount_attempts`, `allow_same_counter_recount`, `grn_tolerance_apply`, `over_receipt_tolerance_pct`.

Ràng buộc: `threshold_x_d1_amount <= threshold_y_d2_amount`, vi phạm trả `422 MASTER_DATA_INVALID_THRESHOLD`.
Tạo kho mới tự tạo dòng cấu hình mặc định (nếu thiếu, `fn_resolve_approval_tier` ném `THIEU_CAU_HINH_KHO`).

## 4. Mã lỗi riêng của module

| HTTP | Mã | Khi nào |
|---|---|---|
| 404 | `NOT_FOUND` | Không có bản ghi, bản ghi của kho khác, zone/SKU/nhóm hàng tham chiếu không tồn tại, khóa không đúng dạng UUID |
| 409 | `MASTER_DATA_DUPLICATE` | Trùng mã duy nhất, `details.fields` nêu cột trùng |
| 409 | `MASTER_DATA_IN_USE` | Vô hiệu hóa bản ghi còn tồn kho hoặc chứng từ đang mở (vị trí/kho/SKU còn hàng, zone còn vị trí hoạt động, NCC còn PO mở, khách còn đơn mở), hoặc vô hiệu hóa kho mình đang làm việc |
| 409 | `MASTER_DATA_NOT_DEACTIVATABLE` | Danh mục không có cột `is_active` |
| 409 | `INVALID_STATE` | Vô hiệu hóa bản ghi đã bị vô hiệu hóa |
| 422 | `VALIDATION_ERROR` | Sai kiểu, trường lạ, lọc cột không cho phép, PATCH rỗng, gán `null` cho cột bắt buộc, tải trọng tối đa nhỏ hơn trọng lượng bì |
| 422 | `MASTER_DATA_INVALID_THRESHOLD` | Ngưỡng D1 lớn hơn ngưỡng D2 |

## 5. Ngoài phạm vi

`users` và `roles` có trong bảng 4.2 của chuẩn API nhưng thuộc bảng của module `auth` (người A, xem 6.1 đặc tả): B-02 gọi API của A, module này không tự cài. `vehicles_drivers` chưa có trong yêu cầu B-01.
