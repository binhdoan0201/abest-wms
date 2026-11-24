# API inbound (người B, B-03 đến B-07)

Tiền tố: `/api/v1`. Response theo chuẩn `docs/api/_conventions.md`. Số lượng là **chuỗi** (`"6.000"`), số tiền là chuỗi 2 chữ số thập phân (`"200000.00"`). Mọi endpoint ghi dùng `version_no` làm khóa lạc quan: lệch trả `409 VERSION_CONFLICT` kèm `details.current_version_no`.

## 1. Luồng tổng quan

```
ERP mock -> PO, ASN (A gọi receive_purchase_order / receive_asn)
nv-nhan: POST /grns -> POST /grns/{id}/lines (lặp) -> POST /grns/{id}/submit
    submit: lệch bằng 0 và không có điều kiện buộc duyệt -> APPROVED ngay
            còn lại -> approvals tính tầng (D1/D2/D3) -> PENDING_Dx, pallet QUARANTINE_HOLD
    duyệt xong (trigger DB đồng bộ) -> APPROVED, PO cập nhật qty_received
    người duyệt yêu cầu đếm lại -> POST /grns/{id}/recount (người khác đếm) -> tính lại, gửi duyệt lại
nv-nhan/thukho: POST /grns/{id}/complete -> nhập tồn tại cửa nhận, pallet STAGED, task PUTAWAY
nv-cat: POST /putaway/suggest -> POST /pallets/{id}/putaway -> pallet STORED
```

Trạng thái GRN: `COUNTING` -> `PENDING_D1/D2/D3` hoặc `APPROVED` -> `CLOSED`; nhánh từ chối `REJECTED`. Sau khi gửi duyệt, trạng thái `PENDING_Dx`, `APPROVED`, `REJECTED` do trigger của DB đồng bộ từ `approval_requests`, service không tự đặt (trừ `APPROVED` khi không cần duyệt).

## 2. Đếm mù (đặc tả 5.4.9)

Khi `is_blind_receipt` là true (mặc định), với vai **nv-nhan** server trả `null` cho: `qty_expected`, `qty_variance`, `variance_amount` (dòng GRN), `has_discrepancy`, `total_discrepancy_amount` (phiếu), và `qty_ordered`, `qty_received` (dòng PO). Thủ kho và quản lý thấy đủ. Lỗi `INBOUND_OVER_RECEIPT` cố ý không kèm số lượng.

nv-nhan chỉ thấy và thao tác phiếu do chính mình nhận (`403 FORBIDDEN` nếu mở phiếu người khác), trừ `recount` (xem mục 5).

## 3. PO và ASN (B-03)

| Phương thức và đường dẫn | Mục đích | Quyền (QL-2.1, QL-2.3 theo đặc tả; còn lại đoán) |
|---|---|---|
| `GET /purchase-orders` | Danh sách PO; lọc `status`, `supplier_id`; sắp xếp `created_at`, `expected_date`, `erp_po_number` | QL-2.1 |
| `GET /purchase-orders/{po_id}` | Chi tiết kèm dòng (số lượng ẩn với nv-nhan) | QL-2.1 |
| `GET /asns` | Danh sách ASN; lọc `status`, `po_id` | QL-2.3 |
| `GET /asns/{asn_id}` | Chi tiết ASN | QL-2.3 |

PO và ASN **không có endpoint tạo**: ERP mock đẩy sang, router tích hợp của A gọi hai hàm công khai `inbound.receive_purchase_order(db, warehouse_id, data, actor_id)` và `inbound.receive_asn(...)`.

Lỗi: `INBOUND_PO_DUPLICATE` 409, `INBOUND_ASN_DUPLICATE` 409, `NOT_FOUND` 404 (NCC, SKU, cửa nhận, khu nhận không hợp lệ).

ASN do chuyển kho (cột `source_outbound_order_id`, patch v4.2.1) cũng đọc được qua hai endpoint này. Schema chưa có bảng dòng ASN, nên khi nhận chỉ theo ASN (không PO) mọi dòng đếm bị coi là ngoài dự kiến và luôn đi vào duyệt.

## 4. Phiếu nhận GRN (B-04)

| Phương thức và đường dẫn | Mục đích | Quyền (QL-2.1, QL-2.3 theo đặc tả; còn lại đoán) |
|---|---|---|
| `POST /grns` | Mở phiếu từ PO hoặc ASN (201) | NH-1 |
| `GET /grns` | Danh sách; lọc `status`, `po_id`; nv-nhan chỉ thấy phiếu của mình | NH-1 |
| `GET /grns/{grn_id}` | Chi tiết kèm dòng | NH-1 |
| `POST /grns/{grn_id}/lines` | Thêm một dòng đếm (201) | NH-2 |

