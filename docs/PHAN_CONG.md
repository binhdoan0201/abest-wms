# Bảng Phân Công Công Việc Dự Án ABEST WMS

## Danh sách Thành viên Nhóm

| Chữ cái | Họ và tên | GitHub Username | Vai trò |
| :---: | :--- | :--- | :--- |
| **A** | **Đoàn Duy Bình** | `@binhdoan0201` | Leader, Kiến trúc, Tích hợp, Quản trị kho mã |
| **B** | **Mai Hữu Phước** | `@HuuPhuoc1235` | Thành viên phát triển |
| **C** | **Hồ Quốc Cường** | `@quoccuong1108` | Thành viên phát triển |
| **D** | **Nguyễn Đức Hiếu** | `@hieunguyen201104` | Thành viên phát triển |

---

## 1. Tóm tắt Phân công (Mục 8.1 Đặc tả)

| Thành viên | Vai trò | Module | Giao diện client phụ trách |
| :--- | :--- | :--- | :--- |
| **Đoàn Duy Bình (A)** | Leader, kiến trúc, tích hợp, danh mục, dashboard | core, auth, inventory, integrations, master_data, dashboard | Khung client, Admin, tra cứu tồn, `bgd` |
| **Mai Hữu Phước (B)** | Nhập kho và kiểm kê | inbound (gồm cất hàng), cycle_count | `nv-nhan`, `nv-cat`, `nv-kiemke` |
| **Hồ Quốc Cường (C)** | Xuất kho | outbound | `nv-soan`, `nv-dongoi` |
| **Nguyễn Đức Hiếu (D)** | Điều phối và duyệt | tasks, approvals | `thukho`, `quanly` |

---

## 2. Nhánh Git Phụ trách (Mục 7.1 Đặc tả)

| Thành viên | Nhánh phụ trách |
| :--- | :--- |
| **Đoàn Duy Bình (Leader)** | `feature/core-auth`, `feature/inventory`, `feature/integrations-mock`, `feature/master-data`, `feature/dashboard` |
| **Mai Hữu Phước** | `feature/inbound`, `feature/cycle-count` |
| **Hồ Quốc Cường** | `feature/outbound` |
| **Nguyễn Đức Hiếu** | `feature/tasks`, `feature/approvals` |

---

## 3. Bảng Phân công Chi tiết Từng Thành viên

### 3.1. Đoàn Duy Bình (A - Leader)

| Mã | Công việc | Nhánh | Ưu tiên | Trạng thái | PR |
| :--- | :--- | :--- | :---: | :---: | :---: |
| A-01 | Khung dự án: cấu trúc thư mục, FastAPI app, cấu hình, phiên DB, Docker Compose, `.env.example`, CI, pre-commit, README, CONTRIBUTING | `feature/core-auth` | P1 | Xong | #1, #3, #7, #8, #9 |
| A-02 | Nạp schema v4.1, Alembic baseline, seed 9 vai trò, ma trận quyền, tài khoản demo | `feature/core-auth` | P1 | Xong | #2 (nạp bằng script SQL, không dùng Alembic) |
| A-03 | Auth: đăng nhập JWT, làm mới token, `/me`, bắt đổi mật khẩu lần đầu, khóa tài khoản khi sai quá số lần | `feature/core-auth` | P1 | Xong | #4; làm mới token: #42 |
| A-04 | RBAC: `require_permission`, lọc theo kho, `X_OWN`/`V_OWN`, kiểm tra SoD ở tầng ứng dụng | `feature/core-auth` | P1 | Xong | #4 |
| A-05 | Audit log, exception handler, chuẩn response, bảng mã lỗi, xử lý xung đột phiên bản (409) | `feature/core-auth` | P1 | Xong | #3 |
| A-06 | Inventory: lô, pallet, tồn 5 trạng thái, sổ cái; `apply_movement` (`RECEIVE`, `PUTAWAY`, `ALLOCATE`, `DEALLOCATE`, `PICK`, `SHIP_GI`, `ADJUSTMENT`, `LOCK_COUNT`); API tra cứu theo SKU, vị trí, lô (QL-1.1 đến QL-1.4) | `feature/inventory` | P1 | Xong | #5 |
| A-07 | ERP mock và TMS mock: đẩy PO, ASN, SO mẫu; nhận GRN, GI; ghi `integration_sync_logs`; thử lại khi lỗi | `feature/integrations-mock` | P1 | Xong | #27, #36 |
| A-08 | Client lõi: `api_client`, phiên đăng nhập, layout, menu theo quyền, trang tra cứu tồn | `feature/core-auth` | P1 | Xong | #6; trang tồn có lọc, lô, lịch sử: #42 |
| A-09 | Review PR, giải quyết xung đột, gộp `develop` và `main`, gắn tag, viết bài test e2e theo kịch bản demo | các nhánh | P1 | Đang làm | #40 (e2e, dữ liệu demo); còn gộp `main`, tag `v0.1-demo` |
| A-10 | API danh mục (chuyển từ B-01): kho và cấu hình, zone, vị trí, nhóm hàng, SKU, mã vạch, NCC, khách hàng, mã lý do, loại thùng | `feature/master-data` | P1 | Xong | #17, #26, #34; danh mục xe: #42 |
| A-11 | Client cho Admin (chuyển từ B-02): màn hình danh mục và quản lý người dùng | `feature/master-data` | P2 | Một phần | Màn hình chỉ đọc: #42; chưa có API ghi `users`, `roles` |
| A-12 | Dashboard cơ bản (chuyển từ D-07): thẻ số task (TK-2.1), tồn, đơn trong ngày cho BGĐ; cảnh báo đơn giản trong app | `feature/dashboard` | P2 | Xong | #29 |
| A-13 | Client cho `bgd` (chuyển từ D-08) | `feature/dashboard` | P1 | Xong | #29 |

