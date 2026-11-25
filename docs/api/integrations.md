# Hợp đồng API Module: Tích hợp hệ thống ngoài (Integrations)

- **Chủ module:** Thành viên A (Đoàn Duy Bình)
- **Nhánh phụ trách:** `feature/integrations-mock`
- **Mã module:** M2 (`integrations`), chỉ dùng ở môi trường dev và demo
- **Mã việc:** A-07

---

## Quy ước chung

- Theo `docs/spec/chuan-api-cong-nghe.md` mục 2.
- **ERP gửi mã, không gửi ID nội bộ.** Ví dụ `warehouse_code`, `supplier_code`, `customer_code`, `sku_code`, `dock_location_code`. `integrations` đổi sang ID bằng `master_data.find_by_code`. Có mã không tồn tại thì trả `422 INTEGRATION_UNKNOWN_CODE`, `details.missing` liệt kê từng trường và mã.
- **Mọi lần nhận và gửi đều ghi `integration_sync_logs`**, kể cả khi lỗi. Phản hồi luôn có `sync_id` (trong `data` khi thành công, trong `error.details` khi lỗi) để tra cứu.
- **Trạng thái nhật ký:**
  - `PENDING`: chờ xử lý;
  - `SUCCESS`: thành công;
  - `FAILED_BUSINESS`: dữ liệu bị từ chối, không tự thử lại, sửa dữ liệu rồi `retry` hoặc `resolve`;
  - `FAILED_TECHNICAL`: lỗi tạm thời, tự thử lại tối đa 5 lần;
  - `RESOLVED`: đã xử lý tay.
- `business_payload` là dữ liệu nghiệp vụ, nên `admin` không xem được (trả `null`, đặc tả 5.4.5).

## Luồng nhận từ ERP (PO, ASN, đơn xuất)

```
ERP mock -> POST /integrations/erp/... -> đổi mã sang ID -> ghi nhật ký PENDING
  -> có module đã đăng ký (register_erp_handler)?
       có  -> gọi hàm xử lý trong SAVEPOINT -> SUCCESS (201) | FAILED_BUSINESS (422) | FAILED_TECHNICAL (503)
       chưa -> giữ PENDING (202); POST /integrations/sync-logs/process sẽ giao lại khi module đã đăng ký
```

Bảng PO, ASN, đơn xuất thuộc `inbound` (B) và `outbound` (C). `integrations` không ghi thẳng các bảng này (quy tắc 2.3). Mỗi module tự đăng ký hàm xử lý trong `__init__.py` của mình:

```python
from server.app.modules.integrations import register_erp_handler
register_erp_handler("PO", receive_purchase_order)    # inbound
register_erp_handler("ASN", receive_asn)              # inbound
register_erp_handler("SO", receive_outbound_order)    # outbound
```

Chữ ký: `handler(db, data: dict, actor_id: UUID) -> UUID` (ID chứng từ vừa tạo). `data` là dữ liệu đã chuẩn hóa, mọi UUID, số, ngày giờ đều ở dạng chuỗi:

| Loại | Trường của `data` |
| --- | --- |
| `PO` | `erp_po_number`, `warehouse_id`, `supplier_id`, `expected_date`, `lines[]`: `line_number`, `sku_id`, `uom_code`, `qty_ordered` |
| `ASN` | `erp_asn_number`, `warehouse_id`, `erp_po_number` (module tự tra PO), `supplier_id`, `expected_arrival_at`, `expected_pallets`, `assigned_dock_location_id` |
| `SO` | `erp_order_number`, `order_type`, `warehouse_id`, `customer_id`, `dest_warehouse_id`, `supplier_id`, `cutoff_time`, `is_urgent`, `urgent_reason`, `route_code`, `lines[]`: `line_number`, `sku_id`, `qty_ordered` (đơn vị cơ sở) |

Hàm xử lý ném `BusinessError` khi dữ liệu không hợp lệ (ví dụ `INBOUND_PO_DUPLICATE`). Mã lỗi đó được trả lại cho ERP và ghi `FAILED_BUSINESS`.

## Luồng gửi sang ERP, TMS (outbox)

