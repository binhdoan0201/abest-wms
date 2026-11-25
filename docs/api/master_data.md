# Hợp đồng API Module: Dữ liệu nguồn (Master Data)

- **Chủ module:** Thành viên A (Đoàn Duy Bình)
- **Nhánh phụ trách:** `feature/master-data`
- **Mã module:** M3 (`master_data`)
- **Mã việc:** A-10 (chuyển từ B-01)

---

## Quy ước chung

Áp dụng toàn bộ quy ước tại `docs/spec/chuan-api-cong-nghe.md` mục 2. Riêng module này:

- **Phạm vi kho**: client **không gửi** `warehouse_id`, server lấy từ token.
  - `zones`, `locations` thuộc kho của người dùng. Bản ghi kho khác trả `404 NOT_FOUND`.
  - `warehouses`: `admin` thấy mọi kho, vai trò khác chỉ thấy kho của mình.
  - Các danh mục còn lại dùng chung toàn hệ thống.
  - Người dùng chưa gán kho gọi tài nguyên theo kho thì nhận `403 FORBIDDEN`.
- **Quyền**: đọc cho mọi vai trò đã đăng nhập; ghi (`POST`, `PATCH`, `deactivate`) cần quyền `AD-1` (chỉ `admin`, theo seed `01_roles_permissions.sql`).
- **Kiểu dữ liệu**: số tiền, số lượng, kích thước (NUMERIC) trả về dạng **chuỗi**, ví dụ `"18500.0000"`. Khi gửi lên có thể dùng chuỗi hoặc số.
- **Trường lạ**: body có trường không khai báo (kể cả `warehouse_id`, mã định danh, `status` của vị trí) trả `422 VALIDATION_ERROR`.
- **Mã định danh không đổi**: các cột mã (`*_code`, `barcode` của SKU) chỉ đặt khi tạo, không sửa qua `PATCH`.
- **Khóa lạc quan**: các bảng danh mục không có cột `version_no`, nên không có `409 VERSION_CONFLICT`; lần ghi sau thắng.
- **Audit**: mọi thao tác ghi đều ghi `audit_logs` với `action_code` là `MASTER_DATA_CREATE`, `MASTER_DATA_UPDATE`, `MASTER_DATA_DEACTIVATE`, `WAREHOUSE_CONFIG_UPDATE`.
- **`users`, `roles`**: thuộc module này (chuẩn API 4.2). Đã có `GET /users` chỉ đọc (mục 8) để thủ kho, quản lý giao task. Các endpoint ghi của `users` và mọi endpoint `roles` làm cùng màn hình Admin (A-11), hiện trả `501 NOT_IMPLEMENTED`.

### Danh sách: phân trang, sắp xếp, tìm kiếm, lọc

- `page` (mặc định 1), `page_size` (mặc định 20, tối đa 100).
- `sort`: tên cột cho phép (xem bảng dưới), thêm `-` phía trước để giảm dần. Mặc định sắp theo cột mã tăng dần.
- `q`: tìm không phân biệt hoa thường, khớp một phần trên các cột tìm kiếm.
- Lọc: tham số trùng tên cột lọc. Kiểu `bool` nhận `true`/`false`; kiểu UUID phải đúng định dạng.
- Tham số lạ, cột sắp xếp không cho phép hoặc giá trị lọc sai kiểu trả `422 VALIDATION_ERROR`.

### Bảng tài nguyên

| `{resource}` | Khóa (`{id}`) | Phạm vi | Cột tìm kiếm `q` | Cột lọc | Duy nhất | Có `is_active` |
| --- | --- | --- | --- | --- | --- | --- |
| `warehouses` | `warehouse_id` (UUID) | xem trên | `erp_warehouse_code`, `warehouse_name` | `is_active` | `erp_warehouse_code` | có |
| `zones` | `zone_id` (UUID) | theo kho | `zone_code`, `zone_name` | `zone_type`, `is_active` | `zone_code` trong kho | có |
| `locations` | `location_id` (UUID) | theo kho | `location_code`, `barcode` | `zone_id`, `status`, `is_active` | `location_code` trong kho | có |
| `item-categories` | `category_id` (UUID) | toàn hệ thống | `category_code`, `category_name` | `shelf_life_violation_action` | `category_code` | không |
| `skus` | `sku_id` (UUID) | toàn hệ thống | `sku_code`, `sku_name` | `category_id`, `storage_requirement`, `is_active` | `sku_code` | có |
| `sku-barcodes` | `barcode_id` (UUID) | toàn hệ thống | `barcode` | `sku_id`, `uom_code` | `barcode` | không |
| `suppliers` | `supplier_id` (UUID) | toàn hệ thống | `erp_supplier_code`, `supplier_name` | `is_active` | `erp_supplier_code` | có |
| `customers` | `customer_id` (UUID) | toàn hệ thống | `erp_customer_code`, `customer_name` | `is_active` | `erp_customer_code` | có |
| `reason-codes` | `reason_code` (**chuỗi**) | toàn hệ thống | `reason_code`, `description` | `reason_category`, `is_active` | `reason_code` | có |
| `box-types` | `box_type_id` (UUID) | toàn hệ thống | `box_code`, `box_name` | (không) | `box_code` | không |