### 3.2. Mai Hữu Phước (B)

| Mã | Công việc | Nhánh | Ưu tiên | Trạng thái | PR |
| :--- | :--- | :--- | :---: | :---: | :---: |
| B-03 | PO, ASN: nhận từ ERP mock, danh sách, chi tiết (QL-2.1, QL-2.3) | `feature/inbound` | P1 | Xong | #18, #31 |
| B-04 | GRN đếm mù: chọn phiếu, quét SKU, lô, hạn dùng, serial, lưu tạm (NH-1 đến NH-4) | `feature/inbound` | P1 | Xong | #38 |
| B-05 | Xử lý lệch: cảnh báo thừa, thiếu, hư, cách ly pallet, tạo yêu cầu duyệt (gọi `approvals` của D), đếm lại NH-5 | `feature/inbound` | P1 | Xong | #38 |
| B-06 | Hoàn tất GRN: tạo pallet, tem pallet (mock), trạng thái STAGED, cộng PO (tương ứng `fn_sync_po_on_grn_approved`), sinh task PUTAWAY | `feature/inbound` | P1 | Xong | #38 |
| B-07 | Cất hàng: gợi ý vị trí theo zone, sức chứa, cất một phần, báo vị trí đầy hoặc sai | `feature/inbound` | P1 | Xong | #38 |
| B-08 | Client cho `nv-nhan` và `nv-cat` | `feature/inbound` | P1 | Một phần | #38; thiếu nút đếm lại GRN, gợi ý vị trí khi cất |
| B-09 | Kiểm kê (chuyển từ D-06): phiếu, khóa vị trí, snapshot, đếm mù, so với Z, đếm lại tới giới hạn, tự đóng phiếu | `feature/cycle-count` | P1 | Xong | #38 |
| B-10 | Client cho `nv-kiemke` (chuyển từ D-08) | `feature/cycle-count` | P1 | Một phần | #38; thiếu đếm lại trên giao diện |

### 3.3. Hồ Quốc Cường (C)

