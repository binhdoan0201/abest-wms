# Tổng duyệt demo – 28/11/2026

Chạy trên `develop` @ `55b7b05` (trùng `main` @ `8427684`, tag `v0.1-demo`), DB reset + `scripts.load_demo`.
Đi qua giao diện client như người dùng bấm, theo `docs/demo/kich-ban-demo.md`; ERP đẩy chứng từ và chạy
hàng đợi gọi API như trên Swagger.

## Kết quả nhanh

- black, ruff, mypy sạch; pytest **186/186** xanh (kể cả e2e kịch bản demo).
- 4 phần chạy được tới cuối, **nhưng Phần 2 kẹt cứng ở bước 3** nếu thủ kho bấm theo đúng kịch bản (xem C1).
  Tổng duyệt phải sửa tay DB mới đi tiếp được.
- Phần 3, Phần 4, Tổng quan cuối buổi: đúng số liệu (40 → 37, 1 GI đã xuất, 1 phiếu nhận hoàn tất,
  3 task `COMPLETED`, hàng đợi ERP 2/2 `SUCCESS`). Biến thể FEFO đúng ở API (lấy lô DEMO-SUA-A).

## A. Chí mạng – sửa trước khi quay

> ✅ C1, C3 đã sửa cùng ngày: nút «↻ Yêu cầu đếm lại» luôn ghi `REQUEST_RECOUNT`, hồ sơ `NEED_INFO` chỉ còn
> nút Từ chối; số lượng, số tiền qua filter `qty`, `qty_input`, `vnd` (`client/app/core/formatting.py`).
> Đã chạy lại trên app: thukho bấm đếm lại → nv_nhan bị chặn đúng lý do → nv_nhan2 đếm lại → `APPROVED`.
>
> ✅ C2 đã sửa: `GET /approvals` trả `object_ref` (số GRN / `số phiếu kiểm kê / vị trí`), chi tiết trả thêm `source`
> (SKU, tên, vị trí, lô, chứng từ hoặc sổ sách, đếm, hư, lệch, giá trị, lý do, người đề xuất). Panel duyệt hiện bảng lệch,
> nhãn tiếng Việt, giờ VN (`vn_datetime`). Cấp D3 (`bgd`) vẫn thấy bảng lệch dù không có quyền đọc GRN.

| # | Ở đâu | Vấn đề (đã tái hiện) | Sửa | Ai | Công |
|---|---|---|---|---|---|
| C1 ✅ | Phê duyệt (GRN) | Bấm «↻ Yêu cầu đếm lại / Bổ sung» **không tick** ô «Yêu cầu nhân viên *kiểm kê* đếm lại» (mặc định không tick, nhãn lại ghi «kiểm kê») → lịch sử ghi `RETURN_FOR_INFO`, không phải `REQUEST_RECOUNT`. Sau đó: nv_nhan2 đếm lại bị chặn «GRN chỉ được đếm lại khi người duyệt yêu cầu đếm lại (NEED_INFO)»; thủ kho bấm lại thì bị báo «đang ở NEED_INFO, không thể yêu cầu bổ sung». `resubmit_approval_info` không có ai gọi → **không có đường thoát** ngoài Từ chối. Kịch bản không nhắc tick ô. | Với `GRN_DISCREPANCY` và `CYCLE_COUNT_DIFF`, nút đếm lại luôn gửi `request_recount=true` (bỏ ô tick, hoặc tick sẵn và đổi nhãn «Yêu cầu đếm lại»). Ẩn các nút quyết định khi hồ sơ đang `NEED_INFO`. | D Hiếu | 20 phút |
| C2 ✅ | Phê duyệt | Hồ sơ duyệt **không cho thấy lệch gì**: chỉ có `GRN_DISCREPANCY`, UUID, `450000.00`, SLA `2026-11-28T05:40:26.565178Z` (giờ UTC). Không có số GRN, SKU, SL chứng từ / thực đếm / hư. Đây là trọng tâm «duyệt đa cấp», người xem sẽ hỏi thủ kho căn cứ vào đâu để duyệt. | Theo `object_type`, gọi `GET /grns/{object_id}` hoặc phiếu kiểm kê để hiện bảng: SKU, tên, SL chứng từ, đếm, hư (kiểm kê: tồn sổ sách, đếm, lệch). Hiện số chứng từ thay cho UUID; tiền `450.000 ₫`; giờ VN `dd/mm/yyyy HH:mm`. | D Hiếu | 1–2 giờ |
| C3 ✅ | Tổng quan và mọi bảng | Số lượng hiện 3 số thập phân theo kiểu Anh: `180.000`, `6.000`, `24.000`, `15.000`. Người Việt đọc thành **180 nghìn**, và đây là màn hình mở đầu của BGĐ. Trang Tồn kho đã hiện đúng `37`, `24` nên các trang đang không thống nhất. | Một filter Jinja dùng chung: bỏ phần thập phân `.000`, phân cách nghìn bằng dấu chấm; áp cho dashboard, GRN, soạn hàng, kiểm kê, phê duyệt. | A Bình | 30 phút |

## B. Cao – lộ yếu nghiệp vụ nếu bị hỏi

