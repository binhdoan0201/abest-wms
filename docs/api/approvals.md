# Hợp đồng API Module: Phê duyệt (Approvals)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/approvals`
- **Mã module:** M7 (`approvals`)

---

## Mã lỗi nghiệp vụ riêng của module
- `APPROVAL_LOCKED_BY_OTHER` (409): Hồ sơ đang được cán bộ duyệt khác mở xử lý.

---

## Danh mục Endpoint

### 1. GET /api/v1/approvals
- **Mục đích:** Xem danh sách hàng chờ duyệt chênh lệch (`?status=&tier=&object_type=&expired=true&page=1&page_size=20`).
- **Vai trò:** `thukho` (D1), `quanly` (D2), `bgd` (D3).
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/approvals/{approval_id}
- **Mục đích:** Xem chi tiết hồ sơ chênh lệch và lịch sử các lần duyệt/chuyển tiếp; tự động khóa phiếu khi mở xem (`?lock=true`).
- **Vai trò:** `thukho`, `quanly`, `bgd`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403, APPROVAL_LOCKED_BY_OTHER 409.

### 3. POST /api/v1/approvals/stock-adjustments
- **Mục đích:** Thủ kho hoặc Quản lý đề xuất điều chỉnh tồn (`ADJUSTMENT`) hoặc hủy hàng (`SCRAP`).
- **Vai trò:** `thukho`, `quanly`.
- **Request body:** `adjustment_type`, `location_id`, `sku_id`, `lot_id`, `source_pallet_id`, `damaged_pallet_id`, `qty_adjustment`, `reason_code`, `proposal_photo_urls`.
- **Phản hồi 201:** Hồ sơ phê duyệt được tạo ở tầng duyệt tương ứng.
- **Lỗi:** VALIDATION_ERROR 422, NOT_FOUND 404, FORBIDDEN 403.

### 4. POST /api/v1/approvals/{approval_id}/approve
- **Mục đích:** Phê duyệt hồ sơ; chuyển tiếp lên cấp cao hơn nếu vượt ngưỡng X/Y; gửi `reauth_method` nếu giá trị vượt ngưỡng xác thực lại; tự động thực thi hậu kiểm nếu là bước duyệt cuối.
- **Vai trò:** Đúng cấp được giao của yêu cầu (D1, D2 hoặc D3).
- **Request body:** `recommendation_or_reason`, `reauth_method`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ được cập nhật sang APPROVED hoặc chuyển tiếp cấp cao hơn (`PENDING_D2`, `PENDING_D3`).
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, REAUTH_REQUIRED 403, SOD_VIOLATION 403, FORBIDDEN 403.

### 5. POST /api/v1/approvals/{approval_id}/reject
- **Mục đích:** Từ chối phê duyệt hồ sơ kèm lý do.
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Request body:** `rejection_reason`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ chuyển sang REJECTED.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, SOD_VIOLATION 403, FORBIDDEN 403.

### 6. POST /api/v1/approvals/{approval_id}/request-info
- **Mục đích:** Trả về cho người lập hồ sơ yêu cầu bổ sung thông tin, giải trình hoặc đếm lại (`request_recount`).
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Request body:** `info_required_note`, `request_recount`, `version_no`.
- **Phản hồi 200:** Hồ sơ chuyển sang NEED_INFO.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, INVALID_STATE 409, FORBIDDEN 403.

### 7. POST /api/v1/approvals/escalate-expired
- **Mục đích:** Kích hoạt quét và tự động leo thang SLA hồ sơ quá hạn (gọi hàm CSDL `fn_escalate_expired_approvals`).
- **Vai trò:** `quanly`.
- **Phản hồi 200:** `{"data": {"escalated_count": 5}}`.
- **Lỗi:** FORBIDDEN 403.
