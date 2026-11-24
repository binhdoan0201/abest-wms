# Hợp đồng API Module: Nhập kho (Inbound)

- **Chủ module:** Thành viên B
- **Nhánh phụ trách:** `feature/inbound`
- **Mã module:** M4 (`inbound`)
- **Mã việc:** B-03 đến B-07

---

## Quy ước chung

Tiền tố: `/api/v1`. Response theo chuẩn `docs/spec/chuan-api-cong-nghe.md` mục 2. Số lượng là **chuỗi** (`"6.000"`), số tiền là chuỗi 2 chữ số thập phân (`"200000.00"`). Mọi endpoint ghi dùng `version_no` làm khóa lạc quan: lệch trả `409 VERSION_CONFLICT` kèm `details.current_version_no`.

## 1. Luồng tổng quan

```
ERP mock -> PO, ASN (A gọi receive_purchase_order / receive_asn)
nv-nhan: POST /grns -> POST /grns/{id}/lines (lặp) -> POST /grns/{id}/submit
    submit: lệch bằng 0 và không có điều kiện buộc duyệt -> APPROVED ngay
            còn lại -> approvals tính tầng (D1/D2/D3) -> PENDING_Dx, pallet QUARANTINE_HOLD
    duyệt xong (trigger DB đồng bộ) -> APPROVED, PO cập nhật qty_received
    người duyệt gọi request-info với request_recount=true (hồ sơ NEED_INFO) -> POST /grns/{id}/recount (người khác đếm) -> tính lại, gửi duyệt lại
nv-nhan: POST /grns/{id}/complete -> nhập tồn tại cửa nhận, pallet STAGED, task PUTAWAY
nv-cat: POST /putaway/suggest -> POST /pallets/{id}/putaway -> pallet STORED
```

Trạng thái GRN: `COUNTING` -> `PENDING_D1/D2/D3` hoặc `APPROVED` -> `CLOSED`; nhánh từ chối `REJECTED`. Sau khi gửi duyệt, trạng thái `PENDING_Dx`, `APPROVED`, `REJECTED` do trigger của DB đồng bộ từ `approval_requests`, service không tự đặt (trừ `APPROVED` khi không cần duyệt).

## 2. Đếm mù (đặc tả 5.4.9)

Khi `is_blind_receipt` là true (mặc định), với vai **nv-nhan** server trả `null` cho: `qty_expected`, `qty_variance`, `variance_amount` (dòng GRN), `has_discrepancy`, `total_discrepancy_amount` (phiếu), và `qty_ordered`, `qty_received` (dòng PO). Thủ kho và quản lý thấy đủ. Lỗi `INBOUND_OVER_RECEIPT` cố ý không kèm số lượng.

nv-nhan chỉ thấy và thao tác phiếu do chính mình nhận (`403 FORBIDDEN` nếu mở phiếu người khác), trừ `recount` (xem mục 5).

## 3. PO và ASN (B-03)

| Phương thức và đường dẫn | Mục đích | Quyền (mã chờ chốt, xem ghi chú dưới) |
|---|---|---|
| `GET /purchase-orders` | Danh sách PO; lọc `status`, `supplier_id`; sắp xếp `created_at`, `expected_date`, `erp_po_number` | QL-2.1 |
| `GET /purchase-orders/{po_id}` | Chi tiết kèm dòng (số lượng ẩn với nv-nhan) | QL-2.1 |
| `GET /asns` | Danh sách ASN; lọc `status`, `po_id` | QL-2.3 |
| `GET /asns/{asn_id}` | Chi tiết ASN | QL-2.3 |

> **Ghi chú mã quyền (chờ chốt với A).** Seed `01_roles_permissions.sql` hiện chỉ có `NH-1` và `QL-2.1`. Các mã `NH-2`, `NH-5`, `CT-1`, `QL-2.3` dùng trong tài liệu này **chưa có trong seed**; nếu dùng vào `require_permission` thì mọi người nhận `403`. Cách xử lý (bổ sung mã vào seed hoặc dùng mã đã có) do A xác nhận; tài liệu sẽ cập nhật theo.

