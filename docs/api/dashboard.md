# Hợp đồng API Module: Bảng điều hành (Dashboard)

- **Chủ module:** Thành viên D
- **Nhánh phụ trách:** `feature/dashboard`
- **Mã module:** M9 (`dashboard`)

---

## Danh mục Endpoint

### 1. GET /api/v1/dashboard/tasks
- **Mục đích:** Xem số liệu tổng quan về các nhiệm vụ kho (tổng số, đang chờ, đang thực hiện, hoàn thành, phân bổ theo loại nhiệm vụ).
- **Vai trò:** `thukho`, `quanly`, `bgd` (QL-8.1).
- **Phản hồi 200:** Dữ liệu thống kê nhiệm vụ theo thời gian thực.
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/dashboard/inventory
- **Mục đích:** Xem số liệu tổng quan về tồn kho (số lượng SKU, vị trí sử dụng, tỷ lệ lấp đầy, cảnh báo hạn sử dụng/cận date).
- **Vai trò:** `thukho`, `quanly`, `bgd` (QL-8.1).
- **Phản hồi 200:** Thống kê tồn kho và tỷ lệ lấp đầy kho.
- **Lỗi:** FORBIDDEN 403.

### 3. GET /api/v1/dashboard/orders
- **Mục đích:** Xem số liệu tổng quan đơn nhập/xuất (đơn PO mở, SO mở, số lượng hồ sơ chờ duyệt, tỷ lệ hoàn tất đơn trong ngày).
- **Vai trò:** `thukho`, `quanly`, `bgd` (QL-8.1).
- **Phản hồi 200:** Thống kê tiến độ đơn hàng nhập xuất.
- **Lỗi:** FORBIDDEN 403.