Module nghiệp vụ ghi dòng `OUTBOUND` + `PENDING` trong **cùng transaction** với nghiệp vụ, nên chỉ chứng từ đã commit mới được gửi:

- `enqueue_to_erp(db, warehouse_id, doc_type, doc_id, payload) -> sync_id`: GRN (B), GI (C), ADJUSTMENT, SCRAP (D).
- Hàm DB `fn_enqueue_erp_change_reply` (phản hồi đổi/hủy đơn) và `approvals` đã ghi dòng `PENDING` theo cùng cách.
- `request_waybill(db, warehouse_id, gi_id, payload) -> str | None`: gọi TMS ngay, trả số vận đơn. TMS lỗi thì trả `None` (đơn để `WAITING_WAYBILL`), dòng nhật ký được thử lại; lấy kết quả sau bằng `get_waybill(db, gi_id)`.

`POST /integrations/sync-logs/process` gửi các dòng chờ và thử lại lỗi kỹ thuật. Demo bấm tay, sau này chạy định kỳ.

ERP, TMS giả lập nằm ở `server/app/integrations/` (`gateways.py` là giao diện, `erp_mock.py`, `tms_mock.py` là bản giả lập). Bản thật sau này cài cùng giao diện, không phải sửa service.

---

## Danh mục Endpoint

### 1. POST /api/v1/integrations/erp/purchase-orders
- **Mục đích:** ERP mock đẩy đơn mua hàng (PO).
- **Vai trò:** `admin` (`AD-1`).
- **Request body:**
```json
{"erp_po_number": "PO-2026-0001", "warehouse_code": "WH01", "supplier_code": "SUPP-001",
 "expected_date": "2026-11-28",
 "lines": [{"line_number": 1, "sku_code": "SKU-FOOD-001", "uom_code": "CTN", "qty_ordered": "10"}]}
```
- **Phản hồi:** `201` đã tạo PO (`data.doc_id`), hoặc `202` đã nhận, chờ `inbound` xử lý. `data` là dòng nhật ký.
- **Lỗi:** VALIDATION_ERROR 422 (thiếu trường, trùng `line_number`), INTEGRATION_UNKNOWN_CODE 422, lỗi nghiệp vụ của `inbound` 422, INTEGRATION_TEMPORARY_ERROR 503, FORBIDDEN 403.

### 2. POST /api/v1/integrations/erp/asns
- **Mục đích:** ERP mock đẩy thông báo giao hàng (ASN).
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** `erp_asn_number`, `warehouse_code`, `erp_po_number` (tùy chọn), `supplier_code` (tùy chọn), `expected_arrival_at`, `expected_pallets` (tùy chọn), `dock_location_code` (tùy chọn, mã vị trí cửa nhận trong kho).
- **Phản hồi:** `201` hoặc `202` như mục 1.
- **Lỗi:** như mục 1.

### 3. POST /api/v1/integrations/erp/outbound-orders
- **Mục đích:** ERP mock đẩy đơn xuất: bán hàng (`SO`), chuyển kho (`INTER_WH_TRANSFER`), trả NCC (`SUPPLIER_RETURN`).
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** `erp_order_number`, `order_type` (mặc định `SO`), `warehouse_code`, `customer_code` (bắt buộc với `SO`), `dest_warehouse_code` (bắt buộc với chuyển kho), `supplier_code` (bắt buộc với trả NCC), `cutoff_time`, `is_urgent`, `urgent_reason`, `route_code`, `lines[]`: `line_number`, `sku_code`, `qty_ordered` (theo đơn vị cơ sở của SKU).
- **Phản hồi:** `201` hoặc `202` (chờ `outbound` xử lý).
- **Lỗi:** như mục 1.

