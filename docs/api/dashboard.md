# Hợp đồng API Module: Bảng điều hành (Dashboard)

- **Chủ module:** Thành viên A (chuyển từ D theo cân bằng khối lượng 13/11)
- **Nhánh phụ trách:** `feature/dashboard`
- **Mã module:** M9 (`dashboard`, chỉ đọc)
- **Mã việc:** A-12 (API, cảnh báo đơn giản), A-13 (màn hình `bgd`)

---

## Quy ước chung

- Tiền tố `/api/v1`, phong bì theo `docs/spec/chuan-api-cong-nghe.md` mục 2.
- Quyền `QL-8.1`: `thukho`, `quanly`, `bgd` xem được; nhân viên và `admin` nhận `403 FORBIDDEN`.
- Module không có bảng riêng. Truy vấn tổng hợp đặt trong `repositories.py` (chuẩn API 7.2), chỉ đọc
  bảng của module khác, không ghi.
- **Phạm vi kho:** người dùng gắn kho chỉ xem kho của mình; gửi `warehouse_id` của kho khác trả
  `404 NOT_FOUND`. Người dùng không gắn kho xem kho được chọn qua `warehouse_id`, hoặc gộp mọi kho
  khi không gửi.
- **«Hôm nay»** tính theo giờ Việt Nam (`Asia/Ho_Chi_Minh`); `scope.business_date` là ngày đó.
- Số lượng hàng là **chuỗi** 3 chữ số thập phân; số đếm là số nguyên; tỷ lệ là phần trăm
  1 chữ số thập phân, `null` khi chưa có mẫu số (ví dụ chưa có task nào xong hôm nay).
- Mọi phản hồi có `scope` (`warehouse_id`, `business_date`, `generated_at`) và `alerts`.

### Cảnh báo đơn giản (A-12)

`alerts` là danh sách `{level, code, message, count}`, chỉ gồm mục có `count > 0`, sắp
`CRITICAL` → `WARNING` → `INFO`. Màn hình gộp cảnh báo của cả ba endpoint.

| Endpoint | `code` | Mức | Khi nào |
|---|---|---|---|
| tasks | `TASK_OVERDUE` | CRITICAL | Task đang mở đã quá `sla_due_at` |
| tasks | `TASK_URGENT_OPEN` | WARNING | Task `URGENT` chưa xong |
| tasks | `TASK_UNASSIGNED` | INFO | Task chưa giao |
| inventory | `LOT_EXPIRED_IN_STOCK` | CRITICAL | Lô đã hết hạn còn tồn |
| inventory | `LOT_NEAR_EXPIRY` | WARNING | Lô hết hạn trong `near_expiry_days` ngày |
| inventory | `SKU_BELOW_MIN_STOCK` | WARNING | Tồn khả dụng dưới `skus.min_stock_level` |
| inventory | `LOCATION_LOCKED` | INFO | Vị trí đang khóa (kiểm kê, bảo trì, hàng hư) |
| orders | `ORDER_LATE` | CRITICAL | Đơn xuất chưa xuất đã quá `cutoff_time` |
| orders | `APPROVAL_OVERDUE` | CRITICAL | Hồ sơ duyệt chờ quá `sla_due_at` |
| orders | `ORDER_ON_HOLD` | WARNING | Đơn xuất `ON_HOLD` (thiếu hàng) |
| orders | `INTEGRATION_FAILED` | WARNING | Nhật ký đồng bộ `FAILED_BUSINESS` / `FAILED_TECHNICAL` |
| orders | `PO_LATE` | WARNING | PO đang mở quá `expected_date` |
| orders | `ERP_CHANGE_PENDING` | INFO | Đơn có `erp_change_pending` |

## Danh mục Endpoint

### 1. GET /api/v1/dashboard/tasks

Thẻ số task (TK-2.1). Query: `warehouse_id` (tùy chọn).

Task «đang mở» là `UNASSIGNED`, `ASSIGNED`, `IN_PROGRESS`, `PAUSED_OFFLINE`.

```
200 {"data": {
  "scope": {"warehouse_id": "…", "business_date": "2026-11-24", "generated_at": "…"},
  "total_tasks": 6, "open_tasks": 4, "unassigned_tasks": 2, "in_progress_tasks": 1,
  "overdue_tasks": 2, "urgent_open_tasks": 1, "completed_today": 2, "on_time_rate_today": 100.0,
  "by_status": {"UNASSIGNED": 2, "ASSIGNED": 1, "IN_PROGRESS": 1, "COMPLETED": 2},
  "open_by_type": {"PICKING": 4}, "open_by_stage": {"SOAN_HANG": 4},
  "overdue_list": [{"task_id": "…", "task_type": "PICKING", "stage": "SOAN_HANG",
                    "priority": "URGENT", "status": "UNASSIGNED", "ref_doc_type": "SO",
                    "ref_doc_id": "…", "zone_code": "ZN-STORAGE", "assigned_to_name": null,
                    "sla_due_at": "…", "minutes_overdue": 45}],
  "alerts": [{"level": "CRITICAL", "code": "TASK_OVERDUE",
              "message": "2 task đã quá hạn xử lý (SLA)", "count": 2}]}}
```
`overdue_list` tối đa 10 dòng, trễ lâu nhất trước. `on_time_rate_today` là tỷ lệ task xong hôm nay
không trễ `sla_due_at`.