### POST /grns
```
{"po_id": "…", "asn_id": null}
```
Gửi `asn_id` thì PO lấy từ ASN (nếu gửi cả hai phải khớp). Không gửi cả hai là nhận không chứng từ: chỉ được khi `blind_receipt_policy` của kho là `WARN_HOLD_D1` (khi đó phiếu luôn phải duyệt D1), còn `REJECT` trả `409 INBOUND_NO_PO_NOT_ALLOWED`. Phiếu mở ở trạng thái `COUNTING`; PO chuyển `RECEIVING`, ASN chuyển `RECEIVING`.

### POST /grns/{grn_id}/lines
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

| Phương thức và đường dẫn | Mục đích | Quyền (QL-2.1, QL-2.3 theo đặc tả; còn lại đoán) |
|---|---|---|
| `POST /grns/{grn_id}/submit` | Nộp phiếu đã đếm xong | NH-1 |
| `POST /grns/{grn_id}/recount` | Đếm lại các dòng của phiếu đang chờ duyệt | NH-5 |

### POST /grns/{grn_id}/submit  body `{"version_no": 4}`
Server tính, theo từng dòng PO: số dự kiến = `qty_ordered - qty_received` của dòng PO (nhiều dòng đếm cùng dòng PO chỉ tính dự kiến một lần); giá trị lệch của dòng = `(|thực đếm - dự kiến| + hàng hư) x unit_cost` của SKU; tổng và phần trăm so với giá trị dự kiến gửi `approvals` để quyết tầng.

Buộc duyệt (kể cả lệch bằng 0 hay nằm trong dung sai): có hàng hư, nhận không PO/ASN, hạn dùng vi phạm mức tối thiểu (nhóm `WARN`). Hàng ngoài PO có lệch lớn hơn 0 nên cũng bị duyệt.

```
200 {"data": {"grn_id": "…", "status": "PENDING_D1", "outcome": "PENDING_APPROVAL",
              "tier": "D1_THUKHO", "approval_id": "…", "recount_count": 0, "version_no": 6}}
```
`outcome` là `AUTO_APPROVED` (status `APPROVED`, `tier` null hoặc `AUTO_TOLERANCE_Z`) hoặc `PENDING_APPROVAL`. Gửi duyệt thì mỗi dòng có hàng đạt được gắn pallet `QUARANTINE_HOLD`, hàng hư gắn pallet `DAMAGED_HOLD`, `grn_lines.is_quarantined = true`, **chưa nhập tồn**. Nếu từ chối, trigger chuyển pallet `QUARANTINE_HOLD` sang `REJECTED_PENDING_RETURN`.

### POST /grns/{grn_id}/recount
```
{"version_no": 6, "lines": [{"grn_line_id": "…", "qty_actual": "10", "qty_damaged": "0"}]}
```
Chỉ khi phiếu `PENDING_D1/D2/D3`. Người đếm lại phải khác người đếm gần nhất, trừ khi `allow_same_counter_recount` của kho bật. Số lần đếm lại tối đa là `max_recount_attempts` (mặc định 2); hết lượt thì cấp duyệt quyết định. Yêu cầu duyệt đang mở bị thay (`SUPERSEDED`), mỗi lần đếm ghi một dòng `grn_count_attempts`, rồi tính lại và gửi duyệt lại như `submit` (có thể tự duyệt nếu đã đúng). `recount` là ngoại lệ của quy tắc "chỉ phiếu của mình": nv-nhan khác được đếm lại.

Lỗi: `INBOUND_GRN_EMPTY` 409, `INBOUND_OVER_RECEIPT` 409 (số hàng đạt cộng với đã nhận vượt đơn quá `over_receipt_tolerance_pct`; chặn sớm vì trigger DB sẽ ném `NHAN_DU_VUOT_DUNG_SAI` lúc duyệt), `INBOUND_RECOUNT_SAME_COUNTER` 409, `INBOUND_RECOUNT_LIMIT` 409, `INVALID_STATE` 409, `VERSION_CONFLICT` 409.

## 6. Hoàn tất GRN (B-06)

| Phương thức và đường dẫn | Mục đích | Quyền (QL-2.1, QL-2.3 theo đặc tả; còn lại đoán) |
|---|---|---|
| `POST /grns/{grn_id}/complete` | Nhập tồn, pallet STAGED, sinh task cất | NH-1 |

