# Hợp đồng API Module: Phê duyệt (Approvals)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/approvals`
- **Mã module:** M7 (`approvals`)

---

## Mã lỗi nghiệp vụ riêng của module
- `APPROVAL_LOCKED_BY_OTHER` (409): Hồ sơ đang được cán bộ duyệt khác mở xử lý (khóa có hiệu lực tối đa 15 phút).
- `REAUTH_REQUIRED` (403): Hồ sơ vượt ngưỡng `reauth_min_amount`, bắt buộc gửi `reauth_method` và `reauth_password`.
- `REAUTH_FAILED` (403): Mật khẩu xác thực lại không chính xác.
- `SOD_VIOLATION` (403): Người lập đề xuất không được tự phê duyệt/từ chối/chuyển tiếp hồ sơ của chính mình.

---

## Danh mục Endpoint

### 1. GET /api/v1/approvals
- **Mục đích:** Xem danh sách hàng chờ duyệt chênh lệch (`?status=&tier=&object_type=&expired=true&page=1&page_size=20`).
- **Vai trò:** `thukho` (D1), `quanly` (D2), `bgd` (D3).
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/approvals/{approval_id}
- **Mục đích:** Xem chi tiết hồ sơ chênh lệch và lịch sử các lần duyệt/chuyển tiếp. Khi `?lock=true` (mặc định) và người xem đúng tầng đang chờ duyệt, hệ thống tự động đặt khóa trong 15 phút (`locked_by_viewer_id`, `locked_at`) để tránh 2 người mở xử lý trùng phiếu.
- **Vai trò:** `thukho`, `quanly`, `bgd`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, APPROVAL_LOCKED_BY_OTHER 409.

### 3. POST /api/v1/approvals/{approval_id}/unlock
- **Mục đích:** Nhả khóa xem hồ sơ chủ động khi người duyệt rời màn hình chi tiết.
- **Vai trò:** `thukho`, `quanly`, `bgd` (người đang giữ khóa hoặc khi khóa đã quá hạn 15 phút).
- **Phản hồi 200:** Hồ sơ với `locked_by_viewer_id = null`.
- **Lỗi:** NOT_FOUND 404, APPROVAL_LOCKED_BY_OTHER 409, FORBIDDEN 403.

### 4. POST /api/v1/approvals/stock-adjustments
- **Mục đích:** Thủ kho đề xuất điều chỉnh tồn (`ADJUSTMENT`) hoặc hủy hàng (`SCRAP`).
- **Vai trò:** `thukho` (quyền `TK-4.3`).
- **Request body:** `adjustment_type`, `location_id`, `sku_id`, `lot_id`, `source_pallet_id`, `damaged_pallet_id`, `qty_adjustment`, `reason_code`, `proposal_photo_urls`.
- **Phản hồi 201:** Hồ sơ phê duyệt được tạo ở tầng `D2_QUANLY`.
- **Lỗi:** VALIDATION_ERROR 422, NOT_FOUND 404, FORBIDDEN 403.

### 5. POST /api/v1/approvals/{approval_id}/approve
- **Mục đích:** Phê duyệt hồ sơ ở tầng được phân luồng và chốt `APPROVED`; gửi kèm `reauth_method` + `reauth_password` nếu giá trị vượt ngưỡng xác thực lại; tự động thực thi hậu kiểm (`apply_movement` + hàng đợi ERP mock cho `STOCK_ADJUSTMENT`) hoặc đặt `WAITING_EXECUTION` cho `GRN_DISCREPANCY` / `CYCLE_COUNT_DIFF`.
- **Vai trò:** Đúng cấp được giao của yêu cầu (D1, D2 hoặc D3).
- **Request body:** `recommendation_or_reason`, `reauth_method`, `reauth_password`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ cập nhật sang `APPROVED`.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, APPROVAL_LOCKED_BY_OTHER 409, REAUTH_REQUIRED 403, REAUTH_FAILED 403, SOD_VIOLATION 403, FORBIDDEN 403.

### 6. POST /api/v1/approvals/{approval_id}/escalate
- **Mục đích:** Thủ kho (`D1_THUKHO`) chủ động chuyển tiếp hồ sơ lên Quản lý kho (`D2_QUANLY`), ghi lịch sử `ESCALATE_NEXT_TIER`.
- **Vai trò:** `thukho` (đúng tầng `D1_THUKHO`).
- **Request body:** `recommendation_or_reason`, `version_no`.
- **Phản hồi 200:** Hồ sơ chuyển sang `current_tier = D2_QUANLY`, `status = PENDING_D2`.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, APPROVAL_LOCKED_BY_OTHER 409, SOD_VIOLATION 403, FORBIDDEN 403.