### 4. POST /api/v1/integrations/erp/outbound-orders/{order_id}/changes
- **Mục đích:** ERP mock đổi hoặc hủy đơn xuất, gọi `fn_receive_erp_order_change`. Hàm DB tự quyết theo trạng thái đơn: tự chấp nhận, chờ Quản lý, hoặc tự từ chối, và tự xếp phản hồi gửi ERP.
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** `change_type` (`CANCEL_ORDER`, `CHANGE_QTY`, `CHANGE_ADDRESS`), `payload` (object), `reason` (tùy chọn).
- **Phản hồi 200:** dòng nhật ký kèm `decision`: `request_id`, `status` (`ACCEPTED`, `PENDING_MANAGER`, `REJECTED`), `decision_path`, `reject_reason_code`, `order_status_at_receipt`.
- **Lỗi:** NOT_FOUND 404 (đơn không tồn tại), INTEGRATION_CHANGE_PENDING 409 (đơn đã có yêu cầu đang chờ Quản lý), FORBIDDEN 403.

### 5. GET /api/v1/integrations/sync-logs
- **Mục đích:** Xem nhật ký đồng bộ, mới nhất trước. Lọc `external_system`, `direction`, `doc_type`, `status`; phân trang `page`, `page_size` (tối đa 100).
- **Vai trò:** `admin` (`AD-1`, mọi kho, không thấy `business_payload`), `thukho`, `quanly` (`QL-2.1`, kho của mình).
- **Phản hồi 200:** danh sách nhật ký với `meta.page`, `meta.page_size`, `meta.total`.
- **Lỗi:** VALIDATION_ERROR 422 (tham số lọc lạ), FORBIDDEN 403.

### 6. POST /api/v1/integrations/sync-logs/process
- **Mục đích:** Chạy hàng đợi, tối đa 50 dòng mỗi lần:
  - gửi các dòng `OUTBOUND` đang `PENDING`;
  - thử lại dòng `FAILED_TECHNICAL` còn lượt;
  - giao lại các dòng ERP `PENDING` cho module đã đăng ký.
- **Vai trò:** `admin`, `quanly`.
- **Phản hồi 200:** `processed`, `SUCCESS`, `FAILED_BUSINESS`, `FAILED_TECHNICAL`.
- **Lỗi:** FORBIDDEN 403.

### 7. POST /api/v1/integrations/sync-logs/{id}/retry
- **Mục đích:** Thử lại một dòng `PENDING`, `FAILED_TECHNICAL` hoặc `FAILED_BUSINESS` (ví dụ sau khi đã bổ sung danh mục còn thiếu).
- **Vai trò:** `admin`, `quanly`.
- **Phản hồi 200:** dòng nhật ký sau khi thử.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409 (đã `SUCCESS` hoặc `RESOLVED`), FORBIDDEN 403.

### 8. POST /api/v1/integrations/sync-logs/{id}/resolve
- **Mục đích:** Đánh dấu đã xử lý tay một dòng lỗi, không gửi lại. Ghi `resolved_by`.
- **Vai trò:** `admin`, `quanly`.
- **Phản hồi 200:** dòng nhật ký `RESOLVED`.
- **Lỗi:** NOT_FOUND 404, INVALID_STATE 409 (dòng không ở trạng thái lỗi), FORBIDDEN 403.

### 9. POST /api/v1/integrations/mock/failures
- **Mục đích:** Cấu hình N lần gọi tiếp theo của ERP hoặc TMS giả lập trả lỗi, để demo và kiểm thử cơ chế thử lại. Bị chặn ở môi trường `production`.
- **Vai trò:** `admin` (`AD-1`).
- **Request body:** `system` (`ERP`, `TMS`), `error_category` (`NONE`, `BUSINESS_ERROR`, `TECHNICAL_ERROR`), `times` (0 đến 100).
- **Phản hồi 200:** cấu hình vừa đặt.
- **Lỗi:** FORBIDDEN 403.

---

## Mã lỗi riêng của module

| Mã | HTTP | Khi nào |
| --- | --- | --- |
| `INTEGRATION_UNKNOWN_CODE` | 422 | Mã ERP (kho, NCC, khách, SKU, vị trí) không có trong danh mục WMS |
| `INTEGRATION_CHANGE_PENDING` | 409 | Đơn đã có yêu cầu đổi/hủy đang chờ Quản lý |
| `INTEGRATION_TEMPORARY_ERROR` | 503 | Lỗi tạm thời khi module xử lý chứng từ; nhật ký `FAILED_TECHNICAL`, sẽ thử lại |
