# Hợp đồng API Module: Phê duyệt (Approvals)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/approvals`
- **Mã module:** M7 (`approvals`)

---

## Danh mục Endpoint

### 1. GET /api/v1/approvals
- **Mục đích:** Xem danh sách hàng chờ duyệt chênh lệch (`?status=&tier=&object_type=&expired=true`).
- **Vai trò:** `thukho` (D1), `quanly` (D2), `bgd` (D3).
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/approvals/{id}
- **Mục đích:** Xem chi tiết hồ sơ chênh lệch và lịch sử các lần duyệt/chuyển tiếp.
- **Vai trò:** `thukho`, `quanly`, `bgd`.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 3. POST /api/v1/approvals/{id}/approve
- **Mục đích:** Phê duyệt hồ sơ; gửi `reauth_method` nếu giá trị vượt ngưỡng xác thực lại.
- **Vai trò:** Đúng cấp được giao của yêu cầu (D1, D2 hoặc D3).
- **Request body:** `recommendation_or_reason`, `reauth_method`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ được cập nhật sang APPROVED hoặc chuyển tiếp cấp cao hơn.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409, REAUTH_REQUIRED 403, SOD_VIOLATION 403.

### 4. POST /api/v1/approvals/{id}/reject
- **Mục đích:** Từ chối phê duyệt hồ sơ kèm lý do.
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Request body:** `rejection_reason`, `version_no`.
- **Phản hồi 200:** Trạng thái hồ sơ chuyển sang REJECTED.
- **Lỗi:** NOT_FOUND 404, VERSION_CONFLICT 409.

### 5. POST /api/v1/approvals/{id}/request-info
- **Mục đích:** Trả về cho người lập hồ sơ yêu cầu bổ sung thông tin hoặc giải trình.
- **Vai trò:** Đúng cấp được giao của yêu cầu.
- **Phản hồi 200:** Hồ sơ chuyển sang INFO_REQUESTED.
- **Lỗi:** NOT_FOUND 404.

### 6. POST /api/v1/approvals/escalate-expired
- **Mục đích:** Kích hoạt quét và tự động leo thang SLA hồ sơ quá hạn (gọi hàm CSDL `fn_escalate_expired_approvals`).
- **Vai trò:** `quanly`.
- **Phản hồi 200:** `{"data": {"escalated_count": 5}}`.
- **Lỗi:** FORBIDDEN 403.