PO và ASN **không có endpoint tạo**: ERP mock đẩy sang, router tích hợp của A gọi hai hàm công khai `inbound.receive_purchase_order(db, warehouse_id, data, actor_id)` và `inbound.receive_asn(...)`.

### 1. GET /api/v1/purchase-orders
### 2. GET /api/v1/purchase-orders/{po_id}
### 3. GET /api/v1/asns
### 4. GET /api/v1/asns/{asn_id}

Lỗi: `INBOUND_PO_DUPLICATE` 409, `INBOUND_ASN_DUPLICATE` 409, `NOT_FOUND` 404 (NCC, SKU, cửa nhận, khu nhận không hợp lệ).

ASN do chuyển kho (cột `source_outbound_order_id`, patch v4.2.1) cũng đọc được qua hai endpoint này. Schema chưa có bảng dòng ASN, nên khi nhận chỉ theo ASN (không PO) mọi dòng đếm bị coi là ngoài dự kiến và luôn đi vào duyệt.

## 4. Phiếu nhận GRN (B-04)

| Phương thức và đường dẫn | Mục đích | Quyền (mã chờ chốt, xem ghi chú dưới) |
|---|---|---|
| `POST /grns` | Mở phiếu từ PO hoặc ASN (201) | NH-1 |
| `GET /grns` | Danh sách; lọc `status`, `po_id`; nv-nhan chỉ thấy phiếu của mình | NH-1 |
| `GET /grns/{grn_id}` | Chi tiết kèm dòng | NH-1 |
| `POST /grns/{grn_id}/lines` | Thêm một dòng đếm (201) | NH-2 |

### 5. POST /api/v1/grns
### 6. GET /api/v1/grns
### 7. GET /api/v1/grns/{grn_id}

Chi tiết `POST /grns`:
```
{"po_id": "…", "asn_id": null}
```
Gửi `asn_id` thì PO lấy từ ASN (nếu gửi cả hai phải khớp). Không gửi cả hai là nhận không chứng từ: chỉ được khi `blind_receipt_policy` của kho là `WARN_HOLD_D1` (khi đó phiếu luôn phải duyệt D1), còn `REJECT` trả `409 INBOUND_NO_PO_NOT_ALLOWED`. Phiếu mở ở trạng thái `COUNTING`; PO chuyển `RECEIVING`, ASN chuyển `RECEIVING`.

### 8. POST /api/v1/grns/{grn_id}/lines
```
{"sku_id": "…", "lot_number": "L240901", "expiry_date": "2027-09-01", "manufacture_date": null,
 "uom_code": "PCS", "qty_actual": "6", "qty_damaged": "1", "reason_code": "DAMAGED",
 "serial_numbers": null, "damage_photo_urls": [], "notes": null, "version_no": 1}
```
- Lô: gửi `lot_id` (lô đã có) **hoặc** `lot_number` (+ `expiry_date`); lô mới tự được tạo. So với chuẩn API 4.5 (chỉ có `lot_id`), đây là mở rộng vì lô hàng nhập mới chưa tồn tại trong hệ thống.
- `po_line_id` không bắt buộc: server tự ghép dòng PO theo SKU và đơn vị; không ghép được thì là hàng ngoài PO (luôn bị đưa vào duyệt).
- Mỗi dòng tăng `version_no` của phiếu. Dòng đếm lặp cùng SKU/lô được phép, hệ thống cộng dồn khi nộp.
- SKU quản lý serial: `serial_numbers` bắt buộc, đúng bằng `qty_actual`, không trùng trong phiếu, và chưa hỗ trợ `qty_damaged` > 0.