### Trường của từng tài nguyên

Ký hiệu: **bắt buộc khi tạo**, *(tạo)* chỉ đặt lúc tạo, còn lại sửa được qua `PATCH`.

| `{resource}` | Trường |
| --- | --- |
| `warehouses` | **`erp_warehouse_code`** *(tạo)*, **`warehouse_name`**, `branch_code`, `address` |
| `zones` | **`zone_code`** *(tạo)*, **`zone_name`**, **`zone_type`** |
| `locations` | **`zone_id`**, **`location_code`** *(tạo)*, **`barcode`**, `aisle`, `rack`, `shelf_level`, `bin`, `max_weight_kg`, `max_volume_m3`, `max_pallets` |
| `item-categories` | **`category_code`** *(tạo)*, **`category_name`**, `min_receiving_shelf_life_days` (≥ 0, mặc định 0), `shelf_life_violation_action` (mặc định `WARN`) |
| `skus` | **`sku_code`** *(tạo)*, **`sku_name`**, `category_id`, **`base_uom`**, `unit_cost` (≥ 0), `min_stock_level` (≥ 0), `is_lot_tracked` (mặc định `true`), `is_expiry_tracked` (mặc định `true`), `is_serial_tracked` (mặc định `false`), `storage_requirement` (mặc định `NORMAL`), `unit_weight_kg` (kg, ≥ 0), `unit_volume_m3` (m³, ≥ 0) |
| `sku-barcodes` | **`sku_id`** *(tạo)*, **`barcode`** *(tạo)*, **`uom_code`**, `conversion_factor` (> 0, mặc định 1) |
| `suppliers` | **`erp_supplier_code`** *(tạo)*, **`supplier_name`**, `contact_person`, `phone`, `email` |
| `customers` | **`erp_customer_code`** *(tạo)*, **`customer_name`**, `shipping_address`, `phone` |
| `reason-codes` | **`reason_code`** *(tạo)*, **`reason_category`**, **`description`** |
| `box-types` | **`box_code`** *(tạo)*, **`box_name`**, **`length_cm`**, **`width_cm`**, **`height_cm`** (> 0), `tare_weight_kg` (≥ 0, mặc định 0), `max_weight_kg` (> 0, không nhỏ hơn `tare_weight_kg`) |

Giá trị hợp lệ:

- `zone_type`: `STORAGE`, `RECEIVING_DOCK`, `PACKING`, `DAMAGED`, `QUARANTINE`, `STAGING`, `COLD`, `HAZMAT`.
- `locations.status` (chỉ đọc, do `inventory` và `cycle_count` cập nhật): `EMPTY`, `PARTIAL`, `FULL`, `COUNTING_LOCKED`, `MAINTENANCE_LOCKED`, `DAMAGED_HOLD`.
- `storage_requirement`: `NORMAL`, `COLD`, `HAZMAT`.
- `shelf_life_violation_action`: `WARN`, `BLOCK`.
- `reason_category`: `DAMAGED`, `DISCREPANCY`, `TASK_REJECT`, `ORDER_CANCEL`, `SCRAP`, `OVERRIDE`, `PACKING_EXCEPTION`.

---

## Danh mục Endpoint

### 1. GET /api/v1/{resource}
- **Mục đích:** Danh sách bản ghi, có phân trang, sắp xếp, tìm kiếm, lọc (xem «Quy ước chung»).
- **Vai trò:** Mọi vai trò đã đăng nhập.
- **Phản hồi 200:** `{"data": [...], "meta": {"request_id", "page", "page_size", "total"}}`.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403 (chưa gán kho với tài nguyên theo kho).

### 2. GET /api/v1/{resource}/{id}
- **Mục đích:** Chi tiết một bản ghi.
- **Vai trò:** Mọi vai trò đã đăng nhập.
- **Phản hồi 200:** Bản ghi.
- **Lỗi:** NOT_FOUND 404 (không có, thuộc kho khác, hoặc `{id}` sai định dạng).