| # | Ở đâu | Vấn đề | Sửa | Ai |
|---|---|---|---|---|
| H1 | Soạn hàng | Dòng soạn chỉ có `SKU-GEN-008 / 10.000`, **không có vị trí lấy, lô, hạn dùng, tên SKU**. Người soạn không biết ra kệ nào; câu chuyện FEFO không hiện trên giao diện. (Đã ghi ở tổng duyệt 27/11, chưa sửa.) | Hiện `location_code`, lô, HSD, tên SKU trên dòng soạn (allocation đã có `location_id`, `lot_id`). | C Cường |
| H2 | Xuất kho – cấp phát | Luôn báo «Đã cấp phát tồn kho thành công!», bỏ qua `has_shortage`, không hiện lô/vị trí được giữ; trạng thái vẫn `NEW`. Khi thiếu hàng, đơn sang `ON_HOLD` nhưng vẫn báo thành công. | Đọc response: thiếu thì cảnh báo vàng; đủ thì hiện «Giữ 10 tại LOC-A02-01, lô DEMO-SUA-A (HSD 04/12)». | C Cường |
| H3 | Nhập kho – đếm lại | Form «Yêu cầu đếm lại (NEED_INFO)» hiện **ngay sau khi nộp** (`PENDING_D1`), trước khi thủ kho yêu cầu. Ô nhập hiện sẵn số đếm cũ (`8.000`, `1.000`) cho người đếm lại, nên lần đếm lại không còn mù. | Chỉ hiện khi hồ sơ duyệt `NEED_INFO` + `REQUEST_RECOUNT`; bỏ placeholder số cũ. | B Phước |
| H4 | Cất hàng – gợi ý vị trí | Gợi ý #1 cho bộ dao kéo là `LOC-A02-01`, **ô đang chứa sữa lô cận date**. Câu SQL xếp `current_capacity_pct DESC`, nên ô đầy một phần của SKU khác được ưu tiên hơn ô trống. | `ORDER BY has_same_sku DESC, (status = 'EMPTY') DESC, ...` hoặc loại ô đang có SKU khác (`inbound/repositories.py:419`). | B Phước |
| H5 | Đóng gói – sau khi xuất | Bấm «Xác nhận xuất kho» xong, thẻ thông tin hiện sai: «Phiếu GI: fbce2043 — Trạng thái đơn: *(trống)* — Mã vận đơn TMS: chờ vận đơn», đúng vào khoảnh khắc kết thúc Phần 3. | Sau confirm, render lại bằng số GI, `SHIPPED`, mã vận đơn thật. | C Cường |

## C. Chuẩn bị kịch bản (không cần code)

1. **Thêm JSON dán sẵn** cho 2 lệnh Swagger: mã NCC là `SUPP-001`, khách hàng là `CUST-001`, `cutoff_time`
   phải nằm trong tương lai. Tổng duyệt gõ thử `NCC-001` → `FAILED_BUSINESS`, Tổng quan của BGĐ hiện đỏ
   «1 chứng từ đồng bộ ERP/TMS bị lỗi» suốt buổi và không có màn hình nào để xử lý. Nếu gõ nhầm thì reset lại DB.
2. ~~Ghi rõ tick ô đếm lại~~: không cần nữa sau khi sửa C1.
3. Phần 2 bước 7: thêm bước `thukho` → **Nhiệm vụ** → «Tự động giao» trước khi `nv_cat` vào. Task cất hàng
   sinh ra `UNASSIGNED` nên trang Nhiệm vụ của nv_cat đang trống (đặc tả 6.2 bước 4 cũng yêu cầu «thukho giao task»).
4. Phần 3 bước 4: đơn chuyển `READY_TO_SHIP` ngay khi tạo kiện, trước khi lập GI. Sửa lời dẫn cho khớp.
5. Phê duyệt: danh sách đặt hồ sơ `SUPERSEDED` lên đầu và không tự tải lại sau khi quyết định. Lúc quay, lọc
   «PENDING_D1» trước khi bấm.
6. Mạng: Tailwind (`cdn.tailwindcss.com`) và htmx (`unpkg.com`) tải từ CDN, mất mạng là giao diện vỡ hết.
   Nên tải về `client/app/static/` để chạy offline.

## D. Thấp – nếu còn thời gian

- Tổng quan «Tồn khả dụng 180» tính cả 6 bánh mì **đã hết hạn**; nên loại lô hết hạn khỏi khả dụng.
- Sau khi đếm lại hết hư, pallet `…-DMG` rỗng vẫn ở `DAMAGED_HOLD` tại `LOC-RCV-01`.
- Mã trạng thái tiếng Anh (`COUNTING`, `PENDING_D1`, `RETURN_FOR_INFO`, `WAITING_EXECUTION`) trên Nhập kho,
  Phê duyệt; ngày dạng `2026-11-27` thay vì `27/11/2026`.
- Ô «ASN ID (nếu có)» vẫn bắt gõ UUID; ô chọn PO tự quay về «Nhận không PO» sau khi mở phiếu, dễ lỡ tay mở GRN thứ hai.
- Thủ kho, quản lý đăng nhập vào **Tồn kho**; nên vào Phê duyệt/Nhiệm vụ (thủ kho), Tổng quan (quản lý).
- Seed dùng tên thật «Siêu thị VinMart Central»; nên đổi sang tên hư cấu.

## Thứ tự đề xuất

1. C1 → C3 → C2 (C1 và C3 dưới 1 giờ, gỡ rủi ro lớn nhất).
2. H1, H2, H5 (Cường), H3, H4 (Phước) làm song song.
3. Cập nhật kịch bản theo mục C, merge `develop` → `main`, gắn lại tag (vd. `v0.1.1-demo`).
4. Tổng duyệt lại: `reset_db.sh` + `load_demo`, đi trọn 4 phần **bằng tay**, không chạy pytest sau đó.