| HTTP | Mã lỗi | Khi nào |
|---|---|---|
| 404 | `NOT_FOUND` | PO/ASN/SKU/lô/mã lý do không tồn tại |
| 403 | `FORBIDDEN` | nv-nhan mở phiếu của người khác |
| 409 | `INBOUND_PO_CLOSED`, `INBOUND_ASN_CLOSED`, `INBOUND_PO_ASN_MISMATCH` | Mở phiếu sai chứng từ |
| 409 | `INBOUND_SKU_NOT_IN_PO`, `INBOUND_UOM_MISMATCH` | `po_line_id` gửi lên không khớp |
| 409 | `INBOUND_LOT_EXPIRY_MISMATCH` | Lô đã có với hạn dùng khác |
| 409 | `INBOUND_SHELF_LIFE_VIOLATION` | Hạn dùng còn lại thấp hơn mức tối thiểu của nhóm hàng đặt `BLOCK` (đặt `WARN` thì nhận nhưng buộc duyệt) |
| 409 | `INVALID_STATE` | Phiếu không còn ở `COUNTING` |
| 409 | `VERSION_CONFLICT` | `version_no` cũ |
| 422 | `INBOUND_LOT_REQUIRED`, `INBOUND_EXPIRY_REQUIRED` | Thiếu lô hoặc hạn dùng |
| 422 | `INBOUND_REASON_REQUIRED` | Có hàng hư mà không có mã lý do |
| 422 | `INBOUND_SERIAL_MISMATCH` | Serial sai số lượng, trùng, hoặc SKU không quản lý serial |
| 422 | `VALIDATION_ERROR` | `qty_damaged` lớn hơn `qty_actual` |

## 5. Xử lý lệch và đếm lại (B-05)

| Phương thức và đường dẫn | Mục đích | Quyền (mã chờ chốt, xem ghi chú dưới) |
|---|---|---|
| `POST /grns/{grn_id}/submit` | Nộp phiếu đã đếm xong | NH-1 |
| `POST /grns/{grn_id}/recount` | Đếm lại các dòng của phiếu đang chờ duyệt | NH-5 |

### 9. POST /api/v1/grns/{grn_id}/submit

Body `{"version_no": 4}`.

**Định nghĩa số đếm.** `qty_actual` là tổng số đếm được và **đã gồm** hàng hư; `qty_damaged` là phần hư nằm trong `qty_actual`. Hàng đạt = `qty_actual - qty_damaged`.

Server tính theo từng dòng PO: số dự kiến = `qty_ordered - qty_received` của dòng PO; các dòng đếm cùng một dòng PO được cộng gộp (`qty_actual`, `qty_damaged`) rồi so với số dự kiến một lần. Giá trị lệch = `(|tổng qty_actual - dự kiến| + tổng qty_damaged) x unit_cost` của SKU. Khi đếm ít hơn dự kiến, công thức bằng đúng `(dự kiến - hàng đạt) x unit_cost`, hàng hư không bị tính hai lần; khi đếm nhiều hơn dự kiến, phần hư được cộng thêm (cách tính thận trọng). Tổng và phần trăm so với giá trị dự kiến gửi `approvals` để quyết tầng.

Buộc duyệt (kể cả lệch bằng 0 hay nằm trong dung sai): có hàng hư, nhận không PO/ASN, hạn dùng vi phạm mức tối thiểu (nhóm `WARN`). Hàng ngoài PO có lệch lớn hơn 0 nên cũng bị duyệt.

```
200 {"data": {"grn_id": "…", "status": "PENDING_D1", "outcome": "PENDING_APPROVAL",
              "tier": "D1_THUKHO", "approval_id": "…", "recount_count": 0, "version_no": 6}}
```
`outcome` là `AUTO_APPROVED` (status `APPROVED`, `tier` null hoặc `AUTO_TOLERANCE_Z`) hoặc `PENDING_APPROVAL`. Gửi duyệt thì mỗi dòng có hàng đạt được gắn pallet `QUARANTINE_HOLD`, hàng hư gắn pallet `DAMAGED_HOLD`, `grn_lines.is_quarantined = true`, **chưa nhập tồn**. Nếu từ chối, trigger chuyển pallet `QUARANTINE_HOLD` sang `REJECTED_PENDING_RETURN`.