Body `{"version_no": 7}`. Chỉ phiếu `APPROVED`. Một transaction: nhập `RECEIVE` hàng đạt tại cửa nhận (cửa của ASN nếu có, nếu không là vị trí đầu tiên khu `RECEIVING_DOCK`), hàng hư vào bucket `qty_damaged` của pallet `DAMAGED_HOLD` riêng, pallet hàng đạt sang `STAGED`, mỗi pallet hàng đạt một task `PUTAWAY` chưa giao (`UNASSIGNED`), GRN sang `CLOSED`, ASN sang `COMPLETED`. Hàng có serial nhập từng serial một.

```
200 {"data": {"grn_id": "…", "status": "CLOSED", "version_no": 8,
              "pallets": [{"pallet_id": "…", "pallet_code": "GRN-20261122-AB12CD-P01",
                           "label_barcode": "GRN-20261122-AB12CD-P01", "status": "STAGED",
                           "current_location_id": "…", "version_no": 2}]}}
```
Lỗi: `INBOUND_GRN_NOT_APPROVED` 409 (chưa duyệt hoặc đã hoàn tất), `INBOUND_NO_DOCK_LOCATION` 409, `VERSION_CONFLICT` 409.

## 7. Cất hàng (B-07)

| Phương thức và đường dẫn | Mục đích | Quyền (QL-2.1, QL-2.3 theo đặc tả; còn lại đoán) |
|---|---|---|
| `POST /putaway/suggest` | Gợi ý vị trí cất | CT-1 |
| `POST /pallets/{pallet_id}/putaway` | Xác nhận cất | CT-1 |

### POST /putaway/suggest  body `{"pallet_id": "…"}`
Trả tối đa 5 vị trí: khu đúng yêu cầu bảo quản (`NORMAL` vào `STORAGE`, `COLD` vào `COLD`, `HAZMAT` vào `HAZMAT`; pallet trộn lấy yêu cầu khắt khe nhất), vị trí `EMPTY` hoặc `PARTIAL`, đang hoạt động, loại trừ vị trí hiện tại. Thứ tự: nơi đã có cùng SKU trước (gom hàng), rồi nơi đã đầy hơn, rồi theo mã vị trí.

### POST /pallets/{pallet_id}/putaway
```
{"location_id": "…", "scanned_pallet_code": "GRN-…-P01", "scanned_location_barcode": "A-01-02",
 "lines": null, "version_no": 2}
```
`lines` bỏ trống là cất cả pallet; gửi `[{sku_id, lot_id, serial_number, qty}]` là cất một phần (pallet ở `PUTAWAY_IN_PROGRESS` đến khi cất hết thì `STORED`). Tồn chuyển bằng `transfer_inventory` với `tx_type = PUTAWAY`.

Lỗi: `INBOUND_PALLET_NOT_PUTAWAYABLE` 409 (không ở STAGED/PUTAWAY_IN_PROGRESS), `INBOUND_PALLET_EMPTY` 409, `INBOUND_WRONG_PALLET` 409, `INBOUND_WRONG_LOCATION` 409 (mã quét sai hoặc trùng vị trí hiện tại), `INBOUND_LOCATION_FULL` 409, `INBOUND_LOCATION_LOCKED` 409, `INBOUND_LOCATION_ZONE_MISMATCH` 409, `INBOUND_PUTAWAY_QTY_EXCEEDS` 409, `NOT_FOUND` 404, `VERSION_CONFLICT` 409.

## 8. Hợp đồng với module khác (cần A và D xác nhận)

`approvals` (D): `submit_for_approval(db, *, warehouse_id, object_type, object_id, proposer_user_id, amount, percent, force_review)` trả đối tượng có `tier` (`AUTO_TOLERANCE_Z`, `D1_THUKHO`, `D2_QUANLY`, `D3_BGD`) và `approval_id` (None khi `AUTO_TOLERANCE_Z`, không tạo yêu cầu); `supersede_open_request(db, *, object_type, object_id, actor_id)` chuyển yêu cầu đang mở sang `SUPERSEDED`.
`inventory` (A): `apply_movement`, `transfer_inventory` theo chữ ký C đã dùng.
`tasks` (D): `create_task(db, *, warehouse_id, task_type, stage, ref_doc_type, ref_doc_id, priority, assigned_to, assigned_by)` chấp nhận `assigned_to=None`.
`master_data` (B): `get_config_for_warehouse(db, warehouse_id)`.
