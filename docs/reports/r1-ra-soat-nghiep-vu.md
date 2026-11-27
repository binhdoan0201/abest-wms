# Rà soát nghiệp vụ: ABEST WMS so với vận hành kho thực tế

**Mã báo cáo:** `r1-ra-soat-nghiep-vu`
**Người yêu cầu:** Leader A (Bình)
**Ngày:** 2026-11-24
**Phạm vi rà soát:** `docs/spec/dac-ta-du-an.md`, `docs/spec/chuan-api-cong-nghe.md`, `database/schema.sql`, `database/patch_v4_2_1.sql`, `docs/api/*.md` trên `develop`, cùng các PR đang mở (#17 master_data, #18 inbound).

---

## 1. Kết luận chung

Khung nghiệp vụ được phân tích tốt. Nhiều điểm kiểm soát còn chặt hơn kho thực tế ở Việt Nam:

- Đếm mù khi nhận hàng và kiểm kê; đếm lại phải là người khác.
- Tách bạch nhiệm vụ (SoD) ở mọi cấp duyệt, cưỡng chế ở cả DB và ứng dụng.
- Duyệt chênh lệch theo giá trị với ngưỡng X, Y, Z cấu hình theo kho; xác thực lại khi giá trị lớn.
- Tồn kho 5 trạng thái (khả dụng, đã cấp phát, đang đếm, khóa, hư) với sổ cái bất biến.
- Lô, hạn dùng, FEFO/FIFO; khóa vị trí khi kiểm kê.
- Cách ly hàng lệch hoặc hư trước khi duyệt; tiêu hủy phải duyệt và có bằng chứng.
- Đơn bị ERP đổi hoặc hủy thì đóng băng, hoàn tác bằng task trả hàng về kệ.

Phạm vi demo bỏ RMA, cross-dock, kitting, wave nâng cao là hợp lý.

Có **4 lỗ hổng cần xử lý trong giai đoạn 2** vì chạm trực tiếp vào kịch bản demo (mục 2), và **5 điểm nên ghi vào «giai đoạn sau»** (mục 3).

---

## 2. Lỗ hổng cần xử lý ngay

| # | Lỗ hổng | Rủi ro ngoài đời | Đề xuất | Người làm |
| --- | --- | --- | --- | --- |
| 2.1 | Xuất kho chưa loại lô hết hạn | Giao hàng hết hạn cho khách | Thêm quy tắc cấp phát | C (C-02) |
| 2.2 | Một dòng lệch giữ cả phiếu nhận | Tắc cửa nhận nhiều giờ | Duyệt theo dòng hoặc tách dòng lệch | B (B-05, B-06), D |
| 2.3 | Đơn vị tính chưa nhất quán | Sai số lượng tồn khi nhận theo thùng | Chốt quy về `base_uom`, một nguồn hệ số quy đổi | A, B, C |
| 2.4 | SKU không có khối lượng, kích thước | Gợi ý cất và đóng gói không kiểm được tải | Thêm cột vào `skus` | A (A-10) |

### 2.1. Xuất kho chưa loại lô hết hạn

- **Hiện trạng:** FEFO chỉ sắp thứ tự lô theo hạn dùng. Đặc tả (C-02), chuẩn API (`POST /outbound-orders/{id}/allocate`) và DB đều không có quy tắc loại lô đã hết hạn hoặc sắp hết hạn khỏi cấp phát.
- **Ngoài đời:** đây là lỗi nghiêm trọng nhất của kho hàng có hạn dùng (thực phẩm, dược, mỹ phẩm). Khách hàng lớn thường yêu cầu hạn dùng còn lại tối thiểu, ví dụ còn ít nhất 2/3 hạn.
- **Đề xuất:**
  1. Bắt buộc: không cấp phát lô có `expiry_date` < ngày giao (`cutoff_time`).
  2. Nên có: hạn dùng còn lại tối thiểu khi xuất, theo nhóm hàng hoặc khách hàng. Có thể tái dùng ý tưởng `min_receiving_shelf_life_days` của `item_categories` cho chiều xuất.
  3. Lô hết hạn đang nằm ở vị trí khả dụng phải được cảnh báo để đề xuất tiêu hủy (`STOCK_SCRAP`).

### 2.2. Một dòng lệch giữ cả phiếu nhận

- **Hiện trạng** (theo `docs/api/inbound.md`, PR #18): chỉ cần một dòng hư hoặc lệch là cả GRN sang `PENDING_Dx`, mọi dòng bị cách ly (`QUARANTINE_HOLD`) và chưa nhập tồn. SLA duyệt từ 4 giờ (D1) đến 24 giờ (D3).
- **Ngoài đời:** một xe 20 pallet chỉ hư 1 thùng thì 19 pallet còn lại vẫn được nhập và cất ngay. Giữ cả xe làm tắc cửa nhận, chậm cất hàng, và hàng không hiện trên tồn để bán.
- **Đề xuất (chọn một, B và D thống nhất):**
  - **Tách dòng lệch**: khi nộp, dòng khớp được nhập ngay (hoàn tất một phần), dòng lệch tạo phiếu riêng để duyệt; hoặc
  - **Duyệt theo dòng**: yêu cầu duyệt gắn với dòng GRN thay vì cả phiếu.

  Cách thứ nhất ít đụng tới `approvals` hơn vì `approval_requests` đã thiết kế theo đối tượng (`object_id`).

### 2.3. Đơn vị tính chưa nhất quán

- **Hiện trạng:**
  - `po_lines` và `grn_lines` có `uom_code` (có thể là thùng, lốc).
  - `inventory_balances`, `inventory_transactions`, `outbound_order_lines` không có cột đơn vị, nên ngầm hiểu là đơn vị cơ sở `skus.base_uom`.
  - Hệ số quy đổi chỉ nằm ở `sku_barcodes.conversion_factor`, tức theo từng mã vạch. Không có bảng quy đổi đơn vị theo SKU.
- **Ngoài đời:** NCC giao theo thùng, khách đặt theo thùng hoặc cái. Nhận 10 thùng mà SKU chưa có mã vạch thùng thì hệ thống không biết là bao nhiêu cái.
- **Đề xuất:**
  1. Quy tắc chung (ghi vào chuẩn API): **mọi số lượng ghi tồn và so lệch đều quy về `base_uom`** trước khi gọi `apply_movement`.
  2. Nguồn hệ số: trước mắt dùng `sku_barcodes` (yêu cầu mỗi đơn vị trên PO phải có một mã vạch có `conversion_factor`); về lâu dài thêm bảng `sku_uoms` (SKU, đơn vị, hệ số).
  3. `master_data` (A) bổ sung hàm công khai `convert_to_base_uom(db, sku_id, uom_code, qty)` để B, C dùng chung.

### 2.4. SKU không có khối lượng, kích thước

- **Hiện trạng:** `locations` có `max_weight_kg`, `max_volume_m3`, `box_types` có kích thước và tải tối đa, nhưng `skus` không có khối lượng hay thể tích.
- **Hệ quả:**
  - Gợi ý cất hàng (B-07) không kiểm được tải trọng thật, chỉ dựa vào số pallet.
  - Đóng gói (C-05) phải cân và nhập tay, không đối chiếu được khối lượng thùng với hàng trong đơn để phát hiện soạn sai.
- **Đề xuất:** thêm vào `skus` các cột `unit_weight_kg`, `unit_volume_m3` (tùy chọn `length_cm`, `width_cm`, `height_cm`) theo `base_uom`. Đổi schema nên do A làm (A-10, kèm migration), cập nhật `docs/api/master_data.md`.

---

## 3. Ghi vào «giai đoạn sau»

Các điểm dưới đây không cần làm cho demo, nhưng nên ghi vào đặc tả mục 1.2 («Để giai đoạn sau») để giảng viên hoặc khách hàng thấy nhóm đã cân nhắc.

| # | Điểm | Ngoài đời | Hiện trạng dự án |
| --- | --- | --- | --- |
| 3.1 | Bổ sung hàng cho ô soạn | Kho có khu lưu trữ (pallet trên cao) và ô soạn (tầm tay); khi ô soạn xuống dưới mức tối thiểu thì sinh task bổ sung | Chưa phân biệt ô soạn và khu lưu trữ; `task_type` không có loại bổ sung hàng; soạn thẳng từ pallet. Ổn cho demo |
| 3.2 | Khóa lô (thu hồi, chờ kiểm chất lượng) | NCC báo thu hồi một lô thì phải chặn xuất lô đó ở mọi vị trí ngay lập tức | `lots` không có trạng thái; chỉ chặn được qua trạng thái pallet hoặc vị trí |
| 3.3 | Khiếu nại NCC khi nhận thiếu, hư | Nhận thiếu, hư sinh khiếu nại NCC và báo ERP để đối chiếu 3 bên (PO, phiếu nhận, hóa đơn) | Chênh lệch chỉ được duyệt nội bộ (D1 đến D3); có GI `SUPPLIER_RETURN` nhưng chưa có luồng khiếu nại |
| 3.4 | Hàng đang chuyển giữa hai kho | Từ lúc xuất kho A đến lúc nhận ở kho B, hàng thuộc tồn «đang chuyển» | WMS không theo dõi; ERP giữ phần này. Cần ghi rõ giả định |
| 3.5 | Đối soát tồn WMS với ERP | Cuối ngày hoặc cuối kỳ so tồn hai hệ thống, xử lý chênh | Có `integration_sync_logs` cho từng giao dịch, chưa có đối soát tổng |

---

## 4. Hợp đồng liên module cần thống nhất thêm

Phát hiện trong quá trình review PR #15, #17, #18:

1. **Ghi tồn sau khi duyệt GRN:** đã chốt theo `docs/api/inbound.md`. `inbound` ghi tồn trong `POST /grns/{id}/complete`. Còn thiếu: ai cập nhật `approval_requests.execution_status` sang đã thực thi (B gọi một hàm công khai của `approvals` do D bổ sung).
2. **Đếm lại khi nhận hàng:** chỉ đếm lại khi hồ sơ duyệt ở `NEED_INFO` do người duyệt yêu cầu (`request_recount`). Đây là điều kiện của `approvals.supersede_approval_for_recount` và đặc tả NH-5.
3. **Ghi tồn sau duyệt kiểm kê** (kịch bản demo bước 8): cần B (`cycle_count`) và D (`approvals`) chốt tương tự mục 1.
4. **Mã quyền:** dùng đúng 14 mã đã nạp theo ma trận mục 5.3 (`NH-1`, `CAT-1`, `SO-1`, `DG-1`, `KK-1`, `TK-1.1`, `TK-3.2`, `TK-4.4`, `QL-1.1`, `QL-2.1`, `QL-5.3`, `QL-8.1`, `QL-9.10`, `AD-1`), không tự đặt mã mới.

---

## 5. Việc đề xuất

| Việc | Người | Ưu tiên |
| --- | --- | --- |
| Thêm quy tắc loại lô hết hạn vào C-02 và `docs/api/outbound.md` | C | Cao |
| Chốt cách xử lý GRN có dòng lệch (tách dòng hoặc duyệt theo dòng) | B, D | Cao |
| Ghi quy tắc `base_uom` vào chuẩn API; thêm `convert_to_base_uom` | A | Cao |
| Thêm khối lượng, thể tích cho `skus` | A | Trung bình |
| Hàm cập nhật `execution_status` sau thực thi; chốt luồng ghi tồn sau duyệt kiểm kê | D, B | Trung bình |
| Bổ sung mục 3 vào đặc tả 1.2 «Để giai đoạn sau» | A | Thấp |