Lỗi: `FORBIDDEN` 403, `NOT_FOUND` 404 (kho khác).

### 2. GET /api/v1/dashboard/inventory

Query: `warehouse_id` (tùy chọn), `near_expiry_days` (1–365, mặc định 30).

```
200 {"data": {
  "scope": {…}, "near_expiry_days": 30, "skus_in_stock": 1, "pallets_in_stock": 0,
  "quantities": {"available": "126.000", "allocated": "0.000", "counting": "0.000",
                 "locked": "0.000", "damaged": "1.000", "on_hand": "126.000"},
  "locations": {"total": 30, "occupied": 3, "empty": 27, "locked": 0, "occupancy_rate": 10.0,
                "by_status": {"EMPTY": 27, "PARTIAL": 3}},
  "expired_lots": 1, "near_expiry_lots": 1,
  "expiring_list": [{"sku_code": "SKU-FOOD-001", "sku_name": "…", "lot_number": "L01",
                     "expiry_date": "2026-11-22", "days_left": -2, "qty_on_hand": "6.000"}],
  "below_min_stock_skus": 9,
  "below_min_stock_list": [{"sku_code": "…", "sku_name": "…", "min_stock_level": "10.000",
                            "qty_available": "0.000"}],
  "alerts": […]}}
```
- `on_hand` = khả dụng + đã giữ + đang kiểm + khóa (không gồm hàng hư).
- Vị trí «đã dùng» là `PARTIAL`, `FULL`; «khóa» là `COUNTING_LOCKED`, `MAINTENANCE_LOCKED`,
  `DAMAGED_HOLD`. Chỉ tính vị trí đang hoạt động.
- `expiring_list` gồm lô đã hết hạn và sắp hết hạn còn tồn, hạn gần nhất trước, tối đa 10 dòng.

Lỗi: `FORBIDDEN` 403, `NOT_FOUND` 404, `VALIDATION_ERROR` 422 (`near_expiry_days` ngoài khoảng).

### 3. GET /api/v1/dashboard/orders

Đơn nhập, xuất trong ngày, hồ sơ chờ duyệt. Query: `warehouse_id` (tùy chọn).

```
200 {"data": {
  "scope": {…},
  "inbound": {"open_pos": 0, "pos_due_today": 0, "pos_late": 0, "grns_today": 0,
              "grns_closed_today": 0, "grns_pending_approval": 0},
  "outbound": {"open_orders": 3, "open_by_status": {"NEW": 1, "PICKING": 1, "ON_HOLD": 1},
               "urgent_open": 1, "late": 1, "on_hold": 1, "due_today": 4, "due_today_shipped": 1,
               "fulfillment_rate_today": 25.0, "gi_confirmed_today": 0, "erp_change_pending": 0},
  "approvals": {"pending_total": 0, "pending_by_status": {}, "overdue": 0},
  "integration_failures": 0,
  "late_orders": [{"order_id": "…", "erp_order_number": "SO-001", "order_type": "SO",
                   "status": "PICKING", "is_urgent": true, "cutoff_time": "…",
                   "minutes_late": 50}],
  "alerts": […]}}
```
- PO «đang mở»: `PENDING`, `RECEIVING`, `PARTIAL_RECEIVED`.
- WMS kết thúc trách nhiệm tại `SHIPPED`. Đơn «đã xuất» là `SHIPPED`, `IN_TRANSIT`, `DELIVERED`,
  `PARTIAL_DELIVERED`, `DELIVERY_FAILED`; «đang mở» là mọi trạng thái khác trừ `CANCELLED`.
- `fulfillment_rate_today` = đơn có giờ cắt xe hôm nay đã xuất / đơn có giờ cắt xe hôm nay
  (không tính đơn hủy).
- Hồ sơ chờ duyệt: `PENDING_D1`, `PENDING_D2`, `PENDING_D3`, `NEED_INFO`.
- `late_orders` ưu tiên đơn khẩn, rồi trễ lâu nhất; tối đa 10 dòng.

Lỗi: `FORBIDDEN` 403, `NOT_FOUND` 404.

## Màn hình (A-13)

- `GET /dashboard` (client web): cảnh báo, khối Nhiệm vụ, Tồn kho, Đơn trong ngày. `bgd` đăng
  nhập xong vào thẳng trang này; vai trò khác vẫn vào `/inventory`.
- `POST /dashboard/refresh` (HTMX): trả phần thân, tự gọi mỗi 60 giây hoặc khi bấm «Làm mới».
- Một API lỗi chỉ làm trống khối của nó, các khối khác vẫn hiển thị.