### 3. POST /api/v1/{resource}
- **Mục đích:** Tạo bản ghi.
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** các trường ở bảng «Trường của từng tài nguyên».
- **Phản hồi 201:** Bản ghi vừa tạo. Tạo `warehouses` thì tự tạo dòng `warehouse_configs` mặc định.
- **Lỗi:** VALIDATION_ERROR 422, FORBIDDEN 403, NOT_FOUND 404 (`zone_id`, `category_id`, `sku_id` tham chiếu không tồn tại hoặc thuộc kho khác), MASTER_DATA_DUPLICATE 409 (`details.fields` nêu cột trùng).

Ví dụ:

```
POST /api/v1/skus
{"sku_code": "SP001", "sku_name": "Sữa tươi 1L", "base_uom": "PCS", "unit_cost": "18500", "storage_requirement": "COLD"}

201 {"data": {"sku_id": "...", "sku_code": "SP001", "unit_cost": "18500.0000", "is_lot_tracked": true,
              "is_expiry_tracked": true, "is_serial_tracked": false, "storage_requirement": "COLD", "is_active": true, ...},
     "meta": {"request_id": "..."}}
```

### 4. PATCH /api/v1/{resource}/{id}
- **Mục đích:** Sửa một phần, chỉ trường gửi lên mới đổi.
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** các trường sửa được. Body rỗng, gửi cột mã, hoặc gán `null` cho cột bắt buộc trả 422.
- **Phản hồi 200:** Bản ghi sau khi sửa.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VALIDATION_ERROR 422, MASTER_DATA_DUPLICATE 409.

### 5. POST /api/v1/{resource}/{id}/deactivate
- **Mục đích:** Ngừng sử dụng bản ghi (đặt `is_active = false`), không xóa.
- **Vai trò:** `admin` (`AD-1`).
- **Phản hồi 200:** Bản ghi với `is_active = false`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, INVALID_STATE 409 (đã ngừng từ trước), MASTER_DATA_NOT_DEACTIVATABLE 409 (`item-categories`, `sku-barcodes`, `box-types` không có `is_active`), MASTER_DATA_IN_USE 409:
  - `warehouses`: kho đang làm việc của chính người gọi, hoặc kho còn tồn;
  - `zones`: còn vị trí đang hoạt động;
  - `locations`, `skus`: còn tồn (bất kỳ trạng thái nào lớn hơn 0).

### 6. GET /api/v1/warehouses/{id}/config
- **Mục đích:** Đọc tham số vận hành của kho (`warehouse_configs`).
- **Vai trò:** Mọi vai trò đã đăng nhập, chỉ kho của mình; `admin` xem mọi kho.
- **Phản hồi 200:** Toàn bộ cột của `warehouse_configs` (NUMERIC dạng chuỗi, JSONB dạng object).
- **Lỗi:** NOT_FOUND 404.

### 7. PATCH /api/v1/warehouses/{id}/config
- **Mục đích:** Sửa tham số vận hành, trường nào gửi mới đổi.
- **Vai trò:** `admin` (`AD-1`).
- **Request body** (đều tùy chọn, không nhận `null`):

| Trường | Ràng buộc |
| --- | --- |
| `threshold_x_d1_amount`, `threshold_y_d2_amount`, `tolerance_z_amount`, `reauth_min_amount` | ≥ 0 |
| `tolerance_z_percent`, `over_receipt_tolerance_pct` | 0 đến 100 |
| `tolerance_z_mode` | `AMOUNT_ONLY`, `PERCENT_ONLY`, `BOTH_AND` |
| `picking_rule` | `FEFO`, `FIFO` |
| `blind_receipt_policy` | `REJECT`, `WARN_HOLD_D1` |
| `missing_cert_policy` | `HARD_BLOCK`, `SOFT_OVERRIDE` |
| `counting_location_tx_policy` | `BLOCK`, `QUEUE` |
| `task_sla_minutes` | object `{task_type: số phút > 0}`, khóa là giá trị của `task_type` |
| `approval_sla_hours` | object có đủ `D1`, `D2`, `D3`, giá trị > 0 |
| `max_open_tasks_per_user`, `max_recount_attempts`, `dashboard_refresh_seconds`, `offline_task_reclaim_minutes` | số nguyên > 0 |
| `allow_same_counter_recount`, `grn_tolerance_apply` | `true`/`false` |

- **Phản hồi 200:** Cấu hình sau khi sửa (ghi `updated_by`, `updated_at`).
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, VALIDATION_ERROR 422, MASTER_DATA_INVALID_THRESHOLD 422 (sau khi sửa mà `threshold_x_d1_amount > threshold_y_d2_amount`).

---

### 8. GET /api/v1/users