| Mã | Công việc | Nhánh | Ưu tiên | Trạng thái | PR |
| :--- | :--- | :--- | :---: | :---: | :---: |
| C-01 | Nhận SO từ ERP mock: đơn và dòng, danh sách theo trạng thái (QL-3.1) | `feature/outbound` | P1 | Xong | #30, #37 |
| C-02 | Cấp phát tồn FEFO/FIFO, ưu tiên lô `is_priority_dispatch`, đơn thiếu hàng chuyển ON\_HOLD | `feature/outbound` | P1 | Xong | #30, #39 |
| C-03 | Phiên soạn (đơn lẻ, batch), sinh `pick_lines`, giao task PICKING qua `tasks`, sắp lộ trình theo vị trí | `feature/outbound` | P1 | Xong | #30 |
| C-04 | Thực hiện pick: quét vị trí, SKU, số lượng, bỏ qua dòng, ngoại lệ thiếu, hư, sai lô, thay lô | `feature/outbound` | P1 | Xong | #30 |
| C-05 | Đóng gói: kiểm đơn, chọn loại thùng, cân nặng, số kiện, `packages` | `feature/outbound` | P1 | Xong | #30 |
| C-06 | GI: gán xe và tài xế, quét kiện, chữ ký, SHIPPED và trừ tồn qua `inventory`; ba loại GI: `SO_SHIPMENT`, `INTER_WH_TRANSFER`, `SUPPLIER_RETURN` | `feature/outbound` | P1 | Xong | #30, #37 |
| C-07 | ERP đổi hoặc hủy đơn: cờ `erp_change_pending`, hoàn tác phần đã làm bằng task RETURN\_PICKING (QL-5.1) | `feature/outbound` | P2 | Một phần | #30; thiếu task `RETURN_PICKING` khi hủy đơn đã soạn |
| C-08 | Client cho `nv-soan` và `nv-dongoi` | `feature/outbound` | P1 | Một phần | #30; thiếu chọn thùng, gán xe, tài xế |

### 3.4. Nguyễn Đức Hiếu (D)

| Mã | Công việc | Nhánh | Ưu tiên | Trạng thái | PR |
| :--- | :--- | :--- | :---: | :---: | :---: |
| D-01 | Module `tasks`: tạo, trạng thái, nhận, từ chối, hoàn tất, chống giao trùng bằng `version_no`, giới hạn task mở, SLA. **Làm sớm, B và C phụ thuộc** | `feature/tasks` | P1 | Xong | #14 |
| D-02 | Giao task thủ công và tự động, điều chuyển, đổi ưu tiên, hủy, task bị từ chối (TK-1.1 đến TK-1.6) | `feature/tasks` | P1 | Một phần | #14; thiếu đổi ưu tiên, giao tự động |
| D-03 | Engine phê duyệt: tính tầng theo Z, X, Y và người lập, D1 đến D3, SoD, lịch sử, khóa phiếu đang mở, leo thang khi quá SLA (kích hoạt tay trong demo) | `feature/approvals` | P1 | Xong | #15 |
| D-04 | Thủ kho duyệt: hàng chờ, chênh lệch nhận, chênh lệch kiểm kê, yêu cầu đếm lại, chuyển D2, đề xuất điều chỉnh (TK-3.1 đến TK-4.4) | `feature/approvals` | P1 | Xong | #15, #32 |
| D-05 | Quản lý và BGĐ duyệt D2, D3; thực thi sau duyệt (ghi tồn qua `inventory`, đẩy ERP mock) (QL-7.1 đến QL-7.6) | `feature/approvals` | P1 | Xong | #15, #32 |
| D-08 | Client cho `thukho` và `quanly` | `feature/tasks`, `feature/approvals` | P1 | Xong | #33 |

---

## 4. Phụ thuộc giữa các Thành viên

- **B (Mai Hữu Phước)** và **C (Hồ Quốc Cường)** gọi hàm dịch vụ của `inventory` do **A (Đoàn Duy Bình)** phụ trách và `tasks` do **D (Nguyễn Đức Hiếu)** phụ trách.
- **B (Mai Hữu Phước)** gọi hàm dịch vụ của `approvals` do **D (Nguyễn Đức Hiếu)** phụ trách khi phát hiện chênh lệch nhận hàng hoặc kiểm kê.
- Phân hệ **dashboard** do **A (Đoàn Duy Bình)** phụ trách đọc số liệu tổng hợp từ mọi module trong hệ thống.

---

> Nguồn: `docs/spec/dac-ta-du-an.md` mục 7 và 8; khi đặc tả đổi thì cập nhật file này.
>
> Trạng thái cập nhật ngày 26/11/2026 theo code trên `develop` và các PR đã merge. «Một phần»: phần còn thiếu ghi ở cột PR.