### 10. POST /api/v1/grns/{grn_id}/recount
```
{"version_no": 6, "lines": [{"grn_line_id": "…", "qty_actual": "10", "qty_damaged": "0"}]}
```
Chỉ đếm lại được khi hồ sơ duyệt của GRN đang `NEED_INFO` do người duyệt yêu cầu đếm lại (`request-info` với `request_recount=true`); các trường hợp khác trả `409 INVALID_STATE`. Điều kiện này khớp `supersede_approval_for_recount` bên `approvals` và đặc tả NH-5 (đếm lại khi bị yêu cầu). Người đếm lại phải khác người đếm gần nhất, trừ khi `allow_same_counter_recount` của kho bật. Số lần đếm lại tối đa là `max_recount_attempts` (mặc định 2); hết lượt thì cấp duyệt quyết định. Hồ sơ duyệt cũ được thay bằng `supersede_approval_for_recount` (`SUPERSEDED`), mỗi lần đếm ghi một dòng `grn_count_attempts`, rồi tính lại và gửi duyệt lại như `submit` (có thể tự duyệt nếu đã đúng). Điều kiện này cần Hiếu (D) xác nhận. `recount` là ngoại lệ của quy tắc "chỉ phiếu của mình": nv-nhan khác được đếm lại.

Lỗi: `INBOUND_GRN_EMPTY` 409, `INBOUND_OVER_RECEIPT` 409 (số hàng đạt cộng với đã nhận vượt đơn quá `over_receipt_tolerance_pct`; chặn sớm vì trigger DB sẽ ném `NHAN_DU_VUOT_DUNG_SAI` lúc duyệt), `INBOUND_RECOUNT_SAME_COUNTER` 409, `INBOUND_RECOUNT_LIMIT` 409, `INVALID_STATE` 409, `VERSION_CONFLICT` 409.

## 6. Hoàn tất GRN (B-06)

| Phương thức và đường dẫn | Mục đích | Quyền (mã chờ chốt, xem ghi chú dưới) |
|---|---|---|
| `POST /grns/{grn_id}/complete` | Nhập tồn, pallet STAGED, sinh task cất | NH-1 |

### 11. POST /api/v1/grns/{grn_id}/complete