Danh sách người dùng, chỉ đọc. Dùng cho màn hình giao task (D-08) và màn hình Admin (A-11).

| Vai trò (quyền) | Phạm vi | Trường trả về |
|---|---|---|
| `admin` (`AD-1`) | Mọi kho; lọc `warehouse_id` tùy chọn; mọi trạng thái | Đủ, gồm `email`, `phone`, `last_login_at` |
| `thukho`, `quanly` (`TK-1.1`) | Chỉ kho của mình (bỏ qua `warehouse_id` gửi lên); mặc định `status=ACTIVE` | Không có `email`, `phone`, `last_login_at` |

Nhân viên và `bgd` nhận `403 FORBIDDEN`.

Query: `role_code` (`nv-nhan`, `nv-cat`, `nv-soan`, `nv-dongoi`, `nv-kiemke`, `thukho`, `quanly`, `bgd`, `admin`), `status` (`ACTIVE`, `LOCKED`, `INACTIVE`, `EXPIRED`), `q` (tìm theo `username`, `full_name`), `page`, `page_size` (1–100). Sắp theo `role_code`, `username`.

```
200 {"data": [{"user_id": "…", "username": "nv_soan", "full_name": "Phạm Văn Soạn",
               "role_code": "nv-soan", "role_name": "Nhân viên soạn hàng",
               "primary_stage": "SOAN_HANG", "primary_warehouse_id": "…", "status": "ACTIVE",
               "is_active": true, "is_seasonal": false, "valid_until": null,
               "is_safety_checked": true, "can_receive_tasks": true}],
     "meta": {"page": 1, "page_size": 20, "total": 1}}
```

`can_receive_tasks`: `ACTIVE`, và nếu là thời vụ thì phải đã kiểm an toàn (`is_safety_checked`) và còn hạn (`valid_until`) theo NV-DC-1. Màn hình giao task nên chỉ cho chọn người có giá trị `true`.

Lỗi: `FORBIDDEN` 403; `VALIDATION_ERROR` 422 (`role_code`, `status`, `warehouse_id`, `page`, `page_size` sai).

## Mã lỗi riêng của module

| Mã | HTTP | Khi nào |
| --- | --- | --- |
| `MASTER_DATA_DUPLICATE` | 409 | Trùng cột duy nhất; `details.fields` nêu cột trùng |
| `MASTER_DATA_IN_USE` | 409 | Ngừng sử dụng bản ghi còn được dùng (xem endpoint 5) |
| `MASTER_DATA_NOT_DEACTIVATABLE` | 409 | Danh mục không có cột `is_active` |
| `MASTER_DATA_INVALID_THRESHOLD` | 422 | Ngưỡng D1 lớn hơn ngưỡng D2 |
| `MASTER_DATA_UOM_NOT_CONVERTIBLE` | 422 | `convert_to_base_uom`: đơn vị chưa có mã vạch quy đổi hoặc có nhiều hệ số khác nhau |

## Hàm công khai cho module khác

Module khác đọc danh mục qua các hàm export trong `server.app.modules.master_data`, không truy vấn thẳng bảng:

| Hàm | Trả về |
| --- | --- |
| `get_warehouse_config(db, warehouse_id)` | `dict` toàn bộ cấu hình kho (NUMERIC là `Decimal`), ném `NOT_FOUND` nếu không có |
| `get_sku(db, sku_id)` | `dict` thông tin SKU (gồm `unit_cost`, cờ theo dõi lô/hạn/serial), ném `NOT_FOUND` nếu không có |
| `get_location(db, location_id, warehouse_id)` | `dict` thông tin vị trí trong kho, ném `NOT_FOUND` nếu không có hoặc khác kho |
| `convert_to_base_uom(db, sku_id, uom_code, qty)` | `Decimal` số lượng theo `skus.base_uom`. Hệ số lấy từ `sku_barcodes.conversion_factor` (1 `uom_code` = hệ số × `base_uom`); `uom_code` trùng `base_uom` thì trả nguyên `qty`. Ném `NOT_FOUND` hoặc `MASTER_DATA_UOM_NOT_CONVERTIBLE` |

Quy tắc đơn vị tính (chuẩn API mục 2.3): tồn kho, sổ cái, cấp phát và so lệch luôn tính theo `base_uom`. `inbound` quy đổi số lượng dòng PO, dòng GRN; `outbound` quy đổi dòng đơn (nếu có đơn vị khác) trước khi gọi `inventory`.

`unit_weight_kg`, `unit_volume_m3` tính cho 1 đơn vị `base_uom`, có thể `null` khi ERP chưa có dữ liệu; gợi ý cất hàng và đóng gói bỏ qua kiểm tra tải khi giá trị là `null`.