### 7. POST /api/v1/approvals/{approval_id}/reject
- **Mục đích:** Từ chối phê duyệt hồ sơ kèm lý do.
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Request body:** `rejection_reason`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ chuyển sang `REJECTED`.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, APPROVAL_LOCKED_BY_OTHER 409, SOD_VIOLATION 403, FORBIDDEN 403.

### 8. POST /api/v1/approvals/{approval_id}/request-info
- **Mục đích:** Trả về cho người lập hồ sơ yêu cầu bổ sung thông tin, giải trình hoặc đếm lại (`request_recount`). Sau đó module gốc gọi `resubmit_approval_info` (đưa về `PENDING_*`) hoặc `supersede_approval_for_recount` (đưa về `SUPERSEDED`).
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Request body:** `info_required_note`, `request_recount`, `version_no`.
- **Phản hồi 200:** Hồ sơ chuyển sang `NEED_INFO`.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, APPROVAL_LOCKED_BY_OTHER 409, FORBIDDEN 403.

### 9. POST /api/v1/approvals/escalate-expired
- **Mục đích:** Kích hoạt quét và tự động leo thang SLA hồ sơ quá hạn (gọi hàm CSDL `fn_escalate_expired_approvals`). Lưu ý: hàm CSDL quét toàn cục các hồ sơ quá hạn trên hệ thống.
- **Vai trò:** `quanly`.
- **Phản hồi 200:** `{"data": {"escalated_count": 5}}`.
- **Lỗi:** FORBIDDEN 403.


---

## Hàm công khai liên module (Quy tắc 2.3)

Import từ `server.app.modules.approvals`:

1. `create_approval_request(db, warehouse_id, object_type, object_id, proposer_user_id, discrepancy_amount, discrepancy_percent=0, force_review=False) -> ApprovalRequest | None`: Khởi tạo hồ sơ duyệt hoặc trả `None` nếu nằm trong dung sai Z (`AUTO_TOLERANCE_Z`).
2. `resubmit_approval_info(db, approval_id, warehouse_id, actor_user_id, note, new_discrepancy_amount=None, new_discrepancy_percent=0) -> ApprovalRequest`: Mở lại hồ sơ từ `NEED_INFO` sang `PENDING_D*`.
3. `supersede_approval_for_recount(db, approval_id, warehouse_id, actor_user_id, note=...) -> ApprovalRequest`: Đóng hồ sơ `NEED_INFO` sang `SUPERSEDED` khi thực hiện đếm lại.
4. `update_approval_execution_status(db, approval_id, warehouse_id, actor_user_id, execution_status="EXECUTED_INVENTORY", note=None) -> ApprovalRequest`: Cập nhật `execution_status` sau khi phân hệ nguồn thực thi hậu kiểm (`WAITING_EXECUTION` -> `EXECUTED_INVENTORY`, hoặc cập nhật trạng thái đồng bộ ERP `SYNCED_ERP` / `FAILED_SYNC`).
5. `mark_object_approval_executed(db, warehouse_id, object_type, object_id, actor_user_id, execution_status="EXECUTED_INVENTORY", note=None) -> ApprovalRequest | None`: Cập nhật `execution_status` theo đối tượng nguồn (`GRN_DISCREPANCY`, `CYCLE_COUNT_DIFF`); trả `None` nếu đối tượng tự động duyệt qua dung sai Z nên không phát sinh bản ghi `approval_requests`.

### Chốt trách nhiệm ghi tồn hậu kiểm (Issue #24)

- **`STOCK_ADJUSTMENT`:** Do `approvals` tự gọi `apply_movement` và đẩy hàng đợi ERP ngay trong `POST /api/v1/approvals/{approval_id}/approve` (`execution_status = EXECUTED_INVENTORY`).
- **`GRN_DISCREPANCY`:** Khi duyệt xong, `approvals` đặt `execution_status = WAITING_EXECUTION`. Phân hệ `inbound` thực thi ghi tồn trong `POST /grns/{id}/complete` rồi gọi `mark_object_approval_executed(..., "GRN_DISCREPANCY", grn_id, ...)` để chuyển sang `EXECUTED_INVENTORY`.
- **`CYCLE_COUNT_DIFF`:** Khi duyệt xong, `approvals` đặt `execution_status = WAITING_EXECUTION`. Phân hệ `cycle_count` thực thi ghi tồn điều chỉnh kiểm kê (`apply_movement` với `tx_type="CYCLE_COUNT"`) rồi gọi `mark_object_approval_executed(..., "CYCLE_COUNT_DIFF", count_line_id, ...)` để chuyển sang `EXECUTED_INVENTORY`.
