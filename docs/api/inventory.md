# Hợp đồng API Module: Quản lý Tồn kho (Inventory)

- **Chủ module:** Thành viên A
- **Nhánh phụ trách:** `feature/inventory`
- **Mã module:** M1 (`inventory`)

---

## Nguyên tắc nghiệp vụ
Không có endpoint ghi tồn kho công khai qua HTTP: Mọi biến động tồn kho bắt buộc thực hiện qua hai hàm CSDL PostgreSQL `fn_apply_inventory_movement` và `fn_transfer_inventory` được gọi độc quyền bởi `InventoryService` trong cùng transaction với chứng từ nghiệp vụ tương ứng.

---

## Danh mục Endpoint

### 1. GET /api/v1/inventory/balances
- **Mục đích:** Tra cứu số dư tồn kho theo SKU, vị trí lưu trữ, lô hàng và trạng thái kiểm soát chất lượng (`?sku_id=&location_id=&lot_id=`).
- **Vai trò:** `nv-nhan`, `nv-cat`, `nv-soan`, `nv-dongoi`, `thukho`, `quanly`, `bgd` (QL-1.1).
- **Phản hồi 200:** Danh sách số dư tồn kho (`qty_on_hand`, `qty_allocated`, `qty_available`, `status`).
- **Lỗi:** FORBIDDEN 403.

### 2. GET /api/v1/inventory/transactions
- **Mục đích:** Xem sổ cái lịch sử các giao dịch biến động tồn kho (append-only ledger).
- **Vai trò:** `thukho`, `quanly` (QL-1.1).
- **Phản hồi 200:** Danh sách bản ghi giao dịch biến động tồn kho.
- **Lỗi:** FORBIDDEN 403.

### 3. GET /api/v1/lots
- **Mục đích:** Danh sách các lô hàng, ngày sản xuất, hạn sử dụng và cảnh báo cận date.
- **Vai trò:** `thukho`, `quanly`, `nv-cat`, `nv-soan` (QL-1.1).
- **Phản hồi 200:** Danh sách lô hàng.
- **Lỗi:** FORBIDDEN 403.

### 4. GET /api/v1/pallets
- **Mục đích:** Xem danh sách pallet trong kho, vị trí hiện tại và trạng thái (EMPTY, STAGED, STORED...).
- **Vai trò:** `thukho`, `quanly`, `nv-nhan`, `nv-cat` (QL-1.1).
- **Phản hồi 200:** Danh sách pallet.
- **Lỗi:** FORBIDDEN 403.

### 5. GET /api/v1/pallets/{id}
- **Mục đích:** Xem chi tiết một pallet và danh sách hàng hóa/lô đang chứa trên pallet.
- **Vai trò:** `thukho`, `quanly`, `nv-nhan`, `nv-cat` (QL-1.1).
- **Phản hồi 200:** Chi tiết pallet.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.

### 6. GET /api/v1/locations/{id}/stock
- **Mục đích:** Tra cứu hàng hóa và pallet đang lưu trữ thực tế tại một vị trí ô kệ.
- **Vai trò:** `thukho`, `quanly`, `nv-cat`, `nv-soan` (QL-1.1).
- **Phản hồi 200:** Danh sách tồn kho tại vị trí chỉ định.
- **Lỗi:** NOT_FOUND 404, FORBIDDEN 403.