Vai trò: `nv-nhan`, đúng chuẩn API mục 4.5. Phần ghi tồn sau khi duyệt GRN do `inbound` làm (chốt việc còn treo từ PR #15).

Body `{"version_no": 7}`. Chỉ phiếu `APPROVED`. Một transaction: nhập `RECEIVE` hàng đạt tại cửa nhận (cửa của ASN nếu có, nếu không là vị trí đầu tiên khu `RECEIVING_DOCK`), hàng hư vào bucket `qty_damaged` của pallet `DAMAGED_HOLD` riêng, pallet hàng đạt sang `STAGED`, mỗi pallet hàng đạt một task `PUTAWAY` chưa giao (`UNASSIGNED`), GRN sang `CLOSED`, ASN sang `COMPLETED`. Hàng có serial nhập từng serial một.

```
200 {"data": {"grn_id": "…", "status": "CLOSED", "version_no": 8,
              "pallets": [{"pallet_id": "…", "pallet_code": "GRN-20261122-AB12CD-P01",
                           "label_barcode": "GRN-20261122-AB12CD-P01", "status": "STAGED",
                           "current_location_id": "…", "version_no": 2}]}}
```
Sau `complete`, `approval_requests.execution_status` vẫn là `WAITING_EXECUTION`. Ai cập nhật sang trạng thái đã thực thi (ví dụ thêm hàm công khai bên `approvals`) **chờ thống nhất với Hiếu (D)**.

Lỗi: `INBOUND_GRN_NOT_APPROVED` 409 (chưa duyệt hoặc đã hoàn tất), `INBOUND_NO_DOCK_LOCATION` 409, `VERSION_CONFLICT` 409.

## 7. Cất hàng (B-07)

| Phương thức và đường dẫn | Mục đích | Quyền (mã chờ chốt, xem ghi chú dưới) |
|---|---|---|
| `POST /putaway/suggest` | Gợi ý vị trí cất | CT-1 |
| `POST /pallets/{pallet_id}/putaway` | Xác nhận cất | CT-1 |

### 12. POST /api/v1/putaway/suggest

Body `{"pallet_id": "…"}`.
Trả tối đa 5 vị trí: khu đúng yêu cầu bảo quản (`NORMAL` vào `STORAGE`, `COLD` vào `COLD`, `HAZMAT` vào `HAZMAT`; pallet trộn lấy yêu cầu khắt khe nhất), vị trí `EMPTY` hoặc `PARTIAL`, đang hoạt động, loại trừ vị trí hiện tại. Thứ tự: nơi đã có cùng SKU trước (gom hàng), rồi nơi đã đầy hơn, rồi theo mã vị trí.

### 13. POST /api/v1/pallets/{pallet_id}/putaway
```
{"location_id": "…", "scanned_pallet_code": "GRN-…-P01", "scanned_location_barcode": "A-01-02",
 "lines": null, "version_no": 2}
```
`lines` bỏ trống là cất cả pallet; gửi `[{sku_id, lot_id, serial_number, qty}]` là cất một phần (pallet ở `PUTAWAY_IN_PROGRESS` đến khi cất hết thì `STORED`). Tồn chuyển bằng `transfer_inventory` với `tx_type = PUTAWAY`.

Lỗi: `INBOUND_PALLET_NOT_PUTAWAYABLE` 409 (không ở STAGED/PUTAWAY_IN_PROGRESS), `INBOUND_PALLET_EMPTY` 409, `INBOUND_WRONG_PALLET` 409, `INBOUND_WRONG_LOCATION` 409 (mã quét sai hoặc trùng vị trí hiện tại), `INBOUND_LOCATION_FULL` 409, `INBOUND_LOCATION_LOCKED` 409, `INBOUND_LOCATION_ZONE_MISMATCH` 409, `INBOUND_PUTAWAY_QTY_EXCEEDS` 409, `NOT_FOUND` 404, `VERSION_CONFLICT` 409.

## 8. Hợp đồng với module khác

Chữ ký lấy từ code thật trên `develop`.

`approvals` (D), xem `docs/api/approvals.md`:
- `create_approval_request(db, warehouse_id, object_type, object_id, proposer_user_id, discrepancy_amount, discrepancy_percent=0, force_review=False)` trả `ApprovalRequest`, hoặc `None` khi lệch nằm trong dung sai Z (không tạo yêu cầu, GRN tự duyệt).
- `supersede_approval_for_recount(db, approval_id, warehouse_id, actor_user_id, note)` thay hồ sơ cũ khi đếm lại.
- `resubmit_approval_info(...)` gửi lại thông tin cho hồ sơ `NEED_INFO`.

`tasks` (D): `create_task(db, warehouse_id, creator_id, req: CreateTaskRequest)`, trong đó `req` gồm `task_type`, `stage`, `ref_doc_type`, `ref_doc_id`, `zone_id`, `priority`. Không có `assigned_to`; task tạo ra ở trạng thái `UNASSIGNED`.

`master_data` (A, PR #17): `get_warehouse_config(db, warehouse_id)` trả dict (NUMERIC giữ kiểu `Decimal`); ngoài ra có `get_sku`, `get_location`.

`inventory` (A):
- `apply_movement(db, warehouse_id, location_id, sku_id, lot_id, pallet_id, serial_number, tx_type, delta_available=0, delta_allocated=0, delta_counting=0, delta_locked=0, delta_damaged=0, ref_doc_type="MANUAL", ref_doc_id, performed_by)`. Inbound dùng với `tx_type="RECEIVE"`.
- `transfer_inventory(db, warehouse_id, from_location_id, to_location_id, sku_id, lot_id, pallet_id, serial_number, qty, tx_type, ref_doc_type, ref_doc_id, performed_by, bucket)`. Inbound dùng với `tx_type="PUTAWAY"`, `bucket="AVAILABLE"`. *(Tên tham số theo lời gọi hiện tại của inbound; đối chiếu lại với `server/app/modules/inventory/services.py` trên `develop` trước khi gộp.)*
